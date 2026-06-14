# Order Lifecycle & Returns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full order lifecycle (ship/deliver/cancel with an audit log) and a line-item returns/refunds (RMA) subsystem, with staff API + Django admin actions and a customer order-detail/returns UI.

**Architecture:** A hand-rolled state machine — `orders/transitions.py` holds an `ALLOWED_TRANSITIONS` map and transition helpers that run side effects (restock, coupon-redemption release, mock refund) inside `@transaction.atomic` and write an `OrderEvent` each time. Returns live in a new `returns` app with a pure refund-math module (`returns/refunds.py`) and its own state machine (`returns/services.py`). The frontend adds an order-detail page with a timeline, cancel button, and return-request flow.

**Tech Stack:** Django 5, DRF, SimpleJWT, PostgreSQL/SQLite, Next.js 14 (App Router), TypeScript. Backend tests use DRF `APITestCase` via `python manage.py test`. Frontend verified with `npx tsc --noEmit`.

**Spec:** `docs/superpowers/specs/2026-06-13-order-lifecycle-returns-design.md`

**Working dirs:** backend commands from `backend/`; frontend from `frontend/`. Git author `abdullah5111`, scoped lowercase imperative messages, **no Claude co-author trailer**. Always scoped `git add` (never `git add -A`).

## IMPORTANT: exactly 4 commits

Per the user's instruction this work lands in **exactly four commits**, one per Task below. Each Task is TDD (write its tests first, watch them fail, implement, watch them pass) but has a **single commit at the very end of the Task**. Do NOT commit mid-Task.

| Commit | Task | Message |
|--------|------|---------|
| 1 | Task 1 | `add order lifecycle state machine and events` |
| 2 | Task 2 | `add line-item returns and refunds` |
| 3 | Task 3 | `add order detail and returns ui` |
| 4 | Task 4 | `document order lifecycle and returns` |

## File Structure

**Task 1 (backend lifecycle)** — modify `orders/models.py`, `orders/serializers.py`, `orders/views.py`, `orders/admin.py`, `orders/tests.py`; create `orders/transitions.py`; new migration.
**Task 2 (backend returns)** — new `returns/` app (models, refunds, services, serializers, views, urls, admin, tests, migrations); modify `core/settings.py`, `core/urls.py`.
**Task 3 (frontend)** — new `app/orders/[id]/page.tsx`; modify `app/orders/page.tsx`, `lib/api.ts`.
**Task 4 (docs)** — modify `README.md`.

---

## Task 1: Order lifecycle state machine + events

**Files:**
- Modify: `backend/orders/models.py`
- Create: `backend/orders/transitions.py`
- Modify: `backend/orders/serializers.py`, `backend/orders/views.py`, `backend/orders/admin.py`
- Modify (append tests): `backend/orders/tests.py`
- Migration: generated

### Step 1: Extend the `Order` model + add `OrderEvent`

In `backend/orders/models.py`, add two statuses to `Order.Status` (after `CANCELLED`):
```python
        CANCELLED = "cancelled", "Cancelled"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"
        REFUNDED = "refunded", "Refunded"
```

Add these fields to `Order` (after `coupon_code`):
```python
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    tracking_carrier = models.CharField(max_length=60, blank=True)
    refunded_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
```

At the end of `backend/orders/models.py`, add the event model:
```python
class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.CharField(max_length=255)
    to_status = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Order #{self.order_id}: {self.message}"
```
(`settings` is already imported at the top of the file.)

### Step 2: Create the transition module

`backend/orders/transitions.py`:
```python
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from products.models import Product
from .models import Order, OrderEvent

ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.PAID, Order.Status.CANCELLED},
    Order.Status.PAID: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
    Order.Status.PARTIALLY_REFUNDED: set(),
    Order.Status.REFUNDED: set(),
}


class TransitionError(Exception):
    """Raised when an order status change is not allowed."""


def _check(order, to_status):
    if to_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise TransitionError(f"Cannot move order from '{order.status}' to '{to_status}'.")


def log_event(order, actor, message, to_status=""):
    OrderEvent.objects.create(order=order, actor=actor, message=message, to_status=to_status)


@transaction.atomic
def mark_paid(order, actor=None):
    _check(order, Order.Status.PAID)
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at", "updated_at"])
    log_event(order, actor, "Payment received", Order.Status.PAID)
    return order


@transaction.atomic
def ship(order, actor=None, tracking_number="", tracking_carrier=""):
    _check(order, Order.Status.SHIPPED)
    order.status = Order.Status.SHIPPED
    order.shipped_at = timezone.now()
    order.tracking_number = tracking_number
    order.tracking_carrier = tracking_carrier
    order.save(update_fields=[
        "status", "shipped_at", "tracking_number", "tracking_carrier", "updated_at",
    ])
    detail = " via " + tracking_carrier if tracking_carrier else ""
    detail += f" ({tracking_number})" if tracking_number else ""
    log_event(order, actor, ("Shipped" + detail).strip(), Order.Status.SHIPPED)
    return order


@transaction.atomic
def deliver(order, actor=None):
    _check(order, Order.Status.DELIVERED)
    order.status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()
    order.save(update_fields=["status", "delivered_at", "updated_at"])
    log_event(order, actor, "Delivered", Order.Status.DELIVERED)
    return order


@transaction.atomic
def cancel(order, actor=None):
    _check(order, Order.Status.CANCELLED)
    was_paid = order.status == Order.Status.PAID
    # Restock every item.
    for item in order.items.all():
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
    # Release the coupon redemption so the coupon frees up (import locally to
    # avoid a circular import at module load).
    from coupons.models import CouponRedemption
    CouponRedemption.objects.filter(order=order).delete()
    if was_paid:
        order.refunded_total = order.total
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.save(update_fields=["status", "cancelled_at", "refunded_total", "updated_at"])
    log_event(
        order, actor,
        "Cancelled and refunded" if was_paid else "Cancelled",
        Order.Status.CANCELLED,
    )
    return order
```

### Step 3: Serializers — event nesting, new fields, transition input

In `backend/orders/serializers.py`, add an event serializer and a ship-input serializer (place near the top, after the existing imports / `OrderItemSerializer`):
```python
class OrderEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = OrderEvent
        fields = ("id", "message", "to_status", "actor_name", "created_at")


class ShipInputSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    tracking_carrier = serializers.CharField(required=False, allow_blank=True)
```
Update the imports at the top of the file to include the event model:
```python
from .models import Order, OrderItem, OrderEvent
```
In `OrderSerializer.Meta.fields`, add the new fields and `events` (place after `coupon_code`, before `total` is fine; `events` near `items`):
```python
            "subtotal", "discount_total", "shipping_total", "coupon_code",
            "paid_at", "shipped_at", "delivered_at", "cancelled_at",
            "tracking_number", "tracking_carrier", "refunded_total",
            "total", "items", "events", "created_at",
```
Add `events` to `read_only_fields` and declare it on the serializer:
```python
    items = OrderItemSerializer(many=True)
    events = OrderEventSerializer(many=True, read_only=True)
```
Add the new read-only fields to `read_only_fields`:
```python
        read_only_fields = (
            "status", "subtotal", "discount_total", "shipping_total", "total",
            "paid_at", "shipped_at", "delivered_at", "cancelled_at",
            "tracking_number", "tracking_carrier", "refunded_total", "created_at",
            "ship_recipient", "ship_phone", "ship_line1", "ship_line2",
            "ship_city", "ship_state", "ship_postal_code", "ship_country",
        )
```

### Step 4: Views — staff-wide queryset + cancel/ship/deliver actions

Replace `backend/orders/views.py` with:
```python
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import transitions
from .models import Order
from .serializers import OrderSerializer, ShipInputSerializer


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items__product", "events")
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def _transition(self, request, fn, **kwargs):
        order = self.get_object()
        try:
            fn(order, actor=request.user, **kwargs)
        except transitions.TransitionError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        return self._transition(request, transitions.mark_paid)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, transitions.cancel)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def ship(self, request, pk=None):
        serializer = ShipInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._transition(
            request, transitions.ship,
            tracking_number=serializer.validated_data.get("tracking_number", ""),
            tracking_carrier=serializer.validated_data.get("tracking_carrier", ""),
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def deliver(self, request, pk=None):
        return self._transition(request, transitions.deliver)
```
Note: cancel is allowed for any authenticated owner (queryset scoping ensures non-staff only reach their own orders) or staff. ship/deliver require `IsAdminUser`.

### Step 5: Admin actions + event inline

Replace `backend/orders/admin.py` with:
```python
from django.contrib import admin

from . import transitions
from .models import Order, OrderItem, OrderEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ("message", "to_status", "actor", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "refunded_total", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")
    inlines = [OrderItemInline, OrderEventInline]
    actions = ("mark_shipped", "mark_delivered", "cancel_orders")

    @admin.action(description="Mark selected orders shipped")
    def mark_shipped(self, request, queryset):
        for order in queryset:
            try:
                transitions.ship(order, actor=request.user)
            except transitions.TransitionError:
                self.message_user(request, f"Order #{order.id}: cannot ship from {order.status}.")

    @admin.action(description="Mark selected orders delivered")
    def mark_delivered(self, request, queryset):
        for order in queryset:
            try:
                transitions.deliver(order, actor=request.user)
            except transitions.TransitionError:
                self.message_user(request, f"Order #{order.id}: cannot deliver from {order.status}.")

    @admin.action(description="Cancel selected orders")
    def cancel_orders(self, request, queryset):
        for order in queryset:
            try:
                transitions.cancel(order, actor=request.user)
            except transitions.TransitionError:
                self.message_user(request, f"Order #{order.id}: cannot cancel from {order.status}.")
```

### Step 6: Write the tests (TDD — write FIRST, before steps 1-5 if working strictly; here append then run)

Append to `backend/orders/tests.py` (it already imports `Decimal`, `override_settings`, `Coupon`, `Category`, `Product`, `get_user_model`, `APITestCase`, `CouponRedemption`, `Order`). Add `from orders.models import OrderEvent` and `from django.contrib.auth import get_user_model` is present:
```python
@override_settings(SHIPPING_FLAT_FEE=Decimal("5.00"), FREE_SHIPPING_THRESHOLD=Decimal("50.00"))
class OrderLifecycleTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=Decimal("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", password="pw-123456")
        self.staff = User.objects.create_user(username="staff", password="pw-123456", is_staff=True)
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
        # ship requires staff
        res = self.client.post(f"/api/orders/{order.id}/ship/", {"tracking_carrier": "UPS", "tracking_number": "1Z9"}, format="json")
        self.assertEqual(res.status_code, 403)  # non-staff
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
        order = self._order()  # pending
        self.client.force_authenticate(self.staff)
        res = self.client.post(f"/api/orders/{order.id}/deliver/")  # cannot deliver a pending order
        self.assertEqual(res.status_code, 400)

    def test_cancel_restocks_and_releases_coupon(self):
        Coupon.objects.create(code="SAVE10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        order = self._order(coupon_code="SAVE10")
        self.client.post(f"/api/orders/{order.id}/pay/")
        self.p.refresh_from_db()
        stock_after_order = self.p.stock  # 10 - 2 = 8
        self.assertEqual(stock_after_order, 8)
        self.assertEqual(CouponRedemption.objects.filter(order=order).count(), 1)
        res = self.client.post(f"/api/orders/{order.id}/cancel/")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p.stock, 10)  # restocked
        self.assertEqual(order.refunded_total, order.total)  # was paid → refund recorded
        self.assertEqual(CouponRedemption.objects.filter(order=order).count(), 0)  # released

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
        other = User.objects.create_user(username="other", password="pw-123456")
        self.client.force_authenticate(other)
        res = self.client.get(f"/api/orders/{order.id}/")
        self.assertEqual(res.status_code, 404)
```

### Step 7: Make migration, run, commit

- [ ] Run `python manage.py makemigrations orders` (adds statuses choices [no DB change], fields, OrderEvent).
- [ ] Run `python manage.py migrate`.
- [ ] Run `python manage.py test orders -v 2` → expect PASS (existing PricingTests + OrderCouponTests + new OrderLifecycleTests).
- [ ] Run `python manage.py test -v 1` → full suite green.
- [ ] **Commit (the only commit for Task 1):**
```bash
git add backend/orders backend/orders/migrations
git commit -m "add order lifecycle state machine and events"
```

---

## Task 2: Line-item returns and refunds

**Files:**
- Create: `backend/returns/` (`__init__.py`, `apps.py`, `models.py`, `refunds.py`, `services.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `tests.py`, `migrations/__init__.py`)
- Modify: `backend/core/settings.py` (INSTALLED_APPS + `RETURN_WINDOW_DAYS`), `backend/core/urls.py`

### Step 1: App scaffold + settings

`backend/returns/__init__.py`: empty. `backend/returns/migrations/__init__.py`: empty.
`backend/returns/apps.py`:
```python
from django.apps import AppConfig


class ReturnsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "returns"
```
In `backend/core/settings.py`: add `"returns",` to `INSTALLED_APPS` after `"coupons",`; add at the bottom:
```python
RETURN_WINDOW_DAYS = config("RETURN_WINDOW_DAYS", default=30, cast=int)
```

### Step 2: Models

`backend/returns/models.py`:
```python
from django.conf import settings
from django.db import models

from orders.models import Order, OrderItem


class Return(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        RECEIVED = "received", "Received"
        REFUNDED = "refunded", "Refunded"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="returns")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    staff_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Return #{self.pk} for order #{self.order_id} ({self.status})"


class ReturnLine(models.Model):
    class Reason(models.TextChoices):
        DEFECTIVE = "defective", "Defective"
        WRONG_ITEM = "wrong_item", "Wrong item"
        NOT_AS_DESCRIBED = "not_as_described", "Not as described"
        NO_LONGER_NEEDED = "no_longer_needed", "No longer needed"
        OTHER = "other", "Other"

    return_request = models.ForeignKey(Return, on_delete=models.CASCADE, related_name="lines")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.quantity}× item {self.order_item_id} ({self.reason})"
```

### Step 3: Pure refund math

`backend/returns/refunds.py`:
```python
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def refund_for(return_request) -> Decimal:
    """Proportional refund: line value minus its share of the order discount.

    Shipping is never refunded.
    """
    order = return_request.order
    subtotal = order.subtotal
    total = Decimal("0")
    for line in return_request.lines.all():
        line_value = line.order_item.unit_price * line.quantity
        if subtotal and order.discount_total:
            discount_share = order.discount_total * (line_value / subtotal)
        else:
            discount_share = Decimal("0")
        total += line_value - discount_share
    return money(total)
```

### Step 4: Return state machine service

`backend/returns/services.py`:
```python
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from orders.models import Order
from orders.transitions import log_event
from products.models import Product

from .models import Return
from .refunds import refund_for

ALLOWED = {
    Return.Status.REQUESTED: {Return.Status.APPROVED, Return.Status.REJECTED},
    Return.Status.APPROVED: {Return.Status.RECEIVED, Return.Status.REJECTED},
    Return.Status.RECEIVED: {Return.Status.REFUNDED},
    Return.Status.REFUNDED: set(),
    Return.Status.REJECTED: set(),
}


class ReturnTransitionError(Exception):
    """Raised when a return status change is not allowed."""


def _check(ret, to_status):
    if to_status not in ALLOWED.get(ret.status, set()):
        raise ReturnTransitionError(f"Cannot move return from '{ret.status}' to '{to_status}'.")


@transaction.atomic
def approve(ret, actor=None):
    _check(ret, Return.Status.APPROVED)
    ret.status = Return.Status.APPROVED
    ret.decided_at = timezone.now()
    ret.save(update_fields=["status", "decided_at"])
    log_event(ret.order, actor, f"Return #{ret.id} approved")
    return ret


@transaction.atomic
def reject(ret, actor=None, staff_note=""):
    _check(ret, Return.Status.REJECTED)
    ret.status = Return.Status.REJECTED
    ret.decided_at = timezone.now()
    ret.staff_note = staff_note
    ret.save(update_fields=["status", "decided_at", "staff_note"])
    log_event(ret.order, actor, f"Return #{ret.id} rejected")
    return ret


@transaction.atomic
def receive(ret, actor=None):
    _check(ret, Return.Status.RECEIVED)
    for line in ret.lines.all():
        Product.objects.filter(pk=line.order_item.product_id).update(
            stock=F("stock") + line.quantity
        )
    ret.status = Return.Status.RECEIVED
    ret.received_at = timezone.now()
    ret.save(update_fields=["status", "received_at"])
    log_event(ret.order, actor, f"Return #{ret.id} items received and restocked")
    return ret


@transaction.atomic
def refund(ret, actor=None):
    _check(ret, Return.Status.REFUNDED)
    amount = refund_for(ret)
    ret.refund_amount = amount
    ret.status = Return.Status.REFUNDED
    ret.refunded_at = timezone.now()
    ret.save(update_fields=["status", "refund_amount", "refunded_at"])

    order = ret.order
    order.refunded_total = order.refunded_total + amount
    # Unit-count to decide partial vs full.
    purchased_units = sum(i.quantity for i in order.items.all())
    refunded_units = sum(
        line.quantity
        for r in order.returns.filter(status=Return.Status.REFUNDED)
        for line in r.lines.all()
    )
    order.status = (
        Order.Status.REFUNDED if refunded_units >= purchased_units
        else Order.Status.PARTIALLY_REFUNDED
    )
    order.save(update_fields=["refunded_total", "status", "updated_at"])
    log_event(order, actor, f"Return #{ret.id} refunded ${amount}", order.status)
    return ret
```

### Step 5: Serializers (create validation + output)

`backend/returns/serializers.py`:
```python
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers

from orders.models import Order, OrderItem

from .models import Return, ReturnLine


class ReturnLineInputSerializer(serializers.Serializer):
    order_item = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=ReturnLine.Reason.choices)
    note = serializers.CharField(required=False, allow_blank=True)


class ReturnLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="order_item.product.name", read_only=True)

    class Meta:
        model = ReturnLine
        fields = ("id", "order_item", "product_name", "quantity", "reason", "note")


class ReturnSerializer(serializers.ModelSerializer):
    lines = ReturnLineSerializer(many=True, read_only=True)

    class Meta:
        model = Return
        fields = (
            "id", "order", "status", "refund_amount", "staff_note",
            "created_at", "decided_at", "received_at", "refunded_at", "lines",
        )
        read_only_fields = (
            "status", "refund_amount", "staff_note",
            "created_at", "decided_at", "received_at", "refunded_at",
        )


class ReturnCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    lines = ReturnLineInputSerializer(many=True)

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]
        if order.user_id != request.user.id:
            raise serializers.ValidationError({"order": "Not your order."})
        if order.status != Order.Status.DELIVERED:
            raise serializers.ValidationError({"order": "Only delivered orders can be returned."})
        window = timedelta(days=settings.RETURN_WINDOW_DAYS)
        if not order.delivered_at or timezone.now() - order.delivered_at > window:
            raise serializers.ValidationError({"order": "Return window has closed."})
        if not attrs["lines"]:
            raise serializers.ValidationError({"lines": "At least one item is required."})

        # Map order_item id -> OrderItem for this order.
        items = {i.id: i for i in order.items.all()}
        # Already-returned quantities across this order's non-rejected returns.
        returned = {}
        for r in order.returns.exclude(status=Return.Status.REJECTED):
            for ln in r.lines.all():
                returned[ln.order_item_id] = returned.get(ln.order_item_id, 0) + ln.quantity

        for line in attrs["lines"]:
            oi_id = line["order_item"]
            if oi_id not in items:
                raise serializers.ValidationError({"lines": f"Item {oi_id} is not on this order."})
            remaining = items[oi_id].quantity - returned.get(oi_id, 0)
            if line["quantity"] > remaining:
                raise serializers.ValidationError(
                    {"lines": f"Item {oi_id}: only {remaining} unit(s) returnable."}
                )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        order = validated_data["order"]
        ret = Return.objects.create(order=order, requested_by=request.user)
        for line in validated_data["lines"]:
            ReturnLine.objects.create(
                return_request=ret,
                order_item=OrderItem.objects.get(pk=line["order_item"]),
                quantity=line["quantity"],
                reason=line["reason"],
                note=line.get("note", ""),
            )
        from orders.transitions import log_event
        log_event(order, request.user, f"Return #{ret.id} requested")
        return ret

    def to_representation(self, instance):
        return ReturnSerializer(instance, context=self.context).data
```

### Step 6: Views + urls

`backend/returns/views.py`:
```python
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
```
`backend/returns/urls.py`:
```python
from rest_framework.routers import DefaultRouter

from .views import ReturnViewSet

router = DefaultRouter()
router.register("returns", ReturnViewSet, basename="return")

urlpatterns = router.urls
```
In `backend/core/urls.py`, add after the coupons include:
```python
    path("api/", include("returns.urls")),
```

### Step 7: Admin

`backend/returns/admin.py`:
```python
from django.contrib import admin

from . import services
from .models import Return, ReturnLine


class ReturnLineInline(admin.TabularInline):
    model = ReturnLine
    extra = 0
    readonly_fields = ("order_item", "quantity", "reason", "note")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "refund_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("order__id", "requested_by__username")
    readonly_fields = ("order", "requested_by", "refund_amount",
                       "created_at", "decided_at", "received_at", "refunded_at")
    inlines = [ReturnLineInline]
    actions = ("approve_returns", "receive_returns", "refund_returns")

    @admin.action(description="Approve selected returns")
    def approve_returns(self, request, queryset):
        for ret in queryset:
            try:
                services.approve(ret, actor=request.user)
            except services.ReturnTransitionError:
                self.message_user(request, f"Return #{ret.id}: cannot approve from {ret.status}.")

    @admin.action(description="Mark received (restock)")
    def receive_returns(self, request, queryset):
        for ret in queryset:
            try:
                services.receive(ret, actor=request.user)
            except services.ReturnTransitionError:
                self.message_user(request, f"Return #{ret.id}: cannot receive from {ret.status}.")

    @admin.action(description="Refund selected returns")
    def refund_returns(self, request, queryset):
        for ret in queryset:
            try:
                services.refund(ret, actor=request.user)
            except services.ReturnTransitionError:
                self.message_user(request, f"Return #{ret.id}: cannot refund from {ret.status}.")
```

### Step 8: Tests

`backend/returns/tests.py`:
```python
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase

from coupons.models import Coupon
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
        self.user = User.objects.create_user(username="buyer", password="pw-123456")
        self.staff = User.objects.create_user(username="staff", password="pw-123456", is_staff=True)
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
        stock_before = self.p.stock  # 8 after ordering 2
        res = self._create_return(qty=2)
        self.assertEqual(res.status_code, 201)
        ret_id = res.data["id"]
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f"/api/returns/{ret_id}/approve/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/returns/{ret_id}/receive/").status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.stock, stock_before + 2)  # restocked on receive
        self.assertEqual(self.client.post(f"/api/returns/{ret_id}/refund/").status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REFUNDED)  # all units returned
        self.assertEqual(self.order.refunded_total, Decimal("80.00"))  # 2 × 40

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

    def test_cannot_return_more_than_purchased(self):
        res = self._create_return(qty=3)  # only 2 purchased
        self.assertEqual(res.status_code, 400)

    def test_no_double_return(self):
        first = self._create_return(qty=2)
        self.assertEqual(first.status_code, 201)
        second = self._create_return(qty=1)  # nothing left
        self.assertEqual(second.status_code, 400)

    def test_non_delivered_order_cannot_be_returned(self):
        body = {"shipping_address": "x", "items": [{"product": self.p.id, "quantity": 1}]}
        res = self.client.post("/api/orders/", body, format="json")
        new_order = Order.objects.get(id=res.data["id"])  # pending
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
        res = self.client.post(f"/api/returns/{ret_id}/approve/")  # still the buyer
        self.assertEqual(res.status_code, 403)

    def test_illegal_return_transition_rejected(self):
        ret_id = self._create_return(qty=1).data["id"]
        self.client.force_authenticate(self.staff)
        res = self.client.post(f"/api/returns/{ret_id}/refund/")  # cannot refund before received
        self.assertEqual(res.status_code, 400)


class RefundMathTests(APITestCase):
    def test_proportional_discount_applied(self):
        cat = Category.objects.create(name="Gear")
        p = Product.objects.create(name="W", price=Decimal("100.00"), stock=10, category=cat)
        user = User.objects.create_user(username="u", password="pw-123456")
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
        # line_value 100, discount_share = 10 * (100/100) = 10 → refund 90
        self.assertEqual(refund_for(ret), Decimal("90.00"))
```

### Step 9: Migrate, run, commit

- [ ] `python manage.py makemigrations returns`
- [ ] `python manage.py migrate`
- [ ] `python manage.py test returns orders -v 2` → expect PASS.
- [ ] `python manage.py test -v 1` → full suite green.
- [ ] **Commit (the only commit for Task 2):**
```bash
git add backend/returns backend/core/settings.py backend/core/urls.py
git commit -m "add line-item returns and refunds"
```

---

## Task 3: Order detail & returns UI

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/orders/[id]/page.tsx`
- Modify: `frontend/app/orders/page.tsx`

### Step 1: API client types + methods

In `frontend/lib/api.ts`, add types after the `Order` type, and extend `Order`:
```typescript
export type OrderEvent = {
  id: number;
  message: string;
  to_status: string;
  actor_name: string | null;
  created_at: string;
};

export type ReturnReason =
  | "defective" | "wrong_item" | "not_as_described" | "no_longer_needed" | "other";

export type ReturnLine = {
  id: number;
  order_item: number;
  product_name: string;
  quantity: number;
  reason: ReturnReason;
  note: string;
};

export type ReturnRequest = {
  id: number;
  order: number;
  status: "requested" | "approved" | "received" | "refunded" | "rejected";
  refund_amount: string;
  staff_note: string;
  created_at: string;
  decided_at: string | null;
  received_at: string | null;
  refunded_at: string | null;
  lines: ReturnLine[];
};
```
Extend the `Order` type (add fields):
```typescript
  paid_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  cancelled_at: string | null;
  tracking_number: string;
  tracking_carrier: string;
  refunded_total: string;
  events: OrderEvent[];
```
Also widen the `Order["status"]` union to include `"partially_refunded"` and `"refunded"`:
```typescript
  status: "pending" | "paid" | "shipped" | "delivered" | "cancelled" | "partially_refunded" | "refunded";
```
Add these methods to the `api` object (after `listOrders`):
```typescript
  getOrder: (token: string, id: number) =>
    request<Order>(`/orders/${id}/`, { headers: { Authorization: `Bearer ${token}` } }),
  cancelOrder: (token: string, id: number) =>
    request<Order>(`/orders/${id}/cancel/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }),
  listReturns: (token: string) =>
    request<Paginated<ReturnRequest>>(`/returns/`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  createReturn: (
    token: string,
    payload: { order: number; lines: { order_item: number; quantity: number; reason: ReturnReason; note?: string }[] }
  ) =>
    request<ReturnRequest>(`/returns/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
```

### Step 2: Orders list — link + new status styles

In `frontend/app/orders/page.tsx`, extend `STATUS_STYLES`:
```typescript
const STATUS_STYLES: Record<Order["status"], string> = {
  pending: "bg-yellow-100 text-yellow-800",
  paid: "bg-blue-100 text-blue-800",
  shipped: "bg-indigo-100 text-indigo-800",
  delivered: "bg-green-100 text-green-800",
  cancelled: "bg-zinc-200 text-zinc-700",
  partially_refunded: "bg-orange-100 text-orange-800",
  refunded: "bg-rose-100 text-rose-800",
};
```
Wrap the order-card header "Order #{id}" in a link to the detail page. Change:
```tsx
                <div className="font-semibold">Order #{order.id}</div>
```
to:
```tsx
                <Link href={`/orders/${order.id}`} className="font-semibold hover:underline">
                  Order #{order.id}
                </Link>
```
(`Link` is already imported in this file.)

### Step 3: Order detail page

Create `frontend/app/orders/[id]/page.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type Order, type ReturnRequest, type ReturnReason } from "@/lib/api";
import { auth } from "@/lib/auth";

const REASONS: { value: ReturnReason; label: string }[] = [
  { value: "defective", label: "Defective" },
  { value: "wrong_item", label: "Wrong item" },
  { value: "not_as_described", label: "Not as described" },
  { value: "no_longer_needed", label: "No longer needed" },
  { value: "other", label: "Other" },
];

function fmt(iso: string | null) {
  return iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
}

export default function OrderDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [order, setOrder] = useState<Order | null>(null);
  const [returns, setReturns] = useState<ReturnRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // return-form state: order_item id -> { quantity, reason }
  const [returnQty, setReturnQty] = useState<Record<number, number>>({});
  const [returnReason, setReturnReason] = useState<Record<number, ReturnReason>>({});
  const [showReturnForm, setShowReturnForm] = useState(false);

  const load = async () => {
    const token = auth.get();
    if (!token) {
      router.push(`/login?next=/orders/${id}`);
      return;
    }
    try {
      const o = await api.getOrder(token, id);
      setOrder(o);
      const r = await api.listReturns(token);
      setReturns(r.results.filter((x) => x.order === id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load order");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const cancel = async () => {
    const token = auth.get();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelOrder(token, id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setBusy(false);
    }
  };

  const submitReturn = async () => {
    const token = auth.get();
    if (!token || !order) return;
    const lines = order.items
      .filter((i) => (returnQty[i.id] ?? 0) > 0)
      .map((i) => ({
        order_item: i.id,
        quantity: returnQty[i.id],
        reason: returnReason[i.id] ?? ("other" as ReturnReason),
      }));
    if (lines.length === 0) {
      setError("Select at least one item to return");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createReturn(token, { order: id, lines });
      setShowReturnForm(false);
      setReturnQty({});
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Return request failed");
    } finally {
      setBusy(false);
    }
  };

  if (error && !order) return <p className="text-red-600 py-12">{error}</p>;
  if (!order) return <p className="text-zinc-500 py-12">Loading…</p>;

  const canCancel = order.status === "pending" || order.status === "paid";
  const canReturn = order.status === "delivered";

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Order #{order.id}</h1>
        <span className="text-sm uppercase px-2 py-1 rounded bg-zinc-100">{order.status}</span>
      </div>

      {order.tracking_number && (
        <p className="text-sm">
          Tracking: <span className="font-medium">{order.tracking_carrier} {order.tracking_number}</span>
        </p>
      )}

      <section>
        <h2 className="font-semibold mb-2">Items</h2>
        <ul className="divide-y border-y">
          {order.items.map((it) => (
            <li key={it.id} className="py-2 flex justify-between text-sm">
              <span>{it.product_name} × {it.quantity}</span>
              <span>${it.subtotal}</span>
            </li>
          ))}
        </ul>
        <div className="mt-2 text-sm space-y-1">
          <div className="flex justify-between"><span>Subtotal</span><span>${order.subtotal}</span></div>
          {Number(order.discount_total) > 0 && (
            <div className="flex justify-between text-green-700"><span>Discount</span><span>−${order.discount_total}</span></div>
          )}
          <div className="flex justify-between"><span>Shipping</span><span>{Number(order.shipping_total) === 0 ? "Free" : `$${order.shipping_total}`}</span></div>
          <div className="flex justify-between font-semibold border-t pt-1"><span>Total</span><span>${order.total}</span></div>
          {Number(order.refunded_total) > 0 && (
            <div className="flex justify-between text-rose-700"><span>Refunded</span><span>−${order.refunded_total}</span></div>
          )}
        </div>
      </section>

      <section>
        <h2 className="font-semibold mb-2">Timeline</h2>
        <ul className="space-y-1 text-sm">
          {order.events.map((ev) => (
            <li key={ev.id} className="flex justify-between">
              <span>{ev.message}</span>
              <span className="text-zinc-500">{fmt(ev.created_at)}</span>
            </li>
          ))}
        </ul>
      </section>

      {returns.length > 0 && (
        <section>
          <h2 className="font-semibold mb-2">Returns</h2>
          <ul className="space-y-2 text-sm">
            {returns.map((r) => (
              <li key={r.id} className="border rounded p-3">
                <div className="flex justify-between">
                  <span>Return #{r.id} — <span className="uppercase">{r.status}</span></span>
                  {Number(r.refund_amount) > 0 && <span className="text-rose-700">${r.refund_amount}</span>}
                </div>
                <ul className="text-zinc-600 mt-1">
                  {r.lines.map((l) => (
                    <li key={l.id}>{l.product_name} × {l.quantity} ({l.reason})</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex gap-3">
        {canCancel && (
          <button onClick={cancel} disabled={busy} className="border rounded px-4 py-2 text-sm disabled:opacity-50">
            {busy ? "…" : "Cancel order"}
          </button>
        )}
        {canReturn && !showReturnForm && (
          <button onClick={() => setShowReturnForm(true)} className="border rounded px-4 py-2 text-sm">
            Request return
          </button>
        )}
      </div>

      {showReturnForm && (
        <section className="border rounded p-4 space-y-3">
          <h2 className="font-semibold">Request a return</h2>
          {order.items.map((it) => (
            <div key={it.id} className="flex items-center gap-3 text-sm">
              <span className="flex-1">{it.product_name} (×{it.quantity})</span>
              <input
                type="number"
                min={0}
                max={it.quantity}
                value={returnQty[it.id] ?? 0}
                onChange={(e) => setReturnQty({ ...returnQty, [it.id]: Number(e.target.value) })}
                className="w-16 border rounded px-2 py-1"
              />
              <select
                value={returnReason[it.id] ?? "other"}
                onChange={(e) => setReturnReason({ ...returnReason, [it.id]: e.target.value as ReturnReason })}
                className="border rounded px-2 py-1"
              >
                {REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          ))}
          <div className="flex gap-2">
            <button onClick={submitReturn} disabled={busy} className="bg-black text-white rounded px-4 py-2 text-sm disabled:opacity-50">
              {busy ? "…" : "Submit return"}
            </button>
            <button onClick={() => setShowReturnForm(false)} className="border rounded px-4 py-2 text-sm">Cancel</button>
          </div>
        </section>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  );
}
```

### Step 4: Type-check + commit

- [ ] Run from `frontend/`: `npx tsc --noEmit` → expect zero errors. If `node_modules` missing, `npm install` first (do not commit the lockfile).
- [ ] **Commit (the only commit for Task 3):**
```bash
git add frontend/lib/api.ts frontend/app/orders
git commit -m "add order detail and returns ui"
```

---

## Task 4: Documentation

**Files:** Modify `README.md`.

### Step 1: Add lifecycle + returns to the README

In `README.md`, under the Orders API table, add the new endpoints and a Returns table. Match the existing table style:
```markdown
| POST   | /api/orders/{id}/cancel/   | owner/staff | Cancel a pending/paid order (restock + release coupon) |
| POST   | /api/orders/{id}/ship/     | staff | Body `{tracking_number, tracking_carrier}` → shipped |
| POST   | /api/orders/{id}/deliver/  | staff | shipped → delivered |
```
And a new subsection:
```markdown
### Returns

| Method | Path                       | Auth | Purpose                                          |
|--------|----------------------------|------|--------------------------------------------------|
| GET/POST | /api/returns/            | JWT  | List my returns / request a return (line items + reason) |
| GET    | /api/returns/{id}/         | owner/staff | Return detail                             |
| POST   | /api/returns/{id}/approve/ | staff | requested → approved                           |
| POST   | /api/returns/{id}/reject/  | staff | → rejected (`{staff_note}`)                    |
| POST   | /api/returns/{id}/receive/ | staff | approved → received (restock)                  |
| POST   | /api/returns/{id}/refund/  | staff | received → refunded (proportional, mock)       |
```
Add to the **Features → Cart & checkout** (or a new **Orders & returns** subsection) these bullets:
```markdown
- Full order lifecycle: pay → ship (with tracking) → deliver, plus customer cancel (restock + coupon release), with a per-event audit timeline
- Line-item returns/RMA: request specific items + reasons within a return window; staff approve → receive (restock) → refund (proportional, mock); orders reflect partial/full refunded status
```

### Step 2: Commit

- [ ] **Commit (the only commit for Task 4):**
```bash
git add README.md
git commit -m "document order lifecycle and returns"
```

---

## Self-Review notes (author)

- **Spec coverage:** lifecycle states + transitions + timestamps + tracking (Task 1); OrderEvent audit log (Task 1); cancel restock + coupon release + mock refund (Task 1); staff API + admin actions (Tasks 1-2); returns app + line-item RMA + state machine + eligibility (delivered-only, window, reason, no-double-return) (Task 2); proportional refund math + unit-counted partial/full status (Task 2); frontend detail/timeline/cancel/return UI (Task 3); docs (Task 4). Coupon release on cancel only — enforced; returns never release (no such code path). ✓
- **4-commit constraint:** exactly one commit per Task, tests bundled with code. ✓
- **Type consistency:** `transitions.{mark_paid,ship,deliver,cancel}`, `services.{approve,reject,receive,refund}`, `TransitionError`/`ReturnTransitionError`, `OrderEvent`/`Return`/`ReturnLine` (`return_request` FK name), `refund_for`, and the TS `Order`/`OrderEvent`/`ReturnRequest`/`ReturnReason` types are used consistently across tasks.
- **Known caveat:** SQLite serializes transactions, so the restock/refund atomicity is exercised but true concurrency (select_for_update on coupon) is only meaningful on Postgres — consistent with the existing codebase's test approach.
