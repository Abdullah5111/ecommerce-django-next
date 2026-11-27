from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.schema import body
from orders.pricing import quote

from .models import Coupon
from .serializers import CouponQuoteSerializer

_MONEY = {"max_digits": 10, "decimal_places": 2}
QUOTE = body(
    "Quote",
    subtotal=serializers.DecimalField(**_MONEY),
    discount_total=serializers.DecimalField(**_MONEY),
    tax_total=serializers.DecimalField(**_MONEY),
    shipping_total=serializers.DecimalField(**_MONEY),
    grand_total=serializers.DecimalField(**_MONEY),
    coupon_code=serializers.CharField(allow_blank=True),
    coupon_error=serializers.CharField(allow_null=True, allow_blank=True),
)


def quote_to_dict(q):
    return {
        "subtotal": str(q.subtotal),
        "discount_total": str(q.discount_total),
        "tax_total": str(q.tax_total),
        "shipping_total": str(q.shipping_total),
        "grand_total": str(q.grand_total),
        "coupon_code": q.coupon_code,
        "coupon_error": q.coupon_error,
    }


class CouponQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=CouponQuoteSerializer, responses={200: QUOTE, 400: OpenApiResponse(description="Invalid items.")})
    def post(self, request):
        serializer = CouponQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pairs = []
        for it in serializer.validated_data["items"]:
            product = it["product"]
            variant = it.get("variant")
            # Mirror the order-create validation: a variant must belong to its
            # product, or the quote would silently price the wrong SKU.
            if variant is not None and variant.product_id != product.pk:
                raise ValidationError(
                    {"items": "Variant does not belong to this product."}
                )
            pairs.append((product, it["quantity"], variant))
        code = (serializer.validated_data.get("code") or "").strip().upper()

        coupon = Coupon.objects.filter(code=code).first() if code else None
        if code and coupon is None:
            data = quote_to_dict(quote(pairs, None, request.user))
            data["coupon_error"] = "Invalid coupon code."
            return Response(data)

        return Response(quote_to_dict(quote(pairs, coupon, request.user)))
