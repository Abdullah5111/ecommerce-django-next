# Coupons & Discounts — Design

**Date:** 2026-06-12
**Status:** Approved (design), pending implementation plan
**Scope:** Backend (Django/DRF) + frontend (Next.js) coupon/discount system with a minimal shipping model.

## Goal

Add a coupon/discount feature to the e-commerce app. A customer enters a promo
code at checkout, sees the discount reflected in a price breakdown, and the
discount is recorded immutably on the resulting order. All four discount types
are supported: **percent off**, **fixed amount off**, **free shipping**, and
**buy-X-get-Y (BOGO)**.

A minimal shipping model is introduced so that "free shipping" means something:
a flat fee, waived automatically over a subtotal threshold or by a free-shipping
coupon.

## Decisions (from brainstorming)

| Question | Decision |
|----------|----------|
| Discount types | percent, fixed, free_shipping, bogo — all four, in one spec |
| Constraints | validity window + active flag, usage limits (global + per-user), min order subtotal, product/category scoping |
| Stacking | **One coupon per order** (applying a new code replaces the old) |
| Shipping model | Flat fee + free over threshold; free-shipping coupon also waives it |
| Tax | **Out of scope.** Totals are structured so tax can slot in later. |

## Core principle

**All pricing is computed and validated server-side.** The client never sends a
total or discount — it sends item ids/quantities and an optional code. The quote
endpoint and order creation both call the *same* pure pricing function so there
is a single source of truth. The coupon is **re-validated atomically at order
creation** (a code valid at quote time may be exhausted by submit time),
mirroring the existing atomic stock-decrement discipline in
`orders/serializers.py`.

## Architecture

### New `coupons` app

Keeps coupon logic isolated from order logic.

```
backend/coupons/
├── models.py        Coupon, CouponRedemption
├── admin.py         Coupon admin (+ redemption inline, read-only)
├── serializers.py   CouponQuoteSerializer (request), price-breakdown output
├── views.py         quote endpoint
├── urls.py          /api/coupons/quote/
└── tests.py         (pricing/validation covered in orders/tests.py too)
```

### Data model

**`Coupon`**

| Field | Type | Notes |
|-------|------|-------|
| `code` | CharField, unique | stored uppercase; matched case-insensitively |
| `kind` | CharField choices | `percent` \| `fixed` \| `free_shipping` \| `bogo` |
| `value` | Decimal(10,2) | percent: 0–100 · fixed: $ off · bogo: % off the free items (100 = free) · free_shipping: unused |
| `min_subtotal` | Decimal(10,2), null | minimum cart subtotal to qualify |
| `starts_at` | datetime, null | coupon not valid before this |
| `expires_at` | datetime, null | coupon not valid after this |
| `is_active` | bool, default True | manual kill switch |
| `max_redemptions` | int, null | global cap across all users |
| `per_user_limit` | int, null | cap per user |
| `categories` | M2M Category, blank | empty = whole catalog |
| `products` | M2M Product, blank | empty = whole catalog |
| `buy_quantity` | int, null | BOGO only |
| `get_quantity` | int, null | BOGO only |
| `created_at` / `updated_at` | datetime | |

`save()` uppercases `code`. Scope = union of `categories` (and descendants) and
`products`; empty scope means the whole catalog is eligible.

**`CouponRedemption`** — one row per successful use, drives usage-limit counts.

| Field | Type | Notes |
|-------|------|-------|
| `coupon` | FK Coupon (PROTECT) | |
| `user` | FK User (PROTECT) | |
| `order` | OneToOne Order (CASCADE) | one redemption per order |
| `discount_amount` | Decimal(10,2) | snapshot |
| `created_at` | datetime | |

Global usage = `count(redemptions for coupon)`; per-user usage =
`count(redemptions for coupon & user)`.

**`Order` additions** (`orders/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `subtotal` | Decimal(10,2), default 0 | Σ line subtotals |
| `discount_total` | Decimal(10,2), default 0 | coupon discount applied |
| `shipping_total` | Decimal(10,2), default 0 | shipping after waivers |
| `total` | Decimal (existing) | **redefined** = subtotal − discount + shipping |
| `coupon` | FK Coupon (SET_NULL, null) | survives coupon deletion |
| `coupon_code` | CharField, blank | text snapshot for history |

`recalculate_total()` is replaced by writing all four totals from the pricing
quote at creation time.

## Pricing service — `orders/pricing.py`

A pure module, **no DB writes**, used by both the quote endpoint and order
creation.

```python
@dataclass
class PriceQuote:
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    grand_total: Decimal
    coupon_code: str | None
    coupon_error: str | None   # None when valid (or no coupon supplied)

def quote(items, coupon=None, user=None) -> PriceQuote:
    # items = [(product, quantity), ...]
```

**Computation order**

1. **subtotal** = Σ(`product.price` × qty). All money is `Decimal`, quantized to
   2 dp with `ROUND_HALF_UP`.
2. **validate** the coupon via `coupon.validate_for(user, items, subtotal)`,
   returning the first failing reason or `None`. If invalid → discount 0,
   `coupon_error` set, pricing continues *without* the coupon (the breakdown
   still renders).
3. **discount** by kind:
   - `percent` → eligible-subtotal × value / 100
   - `fixed` → `min(value, subtotal)` (clamped, never negative)
   - `free_shipping` → 0 here; flagged to waive shipping in step 4
   - `bogo` → among in-scope units sorted cheapest-first: for every
     `buy_quantity` units purchased, the `get_quantity` cheapest units receive
     `value`% off. Deterministic and bounded.
4. **shipping** = `SHIPPING_FLAT_FEE`, waived (0) when
   `subtotal ≥ FREE_SHIPPING_THRESHOLD` **or** a valid `free_shipping` coupon
   applies.
5. **grand_total** = `subtotal − discount_total + shipping_total`, floored at 0.

**Validation reasons** (`Coupon.validate_for`): inactive, not yet started,
expired, below minimum subtotal, global redemption cap reached, per-user limit
reached, no eligible items in scope.

Settings (with defaults in `core/settings.py`):
`SHIPPING_FLAT_FEE = Decimal("5.00")`, `FREE_SHIPPING_THRESHOLD = Decimal("50.00")`.

## API

### New: quote endpoint

`POST /api/coupons/quote/` — **JWT required** (per-user limits need the user;
checkout already requires login).

Request:
```json
{ "code": "SAVE10", "items": [{ "product": 12, "quantity": 2 }] }
```
Response `200` (invalid code is an expected outcome, returned inline — not an error):
```json
{
  "subtotal": "64.00",
  "discount_total": "6.40",
  "shipping_total": "0.00",
  "grand_total": "57.60",
  "coupon_code": "SAVE10",
  "coupon_error": null
}
```

### Changed: order creation

`POST /api/orders/` accepts an optional `coupon_code`. On create, inside the
existing `@transaction.atomic` block:

1. Decrement stock (existing logic).
2. If a code was supplied, `select_for_update()` the coupon row, re-validate,
   and check/increment the global redemption count race-safely.
3. Compute the quote, snapshot `subtotal` / `discount_total` / `shipping_total`
   / `total` / `coupon` / `coupon_code` onto the order.
4. Write a `CouponRedemption`.

If the coupon became invalid/exhausted since the quote → `400` with a clear
message. Order list/detail serializers expose the four totals + `coupon_code`.

### Admin

Register `Coupon` (with M2M scope widgets) and a read-only `CouponRedemption`
inline on the coupon.

## Frontend

- **`lib/api.ts`** — add `quoteOrder(token, { code, items })`; extend
  `createOrder` input with optional `coupon_code` and the `Order` type with
  `subtotal`, `discount_total`, `shipping_total`, `coupon_code`.
- **`app/checkout/page.tsx`** — add a promo-code input with Apply / Remove. On
  apply, call `quoteOrder` and render a breakdown that replaces the single
  "Total" line:
  ```
  Subtotal           $64.00
  Discount (SAVE10)  −$6.40
  Shipping            Free
  ──────────────────────────
  Total              $57.60
  ```
  The applied code is passed to `createOrder`. An invalid code shows the inline
  `coupon_error`; the breakdown still renders without the discount.
- **`app/orders/page.tsx`** — render the discount line + coupon code + shipping
  per order in history.
- The cart page keeps its simple client-side subtotal; the authoritative
  breakdown lives at checkout.

## Testing

- **`orders/tests.py`** (none exist today; NEXT_STEPS explicitly requests order
  tests):
  - pricing unit tests per kind (percent, fixed, free_shipping, bogo)
  - each constraint failure: expired, not-yet-started, below min subtotal,
    global cap reached, per-user limit reached, out-of-scope
  - discount clamping (fixed > subtotal), grand-total floor at 0
  - BOGO math on a mixed cart
  - atomic concurrency test: global redemption cap not exceeded under
    simultaneous order creation
- **`seed.py`** — add demo coupons: `SAVE10` (10% off), `15OFF50` (fixed $15,
  min subtotal $50), `FREESHIP` (free shipping), and one BOGO, so the feature is
  visible immediately on a fresh run.

## Out of scope

- Tax calculation (structurally anticipated, not built).
- Coupon stacking (one per order).
- Shipping zones/carriers/rates beyond the flat-fee + threshold model.
- Gift cards, store credit, automatic (codeless) promotions.

## Affected files

**Backend**
- `coupons/` (new app: models, admin, serializers, views, urls, migrations)
- `orders/models.py` (Order fields), `orders/serializers.py` (coupon_code +
  totals + atomic redemption), `orders/pricing.py` (new), `orders/tests.py` (new)
- `core/settings.py` (INSTALLED_APPS, shipping constants), `core/urls.py`
- `seed.py` (demo coupons)

**Frontend**
- `lib/api.ts`, `app/checkout/page.tsx`, `app/orders/page.tsx`
