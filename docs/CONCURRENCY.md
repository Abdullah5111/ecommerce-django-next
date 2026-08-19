# Concurrency & money-path audit

This app moves money and mutates shared state (stock, coupon redemptions, refund
totals) under concurrent requests. This document records the invariants each
critical path must hold and the mechanism that enforces it, so the guarantees are
reviewable rather than implied. Every claim below is covered by a test.

## Principles

1. **Correctness over throughput.** Where a race is possible, we take a row lock
   (`select_for_update`) or an atomic conditional write, even if it serializes a
   hot row. Comments mark the ceiling where that trade-off could bite at scale.
2. **The database is the arbiter.** Invariants that must never break (no oversell,
   no over-redemption) are enforced by atomic SQL or row locks — not by
   application-level read-then-write.
3. **State machines, not status flags.** Order and return transitions go through
   an explicit allowed-transitions table under a lock, so they're idempotent and
   double-delivery-safe.

## Path-by-path

### Checkout — stock (no oversell)
`orders/serializers.py::create` decrements each line with an atomic conditional
update:

```python
updated = Product.objects.filter(pk=product.pk, stock__gte=quantity).update(stock=F("stock") - quantity)
if not updated:
    raise ValidationError(...)   # someone else took the last unit
```

The whole method is `@transaction.atomic`, so if a *later* line is out of stock,
every earlier decrement rolls back. Variants use the same pattern against
`ProductVariant`. Two buyers racing for the last unit: the DB serializes the two
`UPDATE`s; exactly one sees `stock >= qty`.

### Checkout — coupon redemption limits
The coupon row is locked for the duration of the transaction before its counts
are read:

```python
coupon = Coupon.objects.select_for_update().filter(code=code).first()
```

`validate_for` then checks `max_redemptions` / `per_user_limit` and the
`CouponRedemption` is written — all under that lock. Concurrent orders using the
same code serialize on the coupon row, so the limit can't be exceeded. (The
quote endpoint reads the count *without* a lock — acceptable, because it only
previews; enforcement happens here.)

### Reserve-then-release
Stock is reserved at order creation (status `PENDING`). Unpaid orders are
released by the `release_expired_orders` cron after `PENDING_ORDER_TTL_MINUTES`,
which restocks and deletes the coupon redemption via `transitions.cancel`. The
cron is resilient: an order that raced to `PAID` (or was already cancelled)
between the query and the `cancel()` call fails the state check and is **skipped**,
not allowed to abort the batch.

### Order transitions (pay / ship / deliver / cancel)
Each re-fetches the order `select_for_update` and validates against
`ALLOWED_TRANSITIONS` before writing. Concurrent transitions serialize on the
order row; the loser's `_check` raises. This makes the two payment-confirmation
paths — the interactive `pay` endpoint and the Stripe webhook — **idempotent**:
whichever runs second sees a non-`PENDING` order and no-ops.

### Payments — amount integrity
Marking an order paid requires more than a `succeeded` status. Both
`gateway.verify_paid` (interactive) and the webhook compare the PaymentIntent
**amount** to the order total (`to_cents(order.total)`) before transitioning, so
a mismatched or underpaid intent can't confirm an order. The webhook also
persists the intent id when it resolves an order by metadata, so a later refund
reaches the real Stripe intent instead of the mock path.

### Refunds
`returns/services.py::refund` locks both the return and the order row, computes
`max_refundable = subtotal − discount + tax − refunded_total` (floored at 0), and
caps the payout. Two refunds against different returns of the same order
serialize on the order row; the second recomputes `refunded_total` fresh under
the lock. The return that completes the order pays the exact remaining amount, so
per-return rounding can't strand a cent.

## Accepted, documented trade-offs

- **Denormalized counters** (`sold_count`, `rating_count`, `helpful_count`) are
  recomputed from source (aggregate → absolute write) without a row lock, so
  concurrent writes can momentarily lose an update. This is **self-healing**: the
  next write to that product/review recomputes the correct value. Locking every
  review/order write to remove a transient, self-correcting drift would be
  over-engineering.
- **`create_payment_intent`** isn't locked, so a concurrent double-call can create
  a duplicate (orphaned) intent. Harmless: the webhook confirms by `order_id` +
  amount regardless of which intent id is stored, and unused intents expire.
- **Phone-OTP attempt counter** is a non-atomic cache read-modify-write. The
  "attacker" is the authenticated user brute-forcing their *own* code (they can
  just request a new one), so the lost-increment window has no security value.

## Unreachable-by-design

A refund flipping a `CANCELLED` order back to `REFUNDED` looks possible in
isolation (refund checks the *return's* state, not the order's), but is
unreachable: returns require a `DELIVERED` order, and `cancel` is only allowed
from `PENDING`/`PAID`. The state machine prevents the two from coexisting.
