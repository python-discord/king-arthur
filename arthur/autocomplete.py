"""Shared autocomplete callbacks for slash command options."""

import time
from typing import Any, TYPE_CHECKING

from discord import Interaction, Member, app_commands

from arthur.apis.cloudflare import zones
from arthur.apis.kubernetes import deployments, jobs, namespaces, nodes, pods
from arthur.config import CONFIG
from arthur.log import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

CACHE_TTL = 30.0
MAX_CHOICES = 25
MAX_LENGTH = 100

_cache: dict[Any, tuple[float, Any]] = {}


async def _cached[T](key: Any, fetch: Callable[[], Awaitable[T]]) -> T:
    """Return a recently fetched value, or fetch a new one. Autocomplete fires on every keystroke."""
    now = time.monotonic()
    if (hit := _cache.get(key)) and now - hit[0] < CACHE_TTL:
        return hit[1]
    value = await fetch()
    _cache[key] = (now, value)
    return value


async def _is_devops(interaction: Interaction) -> bool:
    """Autocomplete bypasses command checks, so mirror the bot-wide devops gate."""
    if await interaction.client.is_owner(interaction.user):
        return True
    return isinstance(interaction.user, Member) and CONFIG.devops_role in {
        r.id for r in interaction.user.roles
    }


def _choices(items: list[tuple[str, str]], current: str) -> list[app_commands.Choice[str]]:
    """Filter (label, value) pairs by the typed text and trim to Discord's limits."""
    needle = current.lower()
    return [
        app_commands.Choice(name=label[:MAX_LENGTH], value=value[:MAX_LENGTH])
        for label, value in items
        if needle in label.lower() and len(value) <= MAX_LENGTH
    ][:MAX_CHOICES]


def _namespace_of(interaction: Interaction) -> str:
    """The namespace already typed into the command, or the default."""
    return getattr(interaction.namespace, "namespace", None) or "default"


def _guarded(
    fn: Callable[[Interaction, str], Awaitable[list[tuple[str, str]]]],
    *,
    gate: Callable[[Interaction], Awaitable[bool]] = _is_devops,
) -> Callable[[Interaction, str], Awaitable[list[app_commands.Choice[str]]]]:
    """Wrap a lister so it is permission gated and never raises (an error just shows no choices)."""

    async def callback(interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        try:
            if not await gate(interaction):
                return []
            return _choices(await fn(interaction, current), current)
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug(f"Autocomplete failed for {fn.__name__}")
            return []

    callback.__name__ = fn.__name__
    return callback


@_guarded
async def namespace_autocomplete(_: Interaction, __: str) -> list[tuple[str, str]]:
    """Kubernetes namespaces."""
    result = await _cached("namespaces", namespaces.list_namespaces)
    return [(ns.metadata.name, ns.metadata.name) for ns in result.items]


@_guarded
async def deployment_autocomplete(interaction: Interaction, _: str) -> list[tuple[str, str]]:
    """Deployments in the namespace already chosen."""
    ns = _namespace_of(interaction)
    result = await _cached(("deployments", ns), lambda: deployments.list_deployments(ns))
    return [(d.metadata.name, d.metadata.name) for d in result.items]


@_guarded
async def pod_autocomplete(interaction: Interaction, _: str) -> list[tuple[str, str]]:
    """Pods (and ``deploy/<name>`` shortcuts) in the namespace already chosen."""
    ns = _namespace_of(interaction)
    pod_list = await _cached(("pods", ns), lambda: pods.list_pods(ns))
    deployment_list = await _cached(("deployments", ns), lambda: deployments.list_deployments(ns))
    return [
        (f"deploy/{d.metadata.name}", f"deploy/{d.metadata.name}") for d in deployment_list.items
    ] + [(p.metadata.name, p.metadata.name) for p in pod_list.items]


@_guarded
async def node_autocomplete(interaction: Interaction, _: str) -> list[tuple[str, str]]:
    """Nodes that the invoked command can act on (cordon: schedulable, uncordon: cordoned)."""
    result = await _cached("nodes", nodes.list_nodes)
    command = interaction.command.name if interaction.command else ""
    out = []
    for node in result.items:
        cordoned = bool(node.spec.unschedulable)
        if (command == "cordon" and cordoned) or (command == "uncordon" and not cordoned):
            continue
        out.append((node.metadata.name, node.metadata.name))
    return out


@_guarded
async def cronjob_autocomplete(_: Interaction, __: str) -> list[tuple[str, str]]:
    """CronJobs across all namespaces, as ``namespace/name``."""
    result = await _cached("cronjobs", jobs.list_cronjobs)
    return [(f"{cj.metadata.namespace}/{cj.metadata.name}",) * 2 for cj in result.items]


@_guarded
async def zone_autocomplete(interaction: Interaction, _: str) -> list[tuple[str, str]]:
    """Cloudflare zones."""
    session = interaction.client.http_session
    result = await _cached("zones", lambda: zones.list_zones(session))
    return [(name, name) for name in result]
