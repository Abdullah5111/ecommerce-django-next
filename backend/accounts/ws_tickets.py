"""One-time tickets for opening a WebSocket.

Browsers can't send an Authorization header on a WebSocket handshake, so the
socket used to carry the JWT access token in its URL (``?token=``), where it
lands in server and proxy access logs. Instead the client trades its access
token for a ticket over REST and dials ``?ticket=``: the ticket is random,
lives 30 seconds, and is used up by the first handshake that presents it, so
a logged URL is worthless.

Tickets live on the strict ``otp`` cache alias: if Redis is down, issuing one
fails (503) rather than a skipped write handing out a ticket that can never
work.
"""
import secrets

from django.core.cache import caches
from django.utils.connection import ConnectionProxy

TICKET_TTL_SECONDS = 30

_store = ConnectionProxy(caches, "otp")


def _key(ticket):
    return f"ws-ticket:{ticket}"


def issue(user) -> str:
    """A fresh single-use ticket for ``user``. Raises on a cache (Redis) error."""
    ticket = secrets.token_urlsafe(32)
    _store.set(_key(ticket), user.pk, TICKET_TTL_SECONDS)
    return ticket


def consume(ticket):
    """The user id a ticket was issued for, or None if it is unknown, expired
    or already used. Only one caller can win: the read counts only if this
    caller's delete is the one that removed the key."""
    if not ticket or len(ticket) > 100:
        return None
    key = _key(ticket)
    user_id = _store.get(key)
    if user_id is None or not _store.delete(key):
        return None
    return user_id
