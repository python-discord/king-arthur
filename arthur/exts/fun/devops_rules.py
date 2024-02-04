"""The rules all devops members must follow."""

import discord
from discord.ext.commands import Cog, Context, Greedy, group

from arthur.bot import KingArthur

RULES_URL = "https://raw.githubusercontent.com/python-discord/infra/main/docs/onboarding/rules.md"


class Rules(Cog):
    """The rules all devops members must follow."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.rules: dict

    async def cog_load(self) -> None:
        """Fetch Devops rules from notion of cog load."""
        async with self.bot.http_session.get(RULES_URL) as resp:
            resp.raise_for_status()
            raw_content = await resp.text()
        parsed_content = raw_content.split("---")[-1].strip().split("\n")

        self.rules = {}
        for line in parsed_content:
            number, rule = line.split(".", maxsplit=1)
            self.rules[int(number)] = rule.strip()

    @group(name="rules", aliases=("rule",))
    async def rules_group(self, ctx: Context, rules: Greedy[int]) -> None:
        """List the requested rule(s), or all of them if not defined."""
        if rules:
            output_rules = set(rules) & set(self.rules.keys())
        else:
            output_rules = self.rules.keys()

        if not output_rules:
            await ctx.send(f":x: Rule{'s'[:len(rules) ^ 1]} not found.")
            return

        output = "\n".join(
            f"{key}: {value}" for key, value in self.rules.items() if key in output_rules
        )
        await ctx.send(
            embed=discord.Embed(
                title=f"Rule{'s'[:len(output_rules) ^ 1]}",
                description=output,
                colour=discord.Colour.og_blurple(),
                url="https://www.notion.so/pythondiscord/Rules-149bc48f6f7947afadd8036f11d4e9a7",
            )
        )

    @rules_group.command(name="refresh", aliases=("fetch", "update"))
    async def update_rules(self, _: Context) -> None:
        """Re-fetch the list of rules from notion."""
        await self.cog_load()


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    await bot.add_cog(Rules(bot))
