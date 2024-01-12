import argparse
import logging
import requests
import discord

from typing import List, Union
from datetime import datetime, timedelta

log = logging.getLogger()

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
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.channel_id = channel_id
        self.content = content
        self.embeds = embeds

    async def setup_hook(self) -> None:
        self.bg_task = self.loop.create_task(self.post_announcement())

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def post_announcement(self):
        await self.wait_until_ready()

        channel = self.get_channel(self.channel_id)
        if not channel:
            log.error(f"Failed to get channel with ID {self.channel_id}")
            await self.close()
            return

        first = True
        while len(self.embeds) > 0:
            embed_chunk, self.embeds = self.embeds[:10], self.embeds[10:]

            content = self.content if first else ""
            message = await channel.send(content=content, embeds=embed_chunk)
            if not message:
                log.error(f"Failed to post message to channel")
                await self.close()
                return

            if message.channel.type == discord.ChannelType.news:
                await message.publish()

        await self.close()


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

    def __init__(self, json_obj: dict):
        self.cid = json_obj.get("id", 0)
        self.url = json_obj.get("url", "")
        if self.url == "":
            self.url = json_obj.get("ctftime_url", "")
        self.name = json_obj.get("title")
        if self.name is None or self.name == "":
            self.name = "Unnamed"
        self.logo = CTF.parse_logo_url(json_obj.get("logo", ""))
        self.format = json_obj.get("format")
        if self.format is None or self.format == "":
            self.format = "Unknown"
        if json_obj.get("onsite", False):
            self.location = json_obj.get("location")
            if self.location is None or self.location == "":
                self.location = "Unknown"
        else:
            self.location = "online"
        self.start = CTF.parse_time(json_obj.get("start", "1970-01-01T00:00:00+00:00"))

        self.description = json_obj.get("description")
        if self.description is None or self.description == "":
            self.description = "No description :shrug:"
        elif len(self.description) > 2048:
            self.description = self.description[:2044] + "..."

        self.restrictions = json_obj.get("restrictions")
        if self.restrictions is None or self.restrictions == "":
            self.restrictions = "Unknown"
        self.duration = timedelta(**json_obj.get("duration", dict()))

        self.weight = json_obj.get("weight", 0.0)

    def generate_embed(self):
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
        if url is None or url == "":
            return DEFAULT_ICON
        elif url.startswith("/"):
            return BASE_URL + url
        else:
            return url

    @staticmethod
    def parse_time(time: str) -> datetime:
        if time is None or time == "":
            time = "1970-01-01T00:00:00+00:00"
        return datetime.strptime(time.replace(":", ""), TIME_FORMAT)


def get_ctfs(max_ctfs: int, days: int) -> List[CTF]:
    start = datetime.now()
    end = start + timedelta(days=days)
    url = (
        f"https://ctftime.org/api/v1/events/?limit={max_ctfs}"
        f"&start={int(start.timestamp())}&finish={int(end.timestamp())}"
    )

    return [
        CTF(entry) for entry in requests.get(url, headers={"user-agent": ""}).json()
    ]


def send_updates(
    channel_id: int, token: str, max_ctfs: int, days: int, cache_path: str
):
    cache = ""
    if cache_path:
        with open(cache_path) as f:
            cache = f.read().strip()

    ctfs = get_ctfs(max_ctfs, days)
    embeds = [ctf.generate_embed() for ctf in ctfs]
    ids = ",".join([str(ctf.cid) for ctf in ctfs])
    if cache == ids:
        return False
    else:
        if cache_path:
            with open(cache_path, "w") as f:
                f.write(ids)

        client = CtfTimeClient(
            channel_id=channel_id,
            content=f"CTFs during the upcoming {days} days:",
            embeds=embeds,
            intents=discord.Intents.default(),
        )
        client.run(token)
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

    if args.cache_file:
        try:
            open(args.cache_file, "x").close()
        except FileExistsError:
            pass

    send_updates(
        channel_id=args.channel_id,
        token=args.token,
        max_ctfs=args.max_entries,
        days=args.days,
        cache_path=args.cache_file,
    )
