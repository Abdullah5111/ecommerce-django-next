"""Channel-layer group names for notification pushes."""


def user_group(user_id):
    """Per-user notification group, joined by the browser's one socket
    (chat.consumers.ChatConsumer) and targeted by notifications.service."""
    return f"user_{user_id}"
