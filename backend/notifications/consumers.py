"""Server-push notification socket — one group per user: ``user_<id>``."""
from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer


class NotificationConsumer(JsonWebsocketConsumer):
    def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            self.close(code=4001)  # unauthenticated — reject the handshake
            return
        async_to_sync(self.channel_layer.group_add)(f"user_{user.id}", self.channel_name)
        self.accept()

    def receive(self, text_data=None, bytes_data=None):
        pass  # server-push only; client mutations go through the REST API

    def disconnect(self, code):
        user = self.scope["user"]
        if user.is_authenticated:
            async_to_sync(self.channel_layer.group_discard)(
                f"user_{user.id}", self.channel_name
            )

    def notification(self, event):  # dispatched by the group message's "type"
        self.send_json(event["json"])
