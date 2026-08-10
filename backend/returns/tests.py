from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase

from orders.models import Order
from products.models import Category, Product
from returns.models import Return
from returns.refunds import refund_for

User = get_user_model()


@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"), RETURN_WINDOW_DAYS=30)
class ReturnFlowTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", email="buyer@example.com", password="pw-123456")
        self.staff = User.objects.create_user(username="staff", email="staff@example.com", password="pw-123456", is_staff=True)
        self.client.force_authenticate(self.user)
        self.order = self._delivered_order()

    def _delivered_order(self):
        body = {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 2}]}
        res = self.client.post("/api/orders/", body, format="json")
        order = Order.objects.get(id=res.data["id"])
        self.client.post(f"/api/orders/{order.id}/pay/")
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/orders/{order.id}/ship/", {}, format="json")
        self.client.post(f"/api/orders/{order.id}/deliver/")
        self.client.force_authenticate(self.user)
        order.refresh_from_db()
        return order

    def _item_id(self):
        return self.order.items.first().id

    def _create_return(self, qty=1):
        return self.client.post(
            "/api/returns/",
            {"order": self.order.id, "lines": [{"order_item": self._item_id(), "quantity": qty, "reason": "defective"}]},
            format="json",
        )

    def test_full_return_flow_restocks_and_refunds(self):
        self.p.refresh_from_db()
        stock_before = self.p.stock
        res = self._create_return(qty=2)
        self.assertEqual(res.status_code, 201)
        ret_id = res.data["id"]
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f"/api/returns/{ret_id}/approve/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/returns/{ret_id}/receive/").status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, stock_before + 2)
        self.assertEqual(self.client.post(f"/api/returns/{ret_id}/refund/").status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REFUNDED)
        self.assertEqual(self.order.refunded_total, Decimal("80.00"))

    def test_partial_return_sets_partially_refunded(self):
        res = self._create_return(qty=1)
        ret_id = res.data["id"]
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/returns/{ret_id}/approve/")
        self.client.post(f"/api/returns/{ret_id}/receive/")
        self.client.post(f"/api/returns/{ret_id}/refund/")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PARTIALLY_REFUNDED)
        self.assertEqual(self.order.refunded_total, Decimal("40.00"))

    def test_can_return_remaining_after_partial_refund(self):
        # Return + refund 1 of 2 units → order becomes partially_refunded.
        first = self._create_return(qty=1)
        rid = first.data["id"]
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/returns/{rid}/approve/")
        self.client.post(f"/api/returns/{rid}/receive/")
        self.client.post(f"/api/returns/{rid}/refund/")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PARTIALLY_REFUNDED)
        # The remaining unit is still returnable even though the order is no
        # longer 'delivered'.
        self.client.force_authenticate(self.user)
        second = self._create_return(qty=1)
        self.assertEqual(second.status_code, 201)

    def test_cannot_return_more_than_purchased(self):
        res = self._create_return(qty=3)
        self.assertEqual(res.status_code, 400)

    def test_no_double_return(self):
        first = self._create_return(qty=2)
        self.assertEqual(first.status_code, 201)
        second = self._create_return(qty=1)
        self.assertEqual(second.status_code, 400)

    def test_non_delivered_order_cannot_be_returned(self):
        body = {"shipping_address": "x", "items": [{"product": self.p.id, "quantity": 1}]}
        res = self.client.post("/api/orders/", body, format="json")
        new_order = Order.objects.get(id=res.data["id"])
        r = self.client.post(
            "/api/returns/",
            {"order": new_order.id, "lines": [{"order_item": new_order.items.first().id, "quantity": 1, "reason": "other"}]},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_window_closed_rejected(self):
        self.order.delivered_at = timezone.now() - timedelta(days=31)
        self.order.save(update_fields=["delivered_at"])
        res = self._create_return(qty=1)
        self.assertEqual(res.status_code, 400)

    def test_staff_actions_require_staff(self):
        ret_id = self._create_return(qty=1).data["id"]
        res = self.client.post(f"/api/returns/{ret_id}/approve/")
        self.assertEqual(res.status_code, 403)

    def test_illegal_return_transition_rejected(self):
        ret_id = self._create_return(qty=1).data["id"]
        self.client.force_authenticate(self.staff)
        res = self.client.post(f"/api/returns/{ret_id}/refund/")
        self.assertEqual(res.status_code, 400)

    def test_create_rechecks_remaining_under_lock(self):
        # Simulate the race: everything is already returned, but create() is
        # called directly (as if validate ran on stale data). The in-create
        # re-check must still reject it.
        from rest_framework.exceptions import ValidationError
        from rest_framework.test import APIRequestFactory
        from returns.serializers import ReturnCreateSerializer

        self._create_return(qty=2)  # exhausts the 2 returnable units
        req = APIRequestFactory().post("/api/returns/")
        req.user = self.user
        ser = ReturnCreateSerializer(context={"request": req})
        with self.assertRaises(ValidationError):
            ser.create(
                {
                    "order": self.order,
                    "lines": [{"order_item": self._item_id(), "quantity": 1, "reason": "other"}],
                }
            )


class RefundMathTests(APITestCase):
    def test_proportional_discount_applied(self):
        cat = Category.objects.create(name="Gear")
        p = Product.objects.create(name="W", price=Decimal("100.00"), stock=10, category=cat)
        user = User.objects.create_user(username="u", email="u@example.com", password="pw-123456")
        order = Order.objects.create(
            user=user, shipping_address="x",
            subtotal=Decimal("100.00"), discount_total=Decimal("10.00"),
            shipping_total=Decimal("0.00"), total=Decimal("90.00"),
        )
        from orders.models import OrderItem
        oi = OrderItem.objects.create(order=order, product=p, quantity=1, unit_price=Decimal("100.00"))
        ret = Return.objects.create(order=order, requested_by=user)
        from returns.models import ReturnLine
        ReturnLine.objects.create(return_request=ret, order_item=oi, quantity=1, reason="other")
        self.assertEqual(refund_for(ret), Decimal("90.00"))


@override_settings(
    SHIPPING_FLAT_FEE=Decimal("5.00"),
    FREE_SHIPPING_THRESHOLD=Decimal("50.00"),
    RETURN_WINDOW_DAYS=30,
    TAX_RATE=Decimal("10"),
)
class RefundWithTaxTests(APITestCase):
    """A customer who paid tax must get it back proportionally on return."""

    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", email="buyer@example.com", password="pw-123456")
        self.staff = User.objects.create_user(username="staff", email="staff@example.com", password="pw-123456", is_staff=True)
        self.client.force_authenticate(self.user)
        body = {"shipping_address": "123 Test St", "items": [{"product": self.p.id, "quantity": 2}]}
        self.order = Order.objects.get(id=self.client.post("/api/orders/", body, format="json").data["id"])
        self.client.post(f"/api/orders/{self.order.id}/pay/")
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/orders/{self.order.id}/ship/", {}, format="json")
        self.client.post(f"/api/orders/{self.order.id}/deliver/")
        self.client.force_authenticate(self.user)
        self.order.refresh_from_db()

    def _return(self, qty):
        return self.client.post(
            "/api/returns/",
            {"order": self.order.id, "lines": [{"order_item": self.order.items.first().id, "quantity": qty, "reason": "defective"}]},
            format="json",
        )

    def test_refund_includes_proportional_tax(self):
        # subtotal 80, tax 8.00. Returning one unit: net 40 + its 4.00 tax.
        self.assertEqual(self.order.tax_total, Decimal("8.00"))
        ret_id = self._return(qty=1).data["id"]
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/returns/{ret_id}/approve/")
        self.client.post(f"/api/returns/{ret_id}/receive/")
        self.client.post(f"/api/returns/{ret_id}/refund/")
        self.order.refresh_from_db()
        self.assertEqual(self.order.refunded_total, Decimal("44.00"))

    def test_full_return_refunds_merchandise_and_all_tax(self):
        # Full return (both units): 80 merchandise + 8 tax = 88. The refund cap
        # must include tax, else this clips to 80 and keeps the buyer's tax.
        ret_id = self._return(qty=2).data["id"]
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/returns/{ret_id}/approve/")
        self.client.post(f"/api/returns/{ret_id}/receive/")
        self.client.post(f"/api/returns/{ret_id}/refund/")
        self.order.refresh_from_db()
        self.assertEqual(self.order.refunded_total, Decimal("88.00"))
        self.assertEqual(self.order.status, Order.Status.REFUNDED)
