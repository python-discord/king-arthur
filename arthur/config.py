"""Utilities for interacting with the config for King Arthur The Terrible."""

from os import environ

import pydantic  # noqa: TC002 Pydantic requires this to be present at runtime for parsing
from pydantic_settings import BaseSettings


class Config(
    BaseSettings,
    env_file=".env",
    env_prefix="KING_ARTHUR_",
    extra="ignore",
):
    """Configuration for King Arthur The Terrible."""

    token: pydantic.SecretStr
    prefixes: tuple[str, ...] = ("arthur ", "M-x ")

    cloudflare_token: pydantic.SecretStr | None = None
    youtube_api_key: pydantic.SecretStr | None = None
    grafana_url: str = "https://grafana.pydis.wtf"
    grafana_token: pydantic.SecretStr | None = None
    github_token: pydantic.SecretStr | None = None
    github_org: str = "python-discord"
    github_team: str = "staff"

    devops_role: int = 409416496733880320
    helpers_role: int = 267630620367257601
    admins_role: int = 267628507062992896
    guild_id: int = 267624335836053506
    devops_channel_id: int = 675756741417369640
    devops_vc_id: int = 881573757536329758
    ldap_bootstrap_channel_id: int = 1266358923875586160
    sentry_dsn: str = ""
    numbers_url: str = "https://pydis.wtf/numbers"

    # RCE as a service
    ssh_username: str = "kingarthur"  # the terrible
    ssh_host: str = "lovelace.box.pydis.wtf"

    # LDAP & Directory
    #
    # FreeIPA accesses are generated off this information

    enable_ldap: bool = False

    ldap_host: pydantic.AnyUrl | None = None
    ldap_bind_user: str = (
        "uid=kingarthur,"  # the terrible
        "cn=users,cn=accounts,dc=box,dc=pydis,dc=wtf"
    )
    ldap_bind_password: pydantic.SecretStr | None = None
    ldap_base_dn: str = "dc=box,dc=pydis,dc=wtf"

    ldap_certificate_location: pydantic.FilePath | None = None

    # Keycloak

    keycloak_address: pydantic.AnyUrl | None = None
    keycloak_username: str = "kingarthur"  # the terrible
    keycloak_password: pydantic.SecretStr | None = None
    keycloak_user_realm: str = "pydis"


GIT_SHA = environ.get("GIT_SHA", "development")


CONFIG = Config()
