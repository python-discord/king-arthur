"""The Nodes cog helps with managing Kubernetes nodes."""
import textwrap

from discord import Embed
from discord.ext import commands

from arthur.apis.kubernetes import nodes
from arthur.bot import KingArthur
from arthur.utils import datetime_to_discord


class Nodes(commands.Cog):
    """Commands for working with Kubernetes nodes."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @commands.group(name="nodes", aliases=["node"], invoke_without_command=True)
    async def nodes(self, ctx: commands.Context) -> None:
        """Commands for working with Kubernetes nodes."""
        await ctx.send_help(ctx.command)

    @nodes.command(name="list", aliases=["ls"])
    async def nodes_list(self, ctx: commands.Context) -> None:
        """List Kubernetes nodes in the cluster."""
        cluster_nodes = await nodes.list_nodes()

        return_embed = Embed(title="Cluster nodes")

        for node in cluster_nodes.items:
            statuses = []

            for condition in node.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    statuses.append("Ready")
                    break
            else:
                statuses.append("Unready")

            for condition in node.status.conditions:
                if condition.type == "Ready":
                    pass

                if condition.status is True:
                    statuses.append(condition.type)

            if node.spec.taints:
                for taint in node.spec.taints:
                    statuses.append(taint.effect)

            node_creation = node.metadata.creation_timestamp

            return_embed.add_field(
                name=node.metadata.name,
                value=textwrap.dedent(
                    f"""
                    **Status:** {", ".join(statuses)}
                    **Kubernetes version:** {node.status.node_info.kubelet_version}
                    **Created**: {datetime_to_discord(node_creation, "R")}
                    """
                ),
                inline=False,
            )

        await ctx.send(embed=return_embed)

    @nodes.command(name="cordon")
    async def nodes_cordon(self, ctx: commands.Context, *, node: str) -> None:
        """
        Cordon a node in the cluster.

        Cordoning a node has the effect of preventing any new deployments from being scheduled.
        """
        await nodes.cordon_node(node)

        await ctx.send(
            embed=Embed(
                title=f"Cordoned {node}",
                description=f"`{node}` is now cordoned and no pods will be scheduled to it.",
            )
        )

    @nodes.command(name="uncordon")
    async def nodes_uncordon(self, ctx: commands.Context, *, node: str) -> None:
        """
        Uncordon a node in the cluster.

        Cordoning a node has the effect of preventing any new deployments from being scheduled.
        """
        await nodes.uncordon_node(node)

        await ctx.send(
            embed=Embed(
                title=f"Uncordoned {node}",
                description=f"`{node}` is now uncordoned, future pods may be scheduled to it.",
            )
        )


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Nodes(bot))
