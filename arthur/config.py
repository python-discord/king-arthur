"""Utilities for interacting with the config for King Arthur."""

from os import environ

import pydantic
from pydantic_settings import BaseSettings


class Config(
    BaseSettings,
    env_file=".env",
    env_prefix="KING_ARTHUR_",
    extra="ignore",
):
    """Configuration for King Arthur."""

    token: pydantic.SecretStr
    prefixes: tuple[str, ...] = ("arthur ", "M-x ")

    cloudflare_token: pydantic.SecretStr | None = None
    youtube_api_key: pydantic.SecretStr | None = None
    grafana_url: str = "https://grafana.pydis.wtf"
    grafana_token: pydantic.SecretStr | None = None
    github_token: pydantic.SecretStr
    github_org: str = "python-discord"

    devops_role: int = 409416496733880320
    guild_id: int = 267624335836053506
    devops_channel_id: int = 675756741417369640
    ldap_bootstrap_channel_id: int = 1266358923875586160
    sentry_dsn: str = ""

    # LDAP & Directory
    #
    # FreeIPA accesses are generated off this information

    enable_ldap: bool = False

    ldap_host: pydantic.AnyUrl
    ldap_bind_user: str = "uid=kingarthur,cn=users,cn=accounts,dc=box,dc=pydis,dc=wtf"
    ldap_bind_password: pydantic.SecretStr
    ldap_base_dn: str = "dc=box,dc=pydis,dc=wtf"

    ldap_certificate_location: pydantic.FilePath

    # Keycloak

    keycloak_address: pydantic.AnyUrl
    keycloak_username: str = "kingarthur"
    keycloak_password: pydantic.SecretStr
    keycloak_user_realm: str = "pydis"


GIT_SHA = environ.get("GIT_SHA", "development")


CONFIG = Config()
