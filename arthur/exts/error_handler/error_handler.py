"""This cog provides error handling for King Arthur."""
from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog

from arthur.bot import KingArthur
from arthur.utils import generate_error_message


class ErrorHandler(Cog):
    """Error handling for King Arthur."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    async def _add_error_reaction(self, message: Message) -> None:
        await message.add_reaction("\N{CROSS MARK}")

    @Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle exceptions raised during command processing."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await self._add_error_reaction(ctx.message)
            await ctx.send_help(ctx.command)
        elif isinstance(error, commands.BadArgument):
            await self._add_error_reaction(ctx.message)
            await ctx.send_help(ctx.command)
        elif isinstance(error, commands.CheckFailure):
            await self._add_error_reaction(ctx.message)
        elif isinstance(error, commands.NoPrivateMessage):
            await self._add_error_reaction(ctx.message)
        elif isinstance(error, commands.CommandOnCooldown):
            await self._add_error_reaction(ctx.message)
        elif isinstance(error, commands.DisabledCommand):
            await self._add_error_reaction(ctx.message)
        elif isinstance(error, commands.CommandInvokeError):
            await self._add_error_reaction(ctx.message)
            await ctx.send(
                generate_error_message(
                    description=(
                        f"Command raised an error: `{error.original.__class__.__name__}:"
                        f" {error.original}`"
                    )
                )
            )
        else:
            await ctx.send(
                generate_error_message(
                    description=(
                        f"Unknown exception occurred: `{error.__class__.__name__}:"
                        f" {error}`"
                    )
                )
            )


def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    bot.add_cog(ErrorHandler(bot))
