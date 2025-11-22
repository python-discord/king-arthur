from typing import TYPE_CHECKING

from discord.ext.commands import Cog, Context, command

from arthur.apis.netcup.ssh import rce_as_a_service

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class RemoteCommands(Cog):
    """We love RCE."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @command(name="rce")
    async def rce(self, ctx: Context, *, command: str) -> None:
        """Ed is the standard text editor."""
        if not ctx.guild:
            return
        if not await ctx.bot.is_owner(ctx.author):
            await ctx.message.add_reaction("❌")
            return

        response = await rce_as_a_service(command)

        if not response.stderr and not response.stdout:
            await ctx.send(f"Successfully ran with no output! {response.returncode = }")
            return

        await ctx.send(
            f"{response.returncode = }\n"
            f"stderr:```{response.stderr or '~Empty~'}```\n"
            f"stdout:```{response.stdout or '~Empty~'}```\n"
        )


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(RemoteCommands(bot))
