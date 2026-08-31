from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import UserRateThrottle


class ChatSendThrottle(UserRateThrottle):
    """Sending a chat message. The messages route also serves history reads,
    which must not be rate-limited."""

    scope = "chat-send"

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)
