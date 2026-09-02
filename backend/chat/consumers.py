"""Customer ↔ store support chat over a WebSocket.

Groups: ``chat_u_<customer_id>`` (buyers join their own at connect; staff
join by watching — membership is the authorization) and a shared
``chat_staff`` inbox feed. Messages are created over REST; the socket
carries message broadcasts plus ephemeral typing / read receipts / presence.

ponytail: presence is per-process under the InMemory layer (cluster-wide
once REDIS_URL is set); staff presence only reaches a buyer while that staff
member is watching their thread.
"""
import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.utils import timezone

from .models import ChatThread

STAFF_GROUP = "chat_staff"

# user_id → live connection count; broadcasts fire on transitions only, so
# multiple tabs don't flap. Per-process (see module docstring).
_online: dict[int, int] = {}


def thread_group(user_id):
    """Group name for a customer's thread — keyed by user id, so it exists
    (and is joinable) even before the ChatThread row does."""
    return f"chat_u_{user_id}"


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
        _online[user.id] = _online.get(user.id, 0) + 1
        layer = self.channel_layer
        async_to_sync(layer.group_add)(thread_group(user.id), self.channel_name)
        if user.is_staff:  # staff only — buyers must never see other threads
            async_to_sync(layer.group_add)(STAFF_GROUP, self.channel_name)
        self.accept()
        if not user.is_staff and _online[user.id] == 1:
            self._staff_feed("chat.presence", {"user_id": user.id, "online": True})

    def disconnect(self, code):
        user = self.scope["user"]
        if not user.is_authenticated:
            return
        count = max(0, _online.get(user.id, 0) - 1)
        if count:
            _online[user.id] = count
        else:
            _online.pop(user.id, None)
            if not user.is_staff:
                self._staff_feed("chat.presence", {"user_id": user.id, "online": False})
        if user.is_staff:
            for uid in list(self.watching):
                self._thread(uid, "chat.presence", {"user_id": user.id, "online": False})
                async_to_sync(self.channel_layer.group_discard)(
                    thread_group(uid), self.channel_name
                )
        else:
            self._staff_feed("chat.presence", {"user_id": user.id, "online": False})
        groups = [thread_group(user.id)]
        if user.is_staff:
            groups.append(STAFF_GROUP)
        for group in groups:
            async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)

    # -- client → server (private names: the public methods below are the
    # group-event handlers dispatched by each event's "type").

    def receive(self, text_data=None, bytes_data=None):
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
            {"type": "chat.presence", "user_id": uid, "online": _online.get(uid, 0) > 0}
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
        unread = (
            unread.filter(sender__is_staff=False)
            if user.is_staff
            else unread.filter(sender__is_staff=True)
        )
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
