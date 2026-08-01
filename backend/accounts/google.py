"""Google Sign-In: verify a Google Identity Services ID token.

Enabled only when ``GOOGLE_OAUTH_CLIENT_ID`` is set. ``google-auth`` is imported
lazily and verifies the token's signature, audience, and expiry.
"""
from django.conf import settings

ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleAuthError(Exception):
    """Raised when a Google credential is missing, malformed, or untrusted."""


def is_enabled() -> bool:
    return bool(getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", ""))


def client_id() -> str:
    return getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")


def verify_id_token(token: str) -> dict:
    """Verify a Google ID token and return its claims.
    Raises ``GoogleAuthError`` if disabled or the token is invalid/unverified.
    """
    if not is_enabled():
        raise GoogleAuthError("Google sign-in is not configured.")
    if not token:
        raise GoogleAuthError("Missing Google credential.")

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), client_id()
        )
    except Exception as exc:  # invalid signature / audience / expiry
        raise GoogleAuthError("Invalid Google credential.") from exc

    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("Untrusted token issuer.")
    if not claims.get("email"):
        raise GoogleAuthError("Google account has no email.")
    if claims.get("email_verified") is False:
        raise GoogleAuthError("Google email is not verified.")
    return claims
