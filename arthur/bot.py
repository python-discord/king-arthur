"""Module containing the core bot base for King Arthur."""

from pathlib import Path
from typing import Any

from discord import Interaction, Member, User
from discord.ext import commands
from kubernetes_asyncio import config
from kubernetes_asyncio.config.kube_config import KUBE_CONFIG_DEFAULT_LOCATION
from pydis_core import BotBase
from sentry_sdk import push_scope

from arthur import exts
from arthur.config import CONFIG
from arthur.log import logger


class KingArthur(BotBase):
    """Base bot class for King Arthur."""

    def __init__(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        super().__init__(*args, **kwargs)

        self.add_check(self._is_devops)

    @staticmethod
    def _is_devops(ctx: commands.Context | Interaction) -> bool:
        """Check all commands are executed by authorised personnel."""
        if isinstance(ctx, Interaction):
            if isinstance(ctx.user, Member):
                return CONFIG.devops_role in [r.id for r in ctx.user.roles]
            return False

        if ctx.command.name == "ed":
            return True

        if not ctx.guild:
            return False

        return CONFIG.devops_role in [r.id for r in ctx.author.roles]

    async def setup_hook(self) -> None:
        """Async initialisation method for discord.py."""
        await super().setup_hook()

        # Authenticate with Kubernetes
        if Path(KUBE_CONFIG_DEFAULT_LOCATION).exists():
            await config.load_kube_config()
        else:
            config.load_incluster_config()
        logger.info(f"Logged in <red>{self.user}</>")

        await self.load_extensions(exts, sync_app_commands=False)

        logger.info("Loading <red>jishaku</red>")
        await self.load_extension("jishaku")
        logger.info("Loaded <red>jishaku</red>")

    async def is_owner(self, user: User | Member) -> bool:
        """Check if the invoker is a bot owner."""
        if not user.guild:
            return False

        return CONFIG.devops_role in [r.id for r in user.roles]

    async def on_error(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Log errors raised in event listeners."""
        with push_scope() as scope:
            scope.set_tag("event", event_name)
            scope.set_extra("args", args)
            scope.set_extra("kwargs", kwargs)

            logger.exception(f"Unhandled exception during event: {event_name}.")
