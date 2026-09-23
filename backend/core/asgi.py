import os

from django.conf import settings

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
# Initialize Django (app registry) before importing anything that touches models.
django_asgi_app = get_asgi_application()

from urllib.parse import urlparse

from channels.generic.websocket import WebsocketDenier
from channels.routing import ProtocolTypeRouter, URLRouter
from django.http.request import is_same_domain

from core.routing import websocket_urlpatterns
from notifications.middleware import JWTAuthMiddleware


class SameSiteOriginValidator:
    """Reject cross-site browser origins; allow origin-less handshakes.

    Channels' AllowedHostsOriginValidator denies any handshake without an
    Origin header unless ALLOWED_HOSTS contains "*", and matches full origins
    (scheme://host:port) — locking out non-browser clients and breaking dev's
    app-on-8000 / frontend-on-3000 pairing. Socket auth here is the explicit
    JWT query token (no ambient credentials), so a missing Origin header is
    not a CSRF vector: non-browser clients pass; a browser-supplied Origin
    must still have its host in ALLOWED_HOSTS.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        origin = None
        for name, value in scope.get("headers", []):
            if name == b"origin":
                origin = value.decode("latin1")
                break
        if origin is not None:
            host = urlparse(origin).hostname
            if not host or not any(
                is_same_domain(host, pattern) for pattern in settings.ALLOWED_HOSTS
            ):
                denier = WebsocketDenier()
                return await denier(scope, receive, send)
        return await self.inner(scope, receive, send)


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": SameSiteOriginValidator(
            JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
        ),
    }
)
