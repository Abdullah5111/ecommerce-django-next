import logging

from asgiref.sync import async_to_sync

from .consumers import STAFF_GROUP, thread_group
from .serializers import ChatMessageSerializer

logger = logging.getLogger(__name__)


def broadcast_message(message):
    """Push a new message to its thread group + staff inbox (best-effort)."""
    try:
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        payload = {"type": "chat.message", "message": ChatMessageSerializer(message).data}
        async_to_sync(layer.group_send)(thread_group(message.thread.user_id), payload)
        async_to_sync(layer.group_send)(STAFF_GROUP, payload)
    except Exception:  # never let the socket layer break message creation
        logger.exception("Chat broadcast failed for message %s", message.pk)
