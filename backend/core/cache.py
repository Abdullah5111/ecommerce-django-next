"""A Redis cache that tolerates Redis being down.

The default cache holds things that can be lost: catalog pages (rebuilt from
the database) and rate-limit counters. When Redis can't be reached, reads
here count as a miss and writes are skipped, so the site keeps working —
rate limits stop limiting until Redis is back, instead of every rate-limited
endpoint (login, register, password reset, tokens) failing with a 500.

Phone verification codes must not get this treatment (a skipped write would
text a code that can never verify): they use the strict ``otp`` alias, the
plain Django RedisCache (accounts/otp_store.py).
"""
import logging
import time

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.redis import RedisCache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# One warning per this many seconds while Redis is down — not one per request.
WARN_EVERY_SECONDS = 60
_last_warning = 0.0


def _warn(operation, exc):
    global _last_warning
    now = time.monotonic()
    if now - _last_warning >= WARN_EVERY_SECONDS:
        _last_warning = now
        logger.warning(
            "Redis cache unavailable (%s: %s); serving uncached and with rate "
            "limits off until it recovers.", operation, exc,
        )


class TolerantRedisCache(RedisCache):
    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except RedisError as exc:
            _warn("get", exc)
            return default

    def get_many(self, keys, version=None):
        try:
            return super().get_many(keys, version)
        except RedisError as exc:
            _warn("get_many", exc)
            return {}

    def has_key(self, key, version=None):
        try:
            return super().has_key(key, version)
        except RedisError as exc:
            _warn("has_key", exc)
            return False

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().set(key, value, timeout, version)
        except RedisError as exc:
            _warn("set", exc)
            return None

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().add(key, value, timeout, version)
        except RedisError as exc:
            _warn("add", exc)
            return False

    def set_many(self, data, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().set_many(data, timeout, version)
        except RedisError as exc:
            _warn("set_many", exc)
            return list(data)  # the keys that failed

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout, version)
        except RedisError as exc:
            _warn("touch", exc)
            return False

    def delete(self, key, version=None):
        try:
            return super().delete(key, version)
        except RedisError as exc:
            _warn("delete", exc)
            return False

    def delete_many(self, keys, version=None):
        try:
            return super().delete_many(keys, version)
        except RedisError as exc:
            _warn("delete_many", exc)

    def incr(self, key, delta=1, version=None):
        try:
            return super().incr(key, delta, version)
        except RedisError as exc:
            _warn("incr", exc)
            # Same as a missing key, so callers take their "not cached" path.
            raise ValueError(f"Key '{key}' not found (cache unavailable)") from exc
