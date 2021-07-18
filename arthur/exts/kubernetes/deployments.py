"""The Deployments cog helps with managing Kubernetes deployments."""
import asyncio
from textwrap import dedent

from discord.ext import commands
from discord_components.component import ActionRow, Button, ButtonStyle
from kubernetes_asyncio.client.models import V1Deployment
from kubernetes_asyncio.client.rest import ApiException
from tabulate import tabulate

from arthur.apis.kubernetes import deployments
from arthur.bot import KingArthur
from arthur.utils import generate_error_message


def deployment_to_emote(deployment: V1Deployment) -> str:
    """Convert a deployment to an emote based on it's replica status."""
    if deployment.status.available_replicas == deployment.spec.replicas:
        return "\N{LARGE GREEN CIRCLE}"
    elif deployment.status.available_replicas == 0 or not deployment.status.available_replicas:
        return "\N{LARGE RED CIRCLE}"
    else:
        return "\N{LARGE YELLOW CIRCLE}"


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
        deploys = await deployments.list_deployments(namespace)

        table_data = []

        for deployment in deploys.items:
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

        return_message = dedent(
            """
            **Deployments in namespace `{0}`**
            ```
            {1}
            ```
            """
        )

        await ctx.send(return_message.format(namespace, table))

    @deployments.command(name="restart", aliases=["redeploy"])
    async def deployments_restart(
        self, ctx: commands.Context, deployment: str, namespace: str = "default"
    ) -> None:
        """Restart the specified deployment in the selected namespace (defaults to default)."""
        components = ActionRow(
            Button(
                label="Redeploy",
                style=ButtonStyle.green,
                custom_id=f"{ctx.message.id}-redeploy",
            ),
            Button(
                label="Abort",
                style=ButtonStyle.red,
                custom_id=f"{ctx.message.id}-abort",
            ),
        )

        msg = await ctx.send(
            f":warning: Please confirm you want to restart `deploy/{deployment}` in `{namespace}`",
            components=[components],
        )

        try:
            interaction = await self.bot.wait_for(
                "button_click",
                check=lambda i: i.component.custom_id.startswith(str(ctx.message.id))
                and i.user.id == ctx.author.id,
                timeout=30,
            )
        except asyncio.TimeoutError:
            return await msg.edit(
                generate_error_message(
                    title="What is the airspeed velocity of an unladen swallow?",
                    description=(
                        "Whatever the answer may be, it's certainly "
                        "faster than you could select a confirmation option."
                    ),
                ),
                components=[],
            )

        if interaction.component.custom_id == f"{ctx.message.id}-abort":
            await interaction.respond(
                ":x: Redeployment aborted",
                ephemeral=False,
            )
        else:
            try:
                await deployments.restart_deployment(deployment, namespace)
            except ApiException as e:
                if e.status == 404:
                    return await interaction.respond(
                        generate_error_message(
                            description="Could not find deployment, check the namespace.",
                        ),
                        ephemeral=False
                    )

                return await interaction.respond(
                    generate_error_message(
                        description=f"Unexpected error occurred, error code {e.status}"
                    ),
                    ephemeral=False
                )
            else:
                description = (
                    f":white_check_mark: Restarted deployment "
                    f"`{deployment}` in namespace `{namespace}`."
                )
                await interaction.respond(
                    description,
                    ephemeral=False,
                )

        for component in components.components:
            component.disabled = True

        await msg.edit(components=[components])


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Deployments(bot))
