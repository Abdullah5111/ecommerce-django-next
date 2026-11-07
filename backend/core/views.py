import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import caches
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health(request):
    """Lightweight liveness probe for deploy/uptime checks. Public, no DB hit."""
    return JsonResponse({"status": "ok"})


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _check_cache():
    # Any round trip proves the server answers; a missing key is fine. The
    # strict alias: the default one swallows Redis errors (core/cache.py) and
    # would report "ok" with Redis down.
    caches["otp"].get("ready-probe")


def _check_channel_layer():
    # group_send reads the group's member set from Redis even when it is
    # empty, so this exercises the real fan-out path without reaching anyone.
    async_to_sync(get_channel_layer().group_send)("ready-probe", {"type": "ready.probe"})


def ready(request):
    """Readiness probe: can this instance serve traffic? 200 when its
    dependencies answer, 503 naming the ones that don't.

    Unlike ``health`` it touches the database and, when ``REDIS_URL`` is set,
    the Redis cache and channel layer (each bounded by the connection
    timeouts in settings). Failure details are logged, not returned — the
    endpoint is public.
    """
    probes = {"database": _check_database}
    if settings.REDIS_URL:
        probes["cache"] = _check_cache
        probes["channel_layer"] = _check_channel_layer

    checks = {}
    for name, probe in probes.items():
        try:
            probe()
        except Exception:
            logger.exception("Readiness check failed: %s", name)
            checks[name] = "unavailable"
        else:
            checks[name] = "ok"

    ok = all(state == "ok" for state in checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status=200 if ok else 503,
    )
