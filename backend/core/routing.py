"""Aggregated websocket routes — served under the shared JWT auth middleware
by core.asgi."""
from chat.routing import websocket_urlpatterns as chat_routes
from notifications.routing import websocket_urlpatterns as notification_routes

websocket_urlpatterns = notification_routes + chat_routes
