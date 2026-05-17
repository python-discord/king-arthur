import inspect
import logging
from functools import partial

import loguru
import sentry_sdk
import sentry_sdk.integrations.logging as _sentry_logging
from sentry_sdk.integrations.loguru import LoggingLevels, LoguruIntegration

from arthur.config import CONFIG, GIT_SHA

logger = loguru.logger.opt(colors=True)
logger.opt = partial(logger.opt, colors=True)


class _InterceptHandler(logging.Handler):
    """Intercept standard logging records and forward them to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = loguru.logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find the actual line that logged this message
        # skip loguru internal frames & sentry as it patches the logging module
        _skip = {logging.__file__, _sentry_logging.__file__}
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename in _skip):
            frame = frame.f_back
            depth += 1

        loguru.logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_stdlib_logging() -> None:
    """Route standard library logging through loguru."""
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


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
