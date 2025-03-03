import aiohttp
import discord
from discord.ext import commands, tasks

from arthur.apis import github, grafana
from arthur.bot import KingArthur
from arthur.config import CONFIG
from arthur.log import logger

from . import MissingMembers, SyncFigures


class GrafanaGitHubTeamSync(commands.Cog):
    """
    Update Grafana team membership to match Github team membership.

    Grafana team name must match Github team slug exactly.
    Use `gh api orgs/{org-name}/teams` to get a list of teams in an org
    """

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.sync_github_grafana_teams.start()

    async def _add_missing_members(
        self,
        grafana_team_id: int,
        github_team_members: set[str],
        grafana_team_members: set[str],
        all_grafana_users: list[dict],
    ) -> MissingMembers:
        """
        Adds members to the Grafana team if they're in the Github team and not already present.

        Returns the number of missing members, and the number of members it could actually add.
        """
        missing_members = github_team_members - grafana_team_members
        added_members = 0
        for grafana_user in all_grafana_users:
            if grafana_user["login"] not in missing_members:
                continue
            if "GitHub" not in grafana_user.get("authLabels", []):
                continue

            await grafana.add_user_to_team(
                grafana_user["userId"],
                grafana_team_id,
                self.bot.http_session,
            )
            added_members += 1
        return MissingMembers(count=len(missing_members), successfully_added=added_members)

    async def _remove_extra_members(
        self,
        grafana_team_id: int,
        github_team_members: set[str],
        grafana_team_members: set[str],
        all_grafana_users: list[dict],
    ) -> int:
        """
        Removes Grafana users from a team if they are not present in the Github team.

        Return how many were removed.
        """
        extra_members = grafana_team_members - github_team_members
        removed_members = 0
        for grafana_user in all_grafana_users:
            if grafana_user["login"] not in extra_members:
                continue
            await grafana.remove_user_from_team(
                grafana_user["userId"],
                grafana_team_id,
                self.bot.http_session,
            )
            removed_members += 1
        return removed_members

    async def _sync_teams(self, team: dict[str, str]) -> SyncFigures:
        """
        Ensure members in Github are present in Grafana teams.

        Return the number of members missing from the Grafana team, and the number of members added.
        """
        github_team_members = {
            member["login"]
            for member in await github.list_team_members(team["name"], self.bot.http_session)
        }
        grafana_team_members = {
            member["login"]
            for member in await grafana.list_team_members(team["id"], self.bot.http_session)
            if member.get("auth_module") == "oauth_github"
        }

        all_grafana_users = await grafana.get_all_users(self.bot.http_session)
        added_members = await self._add_missing_members(
            team["id"],
            github_team_members,
            grafana_team_members,
            all_grafana_users,
        )
        removed_members = await self._remove_extra_members(
            team["id"],
            github_team_members,
            grafana_team_members,
            all_grafana_users,
        )

        return SyncFigures(added=added_members, removed=removed_members)

    @tasks.loop(hours=12)
    async def sync_github_grafana_teams(self, channel: discord.TextChannel | None = None) -> None:
        """Update Grafana team membership to match Github team membership."""
        grafana_teams = await grafana.list_teams(self.bot.http_session)
        embed = discord.Embed(
            title="Sync Stats",
            colour=discord.Colour.blue(),
        )
        for team in grafana_teams:
            logger.debug(f"Processing {team['name']}")
            try:
                figures = await self._sync_teams(team)
            except aiohttp.ClientResponseError as e:
                logger.error(e)
                if channel:
                    await channel.send(e)
                continue

            lines = [
                f"Missing: {figures.added.count}",
                f"Added: {figures.added.successfully_added}",
                f"Removed: {figures.removed}",
            ]
            embed.add_field(
                name=team["name"],
                value="\n".join(lines),
                inline=False,
            )

        if channel:
            await channel.send(embed=embed)

    @sync_github_grafana_teams.error
    async def on_task_error(self, error: Exception) -> None:
        """Ensure task errors are output."""
        logger.error(error)

    @commands.group(name="grafana_github", invoke_without_command=True)
    async def grafana_group(self, ctx: commands.Context) -> None:
        """Commands for working with grafana API."""
        await ctx.send_help(ctx.command)

    @grafana_group.command(name="sync")
    async def sync_teams(self, ctx: commands.Context) -> None:
        """Sync Grafana & Github teams now."""
        await self.sync_github_grafana_teams(ctx.channel)


async def setup(bot: KingArthur) -> None:
    """Add GrafanaGitHubTeamSync cog to bot."""
    if not all(
        (
            CONFIG.github_org,
            CONFIG.github_token,
            CONFIG.grafana_url,
            CONFIG.grafana_token,
        )
    ):
        logger.warning(
            "Not loading GrafanaGitHubTeamSync team as a required config entry is missing. See README"
        )
        return
    await bot.add_cog(GrafanaGitHubTeamSync(bot))
