"""The zones cog helps with managing Cloudflare zones."""

from http import HTTPStatus
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from kubernetes_asyncio.client.rest import ApiException

from arthur.apis.kubernetes import jobs
from arthur.autocomplete import cronjob_autocomplete
from arthur.config import CONFIG
from arthur.utils import generate_error_message

if TYPE_CHECKING:
    from kubernetes_asyncio.client.models import V1CronJobList

    from arthur.bot import KingArthurTheTerrible


async def spawn_job(namespace: str, cronjob_name: str, suffix: int) -> str:
    """Create a job from a cronjob's template, returning the new job's name."""
    cronjob = await jobs.get_cronjob(namespace, cronjob_name)
    new_job = await jobs.create_job(
        namespace, f"{cronjob_name}-{suffix}", cronjob.spec.job_template.spec
    )
    return new_job.metadata.name


class CronJobView(discord.ui.View):
    """This view allows users to select and trigger a CronJob."""

    def __init__(self, cron_jobs: V1CronJobList) -> None:
        super().__init__()

        self.cron_jobs = cron_jobs

        for cron_job in self.cron_jobs.items:
            cj = cron_job.metadata.name
            ns = cron_job.metadata.namespace
            self.children[0].add_option(
                label=cron_job.metadata.name, value=f"{ns}/{cj}", description=ns, emoji="🛠️"
            )

    def disable_select(self) -> None:
        """Disable the select button."""
        self.children[0].disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure the user has the DevOps role."""
        return CONFIG.devops_role in [r.id for r in interaction.user.roles]

    @discord.ui.select(
        placeholder="Select a CronJob to trigger...",
    )
    async def select_job(
        self, interaction: discord.Interaction, dropdown: discord.ui.Select
    ) -> None:
        """Drop down menu contains the list of cronjobsb."""
        cronjob_namespace, cronjob_name = dropdown.values[0].split("/")

        new_job_name = await spawn_job(cronjob_namespace, cronjob_name, interaction.message.id)

        self.disable_select()

        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🌬️ Spawned job `{new_job_name}`")


class Jobs(commands.Cog):
    """Commands for working with Kubernetes Jobs & CronJobs."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @commands.hybrid_group(name="cronjob", aliases=["cronjobs", "cj"], invoke_without_command=True)
    async def cronjob(self, ctx: commands.Context) -> None:
        """Commands for working with Kubernetes CronJobs."""
        await ctx.send_help(ctx.command)

    @cronjob.command(name="trigger")
    @app_commands.describe(cronjob="CronJob to trigger as namespace/name (shows a menu if omitted)")
    @app_commands.autocomplete(cronjob=cronjob_autocomplete)
    async def trigger(self, ctx: commands.Context, cronjob: str | None = None) -> None:
        """Command to trigger a Kubernetes cronjob now."""
        await ctx.defer()

        if cronjob is not None:
            namespace, _, cronjob_name = cronjob.partition("/")
            if not cronjob_name:
                await ctx.send(
                    generate_error_message(description="Use the form `namespace/cronjob-name`.")
                )
                return
            suffix = ctx.interaction.id if ctx.interaction else ctx.message.id
            try:
                new_job_name = await spawn_job(namespace, cronjob_name, suffix)
            except ApiException as e:
                description = (
                    "CronJob not found, check the namespace and name."
                    if e.status == HTTPStatus.NOT_FOUND
                    else str(e)
                )
                await ctx.send(generate_error_message(description=description))
                return
            await ctx.send(f"🌬️ Spawned job `{new_job_name}`")
            return

        cronjobs = await jobs.list_cronjobs()

        view = CronJobView(cronjobs)
        await ctx.send(":tools: Pick a CronJob to trigger", view=view)


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add the extension to the bot."""
    await bot.add_cog(Jobs(bot))
