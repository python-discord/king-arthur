"""Commands for managing the GitHub organisation and teams."""

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

    async def _fetch_common_info(
        self,
    ) -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str], set[str], set[str]]:
        """Fetch common data needed for both GitHub org and team synchronisation."""
        keycloak_identities = await all_github_identities()
        github_org_members = await list_organisation_member_identities()
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

        pending_invitations = await list_pending_org_invitations()
        failed_invitations = await list_failed_org_invitations()

        return (
            keycloak_identities,
            github_org_members,
            resolved_keycloak_logins_by_id,
            pending_invitations,
            failed_invitations,
        )

    async def _sync_github_members(
        self,
        report_thread: discord.Thread,
        common_info: tuple[
            dict[str, dict[str, str]], dict[str, str], dict[str, str], set[str], set[str]
        ],
    ) -> tuple[int, int, int]:
        """Dry-run GitHub organisation membership synchronisation with Keycloak."""
        (
            keycloak_identities,
            github_org_members,
            resolved_keycloak_logins_by_id,
            pending_invitations,
            failed_invitations,
        ) = common_info

        desired_by_user_id = {
            identity["user_id"].strip(): resolved_keycloak_logins_by_id[identity["user_id"].strip()]
            for identity in keycloak_identities.values()
            if identity.get("user_id")
            and identity["user_id"].strip() in resolved_keycloak_logins_by_id
        }
        github_by_user_id = dict(github_org_members)

        desired_by_user_id = {
            user_id: username
            for user_id, username in desired_by_user_id.items()
            if self._normalise_login(username) not in self._ignored_github_users_normalised()
        }
        github_by_user_id = {
            user_id: username
            for user_id, username in github_by_user_id.items()
            if self._normalise_login(username) not in self._ignored_github_users_normalised()
        }

        desired_user_ids = set(desired_by_user_id)
        github_user_ids = set(github_by_user_id)

        to_add_user_ids = desired_user_ids - github_user_ids
        to_remove_user_ids = github_user_ids - desired_user_ids
        kept_user_ids = desired_user_ids & github_user_ids

        pending_by_normalised = {
            self._normalise_login(username): username for username in pending_invitations
        }
        failed_by_normalised = {
            self._normalise_login(username): username for username in failed_invitations
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

        to_add = [desired_by_user_id[user_id] for user_id in sorted(actionable_to_add_user_ids)]
        to_remove = [github_by_user_id[user_id] for user_id in sorted(to_remove_user_ids)]
        to_keep = [
            github_by_user_id.get(user_id, desired_by_user_id[user_id])
            for user_id in sorted(kept_user_ids)
        ]
        to_skip_pending = [
            pending_by_normalised.get(
                self._normalise_login(desired_by_user_id[user_id]),
                desired_by_user_id[user_id],
            )
            for user_id in sorted(pending_to_add_user_ids)
        ]
        to_skip_failed = [
            failed_by_normalised.get(
                self._normalise_login(desired_by_user_id[user_id]),
                desired_by_user_id[user_id],
            )
            for user_id in sorted(failed_to_add_user_ids)
        ]

        add_lines = [f":green_circle: would add to org: `{username}`" for username in to_add]
        remove_lines = [
            f":red_circle: would remove from org: `{username}`" for username in to_remove
        ]
        keep_lines = [
            f":large_blue_diamond: would keep in org: `{username}`" for username in to_keep
        ]
        skip_pending_lines = [
            f":yellow_circle: would skip org invite (already pending): `{username}`"
            for username in to_skip_pending
        ]
        skip_failed_lines = [
            f":orange_circle: would skip org invite (failed invite exists): `{username}`"
            for username in to_skip_failed
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

        devops_channel = await self._get_devops_channel()
        if devops_channel is not None:
            for username in to_skip_failed:
                await devops_channel.send(
                    ":warning: GitHub org invite was not re-sent for "
                    f"`{username}` because a failed invitation record already exists."
                )

        added = len(actionable_to_add_user_ids)
        removed = len(to_remove_user_ids)
        kept = len(kept_user_ids)

        return added, removed, kept

    async def _sync_github_teams(
        self,
        report_thread: discord.Thread,
        common_info: tuple[
            dict[str, dict[str, str]], dict[str, str], dict[str, str], set[str], set[str]
        ],
    ) -> tuple[int, int, int]:
        """Dry-run GitHub team membership synchronisation with Keycloak."""
        keycloak_identities, github_org_members, resolved_keycloak_logins_by_id, _, _ = common_info
        ignored_normalised = self._ignored_github_users_normalised()

        desired_org_by_user_id = {
            identity["user_id"].strip(): resolved_keycloak_logins_by_id[identity["user_id"].strip()]
            for identity in keycloak_identities.values()
            if identity.get("user_id")
            and identity["user_id"].strip() in resolved_keycloak_logins_by_id
        }
        desired_org_by_user_id = {
            user_id: username
            for user_id, username in desired_org_by_user_id.items()
            if self._normalise_login(username) not in ignored_normalised
        }
        github_org_by_user_id = {
            user_id: username
            for user_id, username in github_org_members.items()
            if self._normalise_login(username) not in ignored_normalised
        }
        org_users_to_remove = set(github_org_by_user_id) - set(desired_org_by_user_id)
        org_users_to_remove_normalised = {
            self._normalise_login(github_org_by_user_id[user_id]) for user_id in org_users_to_remove
        }

        keycloak_to_github = {
            keycloak_username: resolved_keycloak_logins_by_id[identity["user_id"].strip()]
            for keycloak_username, identity in keycloak_identities.items()
            if identity.get("user_id")
            and identity["user_id"].strip() in github_org_members
            and self._normalise_login(resolved_keycloak_logins_by_id[identity["user_id"].strip()])
            not in ignored_normalised
        }

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

            to_add = [desired_by_normalised[username] for username in sorted(to_add_normalised)]
            to_remove = [
                current_by_normalised[username] for username in sorted(to_remove_normalised)
            ]
            to_keep = [
                current_by_normalised.get(username, desired_by_normalised[username])
                for username in sorted(kept_normalised)
            ]

            add_lines = [
                f":green_circle: would add to `{github_team_slug}`: `{username}`"
                for username in to_add
            ]
            remove_lines = [
                f":red_circle: would remove from `{github_team_slug}`: `{username}`"
                for username in to_remove
            ]
            keep_lines = [
                f":large_blue_diamond: would keep in `{github_team_slug}`: `{username}`"
                for username in to_keep
            ]

            if not add_lines and not remove_lines and not keep_lines:
                await self._send_report_lines(
                    report_thread,
                    [f":white_circle: **Team `{github_team_slug}`**: no membership changes needed"],
                )
            else:
                if not add_lines:
                    add_lines = [f":white_circle: no additions needed in `{github_team_slug}`"]
                if not remove_lines:
                    remove_lines = [f":white_circle: no removals needed in `{github_team_slug}`"]
                if not keep_lines:
                    keep_lines = [f":white_circle: no users would be kept in `{github_team_slug}`"]

                await self._send_report_lines(
                    report_thread,
                    [
                        f":busts_in_silhouette: **Team `{github_team_slug}` dry-run decisions**",
                        *add_lines,
                        *remove_lines,
                        *keep_lines,
                    ],
                )

            added += len(to_add_normalised)
            removed += len(to_remove_normalised)
            kept += len(kept_normalised)

        return added, removed, kept


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(GitHubManagement(bot))
