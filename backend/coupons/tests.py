from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from coupons.models import Coupon
from products.models import Category, Product

User = get_user_model()


def _product(name, price, category):
    return Product.objects.create(name=name, price=Decimal(price), stock=100, category=category)


class CouponModelTests(TestCase):
    def test_code_is_uppercased_on_save(self):
        c = Coupon.objects.create(code="save10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        self.assertEqual(c.code, "SAVE10")


class CouponValidationTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(name="Electronics")
        self.audio = Category.objects.create(name="Audio", parent=self.root)
        self.books = Category.objects.create(name="Books")
        self.headphones = _product("Headphones", "40.00", self.audio)
        self.novel = _product("Novel", "15.00", self.books)
        self.user = User.objects.create_user(username="u", password="pw-123456")

    def _items(self):
        return [(self.headphones, 1), (self.novel, 1)]

    def test_unscoped_coupon_includes_all_items(self):
        c = Coupon.objects.create(code="ALL", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        self.assertEqual(len(c.eligible_items(self._items())), 2)

    def test_category_scope_includes_descendants(self):
        c = Coupon.objects.create(code="ELEC", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        c.categories.add(self.root)  # Audio is a child of Electronics
        eligible = c.eligible_items(self._items())
        self.assertEqual([p for p, _ in eligible], [self.headphones])

    def test_product_scope_limits_to_listed_products(self):
        c = Coupon.objects.create(code="NOVEL", kind=Coupon.Kind.FIXED, value=Decimal("5"))
        c.products.add(self.novel)
        eligible = c.eligible_items(self._items())
        self.assertEqual([p for p, _ in eligible], [self.novel])

    def test_inactive_coupon_is_invalid(self):
        c = Coupon.objects.create(code="OFF", kind=Coupon.Kind.PERCENT, value=Decimal("10"), is_active=False)
        self.assertIsNotNone(c.validate_for(self.user, self._items(), Decimal("55")))

    def test_expired_coupon_is_invalid(self):
        c = Coupon.objects.create(
            code="OLD", kind=Coupon.Kind.PERCENT, value=Decimal("10"),
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(c.validate_for(self.user, self._items(), Decimal("55")), "This coupon has expired.")

    def test_not_yet_started_coupon_is_invalid(self):
        c = Coupon.objects.create(
            code="SOON", kind=Coupon.Kind.PERCENT, value=Decimal("10"),
            starts_at=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(c.validate_for(self.user, self._items(), Decimal("55")), "This coupon is not yet valid.")

    def test_below_min_subtotal_is_invalid(self):
        c = Coupon.objects.create(
            code="BIG", kind=Coupon.Kind.PERCENT, value=Decimal("10"), min_subtotal=Decimal("100"),
        )
        self.assertIsNotNone(c.validate_for(self.user, self._items(), Decimal("55")))

    def test_out_of_scope_cart_is_invalid(self):
        toys = Category.objects.create(name="Toys")
        c = Coupon.objects.create(code="TOYS", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        c.categories.add(toys)
        self.assertEqual(
            c.validate_for(self.user, self._items(), Decimal("55")),
            "This coupon does not apply to the items in your cart.",
        )

    def test_valid_coupon_returns_none(self):
        c = Coupon.objects.create(code="GOOD", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        self.assertIsNone(c.validate_for(self.user, self._items(), Decimal("55")))
