"""Custom command context for King Arthur The Terrible."""

from typing import Any

from discord.ext import commands


class BotContext(commands.Context):
    """Context subclass routing help requests to the help cog."""

    async def send_help(self, *args: Any) -> None:
        """
        Send help for a command, group or cog via the help cog's formatter.

        discord.py's default implementation does nothing when the bot has no help command,
        so this is routed to our own formatter instead.
        """
        help_cog = self.bot.get_cog("Help")
        if help_cog is None:
            return

        formatter = help_cog.formatter
        formatter.context = self

        target = args[0] if args else None
        if target is None:
            await formatter.send_help_for(None)
        elif isinstance(target, str):
            await formatter.send_help_for(target)
        else:
            await formatter.send_help_for(target.qualified_name)
