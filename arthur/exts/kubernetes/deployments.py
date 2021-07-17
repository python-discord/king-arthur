"""The Deployments cog helps with managing Kubernetes deployments."""
from datetime import datetime, timezone

from discord import Colour, Embed
from discord.ext import commands
from kubernetes_asyncio import client
from kubernetes_asyncio.client.api_client import ApiClient
from kubernetes_asyncio.client.rest import ApiException
from tabulate import tabulate

from arthur.bot import KingArthur
from arthur.utils import generate_error_embed


class Deployments(commands.Cog):
    """Commands for working with Kubernetes Deployments."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @commands.group(name="deployments", aliases=["deploy"], invoke_without_command=True)
    async def deployments(self, ctx: commands.Context) -> None:
        """Commands for working with Kubernetes Deployments."""
        await ctx.send_help(ctx.command)

    @deployments.command(name="list", aliases=["ls"])
    async def deployments_list(self, ctx: commands.Context, namespace: str = "default") -> None:
        """List deployments in the selected namespace (defaults to default)."""
        async with ApiClient() as api:
            v1 = client.AppsV1Api(api)
            ret = await v1.list_namespaced_deployment(namespace=namespace)

            table_data = []

            for deployment in ret.items:
                if deployment.status.available_replicas == deployment.spec.replicas:
                    emote = "\N{LARGE GREEN CIRCLE}"
                elif (
                    deployment.status.available_replicas == 0
                    or not deployment.status.available_replicas
                ):
                    emote = "\N{LARGE RED CIRCLE}"
                else:
                    emote = "\N{LARGE YELLOW CIRCLE}"

                table_data.append(
                    [
                        emote,
                        deployment.metadata.name,
                        f"{deployment.status.available_replicas or 0}/{deployment.spec.replicas}",
                    ]
                )

        table = tabulate(
            table_data,
            headers=["Status", "Deployment", "Replicas"],
            tablefmt="psql",
            colalign=("center", "left", "center"),
        )

        return_embed = Embed(
            title=f"Deployments in namespace {namespace}", description=f"```\n{table}\n```"
        )

        await ctx.send(embed=return_embed)

    @deployments.command(name="restart")
    async def deployments_restart(
        self, ctx: commands.Context, deployment: str, namespace: str = "default"
    ) -> None:
        """Restart the specified deployment in the selected namespace (defaults to default)."""
        async with ApiClient() as api:
            v1 = client.AppsV1Api(api)

            try:
                await v1.patch_namespaced_deployment(
                    name=deployment,
                    namespace=namespace,
                    body={
                        "spec": {
                            "template": {
                                "metadata": {
                                    "annotations": {
                                        "king-arthur.pythondiscord.com/restartedAt": datetime.now(
                                            timezone.utc
                                        ).isoformat()
                                    }
                                }
                            }
                        }
                    },
                    field_manager="King Arthur",
                )
            except ApiException as e:
                if e.status == 404:
                    return await ctx.send(
                        embed=generate_error_embed(
                            description="Could not find deployment, check the namespace."
                        )
                    )

                return await ctx.send(
                    embed=generate_error_embed(
                        description=f"Unexpected error occurred, error code {e.status}"
                    )
                )

        return_embed = Embed(
            title="Deployment restarted",
            description=f"Restarted deployment `{deployment}` in the `{namespace}` namespace.",
            colour=Colour.blurple(),
        )

        await ctx.send(embed=return_embed)


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Deployments(bot))
