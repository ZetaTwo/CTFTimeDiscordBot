import os
import functions_framework

from CTFtimeDiscordHooks import send_updates


@functions_framework.http
def ctftime_discord_events(request):
    webhook_url = os.environ['DISCORD_WEBHOOK']

    days = 7
    max_entries = 100
    webhooks = [webhook_url]
    send_updates(webhooks=webhooks, max_ctfs=max_entries, days=days, cache_path=None)
    return "ok"
