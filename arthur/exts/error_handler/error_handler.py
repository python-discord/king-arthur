"""This cog provides error handling for King Arthur The Terrible."""

from contextlib import suppress
from typing import TYPE_CHECKING

from discord import HTTPException, app_commands
from discord.ext import commands
from discord.ext.commands import Cog

from arthur.utils import generate_error_message

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class ErrorHandler(Cog):
    """Error handling for King Arthur The Terrible."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    async def _add_error_reaction(self, ctx: commands.Context) -> None:
        """React to the invoking message; slash invocations have no real message to react to."""
        if ctx.interaction is not None or ctx.message is None:
            return
        with suppress(HTTPException):
            await ctx.message.add_reaction("\N{CROSS MARK}")

    @Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle exceptions raised during command processing."""
        if isinstance(error, commands.HybridCommandError):
            error = error.original
        # Errors raised inside a slash invocation are wrapped by app_commands.
        invoke_failed = isinstance(
            error, app_commands.CommandInvokeError | commands.CommandInvokeError
        )
        if invoke_failed:
            error = error.original

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument | commands.BadArgument):
            await self._add_error_reaction(ctx)
            await ctx.send_help(ctx.command)
        elif isinstance(
            error,
            commands.CheckFailure
            | commands.NoPrivateMessage
            | commands.CommandOnCooldown
            | commands.DisabledCommand,
        ):
            await self._add_error_reaction(ctx)
            if ctx.interaction is not None:
                await ctx.send(
                    generate_error_message(description="You are not permitted to do that."),
                    ephemeral=True,
                )
        elif invoke_failed:
            await self._add_error_reaction(ctx)
            await ctx.send(
                generate_error_message(
                    description=(f"Command raised an error: `{error.__class__.__name__}: {error}`")
                ),
                ephemeral=True,
            )
        else:
            await ctx.send(
                generate_error_message(
                    description=(
                        f"Unknown exception occurred: `{error.__class__.__name__}: {error}`"
                    )
                ),
                ephemeral=True,
            )


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(ErrorHandler(bot))
