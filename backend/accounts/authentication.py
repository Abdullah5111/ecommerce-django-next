"""JWT authentication that honours ``User.tokens_valid_after``.

Blacklisting refresh tokens stops a session from renewing, but an access token
already handed out stays valid until it expires (2h). A password reset sets
``tokens_valid_after``; any token issued at or before it is refused here, for
HTTP (DRF) and WebSocket (``notifications.middleware``) alike.
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


def _issued_at(token):
    iat = token.get("iat")
    if iat is not None:
        return int(iat)
    # Tokens without an iat claim: derive it from the expiry.
    lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
    return int(token["exp"] - lifetime)


def is_revoked(user, token) -> bool:
    cutoff = getattr(user, "tokens_valid_after", None)
    if cutoff is None:
        return False
    # iat has one-second resolution, so a token minted in the same second as
    # the reset counts as before it. Nobody signs back in within that second.
    return _issued_at(token) <= int(cutoff.timestamp())


class RevocableJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if is_revoked(user, validated_token):
            raise AuthenticationFailed("Token has been revoked.", code="token_revoked")
        return user
