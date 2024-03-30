"""The Pods cog helps with managing Kubernetes pods."""

from textwrap import dedent

from discord.ext import commands
from tabulate import tabulate

from arthur.apis.kubernetes import pods
from arthur.bot import KingArthur
from arthur.utils import generate_error_message


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

        table_data = []

        if len(pod_list.items) == 0:
            return await ctx.send(
                generate_error_message(
                    description="No pods found, check the namespace exists."
                )
            )

        for pod in pod_list.items:
            match pod.status.phase:
                case "Running":
                    emote = ":green_circle:"
                case "Pending":
                    emote = ":yellow_circle:"
                case "Succeeded":
                    emote = ":white_check_mark:"
                case "Failed":
                    emote = ":x:"
                case "Unknown":
                    emote = ":question:"
                case _:
                    emote = ":grey_question:"

            table_data.append([
                emote,
                pod.metadata.name,
                pod.status.phase,
                pod.status.pod_ip,
                pod.spec.node_name,
            ])

        table = tabulate(
            table_data,
            headers=["Status", "Pod", "Phase", "IP", "Node"],
            tablefmt="psql",
            colalign=("center", "left", "center", "center", "center")
        )

        return_message = dedent("""
            **Pods in namespace `{0}`**
            ```
            {1}
            ```
            """)

        await ctx.send(return_message.format(namespace, table))
        return None


async def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    await bot.add_cog(Pods(bot))
