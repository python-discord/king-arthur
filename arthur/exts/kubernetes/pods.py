"""The Pods cog helps with managing Kubernetes pods."""

import zoneinfo
from datetime import datetime

import humanize
from discord.ext import commands
from tabulate import tabulate

from arthur.apis.kubernetes import pods
from arthur.bot import KingArthur
from arthur.utils import generate_error_message

MAX_MESSAGE_LENGTH = 2000


def tabulate_pod_data(data: list[list[str]]) -> str:
    """Tabulate the pod data to be sent to Discord."""
    table = tabulate(
        data,
        headers=["Status", "Pod", "Phase", "IP", "Node", "Age", "Restarts"],
        tablefmt="psql",
        colalign=("center", "left", "left", "center", "center", "left", "center"),
    )

    return f"```\n{table}```"


class Pods(commands.Cog):
    """Commands for working with Kubernetes Pods."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @commands.group(name="pods", aliases=["pod"], invoke_without_command=True)
    async def pods_cmd(self, ctx: commands.Context) -> None:
        """Commands for working with Kubernetes Pods."""
        await ctx.send_help(ctx.command)

    @pods_cmd.command(name="list", aliases=["ls"])
    async def pods_list(self, ctx: commands.Context, namespace: str = "default") -> None:
        """List pods in the selected namespace (defaults to default)."""
        pod_list = await pods.list_pods(namespace)

        if len(pod_list.items) == 0:
            return await ctx.send(
                generate_error_message(description="No pods found, check the namespace exists.")
            )

        tables = [[]]

        for pod in pod_list.items:
            match pod.status.phase:
                case "Running":
                    emote = "\N{LARGE GREEN CIRCLE}"
                case "Pending":
                    emote = "\N{LARGE YELLOW CIRCLE}"
                case "Succeeded":
                    emote = "\N{WHITE HEAVY CHECK MARK}"
                case "Failed":
                    emote = "\N{CROSS MARK}"
                case "Unknown":
                    emote = "\N{WHITE QUESTION MARK ORNAMENT}"
                case _:
                    emote = "\N{BLACK QUESTION MARK ORNAMENT}"

            time_human = humanize.naturaldelta(
                datetime.now(tz=zoneinfo.ZoneInfo("UTC")) - pod.metadata.creation_timestamp
            )

            # we know that Linode formats names like "lke<cluster>-<pool>-<node>"
            node_name = pod.spec.node_name.split("-")[2]

            table_data = [
                emote,
                pod.metadata.name,
                pod.status.phase,
                pod.status.pod_ip,
                node_name,
                time_human,
                pod.status.container_statuses[0].restart_count,
            ]

            if len(tabulate_pod_data(tables[-1] + [table_data])) > MAX_MESSAGE_LENGTH:
                tables.append([])
                tables[-1].append(table_data)
            else:
                tables[-1].append(table_data)

        await ctx.send(f"**Pods in namespace `{namespace}`**")

        for table in tables:
            await ctx.send(tabulate_pod_data(table))

        return None


async def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    await bot.add_cog(Pods(bot))
