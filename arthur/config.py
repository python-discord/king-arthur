"""Utilities for interacting with the config for King Arthur."""
from pydantic import BaseSettings


class Config(BaseSettings):
    """Configuration for King Arthur."""

    # Discord bot token
    token: str

    # Discord bot prefix
    prefix: str = "arthur "

    # Authorised role ID for usage
    devops_role: int = 409416496733880320

    class Config:  # noqa: D106
        env_file = ".env"
        env_prefix = "KING_ARTHUR_"


CONFIG = Config()
