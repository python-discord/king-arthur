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

    cloudflare_token: pydantic.SecretStr
    grafana_url: str = "https://grafana.pythondiscord.com"
    grafana_token: pydantic.SecretStr
    github_token: pydantic.SecretStr
    github_org: str = "python-discord"

    devops_role: int = 409416496733880320
    guild_id: int = 267624335836053506
    sentry_dsn: str = ""


GIT_SHA = environ.get("GIT_SHA", "development")


CONFIG = Config()
