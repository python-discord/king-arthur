"""API utilities for fetching data from the LDAP directory."""

from dataclasses import dataclass

from bonsai import LDAPClient, LDAPDN, LDAPSearchScope

from arthur.config import CONFIG
from arthur.constants import LDAP_ROLE_MAPPING


@dataclass
class LDAPUser:
    """A user in the LDAP directory."""

    uid: str
    employee_number: str | None = None
    display_name: str | None = None
    groups: list[str] | None = None


def prepare_dn(dn: str) -> str:
    """Prepare a DN into a fully qualified DN."""
    return f"{dn},{CONFIG.ldap_base_dn}"


def get_cn(dn: str) -> str:
    """Parse a DN and return the cn (or first attribute) in it."""
    parsed = LDAPDN(dn)

    return parsed.rdns[0][0][1]


def create_client() -> LDAPClient:
    """Create an LDAP client with the configured settings."""
    client = LDAPClient(str(CONFIG.ldap_host), tls=True)

    client.set_credentials(
        "SIMPLE", CONFIG.ldap_bind_user, CONFIG.ldap_bind_password.get_secret_value()
    )
    client.set_ca_cert(CONFIG.ldap_certificate_location.as_posix())

    return client


async def find_users() -> list[LDAPUser]:
    """Find all users in the LDAP directory."""
    client = create_client()

    found_users = []

    async with client.connect(is_async=True) as conn:
        users = await conn.search(
            prepare_dn("cn=users,cn=accounts"),
            LDAPSearchScope.SUBTREE,
            "(mail=*@pydis.wtf)",
            ["uid", "employeeNumber", "displayName", "memberOf"],
        )

        for user in users:
            groups = user.get("memberOf", ())
            parsed_groups = []

            for group in groups:
                g_name = get_cn(group)
                if g_name in LDAP_ROLE_MAPPING:
                    parsed_groups.append(g_name)

            new_user = LDAPUser(
                uid=user["uid"][0],
                employee_number=user.get("employeeNumber", [None])[0],
                display_name=user["displayName"][0],
                groups=parsed_groups,
            )

            found_users.append(new_user)

    return found_users


async def find_by_discord_id(discord_id: int) -> LDAPUser | None:
    """Find a user in the LDAP directory by their Discord ID."""
    client = create_client()

    async with client.connect(is_async=True) as conn:
        users = await conn.search(
            prepare_dn("cn=users,cn=accounts"),
            LDAPSearchScope.SUBTREE,
            f"(employeeNumber={discord_id})",
            ["uid", "employeeNumber", "displayName", "memberOf"],
        )

        user = users[0] if users else None

        if not user:
            return None

        groups = user.get("memberOf", ())
        parsed_groups = []

        for group in groups:
            g_name = get_cn(group)
            if g_name in LDAP_ROLE_MAPPING:
                parsed_groups.append(g_name)

        user = LDAPUser(
            uid=user["uid"][0],
            employee_number=user.get("employeeNumber", [None])[0],
            display_name=user["displayName"][0],
            groups=parsed_groups,
        )

        return user


async def get_group_members(group_name: str) -> list[LDAPUser]:
    """
    Get all members of a group in the LDAP directory.

    Users returned by this do not have any fields filled except for their UID.
    """
    client = create_client()

    async with client.connect(is_async=True) as conn:
        group = await conn.search(
            prepare_dn(f"cn={group_name},cn=groups,cn=accounts"),
            LDAPSearchScope.SUBTREE,
            "(objectClass=groupOfNames)",
            ["member"],
        )

        if not group:
            return []

        members = group[0].get("member", [])

        found_users = [LDAPUser(uid=get_cn(member)) for member in members]

        return found_users
