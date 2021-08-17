"""The zones cog helps with managing Cloudflare zones."""
from typing import Optional

import discord
from discord.ext import commands

from arthur.apis.cloudflare import zones
from arthur.bot import KingArthur
from arthur.utils import generate_error_message


class ZonesDropdown(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(label="pythondiscord.com", emoji="🌐", default=True),
            discord.SelectOption(label="pythondiscord.org", emoji="🌐"),
            discord.SelectOption(label="pydis.com", emoji="🌐"),
            discord.SelectOption(label="pydis.org", emoji="🌐")
        ]

        super().__init__(
            placeholder="Select the zone which should be purged...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        zone_name = self.values[0]
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


class ZonesView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.add_item(ZonesDropdown())


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
        await ctx.send("Pick which zone's cache to purge:", view=view)


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Zones(bot))
