"""Send motivating messages to the devops team."""

import random
import re
from datetime import UTC, datetime, time

import discord
from discord.ext import commands, tasks

from arthur.bot import KingArthur
from arthur.config import CONFIG
from arthur.log import logger

MOTIVATION_IMAGE_RE = re.compile(r"data-image=\"(https://assets\.amuniversal\.com/.+?)\"")
THE_CAT = "https://avatar.amuniversal.com/feature_avatars/ubadge_images/features/ga/mid_u-201701251612.png"
GARF_URL = "https://www.gocomics.com/garfield/"


class Motivation(commands.Cog):
    """Motivation is the key to productivity."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.devops_channel = bot.get_channel(CONFIG.devops_channel_id)
        self.send_daily_motivation.start()
        if CONFIG.youtube_api_key:
            self.send_daily_mission.start()

    @tasks.loop(time=time(hour=12, minute=30, tzinfo=UTC))
    async def send_daily_mission(self) -> None:
        """Send the daily mission to the team."""
        params = {
            "part": "snippet",
            "channelId": "UC4CoHBR01SHu6fMy2EaeWcg",
            "key": CONFIG.youtube_api_key.get_secret_value(),
            "order": "date",
            "maxResults": "5",
        }
        async with self.bot.http_session.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        todays_date = datetime.now(UTC).date()
        for video in data["items"]:
            title: str = video["snippet"]["title"]
            if not title.startswith("TODAY&#39;S MISSION:"):
                continue
            date = datetime.fromisoformat(video["snippet"]["publishedAt"]).date()
            if date != todays_date:
                continue

            await self.devops_channel.send(
                f"[Today's mission](https://www.youtube.com/shorts/{video['id']['videoId']})"
            )
            break
        else:
            logger.warning("No mission found for %s", todays_date)

    @tasks.loop(time=time(hour=9, tzinfo=UTC))
    async def send_daily_motivation(self) -> None:
        """Send motivation to the people who need it most."""
        today_date = datetime.now(UTC).date().isoformat()
        today_date_url_friendly = today_date.replace("-", "/")

        async with self.bot.http_session.get(GARF_URL + today_date_url_friendly) as resp:
            resp.raise_for_status()
            raw_content = await resp.text()
        image = MOTIVATION_IMAGE_RE.search(raw_content).group(1)

        embed = discord.Embed(
            title=f"Garfield: {today_date}",
            url=GARF_URL + today_date_url_friendly,
            colour=discord.Colour.orange(),
        )
        embed.set_author(name="GoComics.com", icon_url=THE_CAT, url=GARF_URL)
        embed.set_image(url=image)
        await self.devops_channel.send(embed=embed)

    @commands.command(name="monitor")
    async def monitor(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel | discord.StageChannel | None = None,
    ) -> None:
        """Obey."""
        if not ctx.guild:
            return

        if not channel and isinstance(ctx.author, discord.Member) and (vs := ctx.author.voice):
            channel = vs.channel

        if not channel:
            await ctx.send(":x: You will join a voice channel or pass one as argument!")
            return

        vc = ctx.guild.voice_client
        if vc is None:
            vc = await channel.connect(self_deaf=True, self_mute=False)
        else:
            await vc.move_to(channel)

        selection = random.randint(1, 23)
        monitor = f"https://pydis.wtf/~fredrick/monitor-{selection:03d}.mp3"
        audio = await discord.FFmpegOpusAudio.from_probe(monitor)
        vc.play(audio)
        if random.random() < 0.1:  # noqa: PLR2004
            for emoji in ("🇴", "🇧", "🇪", "🇾"):
                await ctx.message.add_reaction(emoji)
        else:
            await ctx.message.add_reaction("🔊")


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(Motivation(bot))
