from functools import partial

import loguru
import sentry_sdk
from sentry_sdk.integrations.loguru import LoggingLevels, LoguruIntegration

from arthur.config import CONFIG, GIT_SHA

logger = loguru.logger.opt(colors=True)
logger.opt = partial(logger.opt, colors=True)


def setup_sentry() -> None:
    """Set up the Sentry logging integrations."""
    loguru_integration = LoguruIntegration(
        level=LoggingLevels.DEBUG.value, event_level=LoggingLevels.WARNING.value
    )

    sentry_sdk.init(
        dsn=CONFIG.sentry_dsn,
        integrations=[
            loguru_integration,
        ],
        release=f"king-arthur@{GIT_SHA}",
        traces_sample_rate=0.5,
        profiles_sample_rate=0.5,
    )
