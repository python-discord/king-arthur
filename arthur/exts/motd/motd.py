import base64
import io
from typing import TYPE_CHECKING

from discord import File
from discord.ext.commands import Cog, Context, command
from loguru import logger

from arthur.config import CONFIG
from arthur.exts.motd._motd_crypto import decrypt_motd
from arthur.exts.motd._motd_data import MOTD

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class MessageOfTheDay(Cog):
    """Print the motd securely & safely."""

    def __init__(self, _bot: KingArthurTheTerrible) -> None:
        if CONFIG.motd_key is None:
            logger.error("MOTD key not configured, cannot initialize MessageOfTheDay cog.")
            err = "MOTD key not configured"
            raise ValueError(err)

        logger.info("Decrypting MOTD...")
        encrypted = base64.b64decode(MOTD.replace(b"\n", b""))
        self.png_bytes = decrypt_motd(encrypted, CONFIG.motd_key.get_secret_value())

    @command(name="motd")
    async def motd(self, ctx: Context) -> None:
        """Generate an image representing the message of the day."""
        file = File(io.BytesIO(self.png_bytes), filename="motd.png")
        await ctx.send(file=file)


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    if CONFIG.motd_key is None:
        logger.warning("MOTD key not configured, skipping MessageOfTheDay cog.")
        return
    await bot.add_cog(MessageOfTheDay(bot))
