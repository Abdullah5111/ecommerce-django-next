"""The refresh token lives in an httpOnly cookie, never in JS-readable storage.

Login (password or Google) and refresh move the refresh token out of the JSON
body into this cookie; the browser keeps only the short-lived access token, in
memory. Script injected by an XSS bug can't read the cookie, so it can't take
a session away with it.

The cookie is scoped to ``/api/auth/`` so it rides only on the token endpoints.
Those read it only when the request carries ``X-Requested-With``: a custom
header forces a CORS preflight, so another site can't fire them with the
user's cookie.
"""
from django.conf import settings

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/auth/"
CSRF_HEADER = "X-Requested-With"


def move_refresh_to_cookie(response):
    """Take ``refresh`` out of a token response body and set it as the cookie."""
    refresh = response.data.pop("refresh", None) if isinstance(response.data, dict) else None
    if refresh:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            path=COOKIE_PATH,
            httponly=True,
            secure=settings.AUTH_COOKIE_SECURE,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
    return response


def clear_refresh_cookie(response):
    response.delete_cookie(
        REFRESH_COOKIE, path=COOKIE_PATH, samesite=settings.AUTH_COOKIE_SAMESITE
    )
    return response


def refresh_from_request(request):
    """``(token, from_cookie)``: an explicit body token wins (API clients);
    otherwise the cookie, if the request proved it came from our own JS."""
    token = request.data.get("refresh") if hasattr(request.data, "get") else None
    if token:
        return token, False
    if request.headers.get(CSRF_HEADER):
        return request.COOKIES.get(REFRESH_COOKIE), True
    return None, False
