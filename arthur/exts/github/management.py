"""Commands for managing the GitHub organisation and teams."""

from discord.ext.commands import Cog, Context, group

from arthur.apis.github import GitHubError, add_staff_member, remove_org_member
from arthur.bot import KingArthur
from arthur.config import CONFIG


class GitHubManagement(Cog):
    """Ed is the standard text editor."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        """Check if the user has permission to use this cog."""
        return (
            CONFIG.admins_role in [r.id for r in ctx.author.roles]
            or CONFIG.devops_role in [r.id for r in ctx.author.roles]
            or await self.bot.is_owner(ctx.author)
        )

    @group(name="github", invoke_without_command=True)
    async def github(self, ctx: Context) -> None:
        """Group of commands for managing the GitHub organisation."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @github.command(name="add")
    async def add_team_member(self, ctx: Context, username: str) -> None:
        """Add a user to the default GitHub team."""
        try:
            await add_staff_member(username)
            await ctx.send(f":white_check_mark: Successfully invited {username} to the staff team.")
        except GitHubError as e:
            await ctx.send(f":x: Failed to add {username} to the staff team: {e}")

    @github.command(name="remove")
    async def remove_org_member(self, ctx: Context, username: str) -> None:
        """Remove a user from the GitHub organisation."""
        try:
            await remove_org_member(username)
            await ctx.send(
                f":white_check_mark: Successfully removed {username} from the GitHub organisation."
            )
        except GitHubError as e:
            await ctx.send(f":x: Failed to remove {username} from the organisation: {e}")


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(GitHubManagement(bot))
