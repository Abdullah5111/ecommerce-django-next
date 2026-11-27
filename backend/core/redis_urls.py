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


def fail_fast_retry():
    """One immediate retry for a dropped connection, then give up.

    redis-py 8 defaults to 10 retries with exponential backoff, which during an
    outage would stall each cache call far past the connect/read timeouts. The
    cache, phone codes and presence would rather fail in about a second and
    degrade (core/cache.py) or refuse (accounts/otp_store.py).
    """
    from redis.backoff import NoBackoff
    from redis.retry import Retry

    return Retry(NoBackoff(), 1)


def tls_options(url: str, ca_certs: str) -> dict:
    """redis-py connection options for verifying a TLS server.

    Only for ``rediss://`` URLs: redis-py's plain connection rejects the SSL
    keywords outright. Memorystore's in-transit encryption uses its own CA,
    which isn't in the system trust store, so ``ca_certs`` (a PEM path) must
    point at it — without it the TLS handshake fails verification.
    """
    if ca_certs and urlsplit(url).scheme == "rediss":
        return {"ssl_ca_certs": ca_certs}
    return {}
