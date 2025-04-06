import discord
from discord.ext import commands

from arthur.config import CONFIG


class Numbers(commands.GroupCog):
    """Commands for working with and controlling the numbers forwarder."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        """Join devops channel on cog load."""
        devops_vc = self.bot.get_channel(CONFIG.devops_vc_id)
        await self._join_and_play_numbers(devops_vc)  # type: ignore[union-attr]

    async def _join_and_play_numbers(
        self,
        channel: discord.VoiceChannel | discord.StageChannel,
    ) -> None:
        vc = await channel.connect(self_deaf=True, self_mute=False)
        vc.play(discord.FFmpegOpusAudio(CONFIG.numbers_url))

    @commands.group(invoke_without_command=True)
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
            return

        if not channel and isinstance(ctx.author, discord.Member) and (vs := ctx.author.voice):
            channel = vs.channel

        if not channel:
            await ctx.send(":x: Join a voice channel first!")
            return

        if vc := ctx.guild.voice_client:
            await vc.disconnect(force=True)

        await self._join_and_play_numbers(channel)
        await ctx.message.add_reaction("🔊")

    @numbers.command()
    async def stop(self, ctx: commands.Context) -> None:
        """Stop playing URN in the servers voice channel."""
        if ctx.guild and (vc := ctx.guild.voice_client):
            await vc.disconnect(force=True)
            await ctx.message.add_reaction("🔇")
        else:
            await ctx.send(":x: Not in a voice channel!")


async def setup(bot: commands.Bot) -> None:
    """Set up the numbers cog."""
    await bot.add_cog(Numbers(bot))
