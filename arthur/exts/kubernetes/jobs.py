"""The zones cog helps with managing Cloudflare zones."""

import discord
from discord.ext import commands
from kubernetes_asyncio.client.models import V1CronJobList

from arthur.apis.kubernetes import jobs
from arthur.bot import KingArthurTheTerrible
from arthur.config import CONFIG


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

        cronjob = await jobs.get_cronjob(cronjob_namespace, cronjob_name)

        new_job = await jobs.create_job(
            cronjob_namespace,
            f"{cronjob_name}-{interaction.message.id}",
            cronjob.spec.job_template.spec,
        )

        self.disable_select()

        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🌬️ Spawned job `{new_job.metadata.name}`")


class Jobs(commands.Cog):
    """Commands for working with Kubernetes Jobs & CronJobs."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @commands.group(name="cronjob", aliases=["cronjobs", "cj"], invoke_without_command=True)
    async def cronjob(self, ctx: commands.Context) -> None:
        """Commands for working with Kubernetes CronJobs."""
        await ctx.send_help(ctx.command)

    @cronjob.command(name="trigger")
    async def trigger(self, ctx: commands.Context) -> None:
        """Command to trigger a Kubernetes cronjob now."""
        cronjobs = await jobs.list_cronjobs()

        view = CronJobView(cronjobs)
        await ctx.send(":tools: Pick a CronJob to trigger", view=view)


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add the extension to the bot."""
    await bot.add_cog(Jobs(bot))
