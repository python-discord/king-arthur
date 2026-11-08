"""Module containing the core bot base for King Arthur."""

import asyncio
from pathlib import Path
from typing import Any

import discord
from discord import Interaction, Member
from discord.ext import commands
from kubernetes_asyncio import config
from kubernetes_asyncio.client import Configuration
from kubernetes_asyncio.config.kube_config import KUBE_CONFIG_DEFAULT_LOCATION
from pydis_core import BotBase
from sentry_sdk import new_scope

import arthur
from arthur import exts
from arthur.config import CONFIG
from arthur.context import BotContext
from arthur.log import logger


class KingArthurTheTerrible(BotBase):
    """Base bot class for King Arthur The Terrible."""

    def __init__(self, *args: list[Any], **kwargs: dict[str, Any]) -> None:
        kwargs.setdefault("command_prefix", commands.when_mentioned)
        kwargs.setdefault("help_command", None)
        super().__init__(*args, **kwargs)
        self.add_check(self._is_devops)
        self._extensions_finished = asyncio.Event()
        self._finished_extensions: set[str] = set()

    async def get_context(
        self,
        origin: discord.Message | Interaction,
        /,
        *,
        cls: type[commands.Context] = BotContext,
    ) -> commands.Context:
        """Build a context, defaulting to the custom BotContext."""
        return await super().get_context(origin, cls=cls)

    async def _sync_app_commands(self) -> None:
        """Sync commands to the guild once every extension has finished loading."""
        await self._extension_loading_task
        await self._extensions_finished.wait()

        guild = discord.Object(self.guild_id)
        self.tree.copy_global_to(guild=guild)
        self.tree.clear_commands(guild=None)
        await self.tree.sync(guild=guild)
        # Delete stale global commands.
        await self.tree.sync()
        logger.info("Synced application commands to guild <red>{}</>", self.guild_id)

    async def load_extension(self, name: str, **kwargs: Any) -> None:
        """Load an extension, recording that it finished (successfully or not)."""
        try:
            await super().load_extension(name, **kwargs)
        finally:
            self._finished_extensions.add(name)
            if self.all_extensions is not None and self._finished_extensions >= set(
                self.all_extensions
            ):
                self._extensions_finished.set()

    async def _is_devops(self, ctx: commands.Context | Interaction) -> bool:
        """Check all commands are executed by authorised personnel."""
        u = ctx.user if isinstance(ctx, Interaction) else ctx.author
        if await arthur.instance.is_owner(u):
            return True

        if isinstance(ctx, Interaction):
            if isinstance(ctx.user, Member):
                return CONFIG.devops_role in [r.id for r in ctx.user.roles]
            return False

        if ctx.command.name in {"ed", "rules", "monitor"}:
            return True

        if not ctx.guild:
            return False

        return CONFIG.devops_role in [r.id for r in ctx.author.roles]

    async def setup_hook(self) -> None:
        """Async initialisation method for discord.py."""
        await super().setup_hook()

        # Authenticate with Kubernetes
        if Path(KUBE_CONFIG_DEFAULT_LOCATION).exists():  # noqa: ASYNC240
            await config.load_kube_config()
        else:
            config.load_incluster_config()
        Configuration.get_default().disable_strict_ssl_verification = True
        logger.info(f"Logged in <red>{self.user}</>")

        await self.load_extensions(exts)

        logger.info("Loading <red>jishaku</red>")
        await self.load_extension("jishaku")
        logger.info("Loaded <red>jishaku</red>")

    async def on_error(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Log errors raised in event listeners."""
        with new_scope() as scope:
            scope.set_tag("event", event_name)
            scope.set_extra("args", args)
            scope.set_extra("kwargs", kwargs)

            logger.exception(f"Unhandled exception during event: {event_name}.")
