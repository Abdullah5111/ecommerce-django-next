"""Websocket routes — served under the ticket auth middleware by core.asgi.

There is one: ``ws/chat/``, the socket each browser tab opens. It carries chat
and the user's notification pushes (chat/consumers.py).
"""
from chat.routing import websocket_urlpatterns

__all__ = ["websocket_urlpatterns"]
