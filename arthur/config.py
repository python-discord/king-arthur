"""Utilities for interacting with the config for King Arthur."""

import pydantic
from pydantic_settings import BaseSettings


class Config(
    BaseSettings,
    env_file=".env",
    env_prefix="KING_ARTHUR_",
    extra="ignore",
):
    """Configuration for King Arthur."""

    # Discord bot token
    token: pydantic.SecretStr

    # Discord bot prefix
    prefixes: tuple[str, ...] = ("arthur ", "M-x ")

    # Authorised role ID for usage
    devops_role: int = 409416496733880320

    # Token for authorising with the Cloudflare API
    cloudflare_token: pydantic.SecretStr

    # Guild id
    guild_id: int = 267624335836053506


CONFIG = Config()
