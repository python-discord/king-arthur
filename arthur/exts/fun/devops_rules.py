"""The rules all devops members must follow."""

import discord
from discord.ext.commands import Cog, Context, Greedy, MissingRole, group

from arthur.bot import KingArthurTheTerrible
from arthur.config import CONFIG

RULES_URL = (
    "https://raw.githubusercontent.com/python-discord/infra/main/docs/docs/onboarding/rules.md"
)


class Rules(Cog):
    """The rules all devops members must follow."""

    def __init__(self, bot: KingArthurTheTerrible) -> None:
        self.bot = bot
        self.rules: dict

    async def cog_load(self) -> None:
        """Fetch Devops rules from notion of cog load."""
        async with self.bot.http_session.get(RULES_URL) as resp:
            resp.raise_for_status()
            raw_content = await resp.text()
        # Ignore markdown frontmatter
        parsed_content = raw_content.split("---")[-1].strip()
        # Ignore first 4 lines, as they are not the rules
        parsed_content = parsed_content.split("\n")[4:]
        self.rules = {}
        for line in parsed_content:
            number, rule = line.split(".", maxsplit=1)
            self.rules[int(number)] = rule.strip()

    @group(name="rules", aliases=("rule",), invoke_without_command=True)
    async def rules_group(self, ctx: Context, rules: Greedy[int]) -> None:
        """List the requested rule(s), or all of them if not defined."""
        role_ids = {r.id for r in ctx.author.roles}
        if CONFIG.helpers_role not in role_ids:
            raise MissingRole(CONFIG.helpers_role)
        if CONFIG.devops_role not in role_ids:
            rules = [4]

        if rules:
            output_rules = set(rules) & set(self.rules.keys())
        else:
            output_rules = self.rules.keys()

        if not output_rules:
            await ctx.send(f":x: Rule{'s'[: len(rules) ^ 1]} not found.")
            return

        output = "\n".join(
            f"{key}: {value}" for key, value in self.rules.items() if key in output_rules
        )
        await ctx.send(
            embed=discord.Embed(
                title=f"Rule{'s'[: len(output_rules) ^ 1]}",
                description=output,
                colour=discord.Colour.og_blurple(),
                url="https://docs.pydis.wtf/onboarding/rules.html",
            )
        )

    @rules_group.command(name="refresh", aliases=("fetch", "update"))
    async def update_rules(self, ctx: Context) -> None:
        """Re-fetch the list of rules from notion."""
        await self.cog_load()
        await ctx.reply(":+1:")


async def setup(bot: KingArthurTheTerrible) -> None:
    """Add cog to bot."""
    await bot.add_cog(Rules(bot))
