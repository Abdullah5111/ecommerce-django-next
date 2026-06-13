from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from coupons.models import Coupon, CouponRedemption
from orders.models import Order
from orders.pricing import quote
from products.models import Category, Product

User = get_user_model()


def _product(name, price, category):
    return Product.objects.create(name=name, price=Decimal(price), stock=100, category=category)


@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"))
class PricingTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.a = _product("A", "20.00", self.cat)  # cheaper
        self.b = _product("B", "30.00", self.cat)

    def test_subtotal_and_flat_shipping_no_coupon(self):
        q = quote([(self.a, 1)])  # subtotal 20 < 50 threshold
        self.assertEqual(q.subtotal, Decimal("20.00"))
        self.assertEqual(q.discount_total, Decimal("0.00"))
        self.assertEqual(q.shipping_total, Decimal("5.00"))
        self.assertEqual(q.grand_total, Decimal("25.00"))

    def test_free_shipping_over_threshold(self):
        q = quote([(self.a, 1), (self.b, 1)])  # subtotal 50 >= 50
        self.assertEqual(q.shipping_total, Decimal("0.00"))
        self.assertEqual(q.grand_total, Decimal("50.00"))

    def test_percent_coupon(self):
        c = Coupon.objects.create(code="P10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        q = quote([(self.a, 1)], coupon=c)  # 20 - 2 + 5 shipping
        self.assertEqual(q.discount_total, Decimal("2.00"))
        self.assertEqual(q.grand_total, Decimal("23.00"))
        self.assertEqual(q.coupon_code, "P10")
        self.assertIsNone(q.coupon_error)

    def test_fixed_coupon_clamps_to_subtotal(self):
        c = Coupon.objects.create(code="F50", kind=Coupon.Kind.FIXED, value=Decimal("50"))
        q = quote([(self.a, 1)], coupon=c)  # discount clamped to 20
        self.assertEqual(q.discount_total, Decimal("20.00"))
        self.assertEqual(q.grand_total, Decimal("5.00"))  # 0 items value + shipping 5

    def test_free_shipping_coupon_waives_shipping(self):
        c = Coupon.objects.create(code="SHIP", kind=Coupon.Kind.FREE_SHIPPING)
        q = quote([(self.a, 1)], coupon=c)  # 20 subtotal, shipping waived
        self.assertEqual(q.shipping_total, Decimal("0.00"))
        self.assertEqual(q.discount_total, Decimal("0.00"))
        self.assertEqual(q.grand_total, Decimal("20.00"))

    def test_bogo_discounts_cheapest_unit(self):
        # buy 1 get 1 at 100% off; cart has A(20) + B(30) => cheapest (20) free
        c = Coupon.objects.create(
            code="BOGO", kind=Coupon.Kind.BOGO, value=Decimal("100"),
            buy_quantity=1, get_quantity=1,
        )
        q = quote([(self.a, 1), (self.b, 1)], coupon=c)
        self.assertEqual(q.discount_total, Decimal("20.00"))

    def test_invalid_coupon_returns_error_and_no_discount(self):
        c = Coupon.objects.create(code="OFF", kind=Coupon.Kind.PERCENT, value=Decimal("10"), is_active=False)
        q = quote([(self.a, 1)], coupon=c)
        self.assertIsNotNone(q.coupon_error)
        self.assertEqual(q.discount_total, Decimal("0.00"))
        self.assertIsNone(q.coupon_code)


@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"))
class OrderCouponTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", password="pw-123456")
        self.client.force_authenticate(self.user)

    def _payload(self, **extra):
        body = {
            "shipping_address": "123 Test St",
            "items": [{"product": self.p.id, "quantity": 1}],
        }
        body.update(extra)
        return body

    def test_order_without_coupon_snapshots_totals(self):
        res = self.client.post("/api/orders/", self._payload(), format="json")
        self.assertEqual(res.status_code, 201)
        order = Order.objects.get(id=res.data["id"])
        self.assertEqual(order.subtotal, Decimal("40.00"))
        self.assertEqual(order.shipping_total, Decimal("5.00"))
        self.assertEqual(order.total, Decimal("45.00"))
        self.assertEqual(order.coupon_code, "")

    def test_order_with_valid_coupon_applies_and_records_redemption(self):
        Coupon.objects.create(code="SAVE10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        res = self.client.post("/api/orders/", self._payload(coupon_code="save10"), format="json")
        self.assertEqual(res.status_code, 201)
        order = Order.objects.get(id=res.data["id"])
        self.assertEqual(order.discount_total, Decimal("4.00"))
        self.assertEqual(order.total, Decimal("41.00"))  # 40 - 4 + 5
        self.assertEqual(order.coupon_code, "SAVE10")
        self.assertEqual(CouponRedemption.objects.filter(order=order).count(), 1)

    def test_order_with_invalid_coupon_is_rejected(self):
        Coupon.objects.create(code="OFF", kind=Coupon.Kind.PERCENT, value=Decimal("10"), is_active=False)
        res = self.client.post("/api/orders/", self._payload(coupon_code="OFF"), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_unknown_coupon_code_is_rejected(self):
        res = self.client.post("/api/orders/", self._payload(coupon_code="NOPE"), format="json")
        self.assertEqual(res.status_code, 400)

    def test_global_redemption_limit_enforced(self):
        Coupon.objects.create(
            code="ONCE", kind=Coupon.Kind.PERCENT, value=Decimal("10"), max_redemptions=1,
        )
        first = self.client.post("/api/orders/", self._payload(coupon_code="ONCE"), format="json")
        self.assertEqual(first.status_code, 201)
        second = self.client.post("/api/orders/", self._payload(coupon_code="ONCE"), format="json")
        self.assertEqual(second.status_code, 400)
        self.assertEqual(CouponRedemption.objects.count(), 1)

    def test_per_user_limit_enforced(self):
        Coupon.objects.create(
            code="SOLO", kind=Coupon.Kind.PERCENT, value=Decimal("10"), per_user_limit=1,
        )
        self.client.post("/api/orders/", self._payload(coupon_code="SOLO"), format="json")
        second = self.client.post("/api/orders/", self._payload(coupon_code="SOLO"), format="json")
        self.assertEqual(second.status_code, 400)
