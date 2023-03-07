"""Module containing the core bot base for King Arthur."""
from pathlib import Path
from typing import Any, Union

from discord import Interaction, Member, User
from discord.ext import commands
from kubernetes_asyncio import config
from pydis_core import BotBase
from pydis_core.utils import scheduling

from arthur import exts, logger
from arthur.config import CONFIG


class KingArthur(BotBase):
    """Base bot class for King Arthur."""

    def __init__(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        super().__init__(*args, **kwargs)

        self.add_check(self._is_devops)

    @staticmethod
    def _is_devops(ctx: Union[commands.Context, Interaction]) -> bool:
        """Check all commands are executed by authorised personnel."""
        if isinstance(ctx, Interaction):
            if isinstance(ctx.user, Member):
                return CONFIG.devops_role in [r.id for r in ctx.user.roles]
            else:
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
        if (Path.home() / ".kube/config").exists():
            await config.load_kube_config()
        else:
            config.load_incluster_config()
        logger.info(f"Logged in <red>{self.user}</>")

        await self.load_extensions(exts, sync_app_commands=False)

        logger.info("Loading <red>jishaku</red>")
        await self.load_extension("jishaku")
        logger.info("Loaded <red>jishaku</red>")

    async def is_owner(self, user: Union[User, Member]) -> bool:
        """Check if the invoker is a bot owner."""
        if not user.guild:
            return False

        return CONFIG.devops_role in [r.id for r in user.roles]
