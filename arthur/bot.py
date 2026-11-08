"""Module containing the core bot base for King Arthur."""

import asyncio
import contextlib
from pathlib import Path
from typing import Any

import discord
from discord import HTTPException, Interaction, Member
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

    def _resolve_command(self, content: str) -> commands.Command | None:
        """Resolve the command named at the start of ``content`` (prefix already stripped)."""
        view = content.strip()
        if not view:
            return None
        # Split on backticks so ``cmd```code``` still resolves.
        first = view.split("`", 1)[0].split(maxsplit=1)
        if not first:
            return None
        command = self.get_command(first[0])
        rest = view[len(first[0]) :].lstrip()
        while isinstance(command, commands.Group) and rest:
            sub_name = rest.split(maxsplit=1)[0]
            sub = command.get_command(sub_name)
            if sub is None:
                break
            command = sub
            rest = rest[len(sub_name) :].lstrip()
        return command

    @staticmethod
    def _slash_form(command: commands.Command) -> str | None:
        """Get the slash command form of a command, if it has one."""
        chain: list[commands.Command] = []
        current: commands.Command | None = command
        while current is not None:
            chain.append(current)
            current = current.parent
        chain.reverse()
        if any(getattr(c, "app_command", None) is None for c in chain):
            return None
        names = [c.name for c in chain]
        if isinstance(command, commands.HybridGroup) and command.fallback:
            names.append(command.fallback)
        return "/" + " ".join(names)

    async def process_commands(self, message: discord.Message) -> None:
        """Reply with a deprecation notice for old-prefix invocations, else process as normal."""
        if message.author.bot:
            return

        for prefix in CONFIG.prefixes:
            if not message.content.lower().startswith(prefix.lower()):
                continue
            command = self._resolve_command(message.content[len(prefix) :])
            if command is None:
                break

            notice = (
                f"The `{prefix.strip()}` prefix has been retired. "
                f"Use `@{self.user.display_name} {command.qualified_name}`"
            )
            slash = self._slash_form(command)
            if slash:
                notice += f" or `{slash}`"
            notice += " instead."
            with contextlib.suppress(HTTPException):
                await message.reply(notice, mention_author=False)
            return

        await super().process_commands(message)

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

    async def _is_devops(self, ctx: commands.Context | Interaction) -> bool:  # noqa: PLR0911
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

        if ctx.command.cog_name == "GitHubManagement":
            # Commands in this cog have explicit additional checks.
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
