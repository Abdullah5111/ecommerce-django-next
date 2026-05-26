from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__product")

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        """Mock payment endpoint — marks the order as paid."""
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response({"detail": "Order is not pending."}, status=400)
        order.status = Order.Status.PAID
        order.save(update_fields=["status"])
        return Response(self.get_serializer(order).data)
