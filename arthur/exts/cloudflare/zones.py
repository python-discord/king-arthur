"""The zones cog helps with managing Cloudflare zones"""
from typing import Optional

from discord.ext import commands

from arthur.apis.cloudflare import zones
from arthur.bot import KingArthur


class Zones(commands.Cog):
    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @commands.group(name="zones", invoke_without_command=True)
    async def zones(self, ctx: commands.Context) -> None:
        "Commands for working with Cloudflare zones"
        await ctx.send_help(ctx.command)

    @zones.command(name="purge")
    async def purge(self, ctx: commands.Context, zone_name: Optional[str] = "pythondiscord.com"):
        """Command to clear the Cloudflare cache of the specified zone"""
        pydis_zones = await zones.list_zones(zone_name)
        required_id = pydis_zones[zone_name]
        purge_attempt_response = await zones.purge_zone(required_id)

        message = "__Cloudflare cache purge status__\n"

        if purge_attempt_response["success"]:
            message += "Purge status: **Successful** :white_check_mark:\n"
            message += f"Zone purged: **Zone purged: `{zone_name}`"
            return await ctx.send(message)
        else:
            message += "Purge status: **Failed** :x:\n"
            if errors := purge_attempt_response["errors"]:
                message += "__Errors:__\n"
                for error in errors:
                    message += f"**Code**: `{error.code}`\n"
                    message += f"**Message**: {error.message}\n"
            return await ctx.send(message)


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Zones(bot))
