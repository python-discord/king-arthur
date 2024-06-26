"""Send motivating messages to the devops team."""

import re
from datetime import UTC, datetime, time

import discord
from discord.ext import commands, tasks

from arthur.bot import KingArthur
from arthur.config import CONFIG

MOTIVATION_IMAGE_RE = re.compile(r"data-image=\"(https://assets\.amuniversal\.com/.+?)\"")
THE_CAT = "https://avatar.amuniversal.com/feature_avatars/ubadge_images/features/ga/mid_u-201701251612.png"
BASE_URL = "https://www.gocomics.com/garfield/"


class Motivation(commands.Cog):
    """Motivation is the key to productivity."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.devops_channel = bot.get_channel(CONFIG.devops_channel_id)
        self.send_daily_motivation.start()

    @tasks.loop(time=time(hour=9))
    async def send_daily_motivation(self) -> None:
        """Send motivation to the people who need it most."""
        today_date = datetime.now(UTC).date().isoformat()
        today_date_url_friendly = today_date.replace("-", "/")

        async with self.bot.http_session.get(BASE_URL + today_date_url_friendly) as resp:
            resp.raise_for_status()
            raw_content = await resp.text()
        image = MOTIVATION_IMAGE_RE.search(raw_content).group(1)

        embed = discord.Embed(
            title=f"Garfield: {today_date}",
            url=BASE_URL + today_date_url_friendly,
            colour=discord.Colour.orange(),
        )
        embed.set_author(name="GoComics.com", icon_url=THE_CAT, url=BASE_URL)
        embed.set_image(url=image)
        await self.devops_channel.send(embed=embed)


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(Motivation(bot))
