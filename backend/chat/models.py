"""Customer ↔ store support chat: one thread per customer."""
from django.conf import settings
from django.db import models


class ChatThread(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="chat_thread",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat with {self.user}"


class ChatMessage(models.Model):
    thread = models.ForeignKey(
        ChatThread,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    # SET_NULL so deleting a user keeps the transcript; sender becomes unknown.
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="chat_messages",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    body = models.TextField(max_length=2000)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            # Serves the transcript listing + cursor pagination (newest first).
            models.Index(fields=["thread", "-created_at"], name="chat_msg_thread_created_idx"),
        ]

    def __str__(self):
        return f"#{self.pk} in thread {self.thread_id}"
