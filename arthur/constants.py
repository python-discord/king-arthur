"""Constants, primarily used for LDAP enrollment preferences."""

from typing import TypedDict


class LDAPGroupMapping(TypedDict):
    """Mapping of an LDAP group to its Discord role ID and GitHub team ID."""

    discord_role_id: int
    github_team_slug: str


# This is a mapping of LDAP groups to Discord role IDs and GitHub team IDs. It is used to determine
# which users should be eligible for LDAP enrollment.
LDAP_ROLE_MAPPING: dict[str, LDAPGroupMapping] = {
    # "helpers": {"discord_role_id": 267630620367257601, "github_team_slug": "helpers"},  # noqa: ERA001
    "devops": {"discord_role_id": 409416496733880320, "github_team_slug": "devops"},
    "administrators": {"discord_role_id": 267628507062992896, "github_team_slug": "admins"},
    "moderators": {"discord_role_id": 267629731250176001, "github_team_slug": "moderators"},
    "coredevs": {"discord_role_id": 587606783669829632, "github_team_slug": "core-developers"},
    "events": {"discord_role_id": 787816728474288181, "github_team_slug": "events"},
    "directors": {"discord_role_id": 267627879762755584, "github_team_slug": "directors"},
}

# Users are only checked for enrollment if they have this role. This doesn't grant them any
# permissions, it is for performance to avoid iterating roles for every other user in the guild.
HELPER_ROLE_ID = 267630620367257601  # LDAP_ROLE_MAPPING["helpers"]["discord_role_id"]
