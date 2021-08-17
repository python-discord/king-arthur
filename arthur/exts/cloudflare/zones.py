"""The zones cog helps with managing Cloudflare zones."""
import discord
from discord.ext import commands

from arthur.apis.cloudflare import zones
from arthur.bot import KingArthur
from arthur.utils import generate_error_message


class ZonesView(discord.ui.View):
    """This view allows users to select and purge the zones specified."""
    OPTIONS = [
        discord.SelectOption(label="pythondiscord.com", emoji="🌐"),
        discord.SelectOption(label="pythondiscord.org", emoji="🌐"),
        discord.SelectOption(label="pydis.com", emoji="🌐"),
        discord.SelectOption(label="pydis.org", emoji="🌐")
    ]

    def __init__(self) -> None:
        super().__init__()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return KingArthur._is_devops(interaction)

    @discord.ui.select(
        placeholder="The zone(s) which should be purged...",
        min_values=1,
        max_values=4,
        options=OPTIONS,
        # This is needed in order to identify the drop down later on
        # because discord.Item.type is NotImplemented
        custom_id="select"
    )
    async def select_zones(
        self, dropdown: discord.ui.Select,
        interaction: discord.Interaction
    ) -> None:
        """The drop down menu containing the list of zones."""
        pass

    @discord.ui.button(label="Purge zones!", style=discord.ButtonStyle.primary)
    async def purge_zones(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """The button that actually purges the zones."""
        for zone_name in [child for child in self.children if child._provided_custom_id][0].values:
            pydis_zones = await zones.list_zones(zone_name)
            required_id = pydis_zones[zone_name]
            purge_attempt_response = await zones.purge_zone(required_id)
            if purge_attempt_response["success"]:
                message = ":white_check_mark:"
                message += f" **Cache cleared!** The Cloudflare cache for `{zone_name}` was cleared."
            else:
                description_content = f"The cache for `{zone_name}` couldn't be cleared.\n"
                if errors := purge_attempt_response["errors"]:
                    for error in errors:
                        description_content += f"`{error['code']}`: {error['message']}\n"
                message = generate_error_message(description=description_content, emote=":x:")
            await interaction.response.send(message)


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
        view = ZonesView()
        await ctx.send(
            "Pick which zone(s) that should have their cache purged :cloud_lightning:",
            view=view
        )


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Zones(bot))
