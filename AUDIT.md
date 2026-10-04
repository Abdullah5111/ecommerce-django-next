# Audit

Code audit of the storefront across payments, orders, returns, cart, coupons,
auth, uploads, realtime (Channels) and the frontend API contract. Findings
below are confirmed from the code; each fixed item has a regression test.

**Backend tests run only in CI** (GitHub Actions, Python 3.12 + Postgres 16).
The dev machine this audit ran on has no working Python/Django toolchain, so
no backend test was run locally. Frontend checks (`tsc`, `next build`) were
run locally.

Severity: **Critical** exploitable security / payment error / major data loss ·
**High** broken core purchase flow or incorrect money/stock · **Medium**
meaningful functional or a11y defect · **Low** minor.

## Confirmed defects — payments, orders, returns (this round)

| ID | Sev | Area | Reproduction | Expected | Actual | Root cause | File:line | Fix | Test |
|----|-----|------|--------------|----------|--------|------------|-----------|-----|------|
| P-1 | High | Payment / mock isolation | Deploy with `DEBUG=False` but no (or misspelled) `STRIPE_SECRET_KEY`; create an order; `POST /api/orders/{id}/pay/` | Paying refuses — payments aren't configured | Order marked **paid with no charge** | Mock mode = "no Stripe key", with no explicit opt-in | `backend/payments/gateway.py:26`, `backend/orders/views.py:95` | Mock mode requires `PAYMENTS_MOCK` (defaults to `DEBUG`); otherwise pay/intent return 503 | `payments/tests.py` MockIsolationTests |
| P-2 | High | Payment / webhook | Pending order; customer starts card payment; order is cancelled (customer, or `release_expired_orders` after 30 min) before Stripe confirms; `payment_intent.succeeded` arrives | Charge is refunded (or never happens) | Webhook sees non-pending order and returns — **customer charged for a cancelled order**, stock already released | `_mark_paid` returns early for any non-pending status; unpaid cancel leaves the PaymentIntent open | `backend/payments/views.py:43`, `backend/orders/transitions.py:105` | Unpaid cancel cancels the open intent (best-effort); webhook refunds any succeeded intent that isn't the one the order was paid with | `payments/tests.py` StrayPaymentTests |
| P-3 | High | Payment / webhook | Order paid; a stale tab confirms a second intent for the same order | Second charge refunded | Ignored — **double charge** | Same early return as P-2 | `backend/payments/views.py:43` | Covered by P-2's stray-payment refund | `payments/tests.py` StrayPaymentTests |
| P-4 | Medium | Refunds | Staff refunds a return (or customer cancels a paid order); Stripe refund succeeds; the surrounding DB transaction then rolls back; staff retries | One refund | **Second Stripe refund** issued | `Refund.create` has no idempotency key and runs inside the DB transaction | `backend/payments/gateway.py:125` | Idempotency key per refund purpose (`cancel-<order>`, `return-<return>`) | `payments/tests.py` refund idempotency tests |
| P-5 | Low | Order creation | `POST /api/orders/` with `"quantity": 0` lines | 400 | Order created; a zero-item order still pays the shipping fee | `OrderItemSerializer.quantity` inherits `min_value=0` from `PositiveIntegerField` | `backend/orders/serializers.py:12` | `min_value=1` | `orders/tests.py` |

## Fixed earlier (PRs #11–#13)

| ID | Sev | Area | Defect | Fix |
|----|-----|------|--------|-----|
| A-1 | High | Coupons / totals | Quote ignored variants → checkout showed a different total from the one charged | Variant-aware quote (#11) |
| A-2 | High | Settings | `DEBUG=True`, `ALLOWED_HOSTS=*`, known `SECRET_KEY` as code defaults | Secure defaults + fail-closed check (#11) |
| A-3 | High | Coupons | Pay → cancel → refund released the coupon redemption → one-use coupons reusable forever | Refunded cancels keep the redemption (#12) |
| A-4 | Medium | Auth / OTP | Non-ASCII OTP crashed `hmac.compare_digest` (500) | Input validation (#11) |
| A-5 | Medium | Checkout UI | Pay screen showed the stale quote, not the charged total | Server order total (#11) |
| A-6 | Medium | Push / security | Any URL accepted as push endpoint → server-side request to internal hosts | HTTPS + push-service host allowlist (#13) |
| A-7 | Medium | Auth | Token refresh + logout unthrottled | Shared per-IP bucket (#13) |
| A-8 | Low | Cart | Out-of-stock / non-positive adds persisted 0-quantity lines | Guard in shared add path (#13) |
| A-9 | Low | Cart | Non-numeric ids → 500 on add/merge/delete | `_as_id` at every entry point (#13) |

## Verified correct

- Stock can't oversell: conditional `UPDATE … WHERE stock >= qty` per line, inside the order transaction.
- Server prices every order; client sends only product/variant/quantity.
- Pay and webhook are idempotent (`select_for_update` + transition check); the paid amount is checked against the order total.
- Returns: remaining units re-checked under a row lock, so overlapping returns can't double-restock or over-refund; refunds capped at merchandise − discount + tax.
- Orders, returns and chat threads are scoped to their owner; staff-only actions are `IsAdminUser` at the API and gated at the WebSocket layer.

## Unverified risks

- **Refunds/disputes made in the Stripe dashboard** aren't mirrored onto orders (no `charge.refunded` / `charge.dispute.*` webhook handling).
- **Per-process cache**: throttles and phone OTPs live in `LocMemCache`; with several workers, limits are per process and an OTP may be checked by a different process. Needs Redis.
- **Push subscription re-binding**: whoever knows a subscription's endpoint URL can re-register it; the URL carries an unguessable token.
- **Stripe call inside a DB transaction** (cancel/refund): idempotency (P-4) prevents double refunds, but a refund that succeeds before a rollback is still recorded nowhere until the retry.

## Known backlog (not defects)

Live deployment · real flash-sale backend · product Q&A · referral codes ·
store credit / BNPL · live carrier tracking · broader frontend tests
(component/e2e) · remaining auth throttles.
