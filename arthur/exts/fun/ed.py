"""Ed is the standard text editor."""

from discord.ext.commands import Cog, Context, command

from arthur.bot import KingArthur


class Ed(Cog):
    """Ed is the standard text editor."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @command(name="ed", help="[-GVhs] [-p string] [file]")
    async def ed(self, ctx: Context) -> None:
        """Ed is the standard text editor."""
        await ctx.send("?")


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(Ed(bot))
