"""Commands for managing the GitHub organisation and teams."""

from typing import TYPE_CHECKING

from discord.ext import tasks
from discord.ext.commands import Cog

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class GitHubManagement(Cog):
    """GitHub organisation membership synchronisation with LDAP."""

    def __init__(self, bot: "KingArthurTheTerrible") -> None:
        self.bot = bot

    @tasks.loop(minutes=10)
    async def sync_github_org(self) -> None:
        """Synchronise GitHub organisation membership with LDAP."""

async def setup(bot: "KingArthurTheTerrible") -> None:
    """Add cog to bot."""
    await bot.add_cog(GitHubManagement(bot))
