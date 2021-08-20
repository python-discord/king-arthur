"""Module containing the core bot base for King Arthur."""
from pathlib import Path
from typing import Any, Union

from discord import Interaction, Member, User
from discord.ext import commands
from discord.ext.commands import Bot
from kubernetes_asyncio import config

from arthur import logger
from arthur.config import CONFIG
from arthur.extensions import find_extensions


class KingArthur(Bot):
    """Base bot class for King Arthur."""

    def __init__(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        config = {
            "command_prefix": commands.when_mentioned_or(CONFIG.prefix),
            "case_insensitive": True,
        }

        kwargs.update(config)

        super().__init__(*args, **kwargs)

        self.add_check(self._is_devops)

    @staticmethod
    def _is_devops(ctx: Union[commands.Context, Interaction]) -> bool:
        """Check all commands are executed by authorised personnel."""
        if isinstance(ctx, Interaction):
            return CONFIG.devops_role in [r.id for r in ctx.author.roles]

        if ctx.command.name == "ed":
            return True

        if not ctx.guild:
            return False

        return CONFIG.devops_role in [r.id for r in ctx.author.roles]

    async def on_ready(self) -> None:
        """Initialise bot once connected and authorised with Discord."""
        # Authenticate with Kubernetes
        if (Path.home() / ".kube/config").exists():
            await config.load_kube_config()
        else:
            config.load_incluster_config()

        logger.info(f"Logged in <red>{self.user}</>")

        # Start extension loading

        for path, extension in find_extensions():
            logger.info(
                f"Loading extension <magenta>{path.stem}</> " f"from <magenta>{path.parent}</>"
            )

            try:
                self.load_extension(extension)
            except:  # noqa: E722
                logger.exception(
                    f"Failed to load extension <magenta>{path.stem}</> "
                    f"from <magenta>{path.parent}</>",
                )
            else:
                logger.info(
                    f"Loaded extension <magenta>{path.stem}</> " f"from <magenta>{path.parent}</>"
                )

        logger.info("Loading <red>jishaku</red>")
        self.load_extension("jishaku")
        logger.info("Loaded <red>jishaku</red>")

    async def is_owner(self, user: Union[User, Member]) -> bool:
        """Check if the invoker is a bot owner."""
        if not user.guild:
            return False

        return CONFIG.devops_role in [r.id for r in user.roles]
