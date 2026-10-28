"""WebSocket auth: JWT access token from the ``?token=`` query param.

The browser WebSocket API cannot send an Authorization header, so the
documented Channels + SimpleJWT pattern is a query-param token. It validates
signature + expiry; anything invalid becomes AnonymousUser (consumers reject
those with close code 4001). Caveat: the token is visible in server access
logs — swap for one-time connect tickets if this is ever exposed publicly.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from accounts.authentication import is_revoked


@database_sync_to_async
def _load_user(token):
    try:
        user = get_user_model().objects.get(pk=token["user_id"])
    except (get_user_model().DoesNotExist, KeyError, ValueError, TypeError):
        return AnonymousUser()
    if not user.is_active or is_revoked(user, token):
        return AnonymousUser()
    return user


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        params = parse_qs(scope.get("query_string", b"").decode())
        token = params.get("token", [None])[0]
        if token:
            try:
                access = AccessToken(token)
            except TokenError:
                access = None
            scope["user"] = await _load_user(access) if access else AnonymousUser()
        else:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)
