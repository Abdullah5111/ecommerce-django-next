"""Who is connected to the support chat, for presence dots.

The consumer only needs three answers: did this connection make the user
online (first connection), did closing it make them offline (last one), and
are they online right now (for a staff member who starts watching a thread).
Connections are tracked by channel name rather than counted, so one tab
closing can't be mistaken for another.

Two stores, picked by ``REDIS_URL`` (``presence`` at the bottom):

- ``RedisPresence`` — shared by every worker and instance, so a buyer on one
  worker shows online to staff on another, and closing one of two tabs on
  different workers doesn't report offline.
- ``InMemoryPresence`` — per-process; correct for dev, tests and one worker.
"""
import logging
import time

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# A connection not seen for this long is treated as gone, so a worker that
# dies without running disconnect() can't leave its users "online" for long.
# Clients ping every HEARTBEAT_SECONDS (lib/realtime.ts); two missed pings
# are tolerated.
HEARTBEAT_SECONDS = 30
STALE_AFTER_SECONDS = 3 * HEARTBEAT_SECONDS


class InMemoryPresence:
    """Per-process connection sets: correct for dev, tests and one worker."""

    def __init__(self):
        self._connections: dict[int, set[str]] = {}

    def connect(self, user_id: int, channel_name: str) -> bool:
        """Record a connection; True if it is the user's first (now online)."""
        conns = self._connections.setdefault(user_id, set())
        first = not conns
        conns.add(channel_name)
        return first

    def disconnect(self, user_id: int, channel_name: str) -> bool:
        """Drop a connection; True if it was the user's last (now offline)."""
        conns = self._connections.get(user_id)
        if not conns:
            return False
        conns.discard(channel_name)
        if conns:
            return False
        del self._connections[user_id]
        return True

    def touch(self, user_id: int, channel_name: str) -> None:
        """Heartbeat. A process-local connection can't go stale unseen."""

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def connection_count(self, user_id: int) -> int:
        return len(self._connections.get(user_id, ()))

    def clear(self) -> None:
        """Forget everyone (tests: module state isn't rolled back)."""
        self._connections.clear()


class RedisPresence:
    """One sorted set per user: member = channel name, score = last seen.

    Each operation is a single MULTI/EXEC round trip, so two workers
    connecting the same user at once can't both decide they were "first".
    Stale members are pruned as part of every write. If Redis is unreachable
    presence degrades to "no transition, offline" — the socket still works.
    """

    def __init__(self, url, *, prefix="presence:", stale_after=STALE_AFTER_SECONDS,
                 clock=time.time, connect_timeout=0.5, socket_timeout=1.0):
        import redis

        self._redis = redis.Redis.from_url(
            url, socket_connect_timeout=connect_timeout, socket_timeout=socket_timeout
        )
        self._prefix = prefix
        self._stale_after = stale_after
        self._clock = clock

    def _key(self, user_id):
        return f"{self._prefix}{user_id}"

    def _cutoff(self, now):
        return now - self._stale_after

    def connect(self, user_id: int, channel_name: str) -> bool:
        key, now = self._key(user_id), self._clock()
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, "-inf", self._cutoff(now))
            pipe.zcard(key)
            pipe.zadd(key, {channel_name: now})
            # The set expires once every member would be stale anyway.
            pipe.expire(key, int(self._stale_after) + 60)
            _, before, _, _ = pipe.execute()
        except RedisError:
            logger.warning("Presence store unavailable (connect)", exc_info=True)
            return False
        return before == 0

    def disconnect(self, user_id: int, channel_name: str) -> bool:
        key, now = self._key(user_id), self._clock()
        try:
            pipe = self._redis.pipeline()
            pipe.zrem(key, channel_name)
            pipe.zremrangebyscore(key, "-inf", self._cutoff(now))
            pipe.zcard(key)
            removed, _, after = pipe.execute()
        except RedisError:
            logger.warning("Presence store unavailable (disconnect)", exc_info=True)
            return False
        return bool(removed) and after == 0

    def touch(self, user_id: int, channel_name: str) -> None:
        """Heartbeat: refresh a live connection's last-seen time. XX only
        updates members already present, so a ping can't resurrect a
        connection that was pruned or already disconnected."""
        key = self._key(user_id)
        try:
            pipe = self._redis.pipeline()
            pipe.zadd(key, {channel_name: self._clock()}, xx=True)
            pipe.expire(key, int(self._stale_after) + 60)
            pipe.execute()
        except RedisError:
            logger.warning("Presence store unavailable (touch)", exc_info=True)

    def is_online(self, user_id: int) -> bool:
        return self.connection_count(user_id) > 0

    def connection_count(self, user_id: int) -> int:
        try:
            return self._redis.zcount(
                self._key(user_id), self._cutoff(self._clock()), "+inf"
            )
        except RedisError:
            logger.warning("Presence store unavailable (read)", exc_info=True)
            return 0

    def clear(self) -> None:
        """Forget everyone under this prefix (tests)."""
        keys = list(self._redis.scan_iter(match=f"{self._prefix}*"))
        if keys:
            self._redis.delete(*keys)


def _build_store():
    from django.conf import settings

    from core.redis_urls import with_db

    if not settings.REDIS_URL:
        return InMemoryPresence()
    # The channel layer's database: presence is live socket state, and the
    # cache database gets FLUSHDB'd by cache.clear().
    return RedisPresence(
        with_db(settings.REDIS_URL, settings.REDIS_CHANNELS_DB),
        connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
    )


presence = _build_store()
