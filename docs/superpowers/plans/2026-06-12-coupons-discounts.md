# Coupons & Discounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a coupon/discount system (percent, fixed, free-shipping, BOGO) with a minimal flat-fee shipping model, computed and validated entirely server-side and surfaced as a price breakdown at checkout.

**Architecture:** A new `coupons` Django app holds the `Coupon` + `CouponRedemption` models and a quote endpoint. A pure pricing module (`orders/pricing.py`) is the single source of truth for the price breakdown and is called by both the quote endpoint and order creation. Order creation re-validates the coupon atomically (`select_for_update`) and snapshots totals + a `CouponRedemption`. The Next.js checkout page adds a promo-code input that previews the breakdown.

**Tech Stack:** Django 5, DRF, SimpleJWT, PostgreSQL/SQLite, Next.js 14 (App Router), TypeScript. Backend tests use DRF `APITestCase` run via `python manage.py test`. No pytest. The frontend has no test runner, so frontend tasks verify with `npx tsc --noEmit` and a manual dev-server check.

**Spec:** `docs/superpowers/specs/2026-06-12-coupons-discounts-design.md`

**Working directory for all backend commands:** `backend/` (where `manage.py` lives).
**Git identity is already configured** (`abdullah5111`). Commit messages: scoped, lowercase, imperative. **No Claude co-author trailer.**

---

## File Structure

**Backend**
- Create `backend/coupons/__init__.py`, `apps.py`, `models.py`, `admin.py`, `serializers.py`, `views.py`, `urls.py`, `tests.py`
- Create `backend/orders/pricing.py` — pure pricing service
- Create `backend/orders/tests.py` — order + pricing integration tests
- Modify `backend/core/settings.py` — add `coupons` to `INSTALLED_APPS`, shipping constants
- Modify `backend/core/urls.py` — include coupons urls
- Modify `backend/orders/models.py` — new Order total fields + coupon FK
- Modify `backend/orders/serializers.py` — accept `coupon_code`, output totals, atomic redemption
- Modify `backend/seed.py` — demo coupons

**Frontend**
- Modify `frontend/lib/api.ts` — `QuoteResult` type, `quoteOrder()`, extend `Order` + `createOrder`
- Modify `frontend/app/checkout/page.tsx` — promo input + breakdown
- Modify `frontend/app/orders/page.tsx` — render discount/shipping per order

---

## Task 1: Scaffold `coupons` app with models

**Files:**
- Create: `backend/coupons/__init__.py` (empty)
- Create: `backend/coupons/apps.py`
- Create: `backend/coupons/models.py`
- Modify: `backend/core/settings.py` (INSTALLED_APPS + shipping constants)
- Create: `backend/coupons/tests.py`

- [ ] **Step 1: Create the app config**

`backend/coupons/apps.py`:
```python
from django.apps import AppConfig


class CouponsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "coupons"
```

`backend/coupons/__init__.py`: empty file.

- [ ] **Step 2: Write the models**

`backend/coupons/models.py`:
```python
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from products.models import Category, Product


class Coupon(models.Model):
    class Kind(models.TextChoices):
        PERCENT = "percent", "Percent off"
        FIXED = "fixed", "Fixed amount off"
        FREE_SHIPPING = "free_shipping", "Free shipping"
        BOGO = "bogo", "Buy X get Y"

    code = models.CharField(max_length=40, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="percent: 0-100 | fixed: $ off | bogo: % off the free items (100 = free)",
    )
    min_subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    max_redemptions = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(null=True, blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name="coupons")
    products = models.ManyToManyField(Product, blank=True, related_name="coupons")
    buy_quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    get_quantity = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    def eligible_items(self, items):
        """items: list of (product, quantity). Returns the in-scope subset.

        Empty product+category scope means the whole catalog is eligible.
        A category in scope also matches its descendants (by full_slug).
        """
        product_ids = set(self.products.values_list("id", flat=True))
        cats = list(self.categories.all())
        if not product_ids and not cats:
            return list(items)
        cat_ids = set()
        if cats:
            q = Q()
            for c in cats:
                q |= Q(full_slug=c.full_slug) | Q(full_slug__startswith=f"{c.full_slug}/")
            cat_ids = set(Category.objects.filter(q).values_list("id", flat=True))
        return [
            (p, qty)
            for (p, qty) in items
            if p.id in product_ids or p.category_id in cat_ids
        ]

    def validate_for(self, user, items, subtotal):
        """Return the first failing reason as a string, or None if valid."""
        now = timezone.now()
        if not self.is_active:
            return "This coupon is not active."
        if self.starts_at and now < self.starts_at:
            return "This coupon is not yet valid."
        if self.expires_at and now > self.expires_at:
            return "This coupon has expired."
        if self.min_subtotal is not None and subtotal < self.min_subtotal:
            return f"Spend at least ${self.min_subtotal} to use this coupon."
        if self.max_redemptions is not None and self.redemptions.count() >= self.max_redemptions:
            return "This coupon has reached its redemption limit."
        if user is not None and self.per_user_limit is not None:
            if self.redemptions.filter(user=user).count() >= self.per_user_limit:
                return "You have already used this coupon."
        if not self.eligible_items(items):
            return "This coupon does not apply to the items in your cart."
        return None


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="redemption"
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} → order #{self.order_id}"
```

- [ ] **Step 3: Register the app and add shipping constants**

In `backend/core/settings.py`, add `"coupons",` to `INSTALLED_APPS` right after `"orders",`:
```python
    "accounts",
    "products",
    "orders",
    "coupons",
]
```

At the top of `backend/core/settings.py`, add to the imports (after the existing `from decouple import config, Csv`):
```python
from decimal import Decimal
```

At the bottom of `backend/core/settings.py`, add:
```python
# Shipping (used by orders.pricing)
SHIPPING_FLAT_FEE = Decimal(config("SHIPPING_FLAT_FEE", default="5.00"))
FREE_SHIPPING_THRESHOLD = Decimal(config("FREE_SHIPPING_THRESHOLD", default="50.00"))
```

- [ ] **Step 4: Write a failing model test**

`backend/coupons/tests.py`:
```python
from decimal import Decimal

from django.test import TestCase

from coupons.models import Coupon


class CouponModelTests(TestCase):
    def test_code_is_uppercased_on_save(self):
        c = Coupon.objects.create(code="save10", kind=Coupon.Kind.PERCENT, value=Decimal("10"))
        self.assertEqual(c.code, "SAVE10")
```

- [ ] **Step 5: Make migrations and run the test (expect failure first, then pass)**

Run: `python manage.py makemigrations coupons`
Expected: creates `coupons/migrations/0001_initial.py`.

Run: `python manage.py test coupons -v 2`
Expected: PASS (1 test). If the `orders.Order` FK target errors, confirm `orders` is listed before `coupons` in INSTALLED_APPS (it is).

- [ ] **Step 6: Commit**

```bash
git add backend/coupons backend/core/settings.py
git commit -m "add coupon model and shipping settings"
```

---

## Task 2: Coupon scope + validation rules

**Files:**
- Modify: `backend/coupons/tests.py`
- (Logic already written in Task 1 `models.py` — this task proves it.)

- [ ] **Step 1: Write failing tests for scope + each validation reason**

Append to `backend/coupons/tests.py`:
```python
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from products.models import Category, Product

User = get_user_model()


def _product(name, price, category):
    return Product.objects.create(name=name, price=Decimal(price), stock=100, category=category)


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
```

- [ ] **Step 2: Run tests**

Run: `python manage.py test coupons -v 2`
Expected: PASS (all CouponValidationTests + the Task 1 test). If `Product.objects.create` complains about a missing field, check `products/models.py` — `name`, `price`, `stock`, `category` are required and sufficient (slug auto-generates).

- [ ] **Step 3: Commit**

```bash
git add backend/coupons/tests.py
git commit -m "test coupon scope and validation rules"
```

---

## Task 3: Pricing service

**Files:**
- Create: `backend/orders/pricing.py`
- Create: `backend/orders/tests.py`

- [ ] **Step 1: Write the failing pricing tests**

`backend/orders/tests.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test orders -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'orders.pricing'`.

- [ ] **Step 3: Write the pricing module**

`backend/orders/pricing.py`:
```python
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from coupons.models import Coupon

TWO_PLACES = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class PriceQuote:
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    grand_total: Decimal
    coupon_code: str | None
    coupon_error: str | None


def _subtotal(items) -> Decimal:
    total = Decimal("0")
    for product, qty in items:
        total += product.price * qty
    return money(total)


def _bogo_discount(coupon, eligible) -> Decimal:
    units = []
    for product, qty in eligible:
        units.extend([product.price] * qty)
    units.sort()  # cheapest first receive the discount
    buy = coupon.buy_quantity or 1
    get = coupon.get_quantity or 1
    group = buy + get
    free_count = (len(units) // group) * get
    discounted = units[:free_count]
    total = sum((p * coupon.value / Decimal("100") for p in discounted), Decimal("0"))
    return money(total)


def _discount(coupon, items, subtotal) -> Decimal:
    eligible = coupon.eligible_items(items)
    if coupon.kind == Coupon.Kind.PERCENT:
        elig_subtotal = sum((p.price * q for p, q in eligible), Decimal("0"))
        return money(elig_subtotal * coupon.value / Decimal("100"))
    if coupon.kind == Coupon.Kind.FIXED:
        return money(min(coupon.value, subtotal))
    if coupon.kind == Coupon.Kind.BOGO:
        return _bogo_discount(coupon, eligible)
    # FREE_SHIPPING: no line discount; shipping is waived separately
    return Decimal("0.00")


def _shipping(subtotal, free_shipping) -> Decimal:
    if free_shipping or subtotal >= settings.FREE_SHIPPING_THRESHOLD:
        return Decimal("0.00")
    return money(settings.SHIPPING_FLAT_FEE)


def quote(items, coupon=None, user=None) -> PriceQuote:
    """Compute the authoritative price breakdown. Pure — no DB writes.

    items: list of (product, quantity).
    """
    subtotal = _subtotal(items)
    discount = Decimal("0.00")
    code = None
    error = None
    free_shipping = False

    if coupon is not None:
        error = coupon.validate_for(user, items, subtotal)
        if error is None:
            code = coupon.code
            discount = _discount(coupon, items, subtotal)
            free_shipping = coupon.kind == Coupon.Kind.FREE_SHIPPING

    shipping = _shipping(subtotal, free_shipping)
    grand = subtotal - discount + shipping
    if grand < 0:
        grand = Decimal("0.00")

    return PriceQuote(
        subtotal=subtotal,
        discount_total=money(discount),
        shipping_total=shipping,
        grand_total=money(grand),
        coupon_code=code,
        coupon_error=error,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test orders -v 2`
Expected: PASS (all PricingTests).

- [ ] **Step 5: Commit**

```bash
git add backend/orders/pricing.py backend/orders/tests.py
git commit -m "add pricing service for coupons and shipping"
```

---

## Task 4: Quote endpoint

**Files:**
- Create: `backend/coupons/serializers.py`
- Create: `backend/coupons/views.py`
- Create: `backend/coupons/urls.py`
- Modify: `backend/core/urls.py`
- Modify: `backend/coupons/tests.py`

- [ ] **Step 1: Write the serializers**

`backend/coupons/serializers.py`:
```python
from rest_framework import serializers

from products.models import Product


class QuoteItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class CouponQuoteSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    items = QuoteItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required.")
        return value
```

- [ ] **Step 2: Write the view**

`backend/coupons/views.py`:
```python
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
```

- [ ] **Step 3: Wire urls**

`backend/coupons/urls.py`:
```python
from django.urls import path

from .views import CouponQuoteView

urlpatterns = [
    path("coupons/quote/", CouponQuoteView.as_view(), name="coupon-quote"),
]
```

In `backend/core/urls.py`, include it. Open the file first to match the existing include style; add a line alongside the other `path("api/", include(...))` entries:
```python
    path("api/", include("coupons.urls")),
```
(Place it next to the existing `include("orders.urls")` / `include("products.urls")` lines.)

- [ ] **Step 4: Write failing API tests**

Append to `backend/coupons/tests.py`:
```python
from decimal import Decimal as _D

from rest_framework.test import APITestCase


class CouponQuoteApiTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Gear")
        self.p = Product.objects.create(name="Widget", price=_D("40.00"), stock=10, category=self.cat)
        self.user = User.objects.create_user(username="buyer", password="pw-123456")
        self.client.force_authenticate(self.user)

    def test_quote_requires_auth(self):
        self.client.force_authenticate(None)
        res = self.client.post("/api/coupons/quote/", {"items": [{"product": self.p.id, "quantity": 1}]}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_quote_without_code_returns_breakdown(self):
        res = self.client.post(
            "/api/coupons/quote/",
            {"items": [{"product": self.p.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["subtotal"], "40.00")
        self.assertEqual(res.data["shipping_total"], "5.00")
        self.assertIsNone(res.data["coupon_error"])

    def test_quote_with_valid_code_applies_discount(self):
        Coupon.objects.create(code="SAVE10", kind=Coupon.Kind.PERCENT, value=_D("10"))
        res = self.client.post(
            "/api/coupons/quote/",
            {"code": "save10", "items": [{"product": self.p.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res.data["discount_total"], "4.00")
        self.assertEqual(res.data["coupon_code"], "SAVE10")

    def test_quote_with_unknown_code_returns_error_inline(self):
        res = self.client.post(
            "/api/coupons/quote/",
            {"code": "NOPE", "items": [{"product": self.p.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["coupon_error"], "Invalid coupon code.")
        self.assertIsNone(res.data["coupon_code"])
```

- [ ] **Step 5: Run tests**

Run: `python manage.py test coupons -v 2`
Expected: PASS (all coupon tests).

- [ ] **Step 6: Commit**

```bash
git add backend/coupons/serializers.py backend/coupons/views.py backend/coupons/urls.py backend/core/urls.py backend/coupons/tests.py
git commit -m "add coupon quote endpoint"
```

---

## Task 5: Order total fields + coupon FK

**Files:**
- Modify: `backend/orders/models.py`

- [ ] **Step 1: Add fields to the Order model**

In `backend/orders/models.py`, add these fields to `Order` (after the existing `total` field):
```python
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(
        "coupons.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    coupon_code = models.CharField(max_length=40, blank=True)
```

Leave the existing `total`, `recalculate_total`, and other fields as they are. (`recalculate_total` stays defined but order creation will set totals from the pricing quote instead — that wiring happens in Task 6.)

- [ ] **Step 2: Make and run migration**

Run: `python manage.py makemigrations orders`
Expected: creates a migration adding the five fields.

Run: `python manage.py migrate`
Expected: applies cleanly.

- [ ] **Step 3: Verify existing tests still pass**

Run: `python manage.py test orders coupons -v 2`
Expected: PASS (Task 3 + Task 4 tests unaffected).

- [ ] **Step 4: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations
git commit -m "add order total breakdown and coupon fields"
```

---

## Task 6: Wire coupon into order creation (atomic redemption)

**Files:**
- Modify: `backend/orders/serializers.py`
- Modify: `backend/orders/tests.py`

- [ ] **Step 1: Write failing order-creation tests**

Append to `backend/orders/tests.py`:
```python
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from coupons.models import CouponRedemption
from orders.models import Order

User = get_user_model()


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test orders.tests.OrderCouponTests -v 2`
Expected: FAIL — the serializer doesn't accept `coupon_code` yet and totals aren't snapshotted (e.g. `coupon_code` assertion or redemption count fails).

- [ ] **Step 3: Update the order serializer**

In `backend/orders/serializers.py`:

(a) Update imports at the top:
```python
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from accounts.models import Address
from coupons.models import Coupon, CouponRedemption
from products.models import Product
from .models import Order, OrderItem
from .pricing import quote
```

(b) Add a `coupon_code` write field and expose the new totals. Replace the `OrderSerializer` field declarations and `Meta` with:
```python
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    shipping_address = serializers.CharField(required=False, allow_blank=True)
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.none(), write_only=True, required=False
    )
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "shipping_address",
            "shipping_address_id",
            "ship_recipient",
            "ship_phone",
            "ship_line1",
            "ship_line2",
            "ship_city",
            "ship_state",
            "ship_postal_code",
            "ship_country",
            "subtotal",
            "discount_total",
            "shipping_total",
            "coupon_code",
            "total",
            "items",
            "created_at",
        )
        read_only_fields = (
            "status",
            "subtotal",
            "discount_total",
            "shipping_total",
            "total",
            "created_at",
            "ship_recipient",
            "ship_phone",
            "ship_line1",
            "ship_line2",
            "ship_city",
            "ship_state",
            "ship_postal_code",
            "ship_country",
        )
```
Note: `coupon_code` is intentionally **not** in `read_only_fields` — it is writable on input and also returned on output (its stored value).

(c) Replace the `create` method body. Keep the existing address-resolution block; add coupon resolution, pricing, and redemption:
```python
    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        if not items_data:
            raise serializers.ValidationError({"items": "At least one item is required."})

        user = self.context["request"].user

        # Resolve + lock the coupon (if any) so the redemption count is race-safe.
        code = (validated_data.pop("coupon_code", "") or "").strip().upper()
        coupon = None
        if code:
            coupon = Coupon.objects.select_for_update().filter(code=code).first()
            if coupon is None:
                raise serializers.ValidationError({"coupon_code": "Invalid coupon code."})

        # Address resolution (unchanged).
        address = validated_data.pop("shipping_address_id", None)
        order_kwargs = {}
        if address is not None:
            order_kwargs["shipping_address"] = address.as_text()
            order_kwargs["ship_recipient"] = address.recipient
            order_kwargs["ship_phone"] = address.phone
            order_kwargs["ship_line1"] = address.line1
            order_kwargs["ship_line2"] = address.line2
            order_kwargs["ship_city"] = address.city
            order_kwargs["ship_state"] = address.state
            order_kwargs["ship_postal_code"] = address.postal_code
            order_kwargs["ship_country"] = address.country
            validated_data.pop("shipping_address", None)
        else:
            order_kwargs["shipping_address"] = validated_data.pop("shipping_address")

        # Authoritative pricing (re-validates the coupon under the lock).
        pairs = [(it["product"], it["quantity"]) for it in items_data]
        price = quote(pairs, coupon, user)
        if coupon is not None and price.coupon_error:
            raise serializers.ValidationError({"coupon_code": price.coupon_error})

        order = Order.objects.create(
            user=user,
            subtotal=price.subtotal,
            discount_total=price.discount_total,
            shipping_total=price.shipping_total,
            total=price.grand_total,
            coupon=coupon,
            coupon_code=(coupon.code if coupon else ""),
            **order_kwargs,
            **validated_data,
        )

        for item_data in items_data:
            product = item_data["product"]
            quantity = item_data["quantity"]
            updated = Product.objects.filter(
                pk=product.pk, stock__gte=quantity
            ).update(stock=F("stock") - quantity)
            if not updated:
                raise serializers.ValidationError(
                    {"items": f"Not enough stock for {product.name}."}
                )
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )

        if coupon is not None:
            CouponRedemption.objects.create(
                coupon=coupon, user=user, order=order, discount_amount=price.discount_total
            )

        return order
```
The old `order.recalculate_total()` call is removed (totals now come from `quote`). The `validate` method stays unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test orders -v 2`
Expected: PASS (PricingTests + OrderCouponTests).

- [ ] **Step 5: Run the full backend suite**

Run: `python manage.py test -v 1`
Expected: PASS (accounts + products + orders + coupons). No regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/orders/serializers.py backend/orders/tests.py
git commit -m "apply coupon and shipping at order creation"
```

---

## Task 7: Admin registration

**Files:**
- Create: `backend/coupons/admin.py`

- [ ] **Step 1: Register the models**

`backend/coupons/admin.py`:
```python
from django.contrib import admin

from .models import Coupon, CouponRedemption


class CouponRedemptionInline(admin.TabularInline):
    model = CouponRedemption
    extra = 0
    readonly_fields = ("user", "order", "discount_amount", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "kind", "value", "is_active", "starts_at", "expires_at")
    list_filter = ("kind", "is_active")
    search_fields = ("code",)
    filter_horizontal = ("categories", "products")
    inlines = [CouponRedemptionInline]


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "order", "discount_amount", "created_at")
    readonly_fields = ("coupon", "user", "order", "discount_amount", "created_at")
```

- [ ] **Step 2: Verify the admin loads**

Run: `python manage.py check`
Expected: `System check identified no issues`.

- [ ] **Step 3: Commit**

```bash
git add backend/coupons/admin.py
git commit -m "register coupon admin"
```

---

## Task 8: Seed demo coupons

**Files:**
- Modify: `backend/seed.py`

- [ ] **Step 1: Read the current seed file**

Open `backend/seed.py` and find where products/categories are created (it runs via `python manage.py shell < seed.py`). Identify a category variable for the BOGO scope (or use an unscoped BOGO if categories aren't conveniently in scope).

- [ ] **Step 2: Append coupon seeding at the end of `backend/seed.py`**

```python
# --- Demo coupons -------------------------------------------------------
from coupons.models import Coupon  # noqa: E402

Coupon.objects.get_or_create(
    code="SAVE10",
    defaults=dict(kind=Coupon.Kind.PERCENT, value=Decimal("10")),
)
Coupon.objects.get_or_create(
    code="15OFF50",
    defaults=dict(kind=Coupon.Kind.FIXED, value=Decimal("15"), min_subtotal=Decimal("50")),
)
Coupon.objects.get_or_create(
    code="FREESHIP",
    defaults=dict(kind=Coupon.Kind.FREE_SHIPPING),
)
Coupon.objects.get_or_create(
    code="BOGO",
    defaults=dict(kind=Coupon.Kind.BOGO, value=Decimal("100"), buy_quantity=1, get_quantity=1),
)
print("Seeded demo coupons: SAVE10, 15OFF50, FREESHIP, BOGO")
```
If `Decimal` isn't already imported in `seed.py`, add `from decimal import Decimal` near the top.

- [ ] **Step 3: Run the seeder and verify**

Run: `python manage.py shell < seed.py`
Expected: prints `Seeded demo coupons: ...` with no errors.

Run: `python manage.py shell -c "from coupons.models import Coupon; print(list(Coupon.objects.values_list('code', flat=True)))"`
Expected: `['15OFF50', 'BOGO', 'FREESHIP', 'SAVE10']` (order by code).

- [ ] **Step 4: Commit**

```bash
git add backend/seed.py
git commit -m "seed demo coupons"
```

---

## Task 9: Frontend API client

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add the `QuoteResult` type and extend `Order`**

In `frontend/lib/api.ts`, add after the `Order` type definition:
```typescript
export type QuoteResult = {
  subtotal: string;
  discount_total: string;
  shipping_total: string;
  grand_total: string;
  coupon_code: string | null;
  coupon_error: string | null;
};
```

Extend the `Order` type — add these fields inside the existing `Order = { ... }`:
```typescript
  subtotal: string;
  discount_total: string;
  shipping_total: string;
  coupon_code: string;
```

- [ ] **Step 2: Add `quoteOrder` and extend `createOrder` to accept `coupon_code`**

Replace the existing `createOrder` entry in the `api` object with:
```typescript
  createOrder: (
    token: string,
    payload:
      | {
          shipping_address_id: number;
          items: { product: number; quantity: number }[];
          coupon_code?: string;
        }
      | {
          shipping_address: string;
          items: { product: number; quantity: number }[];
          coupon_code?: string;
        }
  ) =>
    request<{ id: number; total: string }>(`/orders/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
  quoteOrder: (
    token: string,
    payload: { code?: string; items: { product: number; quantity: number }[] }
  ) =>
    request<QuoteResult>(`/coupons/quote/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    }),
```

- [ ] **Step 3: Type-check**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: no errors. (If `Order` is constructed literally anywhere in tests/mocks, there are none in this repo — the new fields come from the API.)

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "add quoteOrder api and coupon_code on createOrder"
```

---

## Task 10: Checkout promo code + breakdown

**Files:**
- Modify: `frontend/app/checkout/page.tsx`

- [ ] **Step 1: Add promo-code state and a quote helper**

In `frontend/app/checkout/page.tsx`, inside the `CheckoutPage` component, add state (near the other `useState` calls) and import `QuoteResult`:

Update the api import line to include the type:
```typescript
import { api, type Address, type AddressInput, type QuoteResult } from "@/lib/api";
```

Add state:
```typescript
  const [promoInput, setPromoInput] = useState("");
  const [appliedCode, setAppliedCode] = useState<string | null>(null);
  const [quote, setQuote] = useState<QuoteResult | null>(null);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [quoting, setQuoting] = useState(false);
```

- [ ] **Step 2: Add apply/remove handlers**

Add these functions inside the component (after `handleSaveNewAddress`):
```typescript
  const refreshQuote = async (code?: string) => {
    const token = auth.get();
    if (!token || items.length === 0) return;
    setQuoting(true);
    setPromoError(null);
    try {
      const result = await api.quoteOrder(token, {
        code,
        items: items.map((i) => ({ product: i.product.id, quantity: i.quantity })),
      });
      setQuote(result);
      if (code) {
        if (result.coupon_error) {
          setPromoError(result.coupon_error);
          setAppliedCode(null);
        } else {
          setAppliedCode(result.coupon_code);
        }
      }
    } catch (e) {
      setPromoError(e instanceof Error ? e.message : "Could not apply code");
    } finally {
      setQuoting(false);
    }
  };

  const applyPromo = () => {
    if (!promoInput.trim()) return;
    refreshQuote(promoInput.trim());
  };

  const removePromo = () => {
    setPromoInput("");
    setAppliedCode(null);
    setPromoError(null);
    refreshQuote();
  };
```

- [ ] **Step 3: Fetch an initial (no-code) quote when items/auth are ready**

Add a `useEffect` after the existing address-loading effect:
```typescript
  useEffect(() => {
    if (authed && items.length > 0) {
      refreshQuote(appliedCode ?? undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed, items.length]);
```

- [ ] **Step 4: Pass the applied code when placing the order**

In `placeOrder`, update the `createOrder` call to include the code:
```typescript
      const order = await api.createOrder(token, {
        shipping_address_id: addressId,
        items: items.map((i) => ({ product: i.product.id, quantity: i.quantity })),
        coupon_code: appliedCode ?? undefined,
      });
```

- [ ] **Step 5: Render the promo input + breakdown (authed branch)**

In the authed branch, replace the single total line:
```typescript
              <div className="mt-6 flex justify-between text-lg font-semibold">
                <span>Total</span>
                <span>${total.toFixed(2)}</span>
              </div>
```
with a promo box + breakdown:
```typescript
              <div className="mt-6 border-t pt-4">
                <label className="block text-sm font-medium mb-1">Promo code</label>
                <div className="flex gap-2">
                  <input
                    value={promoInput}
                    onChange={(e) => setPromoInput(e.target.value)}
                    placeholder="e.g. SAVE10"
                    className="flex-1 border rounded px-3 py-2 text-sm"
                    disabled={!!appliedCode}
                  />
                  {appliedCode ? (
                    <button
                      type="button"
                      onClick={removePromo}
                      className="px-4 py-2 text-sm border rounded"
                    >
                      Remove
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={applyPromo}
                      disabled={quoting || !promoInput.trim()}
                      className="px-4 py-2 text-sm border rounded disabled:opacity-50"
                    >
                      {quoting ? "…" : "Apply"}
                    </button>
                  )}
                </div>
                {promoError && <p className="text-red-600 text-sm mt-1">{promoError}</p>}
                {appliedCode && (
                  <p className="text-green-700 text-sm mt-1">Code {appliedCode} applied</p>
                )}
              </div>

              <div className="mt-4 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span>${quote ? quote.subtotal : total.toFixed(2)}</span>
                </div>
                {quote && Number(quote.discount_total) > 0 && (
                  <div className="flex justify-between text-green-700">
                    <span>Discount{appliedCode ? ` (${appliedCode})` : ""}</span>
                    <span>−${quote.discount_total}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Shipping</span>
                  <span>
                    {quote && Number(quote.shipping_total) === 0
                      ? "Free"
                      : `$${quote ? quote.shipping_total : "0.00"}`}
                  </span>
                </div>
                <div className="flex justify-between text-lg font-semibold border-t pt-2 mt-2">
                  <span>Total</span>
                  <span>${quote ? quote.grand_total : total.toFixed(2)}</span>
                </div>
              </div>
```

(The guest/unauthed branch keeps its simple `total` line — promo codes require login.)

- [ ] **Step 6: Type-check and manually verify**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: no errors.

Manual check (backend + frontend running, logged in, item in cart):
1. Go to `/checkout`. Breakdown shows Subtotal / Shipping / Total; shipping is `$5.00` under $50, `Free` at/over $50.
2. Enter `SAVE10`, click Apply → a green "Discount (SAVE10) −$X" line appears and Total drops.
3. Enter `NOPE` → inline red "Invalid coupon code." and no discount.
4. Click Remove → discount clears, breakdown returns to no-code state.
5. Place the order → succeeds; `/orders` shows it.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/checkout/page.tsx
git commit -m "add promo code and price breakdown to checkout"
```

---

## Task 11: Show discount + shipping in order history

**Files:**
- Modify: `frontend/app/orders/page.tsx`

- [ ] **Step 1: Replace the single total line with a breakdown**

In `frontend/app/orders/page.tsx`, replace:
```typescript
              <span className="font-semibold whitespace-nowrap">Total ${order.total}</span>
```
with:
```typescript
              <div className="text-sm text-right whitespace-nowrap">
                <div className="flex justify-end gap-6">
                  <span className="text-zinc-500">Subtotal</span>
                  <span>${order.subtotal}</span>
                </div>
                {Number(order.discount_total) > 0 && (
                  <div className="flex justify-end gap-6 text-green-700">
                    <span>Discount{order.coupon_code ? ` (${order.coupon_code})` : ""}</span>
                    <span>−${order.discount_total}</span>
                  </div>
                )}
                <div className="flex justify-end gap-6">
                  <span className="text-zinc-500">Shipping</span>
                  <span>{Number(order.shipping_total) === 0 ? "Free" : `$${order.shipping_total}`}</span>
                </div>
                <div className="flex justify-end gap-6 font-semibold border-t mt-1 pt-1">
                  <span>Total</span>
                  <span>${order.total}</span>
                </div>
              </div>
```

- [ ] **Step 2: Type-check and verify**

Run (in `frontend/`): `npx tsc --noEmit`
Expected: no errors.

Manual check: place one order with `SAVE10` and one without, then open `/orders`. The discounted order shows a green Discount line with the code; both show Subtotal / Shipping / Total.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/orders/page.tsx
git commit -m "show discount and shipping in order history"
```

---

## Task 12: Update README API table

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the quote endpoint and order fields**

In `README.md`, in the **Catalog** or a new **Coupons** API row group, add:
```markdown
### Coupons

| Method | Path                  | Auth | Purpose                                              |
|--------|-----------------------|------|------------------------------------------------------|
| POST   | /api/coupons/quote/   | JWT  | Price a cart with an optional `code`; returns the breakdown (subtotal, discount, shipping, total) with `coupon_error` inline |
```
And add a sentence under Orders noting `POST /api/orders/` now accepts an optional `coupon_code` and the order response includes `subtotal`, `discount_total`, `shipping_total`, `coupon_code`.

Add a short bullet to the **Features → Cart & checkout** section:
```markdown
- Promo codes at checkout: percent, fixed-amount, free-shipping, and buy-X-get-Y; one per order, validated and priced server-side with a live breakdown
- Flat-fee shipping ($5) waived over $50 subtotal or by a free-shipping coupon
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "document coupons and shipping in readme"
```

---

## Verification (whole feature)

- [ ] Backend suite green: `cd backend && python manage.py test -v 1`
- [ ] Frontend type-check green: `cd frontend && npx tsc --noEmit`
- [ ] Manual end-to-end: seed (`python manage.py shell < seed.py`), run both servers, log in, and confirm all four coupon types behave at checkout and appear in `/admin/coupons/` and `/orders`.

---

## Self-Review notes (author)

- **Spec coverage:** percent/fixed/free-shipping/BOGO (Task 3), all constraints — validity window, active, usage limits, min subtotal, scoping (Tasks 1–2), one-coupon-per-order (single `coupon_code` field, Task 6), flat-fee + threshold shipping (Task 3 + settings Task 1), quote endpoint (Task 4), atomic re-validation + redemption (Task 6), admin (Task 7), seed (Task 8), frontend checkout + history (Tasks 9–11). Tax explicitly omitted per spec.
- **Concurrency note:** the global-redemption-limit test is sequential. True race-safety comes from `select_for_update()` on the coupon row; under SQLite tests run serially, so a threaded test would be flaky — the lock is exercised meaningfully only on Postgres. This is acceptable and matches the existing stock-decrement test approach.
- **Type consistency:** `quote()` signature, `PriceQuote` fields, `Coupon.Kind` members, `related_name="redemptions"`, and the `QuoteResult`/`Order` TS fields are used identically across tasks.
