"""The Deployments cog helps with managing Kubernetes deployments."""
import asyncio

from discord import Colour, Embed
from discord.ext import commands
from discord_components.component import ActionRow, Button, ButtonStyle
from kubernetes_asyncio.client.models import V1Deployment
from kubernetes_asyncio.client.rest import ApiException
from tabulate import tabulate

from arthur.apis.kubernetes import deployments
from arthur.bot import KingArthur
from arthur.utils import generate_error_embed


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

        return_embed = Embed(
            title=f"Deployments in namespace {namespace}", description=f"```\n{table}\n```"
        )

        await ctx.send(embed=return_embed)

    @deployments.command(name="restart", aliases=["redeploy"])
    async def deployments_restart(
        self, ctx: commands.Context, deployment: str, namespace: str = "default"
    ) -> None:
        """Restart the specified deployment in the selected namespace (defaults to default)."""
        confirm_embed = Embed(
            title="Confirm redeployment",
            description=f"Confirm you want to redeploy `{deployment}` in namespace `{namespace}`.",
            colour=Colour.orange(),
        )

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
            embed=confirm_embed,
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
            await msg.edit(
                embed=Embed(
                    title="What is the airspeed velocity of an unladen swallow?",
                    description=(
                        "Whatever the answer may be, it's certainly "
                        "faster than you could select a confirmation option.",
                    ),
                    colour=Colour.greyple(),
                ),
                components=[],
            )

        if interaction.component.custom_id == f"{ctx.message.id}-abort":
            await interaction.respond(
                ephemeral=False,
                embed=Embed(
                    title="Deployment aborted",
                    description="The deployment was aborted.",
                    colour=Colour.red(),
                ),
            )
        else:
            try:
                await deployments.restart_deployment(deployment, namespace)
            except ApiException as e:
                if e.status == 404:
                    return await interaction.respond(
                        ephemeral=False,
                        embed=generate_error_embed(
                            description="Could not find deployment, check the namespace.",
                        ),
                    )

                return await interaction.respond(
                    ephemeral=False,
                    embed=generate_error_embed(
                        description=f"Unexpected error occurred, error code {e.status}"
                    ),
                )
            else:
                description = f"Restarted deployment `{deployment}` in namespace `{namespace}`."
                await interaction.respond(
                    ephemeral=False,
                    embed=Embed(
                        title="Redeployed",
                        description=description,
                        colour=Colour.blurple(),
                    ),
                )

        for component in components.components:
            component.disabled = True

        await msg.edit(embed=confirm_embed, components=[components])


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Deployments(bot))
