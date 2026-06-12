from decimal import Decimal

from django.test import TestCase, override_settings

from coupons.models import Coupon
from orders.pricing import quote
from products.models import Category, Product


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
