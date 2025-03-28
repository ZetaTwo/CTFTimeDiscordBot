import argparse
import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

import requests
import discord

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
log = logging.getLogger("ctftime-discord-bot")

DEFAULT_ICON = (
    "https://pbs.twimg.com/profile_images/2189766987/ctftime-logo-avatar_400x400.png"
)
TIME_FORMAT = "%Y-%m-%dT%H%M%S%z"
BASE_URL = "https://ctftime.org"


class CtfTimeClient(discord.Client):
    def __init__(
        self,
        channel_id: int,
        content: str,
        embeds: List[discord.Embed],
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.channel_id = channel_id
        self.content = content
        self.embeds = embeds

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.post_announcement_task())

    async def on_ready(self) -> None:
        if not self.user:
            log.warning("No user available")
            return
        log.info("Logged in as %s (ID: %d)", self.user.name, self.user.id)

    async def post_announcement_task(self) -> bool:
        try:
            return await self.post_announcement()
        except Exception as e:
            log.error("Unhandled exception while trying to post announcement: %s", e)
            return False

    async def post_announcement(self) -> bool:
        log.info("Posting announcement")
        log.debug("Awaiting Discord ready")
        await self.wait_until_ready()
        log.debug("Discord ready")

        log.debug("Getting Discord channel")
        channel = self.get_channel(self.channel_id)
        if not channel:
            log.error(f"Failed to get channel with ID {self.channel_id}")
            await self.close()
            return False

        if not isinstance(channel, discord.TextChannel):
            log.error(
                "Channel %d is of type %s, expected TextChannel",
                channel.id,
                type(channel),
            )
            return False

        log.info("Posting announcements")
        first = True
        while len(self.embeds) > 0:
            embed_chunk = []
            chunk_len = 0
            while len(self.embeds) > 0:
                next_embed = self.embeds.pop()
                next_embed_len = len(next_embed)
                if chunk_len + next_embed_len > 6000:
                    log.debug("Chunk character length reached. Not adding embed.")
                    self.embeds.append(next_embed)
                    break
                embed_chunk.append(next_embed)
                chunk_len += next_embed_len
                if len(embed_chunk) >= 10:
                    log.debug("Chunk max embeds reached. Not adding embed")
                    break

            log.debug(
                "Posting chunk of %d messages with total length %d",
                len(embed_chunk),
                chunk_len,
            )

            content = self.content if first else None
            message = await channel.send(content=content, embeds=embed_chunk)
            log.debug("Posted chunk of messages, result: %s", message)
            if not message:
                log.error("Failed to post message to channel")
                log.debug("Closing Discord connection")
                await self.close()
                log.debug("Discord connection closed")
                return False

            if message.channel.type == discord.ChannelType.news:
                log.debug("Mark chunk as announcement")
                await message.publish()
            else:
                log.debug(
                    "Destinaton channel not a news channel. Skipping marking chunk as announcement"
                )

        log.debug("Finished posting embeds")
        log.debug("Closing Discord connection")
        await self.close()
        log.debug("Discord connection closed")

        return True


class CTF:
    cid: int
    url: str
    name: str
    logo: str
    format: str
    location: str
    start: datetime
    description: str
    restrictions: str
    duration: timedelta
    weight: float

    def __init__(self, json_obj: Dict[str, Any]):
        self.cid = json_obj.get("id", 0)
        self.url = json_obj.get("url", "")
        if self.url == "":
            self.url = json_obj.get("ctftime_url", "")
        self.name = json_obj.get("title", "")
        if self.name == "":
            self.name = "Unnamed"
        self.logo = CTF.parse_logo_url(json_obj.get("logo", ""))
        self.format = json_obj.get("format", "")
        if self.format == "":
            self.format = "Unknown"
        if json_obj.get("onsite", False):
            self.location = json_obj.get("location", "")
            if self.location == "":
                self.location = "Unknown"
        else:
            self.location = "online"
        self.start = CTF.parse_time(json_obj.get("start", "1970-01-01T00:00:00+00:00"))

        self.description = json_obj.get("description", "")
        if self.description == "":
            self.description = "No description :shrug:"
        elif len(self.description) > 2048:
            self.description = self.description[:2044] + "..."

        self.restrictions = json_obj.get("restrictions", "")
        if self.restrictions == "":
            self.restrictions = "Unknown"
        self.duration = timedelta(**json_obj.get("duration", dict()))

        self.weight = json_obj.get("weight", 0.0)

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            color=0xFF0035,
            title=self.name,
            url=self.url,
            description=self.description,
            timestamp=self.start,
        )
        embed.set_thumbnail(url=self.logo)
        embed.set_footer(
            text=f" ⏳ {self.duration} | 📌 {self.location} "
            f" ⛳ {self.format} | 👮 {self.restrictions} "
            f" 🏋️ {self.weight}"
        )
        return embed

    @staticmethod
    def parse_logo_url(url: str) -> str:
        log.debug("Parsing logo URL: %s", url)
        if url == "":
            return DEFAULT_ICON
        elif url.startswith("/"):
            return BASE_URL + url
        else:
            return url

    @staticmethod
    def parse_time(time: str) -> datetime:
        log.debug("Parsing time: %s", time)
        if time == "":
            time = "1970-01-01T00:00:00+00:00"
        return datetime.strptime(time.replace(":", ""), TIME_FORMAT)


def get_ctfs(max_ctfs: int, days: int) -> Optional[List[CTF]]:
    start = datetime.now()
    end = start + timedelta(days=days)
    url = (
        f"https://ctftime.org/api/v1/events/?limit={max_ctfs}"
        f"&start={int(start.timestamp())}&finish={int(end.timestamp())}"
    )
    log.debug("API URL: %s", url)

    log.debug("Retrieving events from CTFTime API")
    try:
        result = requests.get(
            url,
            headers={"user-agent": "CTFTime Discord bot <calle.svensson@zeta-two.com>"},
        )
    except Exception as e:
        log.error("Failed to retrieve events from CTFTime: %s", str(e))
        return None

    if result.status_code != 200:
        log.error(
            "Unexpected response from CTFTime API, code: %d, body: %s ",
            result.status_code,
            result.text,
        )
        return None

    return [CTF(entry) for entry in result.json()]


def send_updates(
    channel_id: int, token: str, max_ctfs: int, days: int, cache_path: Optional[str]
) -> bool:
    cache = ""
    if cache_path:
        log.debug("Reading cache from: %s", cache_path)
        with open(cache_path) as f:
            cache = f.read().strip()

    log.info("Retrieving CTFs")
    ctfs = get_ctfs(max_ctfs, days)
    if not ctfs:
        return False

    log.info("Got %d entries", len(ctfs))
    log.info("Generating Discrod embeds for entris")
    embeds = [ctf.generate_embed() for ctf in ctfs]

    ids = ",".join([str(ctf.cid) for ctf in ctfs])
    log.debug("Checking cache for CTF IDs: %s", ids)
    if cache == ids:
        log.debug("Cache matches, aborting")
        return False

    if cache_path:
        log.debug("Updating cache with IDs: %s", ids)
        with open(cache_path, "w") as f:
            f.write(ids)

    log.info("Creating Discord client")
    client = CtfTimeClient(
        channel_id=channel_id,
        content=f"CTFs during the upcoming {days} days:",
        embeds=embeds,
        intents=discord.Intents.default(),
    )
    log.info("Running Discord client")
    client.run(token)
    log.info("Finished posting entries to Discord")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--channel-id",
        type=int,
        required=True,
        help="Discord channel id",
    )

    parser.add_argument(
        "-t",
        "--token",
        required=True,
        help="Discord bot token",
    )

    parser.add_argument(
        "-c",
        "--cache-file",
        metavar="path",
        default=None,
        help="a path to file that will be used to cache sent entries",
    )

    parser.add_argument(
        "-m",
        "--max-entries",
        metavar="number",
        type=int,
        default=3,
        help="the maximum number of CTFs that will be sent",
    )
    parser.add_argument(
        "-d",
        "--days",
        metavar="number",
        type=int,
        default=10,
        help="days from today to search CTFs within",
    )
    args = parser.parse_args()

    log.info("Running CTFTime Discord Bot")
    log.info("Discord channel ID: %s", args.channel_id)
    log.info("Number of days: %d", args.days)
    log.info("Max entries: %d", args.max_entries)

    if args.cache_file:
        try:
            log.debug("Creating cache file")
            open(args.cache_file, "x").close()
        except FileExistsError:
            log.debug("Cache file already exists")
            pass

    send_updates(
        channel_id=args.channel_id,
        token=args.token,
        max_ctfs=args.max_entries,
        days=args.days,
        cache_path=args.cache_file,
    )
