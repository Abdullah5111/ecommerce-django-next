from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.pricing import quote

from .models import Coupon
from .serializers import CouponQuoteSerializer


def quote_to_dict(q):
    return {
        "subtotal": str(q.subtotal),
        "discount_total": str(q.discount_total),
        "shipping_total": str(q.shipping_total),
        "grand_total": str(q.grand_total),
        "coupon_code": q.coupon_code,
        "coupon_error": q.coupon_error,
    }


class CouponQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CouponQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pairs = [(it["product"], it["quantity"]) for it in serializer.validated_data["items"]]
        code = (serializer.validated_data.get("code") or "").strip().upper()

        coupon = Coupon.objects.filter(code=code).first() if code else None
        if code and coupon is None:
            data = quote_to_dict(quote(pairs, None, request.user))
            data["coupon_error"] = "Invalid coupon code."
            return Response(data)

        return Response(quote_to_dict(quote(pairs, coupon, request.user)))
