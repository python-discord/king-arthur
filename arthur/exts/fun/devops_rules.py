"""The rules all devops members must follow."""

from typing import TypedDict

import discord
from discord.ext.commands import Cog, Context, Greedy, group

from arthur.bot import KingArthur, logger
from arthur.config import CONFIG

NOTION_API_BASE_URL = "https://api.notion.com/v1"
DEVOPS_RULES_PAGE_CONTENT = (
    f"{NOTION_API_BASE_URL}/blocks/149bc48f-6f79-47af-add8-036f11d4e9a7/children"
)
DISCORD_MARKDOWN_LOOKUP = {
    "bold": "**{}**",
    "italic": "_{}_",
    "strikethrough": "~~{}~~",
    "underline": "__{}__",
}


class NotionAnnotations(TypedDict):
    """The markdown annotations attached to a block of text in Notion."""

    bold: bool
    italic: bool
    strikethrough: bool
    underline: bool


class NotionRichText(TypedDict):
    """A block of text with markdown annotations attached."""

    plain_text: str
    annotations: NotionAnnotations


def notion_block_to_discord_markdown(block: list[NotionRichText]) -> str:
    """Convert the given notion API "block" into Discord markdown text."""
    block_string_parts = []
    for rich_text_part in block:
        block_string_part = rich_text_part["plain_text"]
        for annotation, enabled in rich_text_part["annotations"].items():
            if enabled and annotation in DISCORD_MARKDOWN_LOOKUP:
                block_string_part = DISCORD_MARKDOWN_LOOKUP[annotation].format(block_string_part)
        block_string_parts.append(block_string_part)
    return "".join(block_string_parts)


class Rules(Cog):
    """The rules all devops members must follow."""

    def __init__(self, bot: KingArthur) -> None:
        self.bot = bot
        self.rules: dict

    async def cog_load(self) -> None:
        """Fetch Devops rules from notion of cog load."""
        headers = {
            "Authorization": f"Bearer {CONFIG.notion_api_token}",
            "accept": "application/json",
            "Notion-Version": "2022-06-28",
        }
        async with self.bot.http_session.get(DEVOPS_RULES_PAGE_CONTENT, headers=headers) as resp:
            resp.raise_for_status()
            page_content = await resp.json()

        self.rules = {
            i: notion_block_to_discord_markdown(block["numbered_list_item"]["rich_text"])
            for i, block in enumerate(page_content["results"], 1)
            if block.get("type") == "numbered_list_item"
        }

    @group(name="rules", aliases=("rule",))
    async def rules_group(self, ctx: Context, rules: Greedy[int]) -> None:
        """List the requested rule(s), or all of them if not defined."""
        if rules:
            output_rules = set(rules) & set(self.rules.keys())
        else:
            output_rules = self.rules.keys()

        if not output_rules:
            await ctx.send(f":x: Rule{'s'[:len(rules)^1]} not found.")
            return

        output = "\n".join(
            f"{key}: {value}" for key, value in self.rules.items() if key in output_rules
        )
        await ctx.send(
            embed=discord.Embed(
                title=f"Rule{'s'[:len(output_rules)^1]}",
                description=output,
                colour=discord.Colour.og_blurple(),
                url="https://www.notion.so/pythondiscord/Rules-149bc48f6f7947afadd8036f11d4e9a7",
            )
        )

    @rules_group.command(name="refresh", aliases=("fetch", "update"))
    async def update_rules(self, ctx: Context) -> None:
        """Re-fetch the list of rules from notion."""
        await self.cog_load()


async def setup(bot: KingArthur) -> None:
    """Add cog to bot."""
    if not CONFIG.notion_api_token:
        logger.info(
            f"Not loading {__name__} as env var "
            f"{CONFIG.Config.env_prefix}NOTION_API_TOKEN is not set."
        )
        return
    await bot.add_cog(Rules(bot))
