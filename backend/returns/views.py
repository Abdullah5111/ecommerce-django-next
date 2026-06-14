from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Return
from .serializers import ReturnSerializer, ReturnCreateSerializer


class ReturnViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Return.objects.prefetch_related("lines__order_item__product").select_related("order")
        if self.request.user.is_staff:
            return qs
        return qs.filter(order__user=self.request.user)

    def get_serializer_class(self):
        return ReturnCreateSerializer if self.action == "create" else ReturnSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def _staff_action(self, request, fn, **kwargs):
        ret = self.get_object()
        try:
            fn(ret, actor=request.user, **kwargs)
        except services.ReturnTransitionError as exc:
            return Response({"detail": str(exc)}, status=400)
        ret.refresh_from_db()
        return Response(ReturnSerializer(ret, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def approve(self, request, pk=None):
        return self._staff_action(request, services.approve)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def reject(self, request, pk=None):
        return self._staff_action(request, services.reject, staff_note=request.data.get("staff_note", ""))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def receive(self, request, pk=None):
        return self._staff_action(request, services.receive)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def refund(self, request, pk=None):
        return self._staff_action(request, services.refund)
