from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, Sum
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from payments import gateway
from products.models import Product

from . import transitions
from .models import Order
from .serializers import OrderSerializer, ShipInputSerializer

IDEMPOTENCY_KEY_MAX = Order._meta.get_field("idempotency_key").max_length


class StaffStatsView(APIView):
    """GET /api/staff/stats/ — the overview dashboard's numbers, one request."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Money actually captured: paid, in-flight, and delivered orders.
        revenue = Order.objects.filter(
            status__in=[Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED]
        ).aggregate(total=Sum("total"), count=Count("id"))
        by_status = dict(
            Order.objects.values_list("status").annotate(n=Count("id")).values_list("status", "n")
        )
        low_stock = list(
            Product.objects.filter(stock__lte=5)
            .order_by("stock", "id")
            .values("id", "slug", "name", "stock")[:10]
        )
        from chat.views import _thread_qs

        open_chats = _thread_qs(viewer_is_staff=True).filter(unread__gt=0).count()
        return Response(
            {
                "revenue": revenue["total"] or 0,
                "paid_orders": revenue["count"] or 0,
                "orders_by_status": by_status,
                "total_orders": sum(by_status.values()),
                "low_stock": low_stock,
                "open_chats": open_chats,
            }
        )


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

    def create(self, request, *args, **kwargs):
        """Place an order. With an ``Idempotency-Key`` header, a retry of the
        same request (double-click, lost response) returns the order the first
        attempt created — 200 instead of 201 — rather than placing another.
        """
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key:
            return super().create(request, *args, **kwargs)
        if len(key) > IDEMPOTENCY_KEY_MAX:
            return Response(
                {"detail": f"Idempotency-Key must be at most {IDEMPOTENCY_KEY_MAX} characters."},
                status=400,
            )
        existing = self._order_for_key(key)
        if existing is not None:
            return Response(self.get_serializer(existing).data, status=200)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(idempotency_key=key)
        except IntegrityError:
            # A concurrent request with the same key won the insert; this one's
            # transaction (stock, coupon) rolled back. Hand back the winner.
            existing = self._order_for_key(key)
            if existing is None:
                raise
            return Response(self.get_serializer(existing).data, status=200)
        return Response(serializer.data, status=201)

    def _order_for_key(self, key):
        return (
            Order.objects.prefetch_related("items__product", "events")
            .filter(user=self.request.user, idempotency_key=key)
            .first()
        )

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
        try:
            client_secret, intent_id, mock = gateway.create_payment_intent(order)
        except gateway.PaymentsUnavailable as exc:
            return Response({"detail": str(exc)}, status=503)
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
        # Mock mode (explicitly enabled) confirms immediately; live mode only
        # honors a genuinely succeeded PaymentIntent (defence in depth alongside
        # the webhook); neither configured → refuse rather than mark paid.
        order = self.get_object()
        try:
            ok, detail = gateway.verify_paid(order)
        except gateway.PaymentsUnavailable as exc:
            return Response({"detail": str(exc)}, status=503)
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
