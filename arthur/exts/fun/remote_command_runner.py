import smtplib
from typing import TYPE_CHECKING

from discord.ext.commands import Cog, Context, command

from arthur.apis.directory.ldap import find_by_discord_id
from arthur.apis.email import send_email
from arthur.apis.netcup.ssh import rce_as_a_service

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


MAX_MESSAGE_LENGTH = 2000


def _format_discord_response(returncode: int, stderr: str, stdout: str) -> str:
    """Format command output as a Discord message."""
    return (
        f"returncode={returncode}\n"
        f"stderr:```{stderr or '~Empty~'}```\n"
        f"stdout:```{stdout or '~Empty~'}```\n"
    )


def _format_email_response(command: str, returncode: int, stderr: str, stdout: str) -> str:
    """Format command output as plain text for email delivery."""
    return (
        "King Arthur remote command output\n\n"
        f"command: {command}\n"
        f"returncode: {returncode}\n\n"
        "stderr:\n"
        f"{stderr or '~Empty~'}\n\n"
        "stdout:\n"
        f"{stdout or '~Empty~'}\n"
    )


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
            await ctx.send(f"Successfully ran with no output! returncode={response.returncode}")
            return

        discord_message = _format_discord_response(
            response.returncode,
            response.stderr,
            response.stdout,
        )

        if len(discord_message) <= MAX_MESSAGE_LENGTH:
            await ctx.send(discord_message)
            return

        ldap_user = await find_by_discord_id(ctx.author.id)
        if not ldap_user:
            await ctx.send(
                ":x: Output is too long for Discord and no LDAP user was found for your Discord ID."
            )
            return

        recipient = f"{ldap_user.uid}@pydis.wtf"

        try:
            await send_email(
                recipient=recipient,
                subject=f"King Arthur command output (returncode={response.returncode})",
                body=_format_email_response(
                    command,
                    response.returncode,
                    response.stderr,
                    response.stdout,
                ),
            )
        except RuntimeError, smtplib.SMTPException, OSError:
            await ctx.send(":x: Output is too long for Discord and sending it by e-mail failed.")
            return

        await ctx.send(
            f":mailbox_with_mail: Output was too long for Discord, so it was sent to `{recipient}`."
        )


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(RemoteCommands(bot))
