"""This cog provides error handling for King Arthur The Terrible."""

from typing import TYPE_CHECKING

from discord.ext import commands
from discord.ext.commands import Cog

from arthur.utils import generate_error_message

if TYPE_CHECKING:
    from discord import Message

    from arthur.bot import KingArthurTheTerrible


class ErrorHandler(Cog):
    """Error handling for King Arthur The Terrible."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    async def _add_error_reaction(self, message: Message) -> None:
        await message.add_reaction("\N{CROSS MARK}")

    @Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle exceptions raised during command processing."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument | commands.BadArgument):
            await self._add_error_reaction(ctx.message)
            await ctx.send_help(ctx.command)
        elif isinstance(
            error,
            commands.CheckFailure
            | commands.NoPrivateMessage
            | commands.CommandOnCooldown
            | commands.DisabledCommand
            | commands.DisabledCommand,
        ):
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
                        f"Unknown exception occurred: `{error.__class__.__name__}: {error}`"
                    )
                )
            )


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(ErrorHandler(bot))
