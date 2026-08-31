from rest_framework import serializers

from .models import ChatMessage, ChatThread


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    thread_user_id = serializers.IntegerField(source="thread.user_id", read_only=True)

    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "thread_user_id",
            "sender",
            "sender_username",
            "body",
            "read_at",
            "created_at",
        )
        read_only_fields = ("sender", "read_at")


class ChatThreadSerializer(serializers.ModelSerializer):
    """Expects the ``unread`` / ``last_message_at`` / ``last_message_body``
    annotations from ``views._thread_qs`` — unread counts the *other* side's
    messages still missing a read receipt."""

    username = serializers.CharField(source="user.username", read_only=True)
    unread = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()
    last_message_body = serializers.SerializerMethodField()

    class Meta:
        model = ChatThread
        fields = (
            "id",
            "user",
            "username",
            "unread",
            "last_message_at",
            "last_message_body",
            "created_at",
        )

    def get_unread(self, obj):
        return getattr(obj, "unread", 0)

    def get_last_message_at(self, obj):
        return getattr(obj, "last_message_at", None)

    def get_last_message_body(self, obj):
        return getattr(obj, "last_message_body", None)
