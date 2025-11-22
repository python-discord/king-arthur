import random
from typing import NamedTuple, TYPE_CHECKING

import aiohttp
from bs4 import BeautifulSoup
from discord.ext import commands

from arthur.log import logger

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


class Quote(NamedTuple):
    """A data structure to hold quotes and their source."""

    text: str
    source: str | None

    def __str__(self):
        return f"{self.text}\n-- {self.source}"


class QuotesCog(commands.Cog):
    """A cog that sends programming quotes."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot
        self.quotes = []

    async def cog_load(self) -> None:
        """Fetch the quotes to be used."""
        try:
            async with self.bot.http_session.get(
                "http://quotes.cat-v.org/programming/"
            ) as response:
                content = await response.content.read()
        except aiohttp.ClientResponseError:
            logger.exception("Couldn't fetch programming quotes.")
            return

        soup = BeautifulSoup(content, "html.parser")
        prev_text = None

        for item in soup.article.find_all("p"):
            text = item.get_text().replace("\xa0", "")

            if prev_text is not None:
                if text.startswith("—"):
                    self.quotes.append(Quote(text=prev_text, source=text.removeprefix("— ")))
                elif not prev_text.startswith("—"):
                    self.quotes.append(Quote(text=prev_text, source=None))

            prev_text = text

    @commands.command(name="quote")
    async def quote(self, ctx: commands.Context) -> None:
        """Send a random programming quote."""
        if not self.quotes:
            await ctx.reply(":x: Couldn't fetch quotes, try reloading the cog.")
            return

        quote = random.choice(self.quotes)
        await ctx.reply(str(quote))


async def setup(bot: KingArthurTheTerrible) -> None:
    """Load the QuotesCog."""
    await bot.add_cog(QuotesCog(bot))
