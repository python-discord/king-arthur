from http import HTTPStatus
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks

from arthur.apis.netcup.ssh import rce_as_a_service
from arthur.config import CONFIG
from arthur.log import logger

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class Numbers(commands.Cog):
    """Commands for working with and controlling the numbers forwarder."""

    def __init__(self, bot: KingArthurTheTerrible):
        self.bot = bot
        self.devops_vc: discord.VoiceChannel | discord.StageChannel | None = None
        self.devops_vc_check.start()

    async def cog_load(self) -> None:
        """Join devops channel on cog load."""
        async with self.bot.http_session.head(CONFIG.numbers_url) as resp:
            if resp.status != HTTPStatus.OK:
                logger.warning("Numbers URL is not reachable; not connecting to devops VC.")
                return

        devops_vc = self.bot.get_channel(CONFIG.devops_vc_id)
        if not isinstance(devops_vc, (discord.VoiceChannel, discord.StageChannel)):
            return

        self.devops_vc = devops_vc
        vc = await devops_vc.connect(self_deaf=True, self_mute=False)
        vc.play(discord.FFmpegOpusAudio(CONFIG.numbers_url))

    async def cog_unload(self) -> None:
        """Disconnect from devops channel on cog unload."""
        self.devops_vc_check.cancel()
        if self.devops_vc and (vc := self.devops_vc.guild.voice_client):
            await vc.disconnect(force=True)

    @tasks.loop(hours=1)
    async def devops_vc_check(self) -> None:
        """Ensure the uptime of the numbers relay."""
        if not self.devops_vc or not (vc := self.devops_vc.guild.voice_client):
            return
        if not isinstance(vc, discord.VoiceClient):
            return
        if vc.is_playing():
            return

        vc.play(discord.FFmpegOpusAudio(CONFIG.numbers_url))

    @staticmethod
    async def _signal(ctx: commands.Context, emoji: str) -> None:
        """Acknowledge with a reaction, or a message on slash where there is nothing to react to."""
        if ctx.interaction is not None:
            await ctx.send(emoji)
        else:
            await ctx.message.add_reaction(emoji)

    @commands.hybrid_group(invoke_without_command=True, fallback="join")
    @app_commands.describe(channel="Voice channel to join (defaults to yours)")
    async def numbers(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel | discord.StageChannel | None = None,
    ) -> None:
        """
        Join a voice channel and forward numbers.

        If channel is not provided, the bot will join the voice channel of the user who invoked the command.
        """
        if not ctx.guild:
            await ctx.send(":x: This command can only be used in a server.", ephemeral=True)
            return

        if not channel and isinstance(ctx.author, discord.Member) and (vs := ctx.author.voice):
            channel = vs.channel

        if not channel:
            await ctx.send(":x: Join a voice channel first!")
            return

        await ctx.defer()

        if vc := ctx.guild.voice_client:
            # Should always be the case, but I wanted type hinting
            if isinstance(vc, discord.VoiceClient):
                await vc.move_to(channel)
                await self._signal(ctx, "🔊")
            else:
                await ctx.send(":x: Unable to move the current voice connection.")
            return

        vc = await channel.connect(self_deaf=True, self_mute=False)
        vc.play(discord.FFmpegOpusAudio(CONFIG.numbers_url))
        await self._signal(ctx, "🔊")

    @numbers.command()
    @app_commands.describe(text="Text to read out")
    async def tts(self, ctx: commands.Context, *, text: str) -> None:
        """Have KA read out a message in the current VC."""
        if not await ctx.bot.is_owner(ctx.author):
            if ctx.interaction is not None:
                await ctx.send("❌", ephemeral=True)
            else:
                await ctx.message.add_reaction("❌")
            return

        if not ctx.guild or not ctx.guild.voice_client:
            await ctx.send(":x: Not in a voice channel!", ephemeral=True)
            return

        await ctx.defer()
        await rce_as_a_service(
            f"echo '{text}' > /opt/messages/tts_message.txt && "
            "touch -a -m -t 197501010001 /opt/messages/tts_message.txt && "
            "sudo /opt/numbers-code-generator.sh"
        )
        if ctx.interaction is not None:
            await ctx.send("👍")

    @numbers.command()
    async def stop(self, ctx: commands.Context) -> None:
        """Stop relaying numbers in the voice channel."""
        if ctx.guild and (vc := ctx.guild.voice_client):
            await vc.disconnect(force=True)
            await self._signal(ctx, "🔇")
        else:
            await ctx.send(":x: Not in a voice channel!")


async def setup(bot: KingArthurTheTerrible) -> None:
    """Set up the numbers cog."""
    await bot.add_cog(Numbers(bot))
