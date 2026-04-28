"""Commands for managing the GitHub organisation and teams."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks
from discord.ext.commands import Cog

from arthur.apis.directory import ldap
from arthur.apis.directory.keycloak import all_github_identities
from arthur.apis.github import (
    get_username_for_user_id,
    list_failed_org_invitations,
    list_organisation_member_identities,
    list_pending_org_invitations,
    list_team_members,
)
from arthur.constants import LDAP_ROLE_MAPPING
from arthur.log import logger

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


@dataclass(frozen=True)
class SyncCommonInfo:
    """Shared data fetched once and re-used by org and team sync planning."""

    keycloak_identities: dict[str, dict[str, str]]
    github_org_members_by_id: dict[str, str]
    resolved_logins_by_user_id: dict[str, str]
    pending_invitations: set[str]
    failed_invitations: set[str]


@dataclass(frozen=True)
class MembershipDiff:
    """Resolved dry-run membership actions for a single scope."""

    to_add: list[str]
    to_remove: list[str]
    to_keep: list[str]


@dataclass(frozen=True)
class OrgSyncPlan:
    """Dry-run decisions for organisation sync."""

    diff: MembershipDiff
    skipped_pending: list[str]
    skipped_failed: list[str]
    actionable_add_count: int
    remove_count: int
    keep_count: int


@dataclass(frozen=True)
class TeamSyncPlan:
    """Dry-run decisions for a single team sync."""

    team_slug: str
    diff: MembershipDiff


class GitHubManagement(Cog):
    """GitHub organisation membership synchronisation with LDAP."""

    MAX_REPORT_MESSAGE_LENGTH = 1900
    DRY_RUN_CHANNEL_ID = 675756741417369640
    DRY_RUN_THREAD_ID = 1265289413433364511
    IGNORED_GITHUB_USERS = ("pydis-bot",)

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @staticmethod
    def _normalise_login(username: str) -> str:
        """Return a case-insensitive key used for login comparisons."""
        return username.casefold()

    @classmethod
    def _ignored_github_users_normalised(cls) -> set[str]:
        """Return globally ignored GitHub logins as normalised comparison keys."""
        return {username.casefold() for username in cls.IGNORED_GITHUB_USERS}

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

            common_info = await self._fetch_common_info()
            added_org, removed_org, kept_org = await self._sync_github_members(
                report_thread,
                common_info,
            )
            added_team, removed_team, kept_team = await self._sync_github_teams(
                report_thread,
                common_info,
            )

            logger.info(
                "GitHub: Dry-run complete. "
                f"Org added={added_org}, org removed={removed_org}, org kept={kept_org}, "
                f"team added={added_team}, team removed={removed_team}, team kept={kept_team}."
            )

            await report_thread.send(
                ":white_check_mark: **GitHub membership dry-run complete**\n"
                f":office: Org decisions: +{added_org} / -{removed_org} / ={kept_org}\n"
                f":busts_in_silhouette: Team decisions: +{added_team} / -{removed_team} / ={kept_team}"
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

    async def _get_devops_channel(self) -> discord.TextChannel | None:
        """Resolve the devops text channel used for invitation state notifications."""
        channel = self.bot.get_channel(self.DRY_RUN_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            return channel

        fetched_channel = await self.bot.fetch_channel(self.DRY_RUN_CHANNEL_ID)
        if isinstance(fetched_channel, discord.TextChannel):
            return fetched_channel

        return None

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

    async def _fetch_common_info(self) -> SyncCommonInfo:
        """Fetch common data needed for both GitHub org and team synchronisation."""
        keycloak_identities = await all_github_identities()
        github_org_members = await list_organisation_member_identities()
        resolved_keycloak_logins_by_id = await self._resolve_logins_by_user_id(
            keycloak_identities,
            github_org_members,
        )
        pending_invitations = await list_pending_org_invitations()
        failed_invitations = await list_failed_org_invitations()

        return SyncCommonInfo(
            keycloak_identities=keycloak_identities,
            github_org_members_by_id=github_org_members,
            resolved_logins_by_user_id=resolved_keycloak_logins_by_id,
            pending_invitations=pending_invitations,
            failed_invitations=failed_invitations,
        )

    async def _resolve_logins_by_user_id(
        self,
        keycloak_identities: dict[str, dict[str, str]],
        github_org_members: dict[str, str],
    ) -> dict[str, str]:
        """Resolve the latest GitHub login for each Keycloak-linked GitHub account ID."""
        resolved_keycloak_logins_by_id = dict(github_org_members)
        unresolved_user_ids = {
            identity["user_id"].strip()
            for identity in keycloak_identities.values()
            if identity.get("user_id") and identity["user_id"].strip() not in github_org_members
        }

        for user_id in sorted(unresolved_user_ids):
            resolved_login = await get_username_for_user_id(user_id)
            if resolved_login:
                resolved_keycloak_logins_by_id[user_id] = resolved_login
                continue

            logger.warning(f"GitHub: Could not resolve login for GitHub user ID {user_id}.")

        return resolved_keycloak_logins_by_id

    def _build_org_identity_maps(
        self,
        common_info: SyncCommonInfo,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Build desired/current org user maps keyed by GitHub account ID."""
        ignored_normalised = self._ignored_github_users_normalised()
        desired_by_user_id = {
            identity["user_id"].strip(): common_info.resolved_logins_by_user_id[
                identity["user_id"].strip()
            ]
            for identity in common_info.keycloak_identities.values()
            if identity.get("user_id")
            and identity["user_id"].strip() in common_info.resolved_logins_by_user_id
        }
        github_by_user_id = dict(common_info.github_org_members_by_id)

        desired_by_user_id = {
            user_id: username
            for user_id, username in desired_by_user_id.items()
            if self._normalise_login(username) not in ignored_normalised
        }
        github_by_user_id = {
            user_id: username
            for user_id, username in github_by_user_id.items()
            if self._normalise_login(username) not in ignored_normalised
        }

        return desired_by_user_id, github_by_user_id

    def _build_org_sync_plan(self, common_info: SyncCommonInfo) -> OrgSyncPlan:
        """Construct all dry-run decisions for organisation sync."""
        desired_by_user_id, github_by_user_id = self._build_org_identity_maps(common_info)

        desired_user_ids = set(desired_by_user_id)
        github_user_ids = set(github_by_user_id)

        to_add_user_ids = desired_user_ids - github_user_ids
        to_remove_user_ids = github_user_ids - desired_user_ids
        kept_user_ids = desired_user_ids & github_user_ids

        pending_by_normalised = {
            self._normalise_login(username): username
            for username in common_info.pending_invitations
        }
        failed_by_normalised = {
            self._normalise_login(username): username
            for username in common_info.failed_invitations
        }

        pending_to_add_user_ids = {
            user_id
            for user_id in to_add_user_ids
            if self._normalise_login(desired_by_user_id[user_id]) in pending_by_normalised
        }
        failed_to_add_user_ids = {
            user_id
            for user_id in to_add_user_ids
            if self._normalise_login(desired_by_user_id[user_id]) in failed_by_normalised
        }
        actionable_to_add_user_ids = (
            to_add_user_ids - pending_to_add_user_ids - failed_to_add_user_ids
        )

        diff = MembershipDiff(
            to_add=[desired_by_user_id[user_id] for user_id in sorted(actionable_to_add_user_ids)],
            to_remove=[github_by_user_id[user_id] for user_id in sorted(to_remove_user_ids)],
            to_keep=[
                github_by_user_id.get(user_id, desired_by_user_id[user_id])
                for user_id in sorted(kept_user_ids)
            ],
        )
        skipped_pending = [
            pending_by_normalised.get(
                self._normalise_login(desired_by_user_id[user_id]),
                desired_by_user_id[user_id],
            )
            for user_id in sorted(pending_to_add_user_ids)
        ]
        skipped_failed = [
            failed_by_normalised.get(
                self._normalise_login(desired_by_user_id[user_id]),
                desired_by_user_id[user_id],
            )
            for user_id in sorted(failed_to_add_user_ids)
        ]

        return OrgSyncPlan(
            diff=diff,
            skipped_pending=skipped_pending,
            skipped_failed=skipped_failed,
            actionable_add_count=len(actionable_to_add_user_ids),
            remove_count=len(to_remove_user_ids),
            keep_count=len(kept_user_ids),
        )

    async def _report_org_sync_plan(
        self,
        report_thread: discord.Thread,
        plan: OrgSyncPlan,
    ) -> None:
        """Send dry-run organisation decisions to the configured report thread."""
        add_lines = [
            f":green_circle: would add to org: `{username}`" for username in plan.diff.to_add
        ]
        remove_lines = [
            f":red_circle: would remove from org: `{username}`"
            for username in plan.diff.to_remove
        ]
        keep_lines = [
            f":large_blue_diamond: would keep in org: `{username}`"
            for username in plan.diff.to_keep
        ]
        skip_pending_lines = [
            f":yellow_circle: would skip org invite (already pending): `{username}`"
            for username in plan.skipped_pending
        ]
        skip_failed_lines = [
            f":orange_circle: would skip org invite (failed invite exists): `{username}`"
            for username in plan.skipped_failed
        ]

        if not add_lines:
            add_lines = [":white_circle: no org additions needed"]
        if not remove_lines:
            remove_lines = [":white_circle: no org removals needed"]
        if not keep_lines:
            keep_lines = [":white_circle: no org members would be kept"]
        if not skip_pending_lines:
            skip_pending_lines = [":white_circle: no org invites skipped due to pending invites"]
        if not skip_failed_lines:
            skip_failed_lines = [":white_circle: no org invites skipped due to failed invites"]

        await self._send_report_lines(
            report_thread,
            [
                ":office: **Org dry-run decisions**",
                *add_lines,
                *remove_lines,
                *keep_lines,
                *skip_pending_lines,
                *skip_failed_lines,
                ":grey_question: globally ignored users (not affected): "
                + ", ".join(f"`{username}`" for username in sorted(self.IGNORED_GITHUB_USERS)),
            ],
        )

    async def _notify_failed_invites(self, skipped_failed: list[str]) -> None:
        """Send notifications for failed invitation re-send skips."""
        devops_channel = await self._get_devops_channel()
        if devops_channel is None:
            return

        for username in skipped_failed:
            await devops_channel.send(
                ":warning: GitHub org invite was not re-sent for "
                f"`{username}` because a failed invitation record already exists."
            )

    def _build_keycloak_to_github_map(
        self,
        common_info: SyncCommonInfo,
    ) -> dict[str, str]:
        """Map Keycloak username to current GitHub login for users currently in the org."""
        ignored_normalised = self._ignored_github_users_normalised()
        return {
            keycloak_username: common_info.resolved_logins_by_user_id[identity["user_id"].strip()]
            for keycloak_username, identity in common_info.keycloak_identities.items()
            if identity.get("user_id")
            and identity["user_id"].strip() in common_info.github_org_members_by_id
            and self._normalise_login(
                common_info.resolved_logins_by_user_id[identity["user_id"].strip()]
            )
            not in ignored_normalised
        }

    def _org_users_to_remove_normalised(self, common_info: SyncCommonInfo) -> set[str]:
        """Return normalised logins for users scheduled to be removed from the org."""
        desired_org_by_user_id, github_org_by_user_id = self._build_org_identity_maps(common_info)
        org_users_to_remove = set(github_org_by_user_id) - set(desired_org_by_user_id)
        return {
            self._normalise_login(github_org_by_user_id[user_id])
            for user_id in org_users_to_remove
        }

    def _build_team_sync_plan(
        self,
        team_slug: str,
        desired_team_members: list[str],
        current_team_members: list[str],
        org_users_to_remove_normalised: set[str],
    ) -> TeamSyncPlan:
        """Construct dry-run decisions for one team."""
        ignored_normalised = self._ignored_github_users_normalised()
        desired_by_normalised = {
            self._normalise_login(username): username for username in desired_team_members
        }
        current_by_normalised = {
            self._normalise_login(username): username for username in current_team_members
        }

        desired_by_normalised = {
            normalised: username
            for normalised, username in desired_by_normalised.items()
            if normalised not in ignored_normalised
        }
        current_by_normalised = {
            normalised: username
            for normalised, username in current_by_normalised.items()
            if normalised not in ignored_normalised
            and normalised not in org_users_to_remove_normalised
        }

        desired_normalised = set(desired_by_normalised)
        current_normalised = set(current_by_normalised)

        to_add_normalised = desired_normalised - current_normalised
        to_remove_normalised = current_normalised - desired_normalised
        kept_normalised = desired_normalised & current_normalised

        return TeamSyncPlan(
            team_slug=team_slug,
            diff=MembershipDiff(
                to_add=[desired_by_normalised[username] for username in sorted(to_add_normalised)],
                to_remove=[
                    current_by_normalised[username] for username in sorted(to_remove_normalised)
                ],
                to_keep=[
                    current_by_normalised.get(username, desired_by_normalised[username])
                    for username in sorted(kept_normalised)
                ],
            ),
        )

    async def _report_team_sync_plan(
        self,
        report_thread: discord.Thread,
        plan: TeamSyncPlan,
    ) -> None:
        """Send dry-run team decisions to the configured report thread."""
        add_lines = [
            f":green_circle: would add to `{plan.team_slug}`: `{username}`"
            for username in plan.diff.to_add
        ]
        remove_lines = [
            f":red_circle: would remove from `{plan.team_slug}`: `{username}`"
            for username in plan.diff.to_remove
        ]
        keep_lines = [
            f":large_blue_diamond: would keep in `{plan.team_slug}`: `{username}`"
            for username in plan.diff.to_keep
        ]

        if not add_lines and not remove_lines and not keep_lines:
            await self._send_report_lines(
                report_thread,
                [f":white_circle: **Team `{plan.team_slug}`**: no membership changes needed"],
            )
            return

        if not add_lines:
            add_lines = [f":white_circle: no additions needed in `{plan.team_slug}`"]
        if not remove_lines:
            remove_lines = [f":white_circle: no removals needed in `{plan.team_slug}`"]
        if not keep_lines:
            keep_lines = [f":white_circle: no users would be kept in `{plan.team_slug}`"]

        await self._send_report_lines(
            report_thread,
            [
                f":busts_in_silhouette: **Team `{plan.team_slug}` dry-run decisions**",
                *add_lines,
                *remove_lines,
                *keep_lines,
            ],
        )

    async def _sync_github_members(
        self,
        report_thread: discord.Thread,
        common_info: SyncCommonInfo,
    ) -> tuple[int, int, int]:
        """Dry-run GitHub organisation membership synchronisation with Keycloak."""
        plan = self._build_org_sync_plan(common_info)
        await self._report_org_sync_plan(report_thread, plan)
        await self._notify_failed_invites(plan.skipped_failed)

        return plan.actionable_add_count, plan.remove_count, plan.keep_count

    async def _sync_github_teams(
        self,
        report_thread: discord.Thread,
        common_info: SyncCommonInfo,
    ) -> tuple[int, int, int]:
        """Dry-run GitHub team membership synchronisation with Keycloak."""
        keycloak_to_github = self._build_keycloak_to_github_map(common_info)
        org_users_to_remove_normalised = self._org_users_to_remove_normalised(common_info)

        added = 0
        removed = 0
        kept = 0

        for ldap_group, mapping in LDAP_ROLE_MAPPING.items():
            github_team_slug = mapping["github_team_slug"]
            ldap_members = await ldap.get_group_members(ldap_group)
            desired_team_members = [
                keycloak_to_github[member.uid]
                for member in ldap_members
                if member.uid in keycloak_to_github
            ]

            current_team_members = await list_team_members(github_team_slug)

            plan = self._build_team_sync_plan(
                team_slug=github_team_slug,
                desired_team_members=desired_team_members,
                current_team_members=current_team_members,
                org_users_to_remove_normalised=org_users_to_remove_normalised,
            )
            await self._report_team_sync_plan(report_thread, plan)

            added += len(plan.diff.to_add)
            removed += len(plan.diff.to_remove)
            kept += len(plan.diff.to_keep)

        return added, removed, kept


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(GitHubManagement(bot))
