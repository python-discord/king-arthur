import aiohttp
import discord
from discord.ext import commands, tasks

from arthur.apis import grafana
from arthur.apis.directory import ldap
from arthur.bot import KingArthur
from arthur.config import CONFIG
from arthur.log import logger

from . import MissingMembers, SyncFigures

GRAFANA_TO_LDAP_NAME_MAPPING = {
    "devops": "devops",
    "admins": "administrators",
    "moderators": "moderators",
}


class GrafanaLDAPTeamSync(commands.Cog):
    """
    Update Grafana team membership to match LDAP team membership.

    Whilst the LDAP migration is ongoing, we re-map the LDAP group names to the Grafana teams,
    in future they will be unified.
    """

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.sync_ldap_grafana_teams.start()

    async def _add_missing_members(
        self,
        grafana_team_id: int,
        ldap_team_members: set[str],
        grafana_team_members: set[str],
        all_grafana_users: list[dict],
    ) -> MissingMembers:
        """
        Adds members to the Grafana team if they're in the LDAP team and not already present.

        Returns the number of missing members, and the number of members it could actually add.
        """
        missing_members = ldap_team_members - grafana_team_members
        added_members = 0
        for grafana_user in all_grafana_users:
            if grafana_user["login"] not in missing_members:
                continue
            if grafana_user.get("auth_module") != "ldap":
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
        ldap_team_members: set[str],
        grafana_team_members: set[str],
        all_grafana_users: list[dict],
    ) -> int:
        """
        Removes Grafana users from a team if they are not present in the LDAP team.

        Return how many were removed.
        """
        extra_members = grafana_team_members - ldap_team_members
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
        Ensure members in LDAP are present in Grafana teams.

        Return the number of members missing from the Grafana team, and the number of members added.
        """
        if team["name"] not in GRAFANA_TO_LDAP_NAME_MAPPING:
            return SyncFigures(added=MissingMembers(0, 0), removed=0)

        ldap_team_members = {
            member.uid
            for member in await ldap.get_group_members(GRAFANA_TO_LDAP_NAME_MAPPING[team["name"]])
        }
        grafana_team_members = {
            member["login"]
            for member in await grafana.list_team_members(team["id"], self.bot.http_session)
            if member.get("auth_module") == "ldap"
        }

        all_grafana_users = await grafana.get_all_users(self.bot.http_session)
        added_members = await self._add_missing_members(
            team["id"],
            ldap_team_members,
            grafana_team_members,
            all_grafana_users,
        )
        removed_members = await self._remove_extra_members(
            team["id"],
            ldap_team_members,
            grafana_team_members,
            all_grafana_users,
        )

        return SyncFigures(added=added_members, removed=removed_members)

    @tasks.loop(hours=12)
    async def sync_ldap_grafana_teams(self, channel: discord.TextChannel | None = None) -> None:
        """Update Grafana team membership to match LDAP team membership."""
        grafana_teams = await grafana.list_teams(self.bot.http_session)
        embed = discord.Embed(
            title="Sync Stats",
            colour=discord.Colour.blue(),
        )
        for team in grafana_teams:
            logger.debug(f"Processing {team["name"]}")
            try:
                figures = await self._sync_teams(team)
            except aiohttp.ClientResponseError as e:
                logger.opt(exception=e).error(f"Error whilst procesing Grafana team {team["name"]}")
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

    @sync_ldap_grafana_teams.error
    async def on_task_error(self, error: Exception) -> None:
        """Ensure task errors are output."""
        logger.error(error)

    @commands.group(name="grafana_ldap", invoke_without_command=True)
    async def grafana_group(self, ctx: commands.Context) -> None:
        """Commands for working with grafana API."""
        await ctx.send_help(ctx.command)

    @grafana_group.command(name="sync")
    async def sync_teams(self, ctx: commands.Context) -> None:
        """Sync Grafana & LDAP teams now."""
        await self.sync_ldap_grafana_teams(ctx.channel)


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    if ldap.BONSAI_AVAILABLE and CONFIG.enable_ldap:
        await bot.add_cog(GrafanaLDAPTeamSync(bot))
    else:
        logger.warning(
            "Not loading Grafana LDAP team sync as LDAP dependencies "
            "LDAP dependencies are not installed or LDAP is disabled,"
            " see README.md for more"
        )
