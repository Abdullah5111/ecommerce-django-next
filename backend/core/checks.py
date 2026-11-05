"""Deployment sanity checks.

Without REDIS_URL every process keeps its own cache (rate limits, phone
codes) and channel layer, which is only correct for a single process. That's
fine in dev, so it's a warning for non-DEBUG runs, not an error. It surfaces
twice: as system check core.W001 (runserver, migrate, check --deploy) and as a
log line when the ASGI app starts, because daphne never runs system checks.

An intentional single-process deploy can silence it with
``SILENCED_SYSTEM_CHECKS = ["core.W001"]``.
"""
import logging

from django.conf import settings
from django.core.checks import Warning, register

logger = logging.getLogger(__name__)
CHECK_ID = "core.W001"

REDIS_MISSING = (
    "REDIS_URL is not set while DEBUG is off: the cache (rate limits, phone "
    "verification codes) and the WebSocket channel layer are per-process."
)
REDIS_MISSING_HINT = (
    "Set REDIS_URL before running more than one worker or instance; until then "
    "rate limits multiply by the worker count, phone codes fail across workers "
    "and live updates don't reach users on other workers."
)


def redis_missing_in_production() -> bool:
    return not settings.DEBUG and not settings.REDIS_URL


@register()
def check_redis_configured(app_configs, **kwargs):
    if not redis_missing_in_production():
        return []
    return [Warning(REDIS_MISSING, hint=REDIS_MISSING_HINT, id=CHECK_ID)]


def warn_at_startup() -> None:
    """The same warning as a log line, for servers that skip system checks."""
    if redis_missing_in_production() and CHECK_ID not in settings.SILENCED_SYSTEM_CHECKS:
        logger.warning("%s %s", REDIS_MISSING, REDIS_MISSING_HINT)
