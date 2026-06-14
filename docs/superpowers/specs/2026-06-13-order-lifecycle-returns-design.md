# Order Lifecycle & Returns — Design

**Date:** 2026-06-13
**Status:** Approved (design), pending implementation plan
**Scope:** Backend (Django/DRF) order state machine + line-item returns (RMA), staff API + Django admin actions, and a customer-facing order detail / returns UI (Next.js).

## Goal

Turn the order's one-directional `pay()` flow into a full lifecycle with auditable
transitions, and add a line-item returns/refunds (RMA) subsystem on top.

- **Lifecycle:** ship / deliver / cancel transitions (staff + customer), per-event
  audit log, tracking number, restock + coupon-redemption release on cancel.
- **Returns:** customers request returns on specific delivered items; staff
  approve → receive (restock) → refund (proportional, mock). A full RMA state
  machine with eligibility rules.

## Decisions (from brainstorming)

| Question | Decision |
|----------|----------|
| Staff actions | **Both** Django admin actions AND staff-only (`IsAdminUser`) API endpoints |
| Returns depth | **Line-item RMA** (per-item quantity + reason, partial refunds) |
| Spec structure | **One spec**, implemented modularly |
| Audit trail | **Full `OrderEvent` log** (actor, message, to_status, timestamp) |
| Return states | `requested → approved → received → refunded` (+ `rejected`); restock on *received*, refund recorded on *refunded* |
| Return eligibility | delivered-only · within `RETURN_WINDOW_DAYS` (default 30) · reason required per line · no double-return (cap at purchased − already-returned) |
| Coupon redemption | **Released on cancel, NOT on return** |
| Refunds | **Mock** (no payment gateway yet) — record amounts + adjust status only |

## Architecture

Approach: a hand-rolled state machine (an explicit `ALLOWED_TRANSITIONS` map) plus
side-effect functions, all in `@transaction.atomic`. Returns live in their own
`returns` Django app with a **pure refund-math module** (mirrors `orders/pricing.py`).
No FSM library dependency.

```
backend/orders/
├── models.py        Order (+ statuses, timestamps, tracking, refunded_total), OrderEvent
├── transitions.py   ALLOWED_TRANSITIONS map + transition helpers (ship/deliver/cancel) + OrderEvent writes
├── serializers.py   order detail gains events + returns + new fields; transition input serializers
├── views.py         OrderViewSet: staff-wide queryset, cancel/ship/deliver actions
├── admin.py         Order admin actions + OrderEvent inline
└── tests.py

backend/returns/      NEW app
├── models.py        Return, ReturnLine
├── refunds.py       pure proportional refund calculation
├── serializers.py   ReturnSerializer (+ lines), create/validation
├── views.py         ReturnViewSet: create (customer) + approve/reject/receive/refund (staff)
├── admin.py         Return admin actions + ReturnLine inline
├── urls.py
└── tests.py

frontend/
├── app/orders/[id]/page.tsx   NEW order detail: timeline, tracking, cancel, request-return, returns list
├── app/orders/page.tsx        link each order to detail; add refunded status styles
└── lib/api.ts                 new types + methods
```

## Data model

### `Order` (modify `orders/models.py`)

Add to `Status`: `REFUNDED = "refunded"`, `PARTIALLY_REFUNDED = "partially_refunded"`.

New fields:

| Field | Type | Notes |
|-------|------|-------|
| `paid_at` | DateTime null | stamped on pay |
| `shipped_at` | DateTime null | stamped on ship |
| `delivered_at` | DateTime null | stamped on deliver; anchors the return window |
| `cancelled_at` | DateTime null | stamped on cancel |
| `tracking_number` | Char blank | set on ship |
| `tracking_carrier` | Char blank | set on ship |
| `refunded_total` | Decimal(10,2) default 0 | running sum of all return refunds |

### `OrderEvent` (new, `orders/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `order` | FK Order (CASCADE, related_name="events") | |
| `actor` | FK user (SET_NULL, null) | null = system |
| `message` | CharField(255) | human-readable, e.g. "Shipped via UPS (1Z…)" |
| `to_status` | CharField(30, blank) | order status after the transition, when applicable |
| `created_at` | DateTime auto_now_add | |

`Meta.ordering = ["created_at"]`. Written on every order and return transition.

### `Return` (new, `returns/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `order` | FK Order (PROTECT, related_name="returns") | |
| `requested_by` | FK user (PROTECT) | |
| `status` | Char choices | `Status`: REQUESTED / APPROVED / RECEIVED / REFUNDED / REJECTED |
| `refund_amount` | Decimal(10,2) default 0 | set when refunded |
| `staff_note` | CharField(255) blank | reject reason / inspection note |
| `created_at` | DateTime auto_now_add | |
| `decided_at` | DateTime null | approve/reject time |
| `received_at` | DateTime null | |
| `refunded_at` | DateTime null | |

`Meta.ordering = ["-created_at"]`.

### `ReturnLine` (new, `returns/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `return_request` | FK Return (CASCADE, related_name="lines") | (`return` is reserved; use `return_request`) |
| `order_item` | FK orders.OrderItem (PROTECT) | |
| `quantity` | PositiveSmallIntegerField | ≥1 |
| `reason` | Char choices | `Reason`: DEFECTIVE / WRONG_ITEM / NOT_AS_DESCRIBED / NO_LONGER_NEEDED / OTHER |
| `note` | CharField(255) blank | |

## Behavior

### Order transitions (`orders/transitions.py`)

A module-level map gates legal moves:

```python
ALLOWED_TRANSITIONS = {
    "pending":   {"paid", "cancelled"},
    "paid":      {"shipped", "cancelled"},
    "shipped":   {"delivered"},
    "delivered": set(),            # returns handle post-delivery
    "cancelled": set(),
    "partially_refunded": set(),
    "refunded":  set(),
}
```

Each transition helper runs in `@transaction.atomic`, validates the move, stamps
the relevant timestamp, writes an `OrderEvent(actor, message, to_status)`, and
performs side effects:

- **pay** (customer; existing endpoint moves into this pattern): pending→paid,
  stamp `paid_at`, event "Payment received".
- **ship** (staff): paid→shipped, set `tracking_number`/`tracking_carrier`, stamp
  `shipped_at`, event.
- **deliver** (staff): shipped→delivered, stamp `delivered_at`, event.
- **cancel** (customer or staff; only from pending/paid): →cancelled, **restock
  every item** (`Product.objects.filter(pk=…).update(stock=F("stock")+qty)`),
  **release coupon redemption** (delete the `CouponRedemption` for this order if
  any; `Order.coupon` is already SET_NULL and `coupon_code` snapshot is kept),
  if previously paid add a mock refund of `total` into `refunded_total`, stamp
  `cancelled_at`, event.

Illegal transitions raise `ValidationError` → 400.

### Return transitions (`returns/` + `OrderEvent` on the parent order)

- **create** (customer): build `Return(status=REQUESTED)` + lines. Validations:
  - order status == `delivered`;
  - `delivered_at` within `RETURN_WINDOW_DAYS` (setting, default 30);
  - each line `order_item` belongs to this order;
  - each line `quantity` ≤ `purchased_qty − already_returned_qty` where
    already-returned counts lines on this order's non-REJECTED returns;
  - reason present on each line; at least one line.
  - Writes an OrderEvent "Return requested".
- **approve** (staff): REQUESTED→APPROVED, set `decided_at`, event.
- **reject** (staff): REQUESTED|APPROVED→REJECTED, set `decided_at` + `staff_note`, event.
- **receive** (staff): APPROVED→RECEIVED, **restock the returned line quantities**
  (`F()` increment), set `received_at`, event.
- **refund** (staff): RECEIVED→REFUNDED, compute `refund_amount` (below), add it to
  `Order.refunded_total`, set order status to `refunded` if the cumulative refunded
  units cover the whole order, else `partially_refunded`; set `refunded_at`, event
  "Refunded $X". Mock — no money movement.

All transitions `@transaction.atomic`, gated by a Return `ALLOWED_TRANSITIONS` map.

### Refund math (`returns/refunds.py`, pure)

```
refund_for(return_request) -> Decimal:
  subtotal = order.subtotal
  total = 0
  for line in return.lines:
      line_value = line.order_item.unit_price * line.quantity
      discount_share = order.discount_total * (line_value / subtotal)   # 0 if subtotal == 0
      total += line_value - discount_share
  return money(total)   # quantize 2dp, ROUND_HALF_UP
```

Shipping is never refunded. Reuses the `money()` helper pattern from `orders/pricing.py`
(extract a shared helper if convenient, otherwise replicate the 2dp quantize).

### "Order fully refunded?" determination

After each refund, count units: `refunded_units` = Σ line quantities across this
order's REFUNDED returns; `purchased_units` = Σ order item quantities. The order
becomes `refunded` when `refunded_units == purchased_units`, otherwise
`partially_refunded` (whenever `refunded_units > 0`). Unit-counting is the chosen
rule (a value-based check is not used); it is covered by the full-vs-partial tests.

## API

`OrderViewSet.get_queryset`: `Order.objects.all()` when `request.user.is_staff`, else
filtered to the user. Existing `pay` action stays (now also stamps `paid_at` + event).

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /api/orders/{id}/cancel/ | owner or staff | Cancel a pending/paid order |
| POST | /api/orders/{id}/ship/ | staff | Body `{tracking_number, tracking_carrier}` → shipped |
| POST | /api/orders/{id}/deliver/ | staff | shipped → delivered |
| GET/POST | /api/returns/ | JWT | List my returns / create a return `{order, lines:[{order_item, quantity, reason, note}]}` |
| GET | /api/returns/{id}/ | owner or staff | Return detail |
| POST | /api/returns/{id}/approve/ | staff | requested → approved |
| POST | /api/returns/{id}/reject/ | staff | → rejected (`{staff_note}`) |
| POST | /api/returns/{id}/receive/ | staff | approved → received (restock) |
| POST | /api/returns/{id}/refund/ | staff | received → refunded (compute + record) |

Order detail (`GET /api/orders/{id}/`) gains: the new timestamp/tracking/`refunded_total`
fields, an `events` array (timeline), and a `returns` array (each with `lines`).

## Admin

- **Order admin:** admin actions "Mark shipped", "Mark delivered", "Cancel" (calling
  the same transition helpers); read-only `OrderEvent` inline; show the new fields.
- **Return admin:** list + actions "Approve", "Mark received", "Refund", "Reject";
  read-only `ReturnLine` inline; read-only timestamps.

## Frontend

- **`app/orders/[id]/page.tsx` (new):** order detail — status badge, **event
  timeline** (from `events`), tracking number when shipped, line items + totals
  (incl. `refunded_total`), a **Cancel order** button when status ∈ {pending, paid},
  and when `delivered` a **Request return** form (choose items + quantity ≤ returnable
  + reason); list existing `returns` with status + `refund_amount`.
- **`app/orders/page.tsx`:** each order card links to `/orders/[id]`; add
  `refunded` / `partially_refunded` entries to `STATUS_STYLES`.
- **`lib/api.ts`:** add `OrderEvent`, `Return`, `ReturnLine`, `ReturnReason` types;
  extend `Order` with the new fields, `events`, `returns`; add `getOrder`,
  `cancelOrder`, `shipOrder`, `deliverOrder`, `createReturn`, `listReturns`, and the
  staff return actions.

## Testing

Backend `APITestCase`s:
- order transitions: legal moves succeed + stamp timestamps + write events; illegal
  moves 400; permissions (staff-only ship/deliver; owner-or-staff cancel).
- cancel side effects: restock; coupon redemption deleted (count frees up); mock
  refund recorded if was paid.
- return creation guards: not-delivered rejected; outside window rejected; over-qty
  / double-return rejected; reason required.
- return flow: approve → receive (restock applied) → refund (amount correct incl.
  proportional discount; `refunded_total` updated; order → partially_refunded vs
  refunded); reject path; illegal return transitions 400.
- refund math unit tests (discounted + undiscounted orders, multi-line, partial).

Frontend: `npx tsc --noEmit` clean; manual check of detail page (timeline, cancel,
request-return, returns list).

## Implementation structure — 4 commits

Per the user's instruction, the work lands in **exactly four commits**, each a
coherent, independently-reviewable part (tests included in the same commit as the
code they cover):

1. **`add order lifecycle state machine and events`** — Order status/fields/`OrderEvent`,
   `transitions.py`, ship/deliver/cancel (+ pay update), restock + redemption release,
   staff API actions + staff-wide queryset, Order admin actions, migrations, tests.
2. **`add line-item returns and refunds`** — `returns` app (`Return`/`ReturnLine`,
   `refunds.py`, serializers, `ReturnViewSet` + staff actions, admin, urls), order
   status `refunded`/`partially_refunded` wiring, migrations, tests.
3. **`add order detail and returns ui`** — `app/orders/[id]/page.tsx`, orders-list
   linking + status styles, `lib/api.ts` types/methods.
4. **`document order lifecycle and returns`** — README API tables + feature bullets.

## Out of scope

- Real payment/refund money movement (mock until Stripe lands — clean integration point).
- Partial *cancellation* (cancel is whole-order only; partial unwinds go through returns).
- Exchanges/store credit, return shipping labels, restocking fees.
- Releasing coupon redemptions on returns (only cancel releases).

## Affected / new files

**Backend:** `orders/models.py`, `orders/transitions.py` (new), `orders/serializers.py`,
`orders/views.py`, `orders/admin.py`, `orders/tests.py`, `orders/migrations/*`;
`returns/` (new app: models, refunds, serializers, views, admin, urls, tests, migrations);
`core/settings.py` (INSTALLED_APPS + `RETURN_WINDOW_DAYS`), `core/urls.py`.

**Frontend:** `app/orders/[id]/page.tsx` (new), `app/orders/page.tsx`, `lib/api.ts`.
