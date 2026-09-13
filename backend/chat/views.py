from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .models import ChatMessage, ChatThread
from .serializers import ChatMessageSerializer, ChatThreadSerializer
from .service import broadcast_message
from .throttling import ChatSendThrottle


class ChatMessageCursorPagination(CursorPagination):
    # ("created_at", "id") tiebreak: auto_now_add can collide within a second
    # and the cursor needs a total order.
    ordering = ["-created_at", "-id"]
    page_size = 20


def _thread_qs(viewer_is_staff):
    """Thread annotations; ``unread`` counts the *other* side's unread
    messages (any staff read clears it — shared inbox)."""
    if viewer_is_staff:
        # NULL sender (deleted user) counts as a customer message.
        unread_senders = Q(messages__sender__is_staff=False) | Q(messages__sender__isnull=True)
    else:
        unread_senders = Q(messages__sender__is_staff=True)
    last = ChatMessage.objects.filter(thread=OuterRef("pk")).order_by("-created_at", "-id")
    return ChatThread.objects.select_related("user").annotate(
        unread=Count("messages", filter=Q(messages__read_at__isnull=True) & unread_senders),
        last_message_at=Subquery(last.values("created_at")[:1]),
        last_message_body=Subquery(last.values("body")[:1]),
    )


class ThreadView(APIView):
    """GET /api/chat/thread/ — the caller's thread, or 404 if they have none.
    Threads are created by the first message (POST), never by this endpoint."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: ChatThreadSerializer, 404: None},
        description="The caller's thread, if any. Created by the first message, not here.",
    )
    def get(self, request):
        thread = ChatThread.objects.filter(user=request.user).first()
        if thread is None:
            return Response(status=404)
        return Response(
            ChatThreadSerializer(_thread_qs(request.user.is_staff).get(pk=thread.pk)).data
        )


class MessagesView(generics.ListCreateAPIView):
    """GET /api/chat/messages/ (cursor history) + POST (send).

    Customers always resolve to their own thread (a ?thread= param is
    ignored); staff must pass ``thread`` = the customer's user id (on GET as
    ``?thread=``, on POST in the body).
    """

    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChatSendThrottle]
    pagination_class = ChatMessageCursorPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            uid = self.request.query_params.get("thread")
            if not uid:
                raise ValidationError({"thread": "Staff must pass ?thread=<customer user id>."})
            return ChatMessage.objects.filter(thread__user_id=uid)
        return ChatMessage.objects.filter(thread__user_id=user.id)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_staff:
            uid = self.request.data.get("thread")
            if not uid:
                raise ValidationError({"thread": "Staff must pass thread=<customer user id>."})
            thread = get_object_or_404(ChatThread, user_id=uid)
        else:
            thread, _ = ChatThread.objects.get_or_create(user=user)
        message = serializer.save(thread=thread, sender=user)
        transaction.on_commit(lambda: broadcast_message(message))


class ThreadsView(generics.ListAPIView):
    """GET /api/chat/threads/ — staff inbox, newest activity first.

    ponytail: unpaginated — a storefront inbox holds dozens of threads, not
    thousands; add pagination when it actually grows.
    """

    serializer_class = ChatThreadSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        # nulls_last: threads with no messages yet (idle visitors) must not
        # sort above active conversations — Postgres puts NULLs first on DESC.
        return _thread_qs(viewer_is_staff=True).order_by(
            F("last_message_at").desc(nulls_last=True), "-id"
        )
