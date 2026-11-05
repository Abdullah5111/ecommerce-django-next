"""Who is connected to the support chat, for presence dots.

The consumer only needs three answers: did this connection make the user
online (first connection), did closing it make them offline (last one), and
are they online right now (for a staff member who starts watching a thread).
Connections are tracked by channel name rather than counted, so one tab
closing can't be mistaken for another.

ponytail: the only store is in process memory, so with several workers each
one sees only its own connections — a buyer connected to worker A looks
offline to staff on worker B, and closing one of two tabs on different workers
reports offline. Redis carries the *broadcasts* across workers (channel
layer), not this state. A Redis-backed store with the same interface is the
fix (planned as task 1.2).
"""


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

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    def connection_count(self, user_id: int) -> int:
        return len(self._connections.get(user_id, ()))

    def clear(self) -> None:
        """Forget everyone (tests: module state isn't rolled back)."""
        self._connections.clear()


presence = InMemoryPresence()
