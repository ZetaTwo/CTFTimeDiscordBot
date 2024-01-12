terraform {
  required_version = ">= 1.4.4"
}

locals {
  region = "us-central1"
  # discord_webhook_url = "" # defined in secrets.tf
}

provider "google-beta" {
  project = "ctf-discord"
  region  = local.region
  zone    = "us-central1-b"
}

resource "google_service_account" "account" {
  provider     = google-beta
  account_id   = "ctf-discord"
  display_name = "CTFTime Discord Service Account"
}

resource "google_storage_bucket" "bucket" {
  provider = google-beta
  name     = "ctftime-discord-source"
  location = local.region

  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true
}

data "archive_file" "function_src" {
  type        = "zip"
  source_dir  = "../code"
  output_path = "../build/function-source.zip"
}

resource "google_storage_bucket_object" "source" {
  provider = google-beta
  name     = "function-source.${data.archive_file.function_src.output_sha256}.zip"
  bucket   = google_storage_bucket.bucket.name
  source   = data.archive_file.function_src.output_path
}

resource "google_cloudfunctions2_function" "ctftime_discord_events" {
  provider = google-beta
  location = local.region
  name     = "ctftime-discord-events"

  build_config {
    entry_point = "ctftime_discord_events"
    runtime     = "python311"

    source {
      storage_source {
        bucket = google_storage_bucket.bucket.id
        object = google_storage_bucket_object.source.name
      }
    }
  }

  service_config {
    service_account_email = google_service_account.account.email

    environment_variables = {
      DISCORD_WEBHOOK = local.discord_webhook_url
    }
  }
}

resource "google_cloudfunctions2_function_iam_member" "invoker" {
  provider       = google-beta
  project        = google_cloudfunctions2_function.ctftime_discord_events.project
  location       = google_cloudfunctions2_function.ctftime_discord_events.location
  cloud_function = google_cloudfunctions2_function.ctftime_discord_events.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.account.email}"
}

resource "google_cloud_run_service_iam_member" "cloud_run_invoker" {
  provider = google-beta
  project  = google_cloudfunctions2_function.ctftime_discord_events.project
  location = google_cloudfunctions2_function.ctftime_discord_events.location
  service  = google_cloudfunctions2_function.ctftime_discord_events.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.account.email}"
}

resource "google_cloud_scheduler_job" "weekly" {
  provider = google-beta
  name     = "weekly"
  schedule = "0 0 * * 2"

  http_target {
    uri         = google_cloudfunctions2_function.ctftime_discord_events.url
    http_method = "GET"
    oidc_token {
      audience              = google_cloudfunctions2_function.ctftime_discord_events.url
      service_account_email = google_service_account.account.email
    }
  }
}
