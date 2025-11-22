"""The Certificates cog helps with managing TLS certificates."""

from textwrap import dedent

from discord.ext import commands
from tabulate import tabulate

from arthur.apis.kubernetes import certificates
from arthur.bot import KingArthurTheTerrible


class Certificates(commands.Cog):
    """Commands for working with TLS certificates."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot

    @commands.group(name="certificates", aliases=["certs"], invoke_without_command=True)
    async def certificates(self, ctx: commands.Context) -> None:
        """Commands for working with TLS certificates."""
        await ctx.send_help(ctx.command)

    @certificates.command(name="list", aliases=["ls"])
    async def certificates_list(self, ctx: commands.Context, namespace: str = "default") -> None:
        """List TLS certificates in the selected namespace (defaults to default)."""
        certs = await certificates.list_certificates(namespace)

        table_data = [
            [
                certificate["metadata"]["name"],
                ", ".join(certificate["spec"]["dnsNames"]),
                certificate["spec"]["issuerRef"]["name"],
                certificate["status"]["conditions"][0]["message"],
            ]
            for certificate in certs["items"]
        ]

        table = tabulate(
            table_data, headers=["Name", "DNS Names", "Issuer", "Status"], tablefmt="psql"
        )

        return_message = dedent("""
            **Certificates in namespace `{0}`**
            ```
            {1}
            ```
            """)

        await ctx.send(return_message.format(namespace, table))


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add the extension to the bot."""
    await bot.add_cog(Certificates(bot))
