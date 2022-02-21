"""Module containing the core bot base for King Arthur."""
from pathlib import Path
from typing import Any

from discord.ext import commands
from discord.ext.commands import Bot
from discord_components import DiscordComponents
from kubernetes_asyncio import config

from arthur import logger
from arthur.config import CONFIG
from arthur.extensions import find_extensions


class KingArthur(Bot):
    """Base bot class for King Arthur."""

    def __init__(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        config = {
            "command_prefix": commands.when_mentioned_or(*CONFIG.prefixes),
            "case_insensitive": True,
        }

        kwargs.update(config)

        super().__init__(*args, **kwargs)

        self.add_check(self._is_devops)

    @staticmethod
    async def _is_devops(ctx: commands.Context) -> bool:
        """Check all commands are executed by authorised personnel."""
        if ctx.command.name == "ed":
            return True

        if not ctx.guild:
            return False

        return CONFIG.devops_role in [r.id for r in ctx.author.roles]

    async def on_ready(self) -> None:
        """Initialise bot once connected and authorised with Discord."""
        # Initialise components (e.g. buttons, selections)
        DiscordComponents(self)

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
