"""King Arthur is Python Discord's DevOps utility bot."""

import asyncio
import os
from typing import TYPE_CHECKING

from pydis_core.utils import apply_monkey_patches

if TYPE_CHECKING:
    from arthur.bot import KingArthurTheTerrible


apply_monkey_patches()

# On Windows, the selector event loop is required for aiodns.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

instance: KingArthurTheTerrible = None  # Global Bot instance.
