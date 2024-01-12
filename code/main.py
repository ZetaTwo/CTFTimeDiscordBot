import os
import functions_framework

from CTFtimeDiscordHooks import send_updates


@functions_framework.http
def ctftime_discord_events(request):
    channel_id = int(os.environ['DISCORD_CHANNEL_ID'])
    token = os.environ['DISCORD_BOT_TOKEN']

    days = 7
    max_entries = 100
    send_updates(channel_id=channel_id, token=token, max_ctfs=max_entries, days=days, cache_path=None)
    return "ok"
