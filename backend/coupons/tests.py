from decimal import Decimal

from django.test import TestCase

from coupons.models import Coupon


class CouponModelTests(TestCase):
    def test_code_is_uppercased_on_save(self):
        c = Coupon.objects.create(code="save10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        self.assertEqual(c.code, "SAVE10")
