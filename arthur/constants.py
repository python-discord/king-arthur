"""Constants, primarily used for LDAP enrollment preferences."""

from typing import TypedDict


class LDAPGroupMapping(TypedDict):
    """Mapping of an LDAP group to its Discord role ID."""

    discord_role_id: int


# This is a mapping of LDAP groups to Discord role IDs. It is used to determine
# which users should be eligible for LDAP enrollment.
LDAP_ROLE_MAPPING: dict[str, LDAPGroupMapping] = {
    "helpers": {"discord_role_id": 267630620367257601},
    "devops": {"discord_role_id": 409416496733880320},
    "administrators": {"discord_role_id": 267628507062992896},
    "moderators": {"discord_role_id": 267629731250176001},
    "coredevs": {"discord_role_id": 587606783669829632},
    "events": {"discord_role_id": 787816728474288181},
    "directors": {"discord_role_id": 267627879762755584},
}

# Users are only checked for enrollment if they have this role. This doesn't grant them any
# permissions, it is for performance to avoid iterating roles for every other user in the guild.
HELPER_ROLE_ID = LDAP_ROLE_MAPPING["helpers"]["discord_role_id"]
