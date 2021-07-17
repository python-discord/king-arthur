from pydantic import BaseSettings


class Config(BaseSettings):
    """
    Configuration for King Arthur.
    """

    # Discord bot token
    token: str

    # Discord bot prefix
    prefix: str

    # Authorised role ID for usage
    devops_role: int

    class Config:  # noqa: D106
        env_file = ".env"
        env_prefix = "KING_ARTHUR_"


CONFIG = Config()
