from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
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

    def test_fixed_coupon_scoped_caps_at_eligible_subtotal(self):
        # $50-off scoped to A only ($20 in cart); must not discount B's value too.
        c = Coupon.objects.create(code="F50A", kind=Coupon.Kind.FIXED, value=Decimal("50"))
        c.products.add(self.a)
        q = quote([(self.a, 1), (self.b, 1)], coupon=c)  # subtotal 50
        self.assertEqual(q.discount_total, Decimal("20.00"))  # capped at A, not 50
        self.assertEqual(q.grand_total, Decimal("30.00"))  # 50 - 20, free shipping

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


@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"))
class ReleaseExpiredOrdersTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(
            name="Widget", price=Decimal("40.00"), stock=10, category=self.cat
        )
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _pending_order(self):
        res = self.client.post(
            "/api/orders/",
            {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 2}]},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        return Order.objects.get(id=res.data["id"])

    def test_expired_pending_order_released_and_restocked(self):
        order = self._pending_order()
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 8)  # reserved at creation

        # Backdate past the TTL; update() bypasses auto_now_add.
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        call_command("release_expired_orders")

        order.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p.stock, 10)  # restocked

    def test_recent_pending_order_kept(self):
        order = self._pending_order()
        call_command("release_expired_orders")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)


class OrderLifecycleTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", email="buyer@example.com", password="pw-123456")
        self.staff = User.objects.create_user(username="staff", email="staff@example.com", password="pw-123456", is_staff=True)
        self.client.force_authenticate(self.user)

    def _order(self, coupon_code=None):
        body = {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 2}]}
        if coupon_code:
            body["coupon_code"] = coupon_code
        res = self.client.post("/api/orders/", body, format="json")
        self.assertEqual(res.status_code, 201)
        return Order.objects.get(id=res.data["id"])

    def test_pay_then_ship_then_deliver_stamps_and_logs(self):
        order = self._order()
        self.client.post(f"/api/orders/{order.id}/pay/")
        res = self.client.post(f"/api/orders/{order.id}/ship/", {"tracking_carrier": "UPS", "tracking_number": "1Z9"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.client.force_authenticate(self.staff)
        res = self.client.post(f"/api/orders/{order.id}/ship/", {"tracking_carrier": "UPS", "tracking_number": "1Z9"}, format="json")
        self.assertEqual(res.status_code, 200)
        res = self.client.post(f"/api/orders/{order.id}/deliver/")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertIsNotNone(order.paid_at)
        self.assertIsNotNone(order.shipped_at)
        self.assertIsNotNone(order.delivered_at)
        self.assertEqual(order.tracking_number, "1Z9")
        self.assertEqual(order.events.count(), 3)

    def test_illegal_transition_rejected(self):
        order = self._order()
        self.client.force_authenticate(self.staff)
        res = self.client.post(f"/api/orders/{order.id}/deliver/")
        self.assertEqual(res.status_code, 400)

    def test_cancel_restocks_and_releases_coupon(self):
        Coupon.objects.create(code="SAVE10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        order = self._order(coupon_code="SAVE10")
        self.client.post(f"/api/orders/{order.id}/pay/")
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, 8)
        self.assertEqual(CouponRedemption.objects.filter(order=order).count(), 1)
        res = self.client.post(f"/api/orders/{order.id}/cancel/")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p.stock, 10)
        self.assertEqual(order.refunded_total, order.total)
        self.assertEqual(CouponRedemption.objects.filter(order=order).count(), 0)

    def test_cannot_cancel_shipped_order(self):
        order = self._order()
        self.client.post(f"/api/orders/{order.id}/pay/")
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/orders/{order.id}/ship/", {}, format="json")
        self.client.force_authenticate(self.user)
        res = self.client.post(f"/api/orders/{order.id}/cancel/")
        self.assertEqual(res.status_code, 400)

    def test_user_cannot_see_others_order(self):
        order = self._order()
        other = User.objects.create_user(username="other", email="other@example.com", password="pw-123456")
        self.client.force_authenticate(other)
        res = self.client.get(f"/api/orders/{order.id}/")
        self.assertEqual(res.status_code, 404)


@override_settings(
    SHIPPING_FLAT_FEE=Decimal("5.00"),
    FREE_SHIPPING_THRESHOLD=Decimal("50.00"),
    TAX_RATE=Decimal("10"),  # 10% keeps the arithmetic easy to read
)
class TaxPricingTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.a = _product("A", "20.00", self.cat)
        self.b = _product("B", "30.00", self.cat)

    def test_tax_on_plain_subtotal(self):
        q = quote([(self.a, 1)])  # subtotal 20, tax 2.00, shipping 5
        self.assertEqual(q.tax_total, Decimal("2.00"))
        self.assertEqual(q.grand_total, Decimal("27.00"))  # 20 + 2 + 5

    def test_tax_applies_after_discount(self):
        Coupon.objects.create(code="TEN", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        coupon = Coupon.objects.get(code="TEN")
        q = quote([(self.a, 1)], coupon)  # subtotal 20, disc 2, taxable 18, tax 1.80
        self.assertEqual(q.discount_total, Decimal("2.00"))
        self.assertEqual(q.tax_total, Decimal("1.80"))
        self.assertEqual(q.grand_total, Decimal("24.80"))  # 20 - 2 + 1.80 + 5

    def test_free_shipping_threshold_uses_pretax_subtotal(self):
        q = quote([(self.a, 1), (self.b, 1)])  # subtotal 50 -> free ship, tax 5.00
        self.assertEqual(q.shipping_total, Decimal("0.00"))
        self.assertEqual(q.tax_total, Decimal("5.00"))
        self.assertEqual(q.grand_total, Decimal("55.00"))  # 50 + 5 + 0

    def test_tax_never_negative_when_discount_exceeds_subtotal(self):
        Coupon.objects.create(code="BIG", kind=Coupon.Kind.FIXED, value=Decimal("999"))
        coupon = Coupon.objects.get(code="BIG")
        q = quote([(self.a, 1)], coupon)  # discount capped at subtotal -> taxable 0
        self.assertEqual(q.tax_total, Decimal("0.00"))


@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"))
class TaxDefaultsOffTests(TestCase):
    def test_no_tax_line_without_a_configured_rate(self):
        cat = Category.objects.create(name="Gear")
        q = quote([(_product("A", "20.00", cat), 1)])  # TAX_RATE defaults to 0
        self.assertEqual(q.tax_total, Decimal("0.00"))
        self.assertEqual(q.grand_total, Decimal("25.00"))  # unchanged: 20 + 5


@override_settings(
    SHIPPING_FLAT_FEE=Decimal("5.00"),
    FREE_SHIPPING_THRESHOLD=Decimal("50.00"),
    TAX_RATE=Decimal("10"),
)
class OrderTaxTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", email="buyer@example.com", password="pw-123456")
        self.client.force_authenticate(self.user)

    def test_order_snapshots_tax(self):
        res = self.client.post(
            "/api/orders/",
            {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        order = Order.objects.get(id=res.data["id"])
        self.assertEqual(order.tax_total, Decimal("4.00"))          # 10% of 40
        self.assertEqual(order.total, Decimal("49.00"))             # 40 + 4 + 5
        self.assertEqual(res.data["tax_total"], "4.00")


@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"))
class VariantOrderTests(APITestCase):
    def setUp(self):
        from products.models import ProductVariant
        self.cat = Category.objects.create(name="Apparel")
        self.tee = Product.objects.create(
            name="Tee", price=Decimal("20.00"), stock=0, category=self.cat
        )
        self.small = ProductVariant.objects.create(
            product=self.tee, options={"Size": "S"}, sku="TEE-S", stock=5
        )
        self.large = ProductVariant.objects.create(
            product=self.tee, options={"Size": "L"}, sku="TEE-L", stock=2,
            price=Decimal("26.00"),
        )
        self.user = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pw-123456"
        )
        self.client.force_authenticate(self.user)

    def _order(self, variant, qty=1):
        return self.client.post(
            "/api/orders/",
            {"shipping_address": "123 St", "items": [
                {"product": self.tee.id, "variant": variant.id, "quantity": qty}
            ]},
            format="json",
        )

    def test_order_uses_variant_price_and_snapshots_it(self):
        res = self._order(self.large, 1)
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(id=res.data["id"])
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal("26.00"))   # override, not 20
        self.assertEqual(item.variant_sku, "TEE-L")
        self.assertEqual(item.variant_label, "Size: L")
        self.assertEqual(order.subtotal, Decimal("26.00"))

    def test_variant_inherits_product_price_when_unset(self):
        res = self._order(self.small, 1)
        item = Order.objects.get(id=res.data["id"]).items.get()
        self.assertEqual(item.unit_price, Decimal("20.00"))

    def test_decrements_variant_stock_not_product(self):
        self._order(self.large, 2)
        self.large.refresh_from_db()
        self.small.refresh_from_db()
        self.assertEqual(self.large.stock, 0)   # 2 - 2
        self.assertEqual(self.small.stock, 5)   # untouched

    def test_oversell_on_variant_is_blocked(self):
        res = self._order(self.large, 3)   # only 2 in stock
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.large.refresh_from_db()
        self.assertEqual(self.large.stock, 2)   # untouched

    def test_variant_product_requires_a_variant(self):
        res = self.client.post(
            "/api/orders/",
            {"shipping_address": "123 St", "items": [
                {"product": self.tee.id, "quantity": 1}
            ]},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_variant_must_belong_to_the_product(self):
        other = Product.objects.create(
            name="Mug", price=Decimal("8"), stock=3, category=self.cat
        )
        res = self.client.post(
            "/api/orders/",
            {"shipping_address": "123 St", "items": [
                {"product": other.id, "variant": self.small.id, "quantity": 1}
            ]},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_cancel_restocks_the_variant(self):
        res = self._order(self.large, 2)
        order = Order.objects.get(id=res.data["id"])
        self.client.post(f"/api/orders/{order.id}/cancel/")
        self.large.refresh_from_db()
        self.assertEqual(self.large.stock, 2)   # restored

    def test_percent_coupon_discounts_the_variant_price(self):
        from orders.pricing import Line, quote
        Coupon.objects.create(code="TEN", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        coupon = Coupon.objects.get(code="TEN")
        # Large overrides to 26.00; a 10% coupon must discount 2.60, not 2.00.
        q = quote([Line(self.tee, 1, self.large)], coupon, self.user)
        self.assertEqual(q.subtotal, Decimal("26.00"))
        self.assertEqual(q.discount_total, Decimal("2.60"))
