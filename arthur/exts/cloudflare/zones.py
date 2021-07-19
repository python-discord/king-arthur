"""The zones cog helps with managing Cloudflare zones"""
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
    async def purge(self, ctx: commands.Context, zone_name: str = "pythondiscord.com"):
        pass