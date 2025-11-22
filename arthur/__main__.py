"""Entrypoint for King Arthur The Terrible."""

import asyncio

import aiohttp
import aiohttp.http
import discord
from discord.ext import commands

import arthur
from arthur.bot import KingArthurTheTerrible
from arthur.config import CONFIG
from arthur.log import logger, setup_sentry


async def main() -> None:
    """Entry async method for starting the bot."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.dm_typing = False
    intents.dm_reactions = False
    intents.invites = False
    intents.webhooks = False
    intents.integrations = False
    user_agent = (
        f"github.com/python-discord/king-arthur the terrible ({aiohttp.http.SERVER_SOFTWARE})"
    )

    async with aiohttp.ClientSession(headers={"User-Agent": user_agent}) as session:
        arthur.instance = KingArthurTheTerrible(
            guild_id=CONFIG.guild_id,
            http_session=session,
            command_prefix=commands.when_mentioned_or(*CONFIG.prefixes),
            allowed_roles=(CONFIG.devops_role,),
            case_insensitive=True,
            intents=intents,
            max_messages=100,
        )
        async with arthur.instance as bot:
            await bot.start(CONFIG.token.get_secret_value())


setup_sentry()

with logger.catch():
    asyncio.run(main())
