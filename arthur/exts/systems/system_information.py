"""Return system information on our production 9front infrastructure."""

import asyncio
import base64
import io
import random
from datetime import UTC, datetime
from typing import Literal
from urllib import parse

import aiohttp
from discord import File, Member, Message
from discord.ext import tasks
from discord.ext.commands import Cog, Context, Converter, command
from loguru import logger
from wand.image import Image

from arthur.apis.systems import lib9front
from arthur.bot import KingArthur
from arthur.config import CONFIG
from arthur.exts.systems.motd import MOTD

BASE_RESOURCE = "https://git.9front.org/plan9front/plan9front/HEAD/{}/raw"
THRESHOLD = 0.01
MIN_MINUTES = 30
BLOG_ABOUT_IT_THRESHOLD = 1000
CORPORATE_FRIENDLY_SMILEYS = (
    ":smile:",
    ":slight_smile:",
    ":grin:",
    ":blush:",
)
MANAGEMENT_ONE_TO_ONE_COMMENTS = (
    "Well Clarice, have the lambs stopped screaming?",
    "I do wish we could chat longer, but... I'm having an old friend for dinner. Bye.",
    "What is your father, dear? Is he a coal miner?",
    "Senator, just one more thing: love your suit!",
    "Memory, Agent Starling, is what I have instead of a view.",
    "You still wake up sometimes, don't you? You wake up in the dark and hear the screaming of the lambs.",
    "People will say we're in love.",
    "All good things to those who wait.",
    '"Plum Island Animal Disease Research Center." Sounds charming.',
    "Ready when you are, Sergeant Pembry.",
    "A census taker once tried to test me.",
)


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

    SUPPORTIVE_PYTHON_DISCORD_COMMENTS = """\
{Lemon|Bella|Chris} would {seriously|really|honestly} love to {have a word|discuss this topic} \
with you! There {seems to be|is|appears to be|is assumed to be} a {tiny|minor|major|large} \
{misunderstanding|miscommunication} here!|
{Python|Erlang|Chris' exhaust} is peace. \
{The DevOps team|Decentralized version control|The 2024 presidential election} is replication. \
Your {message|comment|idea|thought} is strength.|
Who controls {King Arthur|Kubernetes|Netcup|Joe's medication} controls the future. \
Who controls {Bella's rations|the dennis.services mail server|`git push -f` access|edit rights to this message} controls the past.|
The best {messages|comments|ideas|chats}... are those that tell you what you know already.|
If you want to keep {a secret|PGP private keys|Lemoncluster access|access to Joe's secret vacation photo library}, you must also hide it from {yourself|the moderators team|the ethical advisory board|Chris}.|
{:warning:|:information_source:|:no_entry_sign:} Detected a high amount of doublethink in this message. \
The {moderators have|administrators have|DevOps team has|Python Discord ethical advisory board has} been informed.|
Reading your message, I realize: Perhaps a lunatic was simply a minority of one.|
It's a beautiful thing, the destruction of words.|
I enjoy talking to you. Your mind appeals to me. It resembles my own mind except that you happen to be {clinically |absolutely |completely |}insane.
"""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.cached_resources = {}
        self.cached_blogcom = None
        self.cached_bullshit = None
        self.last_sent = None
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

        selected_member = random.choice(role.members)
        selected_management_comment = random.choice(MANAGEMENT_ONE_TO_ONE_COMMENTS)

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
                blogcom = self.SUPPORTIVE_PYTHON_DISCORD_COMMENTS

            comment = lib9front.generate_blog_comment(blogcom).strip()

            self.last_sent = datetime.now(tz=UTC)
            async with msg.channel.typing():
                await asyncio.sleep(3)
                await msg.reply(f"{comment} {random.choice(CORPORATE_FRIENDLY_SMILEYS)}")

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


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(SystemInformation(bot))
