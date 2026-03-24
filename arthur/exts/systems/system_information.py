"""Return system information on our production 9front infrastructure."""

import asyncio
import base64
import io
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TYPE_CHECKING
from urllib import parse

import aiohttp
from discord import File, Member, Message
from discord.ext import tasks
from discord.ext.commands import Cog, Context, Converter, command
from loguru import logger
from wand.image import Image

from arthur.apis.systems import lib9front
from arthur.config import CONFIG
from arthur.exts.systems._motd import MOTD

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible

BASE_RESOURCE = "https://git.9front.org/plan9front/plan9front/HEAD/{}/raw"
THRESHOLD = 0.01
MIN_MINUTES = 30
BLOG_ABOUT_IT_THRESHOLD = 1000
RESOURCE_PATH = Path(__file__).parent.parent.parent / "resources" / "systems"


class URLConverter(Converter):
    """Validate a passed argument is a URL, for use in optional converters that are looking for URLs."""

    async def convert(self, _ctx: Context, argument: str) -> str | None:
        """Attempt to convert a string to a URL, return the argument if it is a URL, else return None."""
        try:
            parsed = parse.urlparse(argument)

            if parsed.scheme in {"http", "https"}:
                return argument
        except ValueError:
            return None


class SystemInformation(Cog):
    """Utilities for fetching system information from our 9front infrastructure."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot
        self.cached_resources = {}
        self.cached_blogcom = None
        self.cached_bullshit = None
        self.last_sent = None

        self.smileys = RESOURCE_PATH.joinpath("smileys.txt").read_text().splitlines()
        self.management_comments = (
            RESOURCE_PATH.joinpath("management_comments.txt").read_text().splitlines()
        )
        self.supportive_comments = RESOURCE_PATH.joinpath("supportive_comments.txt").read_text()
        self.uwsgi_loglines = RESOURCE_PATH.joinpath("uwsgi_loglines.txt").read_text().splitlines()

        self.conduct_one_to_ones.start()

    async def fetch_resource(self, name: str) -> str:
        """Fetch the file contents of the given filename, starting from ``/``."""
        if name not in self.cached_resources:
            url = BASE_RESOURCE.format(name)
            async with aiohttp.ClientSession() as session, session.get(url) as resp:
                self.cached_resources[name] = await resp.text()
        return self.cached_resources[name]

    async def cog_unload(self) -> None:
        """Tasks to run when cog is unloaded."""
        self.conduct_one_to_ones.cancel()

    @tasks.loop(hours=12)
    async def conduct_one_to_ones(self) -> None:
        """Conduct management one-to-ones with eligible team members."""
        if random.random() > 0.01:
            # Management budget exceeded for this one-to-one slot.
            return

        guild = self.bot.get_guild(CONFIG.guild_id)

        if guild is None:
            return

        role = guild.get_role(CONFIG.devops_role)

        if role is None:
            return

        mr_hemlock = await guild.fetch_member(98195144192331776)
        if mr_hemlock is None:
            logger.error(
                "arthur-error: king arthur screams: UAAAAAAH my "
                "master disconnected: i will kill myself !!!"
            )
            sys.exit(1)

        selected_member = random.choice(role.members + [mr_hemlock])
        selected_management_comment = random.choice(self.management_comments)

        await selected_member.send(selected_management_comment)
        logger.info("Inspirational management tactic applied to {member}", member=selected_member)

    @Cog.listener()
    async def on_message(self, msg: Message) -> None:
        """Handler for incoming messages, potentially returning system information."""
        if not msg.guild:
            logger.trace("Ignoring DM")
            return

        if msg.author.id == self.bot.user.id:
            logger.trace("Ignoring own message")
            return

        if msg.channel.id != CONFIG.devops_channel_id:
            logger.trace("Ignoring message outside of DevOps channel")
            return

        if self.last_sent:
            if (datetime.now(tz=UTC) - self.last_sent).seconds // 60 < MIN_MINUTES:
                logger.trace("Ignoring message as within cooldown")
                return

        msg_thresh = THRESHOLD

        if isinstance(msg.author, Member):
            if CONFIG.devops_role not in (r.id for r in msg.author.roles):
                logger.trace("Upping threshold due to non-DevOps member")
                msg_thresh *= 10

        if len(msg.content) > BLOG_ABOUT_IT_THRESHOLD:
            msg_thresh += 0.10

        if random.random() < msg_thresh:
            logger.trace("Criteria hit, generating comment.")
            if random.random() < 0.9:
                blogcom = await self.fetch_resource("lib/blogcom")
            else:
                blogcom = self.supportive_comments

            comment = lib9front.generate_blog_comment(blogcom).strip()

            self.last_sent = datetime.now(tz=UTC)
            async with msg.channel.typing():
                await asyncio.sleep(3)
                await msg.reply(f"{comment} {random.choice(self.smileys)}")

    @command(name="software")
    async def software(self, ctx: Context) -> None:
        """Return information on installed and available software."""
        bullshit = await self.fetch_resource("lib/bullshit")
        program = lib9front.generate_buzzwords(bullshit)
        await ctx.reply(program)

    @command(name="face")
    async def face(
        self, ctx: Context, resolution: int | None = 60, *, image_url: URLConverter | None = None
    ) -> None:
        """
        Generate a system-compatible face for the given file.

        If specified, resolution is the integer width and height to use for the generated image, defaulting to 60 (for a 60x60 image).

        The image can be passed in as a URL or attached to the command invocation message.
        """
        image_bytes = io.BytesIO()

        if not image_url:
            if len(ctx.message.attachments) == 0:
                await ctx.reply(":x: Must upload an image or specify image URL")
                return

            await ctx.message.attachments[0].save(image_bytes)
        else:
            async with aiohttp.ClientSession() as session, session.get(image_url) as resp:
                if resp.ok:
                    image_bytes.write(await resp.read())
                    image_bytes.seek(0)
                else:
                    await ctx.reply(
                        f":x: Could not read remote resource, check it exists. (status `{resp.status}`)"
                    )
                    return

        out_bytes = io.BytesIO()

        with Image(file=image_bytes) as img:
            img.resize(resolution, resolution)

            img.quantize(number_colors=2, treedepth=8, dither=True)

            img.type = "grayscale"
            img.format = "png"

            img.save(file=out_bytes)

        out_bytes.seek(0)

        await ctx.reply(file=File(out_bytes, filename="face.png"))

    @command(name="wisdom")
    async def wisdom(
        self, ctx: Context, by: Literal["ken", "rob", "rsc", "theo", "uriel"] | None = None
    ) -> None:
        """Retrieve some software engineering wisdom."""
        if by is None:
            by = random.choice(("ken", "rob", "rsc", "theo", "uriel"))

        contents = await self.fetch_resource(f"lib/{by}")
        result = random.choice(contents.splitlines())
        await ctx.reply(result)

    @command(name="troll")
    async def troll(self, ctx: Context) -> None:
        """Utter statements of utmost importance."""
        contents = await self.fetch_resource("lib/troll")
        result = random.choice(contents.splitlines())
        await ctx.reply(result)

    @command(name="motd")
    async def motd(self, ctx: Context) -> None:
        """Generate an image representing the message of the day."""
        payload = MOTD.replace(b"\n", b"")
        file = File(io.BytesIO(base64.b64decode(payload)), filename="motd.png")
        await ctx.send(file=file)

    @command(name="uwsgi")
    async def uwsgi(self, ctx: Context) -> None:
        """Return a log line suitable for industry standard WSGI servers."""
        message = random.choice(self.uwsgi_loglines)
        await ctx.reply(f"``{message}``")


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(SystemInformation(bot))
