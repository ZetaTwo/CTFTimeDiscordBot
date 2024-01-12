# CTFTime Calendar Discord Bot

This bot is used in the [CTF Discord](https://discord.gg/ArjWjvctft) to post weekly updates about upcoming events from [CTFTime](https://ctftime.org) in the server's calendar channel. The channel is a Discord announement channel which other servers can subscribe to in order to keep up to date with upcoming CTF events.

The bot is written in Python and uses the [discord.py](https://discordpy.readthedocs.io/) library to post messages to Discord. The reason it needs to be a bot and not just a webhook is that you can not publish announcements to other servers with only a webhook. The bot code is in the [code directory](code/). The bot is hosted as a GCP Cloud Function which is executed once per week through a Cloud Scheduler. The deployment is done through [Terraform](https://www.terraform.io/) and you can find the plan for it in the [deployment](deployment/) directory.

## Auhors

The original calendar feed code was written by sigint. I then created the cloud function compatible version and then later converted it from using webhooks into a bot to be able to use announcements.
