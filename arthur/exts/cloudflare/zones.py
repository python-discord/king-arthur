"""The zones cog helps with managing Cloudflare zones."""
import discord
from discord.ext import commands

from arthur.apis.cloudflare import zones
from arthur.bot import KingArthur
from arthur.config import CONFIG
from arthur.utils import generate_error_message


class ZonesView(discord.ui.View):
    """This view allows users to select and purge the zones specified."""

    def __init__(self, domains: dict[str, str]) -> None:
        super().__init__()

        self.domains = domains

        for domain, zone_id in self.domains.items():
            self.children[0].add_option(label=domain, value=domain, description=zone_id, emoji="🌐")

    def disable_select(self) -> None:
        """Disable the select button."""
        self.children[0].disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure the user has the DevOps role."""
        return CONFIG.devops_role in [r.id for r in interaction.user.roles]

    @discord.ui.select(
        placeholder="Select a zone to purge...",
    )
    async def select_zones(
        self, dropdown: discord.ui.Select, interaction: discord.Interaction
    ) -> None:
        """Drop down menu contains the list of zones."""
        zone_name = dropdown.values[0]

        required_id = self.domains[zone_name]
        purge_attempt_response = await zones.purge_zone(required_id)
        if purge_attempt_response["success"]:
            message = ":white_check_mark:"
            message += " **Cache cleared!** "
            message += f"The Cloudflare cache for `{zone_name}` was cleared."
        else:
            description_content = f"The cache for `{zone_name}` couldn't be cleared.\n"
            if errors := purge_attempt_response["errors"]:
                for error in errors:
                    description_content += f"`{error['code']}`: {error['message']}\n"
            message = generate_error_message(description=description_content, emote=":x:")

        self.disable_select()

        await interaction.edit_original_message(view=self)
        await interaction.response.send_message(message)


class Zones(commands.Cog):
    """Commands for working with Cloudflare zones."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @commands.group(name="zones", invoke_without_command=True)
    async def zones(self, ctx: commands.Context) -> None:
        """Commands for working with Cloudflare zones."""
        await ctx.send_help(ctx.command)

    @zones.command(name="purge")
    async def purge(self, ctx: commands.Context) -> None:
        """Command to clear the Cloudflare cache of the specified zone."""
        cf_zones = await zones.list_zones()

        view = ZonesView(cf_zones)
        await ctx.send(":cloud: Pick which zone(s) that should have their cache purged", view=view)


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Zones(bot))
