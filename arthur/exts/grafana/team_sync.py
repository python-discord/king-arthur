import aiohttp
import discord
from discord.ext import commands, tasks

from arthur import logger
from arthur.apis import github, grafana
from arthur.bot import KingArthur


class GrafanaTeamSync(commands.Cog):
    """
    Update Grafana team membership to match Github team membership.

    Grafana team name must match Github team slug exactly.
    Use `gh api orgs/{org-name}/teams` to get a list of teams in an org
    """

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.sync_github_grafana_teams.start()

    async def _sync_teams(self, team: dict[str, str]) -> tuple[int, int]:
        """
        Ensure members in github are present in grafana teams.

        Return the number of members missing from teh grafana team, and the number of members added.
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

        missing_members = github_team_members - grafana_team_members
        grafana_users = await grafana.get_all_users(self.bot.http_session)
        added_members = set()
        for grafana_user in grafana_users:
            if grafana_user["login"] not in missing_members:
                continue
            await grafana.add_user_to_team(
                grafana_user["userId"],
                team["id"],
                self.bot.http_session,
            )
            added_members.add(grafana_user["login"])
        return len(missing_members), len(added_members)

    @tasks.loop(hours=12)
    async def sync_github_grafana_teams(self, channel: discord.TextChannel | None = None) -> None:
        """Update Grafana team membership to match Github team membership."""
        grafana_teams = await grafana.list_teams(self.bot.http_session)
        for team in grafana_teams:
            logger.debug(f"Processing {team['name']}")
            try:
                missing, added = await self._sync_teams(team)
            except aiohttp.ClientResponseError as e:
                logger.error(e)
                if channel:
                    await channel.send(e)
                continue

            if channel and missing:
                await channel.send(
                    f"Found {missing} users not in the {team['name']} grafana team, added {added} of them."
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
