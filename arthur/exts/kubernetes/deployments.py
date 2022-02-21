"""The Deployments cog helps with managing Kubernetes deployments."""
from textwrap import dedent

from discord import ButtonStyle, Interaction, ui
from discord.ext import commands
from kubernetes_asyncio.client.models import V1Deployment
from kubernetes_asyncio.client.rest import ApiException
from tabulate import tabulate

from arthur.apis.kubernetes import deployments
from arthur.bot import KingArthur
from arthur.utils import generate_error_message


class ConfirmDeployment(ui.View):
    """A confirmation view for redeploying to Kubernetes."""

    def __init__(self, author_id: int, deployment_ns: tuple[str, str]) -> None:
        super().__init__()
        self.confirmed = None
        self.interaction = None
        self.authorization = author_id
        self.deployment = deployment_ns[1]
        self.namespace = deployment_ns[0]

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Check the interactor is authorised."""
        if interaction.user.id == self.authorization:
            return True

        await interaction.response.send_message(
            generate_error_message(description="You are not authorized to perform this action."),
            ephemeral=True,
        )

        return False

    @ui.button(label="Confirm", style=ButtonStyle.green, row=0)
    async def confirm(self, _button: ui.Button, interaction: Interaction) -> None:
        """Redeploy the specified service."""
        try:
            await deployments.restart_deployment(self.deployment, self.namespace)
        except ApiException as e:
            if e.status == 404:
                return await interaction.message.edit(
                    content=generate_error_message(
                        description="Could not find deployment, check the namespace.",
                    ),
                    view=None,
                )

            await interaction.message.edit(
                content=generate_error_message(
                    description=f"Unexpected error occurred, error code {e.status}"
                ),
                view=None,
            )
        else:
            description = (
                f":white_check_mark: Restarted deployment "
                f"`{self.deployment}` in namespace `{self.namespace}`."
            )

            await interaction.message.edit(content=description, view=None)

        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.grey, row=0)
    async def cancel(self, _button: ui.Button, interaction: Interaction) -> None:
        """Logic for if the deployment is not approved."""
        await interaction.message.edit(
            content=":x: Redeployment aborted",
            view=None,
        )
        self.stop()


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

        if len(deploys.items) == 0:
            return await ctx.send(
                generate_error_message(
                    description="No deployments found, check the namespace exists."
                )
            )

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
        confirmation = ConfirmDeployment(ctx.author.id, [namespace, deployment])

        msg = await ctx.send(
            f":warning: Please confirm you want to restart `deploy/{deployment}` in `{namespace}`",
            view=confirmation,
        )

        timed_out = await confirmation.wait()

        if timed_out:
            await msg.edit(
                content=generate_error_message(
                    title="What is the airspeed velocity of an unladen swallow?",
                    description=(
                        "Whatever the answer may be, it's certainly "
                        "faster than you could select a confirmation option."
                    ),
                )
            )


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Deployments(bot))
