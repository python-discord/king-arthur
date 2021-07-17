"""King Arthur is Python Discord's DevOps utility bot."""
from functools import partial

import loguru

logger = loguru.logger.opt(colors=True)
logger.opt = partial(logger.opt, colors=True)
