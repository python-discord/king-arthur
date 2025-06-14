"""Constants, primarily used for LDAP enrollment preferences."""

# Users are only checked for enrollment if they have this role. This doesn't grant them any
# permissions, it is for performance to avoid iterating roles for every other user in the guild.
LDAP_BASE_STAFF_ROLE = 267630620367257601

# This is a mapping of LDAP groups to Discord roles. It is used to determine which users should be
# eligible for LDAP enrollment.
LDAP_ROLE_MAPPING = {
    "devops": 409416496733880320,
    "administrators": 267628507062992896,
    "moderators": 267629731250176001,
    "coredevs": 587606783669829632,
    "events": 787816728474288181,
    "directors": 267627879762755584,
}
