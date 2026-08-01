from django.conf import settings
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from payments import gateway

from . import transitions
from .models import Order
from .serializers import OrderSerializer, ShipInputSerializer


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items__product", "events")
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def _transition(self, request, fn, **kwargs):
        order = self.get_object()
        try:
            order = fn(order, actor=request.user, **kwargs)
        except transitions.TransitionError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="create-payment-intent")
    def create_payment_intent(self, request, pk=None):
        """Start (or resume) payment for a pending order — returns the Stripe
        client secret + key. In mock mode `mock` is true and the secret is a stub.
        """
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response({"detail": "Order is not awaiting payment."}, status=400)
        client_secret, intent_id, mock = gateway.create_payment_intent(order)
        if order.payment_intent_id != intent_id:
            order.payment_intent_id = intent_id
            order.save(update_fields=["payment_intent_id", "updated_at"])
        return Response({
            "client_secret": client_secret,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "mock": mock,
        })

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        # Mock mode confirms immediately; live mode only honors a genuinely
        # succeeded PaymentIntent (defence in depth alongside the webhook).
        order = self.get_object()
        if gateway.is_live():
            ok, detail = gateway.verify_paid(order)
            if not ok:
                return Response({"detail": detail}, status=400)
        return self._transition(request, transitions.mark_paid)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, transitions.cancel)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def ship(self, request, pk=None):
        serializer = ShipInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._transition(
            request, transitions.ship,
            tracking_number=serializer.validated_data.get("tracking_number", ""),
            tracking_carrier=serializer.validated_data.get("tracking_carrier", ""),
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def deliver(self, request, pk=None):
        return self._transition(request, transitions.deliver)
