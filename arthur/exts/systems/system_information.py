"""Return system information on our production 9front infrastructure."""

import asyncio
import random
from datetime import UTC, datetime

import aiohttp
from discord import Member, Message
from discord.ext.commands import Cog, Context, command
from loguru import logger

from arthur.apis.systems import lib9front
from arthur.bot import KingArthur
from arthur.config import CONFIG

BASE_RESOURCE = "https://git.9front.org/plan9front/plan9front/HEAD/{}/raw"
BLOGCOM = BASE_RESOURCE.format("lib/blogcom")
BULLSHIT = BASE_RESOURCE.format("lib/bullshit")
THRESHOLD = 0.01
MIN_MINUTES = 30
BLOG_ABOUT_IT_THRESHOLD = 1000
CORPORATE_FRIENDLY_SMILEYS = (
    ":smile:",
    ":slight_smile:",
    ":grin:",
    ":blush:",
)


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
        self.cached_blogcom = None
        self.cached_bullshit = None
        self.last_sent = None

    async def fetch_blogcom(self) -> str:
        """Fetch the blogcom file from the upstream location, or return the cached copy."""
        if not self.cached_blogcom:
            async with aiohttp.ClientSession() as session, session.get(BLOGCOM) as resp:
                self.cached_blogcom = await resp.text()

        return self.cached_blogcom

    async def fetch_bullshit(self) -> str:
        """Fetch the bullshit file from the upstream location, or return the cached copy."""
        if not self.cached_bullshit:
            async with aiohttp.ClientSession() as session, session.get(BULLSHIT) as resp:
                self.cached_bullshit = await resp.text()

        return self.cached_bullshit

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
                blogcom = await self.fetch_blogcom()
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
        bullshit = await self.fetch_bullshit()
        program = lib9front.generate_buzzwords(bullshit)
        await ctx.reply(program)


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(SystemInformation(bot))
