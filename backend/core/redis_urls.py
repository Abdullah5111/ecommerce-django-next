"""Redis connection URLs, derived from the single ``REDIS_URL`` setting.

The cache and the Channels layer share one Redis but use separate logical
databases: Django's ``cache.clear()`` runs FLUSHDB, which on a shared database
would also drop every live WebSocket group.
"""
from urllib.parse import urlsplit, urlunsplit


def with_db(url: str, db: int) -> str:
    """``url`` pointed at logical database ``db`` (replacing any in its path)."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{db}"))
