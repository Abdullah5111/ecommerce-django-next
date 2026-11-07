"""WebSocket auth for the browser's socket: one-time tickets only.

The browser WebSocket API cannot send an Authorization header, so the client
first trades its access token for a one-time ticket (``POST
/api/auth/ws-ticket/``, ``accounts/ws_tickets.py``) and dials ``?ticket=``.
The ticket is used up by the handshake, so the URL a log records is
worthless. Token revocation (password reset) is enforced when the ticket is
issued, by the API's normal JWT authentication.

Anything else — no ticket, an unknown or used one, a deactivated user, or the
retired ``?token=<JWT>`` form — becomes AnonymousUser, which the consumers
reject with close code 4001.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from redis.exceptions import RedisError

from accounts import ws_tickets


@database_sync_to_async
def _user_from_ticket(ticket):
    try:
        user_id = ws_tickets.consume(ticket)
    except RedisError:
        return AnonymousUser()  # can't check the ticket: refuse, don't guess
    if user_id is None:
        return AnonymousUser()
    try:
        user = get_user_model().objects.get(pk=user_id)
    except (get_user_model().DoesNotExist, ValueError, TypeError):
        return AnonymousUser()
    return user if user.is_active else AnonymousUser()


class TicketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get("query_string", b"").decode())
        ticket = params.get("ticket", [None])[0]
        scope["user"] = await _user_from_ticket(ticket) if ticket else AnonymousUser()
        return await super().__call__(scope, receive, send)
