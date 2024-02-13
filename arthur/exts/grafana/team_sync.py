from dataclasses import dataclass

import aiohttp
import discord
from discord.ext import commands, tasks

from arthur import logger
from arthur.apis import github, grafana
from arthur.bot import KingArthur


@dataclass(frozen=True)
class MissingMembers:
    """Number of members that were missing from the Grafana team, and how many could be added."""

    count: int
    successfully_added: int


@dataclass(frozen=True)
class SyncFigures:
    """Figures related to a single sync members task run."""

    added: MissingMembers
    removed: int


class GrafanaTeamSync(commands.Cog):
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
            await grafana.add_user_to_team(
                grafana_user["userId"],
                grafana_team_id,
                self.bot.http_session,
            )
            added_members += 1
        return MissingMembers(count=len(missing_members), successfully_added=added_members)

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
        removed_members = 0  # TODO Actually remove members who shouldn't be present.

        return SyncFigures(added=added_members, removed=removed_members)

    @tasks.loop(hours=12)
    async def sync_github_grafana_teams(self, channel: discord.TextChannel | None = None) -> None:
        """Update Grafana team membership to match Github team membership."""
        grafana_teams = await grafana.list_teams(self.bot.http_session)
        for team in grafana_teams:
            logger.debug(f"Processing {team['name']}")
            try:
                figures = await self._sync_teams(team)
            except aiohttp.ClientResponseError as e:
                logger.error(e)
                if channel:
                    await channel.send(e)
                continue

            if channel:
                await channel.send(
                    f"Found {figures.added.count} users not in the {team['name']} Grafana team, added {figures.added.successfully_added} of them. "
                    f"{figures.removed} members were found in the Grafana team who shouldn't be, and were removed."
                )

    @sync_github_grafana_teams.error
    async def on_task_error(self, error: Exception) -> None:
        """Ensure task errors are output."""
        logger.error(error)

    @commands.group(name="grafana", aliases=("graf",), invoke_without_command=True)
    async def grafana_group(self, ctx: commands.Context) -> None:
        """Commands for working with grafana API."""
        await ctx.send_help(ctx.command)

    @grafana_group.command(name="sync")
    async def sync_teams(self, ctx: commands.Context) -> None:
        """Sync Grafana & Github teams now."""
        await self.sync_github_grafana_teams(ctx.channel)


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(GrafanaTeamSync(bot))
