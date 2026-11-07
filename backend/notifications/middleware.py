"""WebSocket auth for the browser's socket.

The browser WebSocket API cannot send an Authorization header, so the client
first trades its access token for a one-time ticket (``POST
/api/auth/ws-ticket/``, ``accounts/ws_tickets.py``) and dials ``?ticket=``.
The ticket is used up by the handshake, so the URL a log records is
worthless. Anything invalid becomes AnonymousUser (consumers reject those
with close code 4001).

``?token=<access JWT>`` is still accepted while the frontend moves to
tickets; it puts the token in access logs and goes away next.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from redis.exceptions import RedisError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from accounts import ws_tickets
from accounts.authentication import is_revoked


def _active_user(user_id):
    try:
        user = get_user_model().objects.get(pk=user_id)
    except (get_user_model().DoesNotExist, ValueError, TypeError):
        return None
    return user if user.is_active else None


@database_sync_to_async
def _user_from_token(token):
    try:
        user = _active_user(token["user_id"])
    except KeyError:
        return AnonymousUser()
    if user is None or is_revoked(user, token):
        return AnonymousUser()
    return user


@database_sync_to_async
def _user_from_ticket(ticket):
    try:
        user_id = ws_tickets.consume(ticket)
    except RedisError:
        return AnonymousUser()  # can't check the ticket: refuse, don't guess
    if user_id is None:
        return AnonymousUser()
    return _active_user(user_id) or AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get("query_string", b"").decode())
        ticket = params.get("ticket", [None])[0]
        token = params.get("token", [None])[0]
        if ticket:
            scope["user"] = await _user_from_ticket(ticket)
        elif token:
            try:
                access = AccessToken(token)
            except TokenError:
                access = None
            scope["user"] = await _user_from_token(access) if access else AnonymousUser()
        else:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)
