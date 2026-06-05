"""The LDAP cog is used to interact with our directory services, FreeIPA & Keycloak."""

import secrets
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import discord
from discord import ui
from discord.ext import commands, tasks

from arthur.apis.directory import freeipa, keycloak, ldap
from arthur.config import CONFIG
from arthur.constants import HELPER_ROLE_ID, LDAP_ROLE_MAPPING
from arthur.log import logger

if TYPE_CHECKING:
    from datetime import datetime

    from arthur.bot import KingArthurTheTerrible

PASSWORD_RESET_LENGTH = 16

MAX_MESSAGE_LENGTH = 2000

NOTIFICATIONS_ENABLED = True

BOOTSTRAP_CHANNEL_TOPIC = """
This channel is used for Python Discord LDAP enrollment. If you have been added to the LDAP directory, you will receive a message here with instructions on how to create your login credentials.

If you have any questions or need help, feel free to ask in the <#{devops_channel_id}> channel.

You can login to your account at <https://id.pydis.wtf/realms/pydis/account>.
"""

BOOTSTRAP_MESSAGE = """
# Python Discord LDAP
Hello! :wave:

You have been added to the Python Discord LDAP directory. You can now log in to Python Discord managed services using a `@pydis.wtf` account.

**Please press the button below to generate your login credentials.**

You will be prompted to change your password on first login. You will then be prompted to optionally update your name and forwarding email address.

If you have any questions or need help, feel free to ask in the <#{devops_channel_id}> channel.

## GitHub Membership

Once you have created your account, you can link your GitHub account [here](https://id.pydis.wtf/realms/pydis/account/account-security/linked-accounts) to be added to the Python Discord GitHub organization.

This is required to access private repositories and take part in repository maintenance, as well as access the organisation repository that contains discussions.

## Why `pydis.wtf`?

`pydis.wtf` is our internal tooling and systems domain, which is the primary address for our managed services.

Your primary alias is `username@pydis.wtf`, but you will also receive mail to `username@pydis.com` and `username@pythondiscord.com`.

Please note, all addresses are solely forwarding addresses to your configured mailbox (e.g. GMail, Outlook).

These addresses are by design not public or intended for public usage, and should be used only for Python Discord managed services.

## Important Information

- Your username will be set to your Discord account name. Please let DevOps know if you would prefer something else.
- Once you have logged into the account console, you can update your forwarding address.

## Supported Services

**Note:** most of the below services are only accessible to certain groups, so you may not have access to all of them depending on your roles.

- [Grafana](https://grafana.pydis.wtf/)
- [Metabase](https://metabase.pydis.wtf/)
- [PyDis ID Self-Service](<https://id.pydis.wtf/>)
- [ModMail](https://modmail.pydis.wtf/)
- Anti-Spam Message Deletions
"""

CREDENTIALS_SECTION = """
## {title}

To get started, you will need to login [here](<https://id.pydis.wtf/realms/pydis/account>   ) using the following credentials:

- **Username:** `{username}@pydis.wtf`
- **Password:** ||`{password}`||

You will be prompted to reset your password after logging in.
"""

ELIGIBLE_MESSAGE = """
Hi {mention}! You have roles that make you eligible for a new LDAP account. Please read the message above to get started!
"""


class LDAPSyncAction(StrEnum):
    """Represents an action that will be performed against the LDAP directory."""

    ADD = "add"
    REMOVE = "remove"
    KEEP = "keep"
    CHANGE = "change"
    NO_ACTION = "no_action"


@dataclass
class DiffedUser:
    """Represents a user with their Discord and LDAP records, as well as if modification is required."""

    discord_user: discord.Member
    ldap_user: ldap.LDAPUser | None
    groups: list[str]
    action: LDAPSyncAction


class BootstrapType(StrEnum):
    """Represents the type of bootstrap operation."""

    CREATION = "creation"
    RESET = "reset"


class BootstrapView(ui.View):
    """View for the LDAP bootstrap command."""

    def __init__(self, cog: LDAP) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(
        label="Create or Reset Login", style=discord.ButtonStyle.primary, custom_id="generate_creds"
    )
    async def generate_creds(self, interaction: discord.Interaction, _button: ui.Button) -> None:
        """Generate credentials for the user."""
        user = interaction.user

        if HELPER_ROLE_ID not in [role.id for role in user.roles]:
            await interaction.response.send_message(
                "You are not eligible for LDAP enrollment.", ephemeral=True
            )
            return

        bootstrap_type, password, uid = await self.cog.bootstrap(user)

        if bootstrap_type == BootstrapType.CREATION:
            title = "Account Creation"
            logger.info(f"Created account for {user}")
        else:
            title = "Password Reset"
            logger.info(f"Reset password for {user} with LDAP user ID: {uid}")

        content = CREDENTIALS_SECTION.format(
            title=title, username=uid or user.name, password=password
        )

        await interaction.response.send_message(content, ephemeral=True)


class LDAP(commands.Cog):
    """Commands for working with the LDAP Directory."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot
        self._notified_user_ids: set[int] = set()
        self._last_history_scan: datetime | None = None
        self.sync_users.start()

    async def cog_unload(self) -> None:
        """Cancel background tasks on unload."""
        self.sync_users.cancel()

    @tasks.loop(minutes=10)
    async def sync_users(self) -> None:
        """Sync users with the LDAP directory."""
        try:
            logger.info("Syncing users with the LDAP directory.")

            diff, missing_emp, counts, ldap_users = await self.get_user_diff()

            add_users = counts[LDAPSyncAction.ADD]
            remove_users = counts[LDAPSyncAction.REMOVE]
            keep_users = counts[LDAPSyncAction.KEEP]
            change_users = counts[LDAPSyncAction.CHANGE]
            no_action_users = counts[LDAPSyncAction.NO_ACTION]

            logger.info(
                f"LDAP: {add_users} missing users, removing {remove_users} users, "
                f"keeping {keep_users} users, changing {change_users} users and no action for {no_action_users} users."
            )

            if len(missing_emp) > 0:
                logger.error(
                    "LDAP: Some users are missing an employee number. This may lead to duplicated users being created."
                )

                await self.bot.get_channel(CONFIG.devops_channel_id).send(
                    ":x: LDAP Sync: Some users are missing an employee number. This may lead to duplicate users, please rectify."
                )

            now = discord.utils.utcnow()
            channel = self.bot.get_channel(CONFIG.ldap_bootstrap_channel_id)
            history = (
                channel.history(after=self._last_history_scan, oldest_first=True)
                if self._last_history_scan is not None
                else channel.history(limit=None, oldest_first=True)
            )
            async for message in history:
                if (
                    "Python Discord LDAP enrollment" in message.content
                    or len(message.mentions) == 0
                    or message.author != self.bot.user
                ):
                    continue

                self._notified_user_ids.add(message.mentions[0].id)

            self._last_history_scan = now

            handled = set()

            for user in diff:
                await self._process_user(user, self._notified_user_ids)
                handled.add(
                    user.ldap_user.employee_number if user.ldap_user else str(user.discord_user.id)
                )

            await self._handle_left_users(handled, ldap_users)

            logger.info("LDAP: Sync complete.")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"LDAP: Error during sync: {e}", exc_info=True)
            await self.bot.get_channel(CONFIG.devops_channel_id).send(
                f":x: LDAP Sync Error: ```python\n{e}```"
            )

    async def _handle_left_users(self, handled: list[int], ldap_users: list[ldap.LDAPUser]) -> None:
        """Handle users that have left the guild and so were not processed."""
        for user in ldap_users:
            if user.employee_number is None or user.employee_number in handled:
                continue

            if user.locked:
                logger.info(f"LDAP: User {user.uid} is locked, skipping.")
                continue

            logger.info(f"LDAP: Deactivating user {user.uid} as they are no longer in the guild.")
            freeipa.deactivate_user(user.uid)

    async def _process_user(self, user: DiffedUser, notified_user_ids: set[int]) -> None:
        if user.action == LDAPSyncAction.ADD:
            if user.discord_user.id in notified_user_ids:
                return

            if NOTIFICATIONS_ENABLED:
                await self.bot.get_channel(CONFIG.ldap_bootstrap_channel_id).send(
                    ELIGIBLE_MESSAGE.format(mention=user.discord_user.mention)
                )
        if user.action == LDAPSyncAction.KEEP:
            if user.ldap_user and user.ldap_user.locked:
                freeipa.activate_user(user.ldap_user.uid)
        if user.action == LDAPSyncAction.REMOVE:
            if user.ldap_user and not user.ldap_user.locked:
                freeipa.deactivate_user(user.ldap_user.uid)
        elif user.action == LDAPSyncAction.CHANGE:
            freeipa.set_user_groups(user.ldap_user.uid, user.groups)

    async def cleanup_bootstrap(self, user: discord.Member) -> None:
        """Clear up the bootstrap message for a user."""
        channel = self.bot.get_channel(CONFIG.ldap_bootstrap_channel_id)

        async for message in channel.history(limit=None, oldest_first=True):
            if message.author == self.bot.user and user.mention in message.content:
                await message.delete()
                break

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Handle member updates."""
        if before.roles == after.roles:
            return

        before_roles = {role.id for role in before.roles}
        after_roles = {role.id for role in after.roles}

        if HELPER_ROLE_ID in before_roles or HELPER_ROLE_ID in after_roles:
            await self.sync_users()

    async def bootstrap(self, user: discord.Member) -> tuple[BootstrapType, str, str | None]:
        """Bootstrap a user into the LDAP directory, either creating or resetting the password."""
        if ldap_user := await ldap.find_by_discord_id(user.id):
            password = secrets.token_urlsafe(20)

            await keycloak.force_password_reset(ldap_user.uid, password)

            return BootstrapType.RESET, password, ldap_user.uid

        generated_pw = freeipa.create_user(
            user.name,
            user.display_name,
            await self._user_groups(user),
            user.id,
        )

        await self.cleanup_bootstrap(user)

        return BootstrapType.CREATION, generated_pw, None

    async def cog_load(self) -> None:  # noqa: C901, PLR0912
        """Verify the bootstrap channel is setup as intended."""
        self.bot.add_view(BootstrapView(self))
        bootstrap_message = BOOTSTRAP_MESSAGE.format(devops_channel_id=CONFIG.devops_channel_id)

        channel = self.bot.get_channel(CONFIG.ldap_bootstrap_channel_id)

        logger.info("LDAP: Checking bootstrap channel.")

        if not channel:
            logger.error("LDAP: Bootstrap channel not found.")
            return

        await channel.edit(
            topic=BOOTSTRAP_CHANNEL_TOPIC.format(devops_channel_id=CONFIG.devops_channel_id)
        )

        found_message = None
        other_messages = []

        async for message in channel.history(limit=None, oldest_first=True):
            if message.author == self.bot.user and "Python Discord LDAP" in message.content:
                found_message = message

            if message.author == self.bot.user and len(message.mentions) > 0:
                target_user = message.mentions[0]

                if await ldap.find_by_discord_id(target_user.id):
                    other_messages.append(message)

        for message in other_messages:
            await message.delete()

        if found_message:
            logger.info("LDAP: Found bootstrap message.")
            if found_message.content != bootstrap_message:
                await found_message.edit(content=bootstrap_message, view=BootstrapView(self))
        else:
            logger.info("LDAP: Creating bootstrap message.")
            await channel.send(bootstrap_message, view=BootstrapView(self))

        # Validate all enrolled roles can see the channel
        for mapping in LDAP_ROLE_MAPPING.values():
            role = channel.guild.get_role(mapping["discord_role_id"])

            if not role:
                continue

            try:
                if role.id == CONFIG.devops_role:
                    await channel.set_permissions(
                        role,
                        read_messages=True,
                        send_messages=True,
                        manage_channels=True,
                        manage_messages=True,
                        manage_permissions=True,
                    )
                else:
                    await channel.set_permissions(role, read_messages=True, send_messages=False)
            except discord.Forbidden:
                logger.error(f"Could not set permissions for role: {role}")

    @commands.group(name="directory", invoke_without_command=True, aliases=["ldap"])
    async def ldap_group(self, ctx: commands.Context) -> None:
        """Commands for working with the Python Discord directory."""
        await ctx.send_help(ctx.command)

    async def _user_groups(self, user: discord.Member) -> list[str]:
        """Return the groups a user is enrolled in."""
        groups = []
        for role, mapping in LDAP_ROLE_MAPPING.items():
            if mapping["discord_role_id"] not in [r.id for r in user.roles]:
                continue
            if role == "devops" and not await self.bot.is_owner(user):
                continue
            groups.append(role)
        return groups

    async def get_user_diff(
        self,
    ) -> tuple[list[DiffedUser], list[ldap.LDAPUser], Counter[LDAPSyncAction], list[ldap.LDAPUser]]:
        """Calculate and return the diff of users against LDAP from the guild."""
        guild = self.bot.get_guild(CONFIG.guild_id)
        users = await ldap.find_users()
        ldap_discord_id_map = {user.employee_number: user for user in users}

        enrolled_roles = {mapping["discord_role_id"] for mapping in LDAP_ROLE_MAPPING.values()}

        base_role = guild.get_role(HELPER_ROLE_ID)

        diff = []
        missing_emp = [user for user in users if user.employee_number is None]

        for user in guild.members:
            if user.bot:
                continue

            if base_role not in user.roles:
                if user.id in ldap_discord_id_map:
                    action = (
                        LDAPSyncAction.NO_ACTION
                        if ldap_discord_id_map[user.id].locked
                        else LDAPSyncAction.REMOVE
                    )
                    diff.append(DiffedUser(user, ldap_discord_id_map[user.id], [], action))
                continue

            user_role_ids = {r.id for r in user.roles}

            if enrolled_roles & user_role_ids:
                roles = await self._user_groups(user)
                if user.id in ldap_discord_id_map:
                    diff.append(
                        DiffedUser(user, ldap_discord_id_map[user.id], roles, LDAPSyncAction.KEEP)
                    )
                    if set(roles) != set(ldap_discord_id_map[user.id].groups):
                        diff[-1].action = LDAPSyncAction.CHANGE
                else:
                    diff.append(DiffedUser(user, None, roles, LDAPSyncAction.ADD))
            elif user.id in ldap_discord_id_map:
                action = (
                    LDAPSyncAction.NO_ACTION
                    if ldap_discord_id_map[user.id].locked
                    else LDAPSyncAction.REMOVE
                )
                diff.append(DiffedUser(user, ldap_discord_id_map[user.id], [], action))

        counter = Counter([user.action for user in diff])

        return diff, missing_emp, counter, users

    @staticmethod
    def _format_user(discord_user: discord.Member, ldap_user: ldap.LDAPUser | None) -> str:
        """Format the user for display."""
        if not ldap_user or ldap_user.uid == discord_user.name:
            return discord_user.name

        return f"{discord_user.name} (LDAP: {ldap_user.uid})"

    @ldap_group.command(name="sync")
    async def sync(self, ctx: commands.Context) -> None:
        """List users found in the LDAP directory."""
        diff, missing_emp, counts, _ = await self.get_user_diff()

        add_users = counts[LDAPSyncAction.ADD]
        remove_users = counts[LDAPSyncAction.REMOVE]
        keep_users = counts[LDAPSyncAction.KEEP]
        change_users = counts[LDAPSyncAction.CHANGE]
        no_action_users = counts[LDAPSyncAction.NO_ACTION]

        diff_message = "# LDAP Sync Overview\n"

        diff_message += f"**Adding Users:** {add_users}\n"
        diff_message += f"**Removing Users:** {remove_users}\n"
        diff_message += f"**Keeping Users:** {keep_users}\n"
        diff_message += f"**Changing Users:** {change_users}\n"
        diff_message += f"**No Action Required:** {no_action_users}\n\n"

        diff_message += "```diff\n"

        diff_sorted = sorted(diff, key=lambda user: (user.action, user.discord_user.name))

        prefixes = {
            LDAPSyncAction.ADD: "+",
            LDAPSyncAction.REMOVE: "-",
            LDAPSyncAction.KEEP: " ",
            LDAPSyncAction.CHANGE: "~",
            LDAPSyncAction.NO_ACTION: "#",
        }

        messages = [diff_message]

        for user in diff_sorted:
            prefix = prefixes[user.action]

            messages[-1] += f"{prefix}  {self._format_user(user.discord_user, user.ldap_user)}"
            messages[-1] += f" ({', '.join(user.groups)})\n"

            if len(messages[-1]) > MAX_MESSAGE_LENGTH - 100:
                messages[-1] += "```"
                messages.append("```diff\n")

        messages[-1] += "```"

        if len(missing_emp) > 0:
            messages[-1] += (
                ":warning: **Warning: Some LDAP users are missing an employee number. "
                "This may lead to duplicated users being created.**\n\n"
            )
            messages[-1] += "Users missing employee numbers:\n"
            messages[-1] += "\n".join(f"- `{user.uid}`" for user in missing_emp)

        for message in messages:
            await ctx.send(message)


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add the extension to the bot."""
    if not all((ldap.BONSAI_AVAILABLE, freeipa.BONSAI_AVAILABLE, CONFIG.enable_ldap)):
        logger.warning(
            "Not loading LDAP sync utilities as LDAP dependencies are not available "
            "or LDAP is disabled by config, see README.md for more."
        )
        return
    if not all(
        (
            CONFIG.ldap_host,
            CONFIG.ldap_bind_password,
            CONFIG.ldap_certificate_location,
            CONFIG.keycloak_address,
            CONFIG.keycloak_password,
        )
    ):
        logger.warning(
            "Not loading LDAP sync utilities as one or more LDAP environment variables"
            "are not set, see README.md for more."
        )
        return

    await bot.add_cog(LDAP(bot))
