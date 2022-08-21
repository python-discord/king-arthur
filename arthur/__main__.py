"""Entrypoint for King Arthur."""
import asyncio

import aiohttp
import discord
from discord.ext import commands

import arthur
from arthur.bot import KingArthur
from arthur.config import CONFIG


async def main() -> None:
    """Entry async method for starting the bot."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.dm_typing = False
    intents.dm_reactions = False
    intents.invites = False
    intents.webhooks = False
    intents.integrations = False

    async with aiohttp.ClientSession() as session:
        arthur.instance = KingArthur(
            guild_id=CONFIG.guild_id,
            http_session=session,
            command_prefix=commands.when_mentioned_or(*CONFIG.prefixes),
            allowed_roles=(CONFIG.devops_role,),
            case_insensitive=True,
            intents=intents,
        )
        async with arthur.instance as bot:
            await bot.start(CONFIG.token)


with arthur.logger.catch():
    asyncio.run(main())
