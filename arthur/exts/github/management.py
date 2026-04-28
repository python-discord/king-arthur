"""Commands for managing the GitHub organisation and teams."""

from typing import TYPE_CHECKING

import discord
from discord.ext import tasks
from discord.ext.commands import Cog

from arthur.apis.directory import ldap
from arthur.apis.directory.keycloak import all_github_identities
from arthur.apis.github import (
    list_organisation_members,
    list_team_members,
)
from arthur.constants import LDAP_ROLE_MAPPING
from arthur.log import logger

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class GitHubManagement(Cog):
    """GitHub organisation membership synchronisation with LDAP."""

    MAX_REPORT_MESSAGE_LENGTH = 1900
    DRY_RUN_CHANNEL_ID = 675756741417369640
    DRY_RUN_THREAD_ID = 1265289413433364511

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @staticmethod
    def _normalise_login(username: str) -> str:
        """Return a case-insensitive key used for login comparisons."""
        return username.casefold()

    @tasks.loop(minutes=10)
    async def sync_github_org(self) -> None:
        """
        Synchronise GitHub organisation membership with LDAP.

        This consists of two components, a synchronisation of GitHub org membership and then a separate
        sync of GitHub team membership.

        The organisation sync works as follows:
        1. Fetch all users from Keycloak and their GitHub IDs.
        2. Fetch all GitHub members of the organisation.
        3. Compare the two lists and determine which users need to be added or removed from the organisation.

        The team sync works as follows:
        1. For each LDAP group, fetch the corresponding GitHub team.
        2. For each team, fetch the current members of the team.
        3. For each team, determine which users need to be added or removed from the team based on their LDAP group membership.
        """
        try:
            report_thread = await self._get_dry_run_thread()
            if report_thread is None:
                logger.error(
                    "GitHub: Dry-run thread not found "
                    f"(channel={self.DRY_RUN_CHANNEL_ID}, thread={self.DRY_RUN_THREAD_ID})."
                )
                return

            await report_thread.send(
                ":mag: **GitHub membership dry-run started**\n"
                "No changes will be applied. This is a report of what *would* happen."
            )

            added_org, removed_org = await self._sync_github_members(report_thread)
            added_team, removed_team = await self._sync_github_teams(report_thread)

            logger.info(
                "GitHub: Dry-run complete. "
                f"Org added={added_org}, org removed={removed_org}, "
                f"team added={added_team}, team removed={removed_team}."
            )

            await report_thread.send(
                ":white_check_mark: **GitHub membership dry-run complete**\n"
                f":office: Org changes: +{added_org} / -{removed_org}\n"
                f":busts_in_silhouette: Team changes: +{added_team} / -{removed_team}"
            )
        except Exception as e:  # noqa: BLE001
            logger.exception(f"GitHub: Error during sync: {e}", exc_info=True)
            report_thread = await self._get_dry_run_thread()
            if report_thread is not None:
                await report_thread.send(f":x: GitHub dry-run error: ```python\n{e}```")

    async def _get_dry_run_thread(self) -> discord.Thread | None:
        """Resolve the configured dry-run thread, fetching it when not cached."""
        channel = self.bot.get_channel(self.DRY_RUN_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            fetched_channel = await self.bot.fetch_channel(self.DRY_RUN_CHANNEL_ID)
            if not isinstance(fetched_channel, discord.TextChannel):
                return None
            channel = fetched_channel

        thread = self.bot.get_channel(self.DRY_RUN_THREAD_ID)
        if isinstance(thread, discord.Thread):
            return thread

        fetched_thread = await self.bot.fetch_channel(self.DRY_RUN_THREAD_ID)
        if not isinstance(fetched_thread, discord.Thread):
            return None

        if fetched_thread.parent_id != channel.id:
            logger.warning(
                "GitHub: Dry-run thread parent mismatch "
                f"(expected={channel.id}, actual={fetched_thread.parent_id})."
            )

        return fetched_thread

    async def _send_report_lines(self, report_thread: discord.Thread, lines: list[str]) -> None:
        """Send report lines in chunks that fit Discord's message length limit."""
        message = ""
        for line in lines:
            next_message = f"{message}\n{line}" if message else line
            if len(next_message) > self.MAX_REPORT_MESSAGE_LENGTH:
                await report_thread.send(message)
                message = line
                continue
            message = next_message

        if message:
            await report_thread.send(message)

    async def cog_load(self) -> None:
        """Start the GitHub synchronisation task."""
        self.sync_github_org.start()

    async def cog_unload(self) -> None:
        """Stop the GitHub synchronisation task."""
        self.sync_github_org.cancel()

    async def _fetch_common_info(self) -> tuple[dict[str, dict[str, str]], set[str]]:
        """Fetch common data needed for both GitHub org and team synchronisation."""
        keycloak_identities = await all_github_identities()
        github_org_members = set(await list_organisation_members())

        return keycloak_identities, github_org_members

    async def _sync_github_members(self, report_thread: discord.Thread) -> tuple[int, int]:
        """Dry-run GitHub organisation membership synchronisation with Keycloak."""
        keycloak_identities, github_org_members = await self._fetch_common_info()

        desired_org_members = [
            identity["user_name"].strip()
            for identity in keycloak_identities.values()
            if identity.get("user_name")
        ]

        desired_by_normalised = {
            self._normalise_login(username): username for username in desired_org_members
        }
        github_by_normalised = {
            self._normalise_login(username): username for username in github_org_members
        }

        desired_normalised = set(desired_by_normalised)
        github_normalised = set(github_by_normalised)

        to_add_normalised = desired_normalised - github_normalised
        to_remove_normalised = github_normalised - desired_normalised
        kept_normalised = desired_normalised & github_normalised

        to_add = [desired_by_normalised[username] for username in sorted(to_add_normalised)]
        to_remove = [github_by_normalised[username] for username in sorted(to_remove_normalised)]
        to_keep = [
            github_by_normalised.get(username, desired_by_normalised[username])
            for username in sorted(kept_normalised)
        ]

        add_lines = [f":green_circle: would add to org: `{username}`" for username in to_add]
        remove_lines = [
            f":red_circle: would remove from org: `{username}`" for username in to_remove
        ]
        keep_lines = [f":large_blue_circle: would keep in org: `{username}`" for username in to_keep]

        if not add_lines:
            add_lines = [":white_circle: no org additions needed"]
        if not remove_lines:
            remove_lines = [":white_circle: no org removals needed"]
        if not keep_lines:
            keep_lines = [":white_circle: no org members would be kept"]

        await self._send_report_lines(
            report_thread,
            [":office: **Org dry-run decisions**", *add_lines, *remove_lines, *keep_lines],
        )

        added = len(to_add_normalised)
        removed = len(to_remove_normalised)

        return added, removed

    async def _sync_github_teams(self, report_thread: discord.Thread) -> tuple[int, int]:
        """Dry-run GitHub team membership synchronisation with Keycloak."""
        keycloak_identities, _ = await self._fetch_common_info()
        keycloak_to_github = {
            keycloak_username: identity["user_name"]
            for keycloak_username, identity in keycloak_identities.items()
            if identity.get("user_name")
        }

        added = 0
        removed = 0

        for ldap_group, mapping in LDAP_ROLE_MAPPING.items():
            github_team_slug = mapping["github_team_slug"]
            ldap_members = await ldap.get_group_members(ldap_group)
            desired_team_members = [
                keycloak_to_github[member.uid]
                for member in ldap_members
                if member.uid in keycloak_to_github
            ]

            current_team_members = await list_team_members(github_team_slug)

            desired_by_normalised = {
                self._normalise_login(username): username for username in desired_team_members
            }
            current_by_normalised = {
                self._normalise_login(username): username for username in current_team_members
            }

            desired_normalised = set(desired_by_normalised)
            current_normalised = set(current_by_normalised)

            to_add_normalised = desired_normalised - current_normalised
            to_remove_normalised = current_normalised - desired_normalised

            to_add = [desired_by_normalised[username] for username in sorted(to_add_normalised)]
            to_remove = [current_by_normalised[username] for username in sorted(to_remove_normalised)]

            add_lines = [
                f":green_circle: would add to `{github_team_slug}`: `{username}`"
                for username in to_add
            ]
            remove_lines = [
                f":red_circle: would remove from `{github_team_slug}`: `{username}`"
                for username in to_remove
            ]

            if not add_lines and not remove_lines:
                await self._send_report_lines(
                    report_thread,
                    [f":white_circle: **Team `{github_team_slug}`**: no membership changes needed"],
                )
            else:
                await self._send_report_lines(
                    report_thread,
                    [
                        f":busts_in_silhouette: **Team `{github_team_slug}` dry-run decisions**",
                        *add_lines,
                        *remove_lines,
                    ],
                )

            added += len(to_add_normalised)
            removed += len(to_remove_normalised)

        return added, removed


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(GitHubManagement(bot))
