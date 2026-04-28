"""Commands for managing the GitHub organisation and teams."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks
from discord.ext.commands import Cog

from arthur.apis.directory import ldap
from arthur.apis.directory.keycloak import all_github_identities
from arthur.apis.github import (
    GitHubError,
    add_member_to_team,
    add_org_member,
    get_username_for_user_id,
    list_failed_org_invitations,
    list_organisation_member_identities,
    list_pending_org_invitations,
    list_team_members,
    remove_member_from_team,
    remove_org_member,
)
from arthur.config import CONFIG
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
    """Resolved membership actions for a single scope."""

    to_add: list[str]
    to_remove: list[str]
    to_keep: list[str]


@dataclass(frozen=True)
class OrgSyncPlan:
    """Resolved decisions for organisation sync."""

    diff: MembershipDiff
    skipped_pending: list[str]
    skipped_failed: list[str]


@dataclass(frozen=True)
class TeamSyncPlan:
    """Resolved decisions for a single team sync."""

    team_slug: str
    diff: MembershipDiff


class GitHubManagement(Cog):
    """GitHub organisation membership synchronisation with LDAP."""

    MAX_REPORT_MESSAGE_LENGTH = 1900
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
        """Synchronise GitHub organisation and team membership with Keycloak/LDAP."""
        try:
            report_thread = await self._get_debug_thread()
            if report_thread is None:
                logger.error(
                    "GitHub: Sync debug thread not found "
                    f"(channel={CONFIG.devops_channel_id}, thread={CONFIG.github_sync_debug})."
                )
                return

            await report_thread.send(":mag: **GitHub membership sync started**")

            common_info = await self._fetch_common_info()
            org_added, org_removed = await self._sync_github_members(report_thread, common_info)
            team_added, team_removed = await self._sync_github_teams(report_thread, common_info)

            logger.info(
                "GitHub: Sync complete. "
                f"Org added={len(org_added)}, org removed={len(org_removed)}, "
                f"team added={len(team_added)}, team removed={len(team_removed)}."
            )

            await self._report_sync_result(
                report_thread,
                org_added,
                org_removed,
                team_added,
                team_removed,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception(f"GitHub: Error during sync: {e}", exc_info=True)
            report_thread = await self._get_debug_thread()
            if report_thread is not None:
                await report_thread.send(f":x: GitHub sync error: ```python\n{e}```")

    async def _report_sync_result(
        self,
        report_thread: discord.Thread,
        org_added: list[str],
        org_removed: list[str],
        team_added: list[str],
        team_removed: list[str],
    ) -> None:
        """Report applied membership changes after a sync run."""
        org_added_text = ", ".join(f"`{username}`" for username in org_added) or "none"
        org_removed_text = ", ".join(f"`{username}`" for username in org_removed) or "none"
        team_added_text = ", ".join(f"`{change}`" for change in team_added) or "none"
        team_removed_text = ", ".join(f"`{change}`" for change in team_removed) or "none"

        await report_thread.send(
            ":white_check_mark: **GitHub membership sync complete**\n"
            f":office: Org added: {org_added_text}\n"
            f":office: Org removed: {org_removed_text}\n"
            f":busts_in_silhouette: Team added: {team_added_text}\n"
            f":busts_in_silhouette: Team removed: {team_removed_text}"
        )

    async def _get_debug_thread(self) -> discord.Thread | None:
        """Resolve the configured sync debug thread, fetching it when not cached."""
        channel = self.bot.get_channel(CONFIG.devops_channel_id)
        if not isinstance(channel, discord.TextChannel):
            fetched_channel = await self.bot.fetch_channel(CONFIG.devops_channel_id)
            if not isinstance(fetched_channel, discord.TextChannel):
                return None
            channel = fetched_channel

        thread = self.bot.get_channel(CONFIG.github_sync_debug)
        if isinstance(thread, discord.Thread):
            return thread

        fetched_thread = await self.bot.fetch_channel(CONFIG.github_sync_debug)
        if not isinstance(fetched_thread, discord.Thread):
            return None

        if fetched_thread.parent_id != channel.id:
            logger.warning(
                "GitHub: Sync debug thread parent mismatch "
                f"(expected={channel.id}, actual={fetched_thread.parent_id})."
            )

        return fetched_thread

    async def _get_devops_channel(self) -> discord.TextChannel | None:
        """Resolve the devops text channel used for invitation state notifications."""
        channel = self.bot.get_channel(CONFIG.devops_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel

        fetched_channel = await self.bot.fetch_channel(CONFIG.devops_channel_id)
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
        """Construct all decisions for organisation sync."""
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
            self._normalise_login(username): username for username in common_info.failed_invitations
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
        )

    async def _report_org_sync_plan(
        self,
        report_thread: discord.Thread,
        plan: OrgSyncPlan,
    ) -> None:
        """Send planned organisation changes to the configured report thread."""
        add_lines = [f":green_circle: add to org: `{username}`" for username in plan.diff.to_add]
        remove_lines = [
            f":red_circle: remove from org: `{username}`" for username in plan.diff.to_remove
        ]

        if not add_lines:
            add_lines = [":white_circle: no org additions needed"]
        if not remove_lines:
            remove_lines = [":white_circle: no org removals needed"]

        await self._send_report_lines(
            report_thread,
            [
                ":office: **Org sync actions**",
                *add_lines,
                *remove_lines,
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

    async def _apply_org_additions(self, usernames: list[str]) -> list[str]:
        """Apply organisation additions and return successfully added logins."""
        added = []
        for username in usernames:
            try:
                await add_org_member(username)
                added.append(username)
            except GitHubError as e:
                logger.opt(exception=e).error(f"GitHub: Failed to add {username} to org")

        return added

    async def _apply_org_removals(self, usernames: list[str]) -> list[str]:
        """Apply organisation removals and return successfully removed logins."""
        removed = []
        for username in usernames:
            try:
                await remove_org_member(username)
                removed.append(username)
            except GitHubError as e:
                logger.opt(exception=e).error(f"GitHub: Failed to remove {username} from org")

        return removed

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
            self._normalise_login(github_org_by_user_id[user_id]) for user_id in org_users_to_remove
        }

    def _build_team_sync_plan(
        self,
        team_slug: str,
        desired_team_members: list[str],
        current_team_members: list[str],
        org_users_to_remove_normalised: set[str],
    ) -> TeamSyncPlan:
        """Construct decisions for one team."""
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
        """Send planned team changes to the configured report thread."""
        add_lines = [
            f":green_circle: add to `{plan.team_slug}`: `{username}`"
            for username in plan.diff.to_add
        ]
        remove_lines = [
            f":red_circle: remove from `{plan.team_slug}`: `{username}`"
            for username in plan.diff.to_remove
        ]

        if not add_lines and not remove_lines:
            await self._send_report_lines(
                report_thread,
                [f":white_circle: **Team `{plan.team_slug}`**: no membership changes needed"],
            )
            return

        if not add_lines:
            add_lines = [f":white_circle: no additions needed in `{plan.team_slug}`"]
        if not remove_lines:
            remove_lines = [f":white_circle: no removals needed in `{plan.team_slug}`"]

        await self._send_report_lines(
            report_thread,
            [
                f":busts_in_silhouette: **Team `{plan.team_slug}` sync actions**",
                *add_lines,
                *remove_lines,
            ],
        )

    async def _sync_github_members(
        self,
        report_thread: discord.Thread,
        common_info: SyncCommonInfo,
    ) -> tuple[list[str], list[str]]:
        """Synchronise GitHub organisation membership with Keycloak."""
        plan = self._build_org_sync_plan(common_info)
        await self._report_org_sync_plan(report_thread, plan)
        await self._notify_failed_invites(plan.skipped_failed)

        added = await self._apply_org_additions(plan.diff.to_add)
        removed = await self._apply_org_removals(plan.diff.to_remove)

        return added, removed

    async def _sync_github_teams(
        self,
        report_thread: discord.Thread,
        common_info: SyncCommonInfo,
    ) -> tuple[list[str], list[str]]:
        """Synchronise GitHub team membership with Keycloak."""
        keycloak_to_github = self._build_keycloak_to_github_map(common_info)
        org_users_to_remove_normalised = self._org_users_to_remove_normalised(common_info)

        added: list[str] = []
        removed: list[str] = []

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

            for username in plan.diff.to_add:
                try:
                    await add_member_to_team(username, github_team_slug)
                    added.append(f"{username} -> {github_team_slug}")
                except GitHubError as e:
                    logger.opt(exception=e).error(
                        f"GitHub: Failed to add {username} to team {github_team_slug}"
                    )

            for username in plan.diff.to_remove:
                try:
                    await remove_member_from_team(username, github_team_slug)
                    removed.append(f"{username} -> {github_team_slug}")
                except GitHubError as e:
                    logger.opt(exception=e).error(
                        f"GitHub: Failed to remove {username} from team {github_team_slug}"
                    )

        return added, removed


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(GitHubManagement(bot))
