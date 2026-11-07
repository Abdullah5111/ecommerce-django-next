"""Customer ↔ store support chat over a WebSocket.

This is the one WebSocket each browser tab opens (frontend/lib/realtime.ts):
it carries chat and the user's notification pushes. Groups: ``chat_u_<customer_id>``
(buyers join their own at connect; staff join by watching — membership is the
authorization), a shared ``chat_staff`` inbox feed, and ``user_<id>`` for
notifications. Messages are created over REST; the socket
carries message broadcasts plus ephemeral typing / read receipts / presence.

Presence (who is online) is tracked by chat/presence.py, which is per-process
even when REDIS_URL is set: Redis carries the broadcasts, not the state. See
that module. Staff presence only reaches a buyer while that staff member is
watching their thread.
"""
import json
import time

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.db.models import Q
from django.utils import timezone

from notifications.consumers import user_group

from .models import ChatThread
from .presence import presence

STAFF_GROUP = "chat_staff"


def thread_group(user_id):
    """Group name for a customer's thread — keyed by user id, so it exists
    (and is joinable) even before the ChatThread row does."""
    return f"chat_u_{user_id}"


# Minimum gap between accepted client frames. Legit clients send typing at
# most every 2.5s; this stops a hostile client from turning the socket into a
# broadcast amplifier. A dropped read self-heals on the next read/resync.
MIN_FRAME_SECONDS = 0.2


def _safe_uid(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0  # never a real id — handlers no-op on it


class ChatConsumer(JsonWebsocketConsumer):
    def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            self.close(code=4001)  # unauthenticated — reject the handshake
            return
        self.watching = set()  # customer ids this (staff) connection follows
        self._last_frame = 0.0
        # Broadcasts fire on first connect / last disconnect only, so several
        # tabs don't flap.
        first_connection = presence.connect(user.id, self.channel_name)
        layer = self.channel_layer
        async_to_sync(layer.group_add)(thread_group(user.id), self.channel_name)
        # The frontend opens this one socket per tab, so it also carries the
        # user's notification pushes (same group NotificationConsumer joins).
        async_to_sync(layer.group_add)(user_group(user.id), self.channel_name)
        if user.is_staff:  # staff only — buyers must never see other threads
            async_to_sync(layer.group_add)(STAFF_GROUP, self.channel_name)
        self.accept()
        if not user.is_staff and first_connection:
            self._staff_feed("chat.presence", {"user_id": user.id, "online": True})

    def disconnect(self, code):
        user = self.scope["user"]
        if not user.is_authenticated:
            return
        last_connection = presence.disconnect(user.id, self.channel_name)
        if user.is_staff:
            for uid in list(self.watching):
                self._thread(uid, "chat.presence", {"user_id": user.id, "online": False})
                async_to_sync(self.channel_layer.group_discard)(
                    thread_group(uid), self.channel_name
                )
        elif last_connection:  # last tab closed — offline fires once, not per tab
            self._staff_feed("chat.presence", {"user_id": user.id, "online": False})
        groups = [thread_group(user.id), user_group(user.id)]
        if user.is_staff:
            groups.append(STAFF_GROUP)
        for group in groups:
            async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)

    # -- client → server (private names: the public methods below are the
    # group-event handlers dispatched by each event's "type").

    def receive(self, text_data=None, bytes_data=None):
        now = time.monotonic()
        if now - self._last_frame < MIN_FRAME_SECONDS:
            return
        self._last_frame = now
        try:
            msg = json.loads(text_data or "")
        except ValueError:
            return  # malformed frame: ignore, keep the socket alive
        if not isinstance(msg, dict):
            return
        handlers = {
            "chat.watch": self._ws_watch,
            "chat.unwatch": self._ws_unwatch,
            "chat.typing": self._ws_typing,
            "chat.read": self._ws_read,
        }
        handler = handlers.get(msg.get("type"))
        if handler:
            handler(msg)

    def _ws_watch(self, msg):
        user = self.scope["user"]
        if not user.is_staff:
            return  # buyers are already in their own thread group
        uid = _safe_uid(msg.get("thread_user_id"))
        if not ChatThread.objects.filter(user_id=uid).exists():
            return
        self.watching.add(uid)
        async_to_sync(self.channel_layer.group_add)(thread_group(uid), self.channel_name)
        self._thread(uid, "chat.presence", {"user_id": user.id, "online": True})
        # a new watcher needs the customer's current state, not just future ones
        self.send_json(
            {"type": "chat.presence", "user_id": uid, "online": presence.is_online(uid)}
        )

    def _ws_unwatch(self, msg):
        user = self.scope["user"]
        if not user.is_staff:
            return
        uid = _safe_uid(msg.get("thread_user_id"))
        self.watching.discard(uid)
        async_to_sync(self.channel_layer.group_discard)(thread_group(uid), self.channel_name)
        self._thread(uid, "chat.presence", {"user_id": user.id, "online": False})

    def _ws_typing(self, msg):
        user = self.scope["user"]
        if user.is_staff:
            uid = _safe_uid(msg.get("thread_user_id"))
            self._thread(uid, "chat.typing", {"user_id": user.id, "thread_user_id": uid})
        else:
            self._staff_feed("chat.typing", {"user_id": user.id, "thread_user_id": user.id})

    def _ws_read(self, msg):
        """Flip read receipts — each side reads the other's messages — then
        tell both groups so ticks flip and badges clear live."""
        user = self.scope["user"]
        uid = user.id if not user.is_staff else _safe_uid(msg.get("thread_user_id"))
        try:
            thread = ChatThread.objects.get(user_id=uid)
        except ChatThread.DoesNotExist:
            return
        unread = thread.messages.filter(read_at__isnull=True)
        if user.is_staff:
            unread = unread.filter(Q(sender__is_staff=False) | Q(sender__isnull=True))
        else:
            unread = unread.filter(sender__is_staff=True)
        read_at = timezone.now()
        unread.update(read_at=read_at)
        payload = {
            "thread_user_id": uid,
            "reader_id": user.id,
            "read_at": read_at.isoformat(),
        }
        self._thread(uid, "chat.read", payload)
        self._staff_feed("chat.read", payload)

    def _thread(self, uid, type_, payload):
        async_to_sync(self.channel_layer.group_send)(
            thread_group(uid), {"type": type_, **payload}
        )

    def _staff_feed(self, type_, payload):
        async_to_sync(self.channel_layer.group_send)(STAFF_GROUP, {"type": type_, **payload})

    # -- server → client group events (dispatched by the event "type") --

    def chat_message(self, event):
        self.send_json(event)

    def chat_typing(self, event):
        self.send_json(event)

    def chat_read(self, event):
        self.send_json(event)

    def chat_presence(self, event):
        self.send_json(event)

    def notification(self, event):  # pushed by notifications.service
        self.send_json(event["json"])
