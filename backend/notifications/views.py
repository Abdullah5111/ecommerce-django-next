import hmac

from django.db import transaction
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from . import push
from .models import Notification, PushSubscription
from .serializers import NotificationSerializer, PushSubscriptionSerializer


class NotificationViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """List the current user's notifications; mark read / mark all read."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread": count})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"marked_read": updated})


class PushConfigView(APIView):
    """Expose whether push is enabled and the VAPID public key for subscribing."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"enabled": push.is_enabled(), "public_key": push.public_key()})


class PushSubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            existing = (
                PushSubscription.objects.select_for_update()
                .filter(endpoint=data["endpoint"])
                .first()
            )
            # Moving an endpoint to another account needs the subscription's
            # auth secret, which only the browser that created it holds — the
            # same browser signing into a new account has it; someone who
            # merely learned the endpoint URL doesn't.
            if (
                existing is not None
                and existing.user_id != request.user.id
                and not hmac.compare_digest(existing.auth, data["auth"])
            ):
                return Response(
                    {"detail": "This push endpoint is registered to another account."},
                    status=status.HTTP_409_CONFLICT,
                )
            PushSubscription.objects.update_or_create(
                endpoint=data["endpoint"],
                defaults={"user": request.user, "p256dh": data["p256dh"], "auth": data["auth"]},
            )
        return Response({"subscribed": True}, status=201)

    def delete(self, request):
        endpoint = request.data.get("endpoint")
        if endpoint:
            PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response(status=204)
