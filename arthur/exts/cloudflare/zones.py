"""The zones cog helps with managing Cloudflare zones."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from arthur.apis.cloudflare import zones
from arthur.autocomplete import zone_autocomplete
from arthur.config import CONFIG
from arthur.log import logger
from arthur.utils import generate_error_message

if TYPE_CHECKING:
    import aiohttp

    from arthur.bot import KingArthurTheTerrible


async def purge_zone_message(session: aiohttp.ClientSession, zone_id: str, zone_name: str) -> str:
    """Purge a zone's cache, returning the message describing the outcome."""
    purge_attempt_response = await zones.purge_zone(session, zone_id)
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
    return message


class ZonesView(discord.ui.View):
    """This view allows users to select and purge the zones specified."""

    def __init__(self, domains: dict[str, str], session: aiohttp.ClientSession) -> None:
        super().__init__()

        self.domains = domains
        self.session = session

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
        self, interaction: discord.Interaction, dropdown: discord.ui.Select
    ) -> None:
        """Drop down menu contains the list of zones."""
        zone_name = dropdown.values[0]

        message = await purge_zone_message(self.session, self.domains[zone_name], zone_name)

        self.disable_select()

        await interaction.message.edit(view=self)
        await interaction.response.send_message(message)


class Zones(commands.Cog):
    """Commands for working with Cloudflare zones."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @commands.hybrid_group(name="zones")
    async def zones(self, ctx: commands.Context) -> None:
        """Commands for working with Cloudflare zones."""
        await ctx.send_help(ctx.command)

    @zones.command(name="purge")
    @app_commands.describe(zone="Zone to purge (shows a menu if omitted)")
    @app_commands.autocomplete(zone=zone_autocomplete)
    async def purge(self, ctx: commands.Context, zone: str | None = None) -> None:
        """Command to clear the Cloudflare cache of the specified zone."""
        await ctx.defer()

        if zone is not None:
            cf_zones = await zones.list_zones(self.bot.http_session, zone)
            if zone not in cf_zones:
                await ctx.send(generate_error_message(description=f"Zone `{zone}` not found."))
                return
            await ctx.send(await purge_zone_message(self.bot.http_session, cf_zones[zone], zone))
            return

        cf_zones = await zones.list_zones(self.bot.http_session)

        view = ZonesView(cf_zones, self.bot.http_session)
        await ctx.send(":cloud: Pick which zone(s) that should have their cache purged", view=view)


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add the extension to the bot."""
    if not CONFIG.cloudflare_token:
        logger.warning("Not loading Cloudflare Zone cog as cloudflare_token env var is not set.")
        return
    await bot.add_cog(Zones(bot))
