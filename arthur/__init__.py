"""King Arthur is Python Discord's DevOps utility bot."""

import asyncio
import os
from functools import partial
from typing import TYPE_CHECKING

import loguru
from pydis_core.utils import apply_monkey_patches

if TYPE_CHECKING:
    from arthur.bot import KingArthur

logger = loguru.logger.opt(colors=True)
logger.opt = partial(logger.opt, colors=True)

apply_monkey_patches()

# On Windows, the selector event loop is required for aiodns.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

instance: "KingArthur" = None  # Global Bot instance.
