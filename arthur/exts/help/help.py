"""Hybrid help command and the formatter backing it."""

from typing import TYPE_CHECKING

from discord import Interaction, app_commands
from discord.ext import commands

from arthur.utils import generate_error_message

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible
    from arthur.context import BotContext


def slash_name(command: commands.Command) -> str | None:
    """Get the slash form of a command, or None if it has no slash form."""
    parts = []
    current: commands.Command | None = command
    chain = []
    while current is not None:
        chain.append(current)
        current = current.parent
    chain.reverse()

    for item in chain:
        if getattr(item, "app_command", None) is None:
            return None
        parts.append(item.name)

    # Groups with a fallback run as `/group fallback`
    if isinstance(command, commands.HybridGroup) and command.fallback:
        parts.append(command.fallback)

    return "/" + " ".join(parts)


class HelpFormatter:
    """Builds help text for commands, groups and the whole bot."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot
        self.context: BotContext | None = None

    @staticmethod
    def _usage(command: commands.Command) -> str:
        slash = slash_name(command)
        parts = [f"@{{bot}} {command.qualified_name} {command.signature}".strip()]
        if slash:
            parts.append(slash)
        return " | ".join(parts)

    def _bot_name(self) -> str:
        user = self.bot.user
        return user.display_name if user else "King Arthur"

    def _command_help(self, command: commands.Command) -> str:
        lines = [f"**{self._usage(command).format(bot=self._bot_name())}**"]
        if command.help:
            lines.append(command.help)
        if isinstance(command, commands.Group):
            lines.append("")
            lines.append("**Subcommands**")
            lines.extend(
                f"`{sub.name}`: {sub.short_doc or 'No description'}"
                for sub in sorted(command.commands, key=lambda c: c.name)
                if not sub.hidden
            )
        return "\n".join(lines)

    def _overview(self) -> str:
        lines = [
            f"Mention me (`@{self._bot_name()} <command>`) or use slash commands.",
            "",
            "**Commands**",
        ]
        lines.extend(
            f"`{cmd.name}`: {cmd.short_doc or 'No description'}"
            for cmd in sorted(self.bot.commands, key=lambda c: c.name)
            if not cmd.hidden
        )
        return "\n".join(lines)

    async def send_help_for(self, qualified_name: str | None) -> None:
        """Send help for a command (or the overview if None) into the current context."""
        ctx = self.context
        if ctx is None:
            return

        if not qualified_name:
            await ctx.send(self._overview())
            return

        command = self.bot.get_command(qualified_name)
        if command is None:
            await ctx.send(
                generate_error_message(description=f"No command called `{qualified_name}` found.")
            )
            return

        await ctx.send(self._command_help(command))


class Help(commands.Cog):
    """Help for King Arthur The Terrible."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot
        self.formatter = HelpFormatter(bot)

    async def _autocomplete(self, _: Interaction, current: str) -> list[app_commands.Choice[str]]:
        names = sorted(
            {
                cmd.qualified_name
                for cmd in self.bot.walk_commands()
                if not cmd.hidden and current.lower() in cmd.qualified_name.lower()
            }
        )
        return [app_commands.Choice(name=n, value=n) for n in names[:25]]

    @commands.hybrid_command(name="help")
    @app_commands.describe(command="The command to get help for")
    @app_commands.autocomplete(command=_autocomplete)
    async def help(self, ctx: commands.Context, *, command: str | None = None) -> None:
        """Show help for King Arthur's commands."""
        self.formatter.context = ctx
        await self.formatter.send_help_for(command)


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add the extension to the bot."""
    await bot.add_cog(Help(bot))
