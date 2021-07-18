"""The Certificates cog helps with managing TLS certificates."""
from datetime import datetime
from textwrap import dedent

from discord import Embed
from discord.ext import commands

from arthur.apis.kubernetes import certificates
from arthur.bot import KingArthur
from arthur.utils import datetime_to_discord


class Certificates(commands.Cog):
    """Commands for working with TLS certificates."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot

    @commands.group(name="certificates", aliases=["certs"], invoke_without_command=True)
    async def certificates(self, ctx: commands.Context) -> None:
        """Commands for working with TLS certificates."""
        await ctx.send_help(ctx.command)

    @certificates.command(name="list", aliases=["ls"])
    async def certificates_list(self, ctx: commands.Context, namespace: str = "default") -> None:
        """List TLS certificates in the selected namespace (defaults to default)."""
        certs = certificates.list_certificates(namespace)

        return_embed = Embed(title=f"Certificates in namespace {namespace}")

        for certificate in certs["items"]:
            expiry = datetime.fromisoformat(
                certificate["status"]["notAfter"].rstrip("Z") + "+00:00"
            )
            renews = datetime.fromisoformat(
                certificate["status"]["renewalTime"].rstrip("Z") + "+00:00"
            )
            body = dedent(
                f"""
                **Subjects:** {", ".join(certificate["spec"]["dnsNames"])}
                **Issuer:** {certificate["spec"]["issuerRef"]["name"]}
                **Status:** {certificate["status"]["conditions"][0]["message"]}
                **Expires:** {datetime_to_discord(expiry)} ({datetime_to_discord(expiry, "R")})
                **Renews:** {datetime_to_discord(renews)} ({datetime_to_discord(renews, "R")})
                """
            )

            return_embed.add_field(name=certificate["metadata"]["name"], value=body.strip())

        await ctx.send(embed=return_embed)


def setup(bot: KingArthur) -> None:
    """Add the extension to the bot."""
    bot.add_cog(Certificates(bot))
