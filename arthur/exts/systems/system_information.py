"""Return system information on our production 9front infrastructure."""

import random
from datetime import datetime

import aiohttp
from discord import Message
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
            if (datetime.utcnow() - self.last_sent).seconds // 60 < MIN_MINUTES:
                logger.trace("Ignoring message as within cooldown")
                return

        msg_thresh = THRESHOLD

        if CONFIG.devops_role not in (r.id for r in msg.author.roles):
            logger.trace("Upping threshold due to non-DevOps member")
            msg_thresh *= 10

        if len(msg.content) > BLOG_ABOUT_IT_THRESHOLD:
            msg_thresh += 0.10

        if random.random() < msg_thresh:
            logger.trace("Criteria hit, generating comment.")

            blogcom = await self.fetch_blogcom()

            comment = lib9front.generate_blog_comment(blogcom).strip()

            await msg.reply(f"{comment} {random.choice(CORPORATE_FRIENDLY_SMILEYS)}")

            self.last_sent = datetime.utcnow()

    @command(name="software")
    async def software(self, ctx: Context) -> None:
        """Return information on installed and available software."""
        bullshit = await self.fetch_bullshit()
        program = lib9front.generate_buzzwords(bullshit)
        await ctx.reply(program)


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(SystemInformation(bot))
