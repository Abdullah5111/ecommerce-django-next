from django.urls import path

from .views import CouponQuoteView

urlpatterns = [
    path("coupons/quote/", CouponQuoteView.as_view(), name="coupon-quote"),
]
