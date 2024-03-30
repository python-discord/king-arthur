"""The Pods cog helps with managing Kubernetes pods."""

from textwrap import dedent

from discord.ext import commands
from tabulate import tabulate

from arthur.apis.kubernetes import pods
from arthur.bot import KingArthur
from arthur.utils import generate_error_message

MAX_MESSAGE_LENGTH = 4000


def tabulate_pod_data(data: list[list[str]]) -> str:
    """Tabulate the pod data to be sent to Discord."""
    table = tabulate(
        data,
        headers=["Status", "Pod", "Phase", "IP", "Node"],
        tablefmt="psql",
        colalign=("center", "left", "center", "center", "center"),
    )

    return dedent(f"""
        ```
        {table}
        ```
        """)


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

        tables = []

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

            table_data = [
                emote,
                pod.metadata.name,
                pod.status.phase,
                pod.status.pod_ip,
                pod.spec.node_name,
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
