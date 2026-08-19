# Commerce — Django + Next.js

[![CI](https://github.com/Abdullah5111/ecommerce-django-next/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdullah5111/ecommerce-django-next/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5-092E20?logo=django&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A production-shaped, full-stack storefront — Django REST Framework + Next.js 14 — built to demonstrate **correctness under concurrency, money-handling you can trust, and security done properly**, not just CRUD. Catalog & faceted search, cart, coupons, an order state machine, returns/refunds, Stripe payments, and multi-channel notifications, all covered by ~250 tests running on Postgres in CI.

> **The whole app runs with zero external credentials.** Stripe, Google sign-in, and Web Push each degrade to a keyless mock so you can clone it and check out end-to-end in one command.

## Live demo

- **App:** _add your deployed URL here_ · **API docs:** `/<demo-host>/api/docs`
- **Demo login:** _add demo credentials_ — then add to cart, apply coupon `SAVE10`, and check out (runs in keyless **mock payment** mode).

<!-- Screenshots: drop 2–3 images in docs/screenshots/ and reference them here.
     A storefront/PDP shot + the checkout breakdown + Swagger UI reads best. -->

## Engineering highlights

The parts that took real thought — each is backed by tests and, where it's subtle, a `# ponytail:` note in the code marking the trade-off.

**Money correctness**
- **No-oversell inventory** — checkout decrements stock with an atomic conditional `UPDATE … WHERE stock >= qty` (products *and* variants); the whole order is one transaction, so a later line failing rolls back every earlier decrement.
- **Reserve-then-release** — stock is reserved at order creation and returned by a TTL cron (`release_expired_orders`) that skips orders which raced out of `PENDING` instead of aborting the batch.
- **Proportional refunds** — a return refunds the line's share of the order discount **plus the tax actually charged** on those items (shipping excluded), and the *final* return pays the exact remaining cent so rounding never strands money.
- **Stripe hardening** — the webhook *and* the interactive pay path both verify the PaymentIntent **amount matches the order total** (not just `status == succeeded`); zero-decimal currencies (JPY/KRW) are billed as whole units, not ×100; the webhook persists the intent id so later refunds actually reach Stripe.
- **Coupons** — redemption caps (`max_redemptions`, `per_user_limit`) enforced under a `SELECT … FOR UPDATE` row lock at checkout; percent discounts capped at the eligible subtotal; kind-aware validation on save.

**Concurrency**
- Order lifecycle is a guarded **state machine** (`select_for_update` + an explicit allowed-transitions table) — idempotent, so a Stripe webhook and the customer's "pay" click can't double-confirm.
- A cross-cutting **concurrency audit** ([docs/CONCURRENCY.md](./docs/CONCURRENCY.md)) walks every money path and shows which row lock makes each critical section safe.

**Security**
- JWT with refresh-token rotation + blacklist; **password reset revokes all outstanding sessions**.
- Django password validators enforced at registration; **scoped rate-limiting** on login/register/reset (brute-force + reset-email bombing).
- Uploads validated by real image bytes (Pillow) + an extension allowlist (no SVG script vector).

**Performance**
- **N+1 elimination** across list endpoints (prefetched variants/images, single-query coupon-scope resolution, denormalized counters via signals).
- Postgres full-text search; composite DB indexes; 5-minute caching on featured/bestsellers/related with signal-driven invalidation.

**Architecture & ops**
- Notification fan-out (email + Web Push) runs **off the request path** via a bounded thread pool (opt-in, no broker) so order transitions don't block on SMTP/push I/O.
- **OpenAPI 3** schema with Swagger UI / ReDoc; Dockerized; CI runs the suite on **Postgres 16** (so the full-text path is exercised, not just SQLite).

## Stack

| Layer     | Tech                                                          |
|-----------|---------------------------------------------------------------|
| Frontend  | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS   |
| Backend   | Django 5, Django REST Framework, SimpleJWT (+ token blacklist)|
| Database  | PostgreSQL 16 (SQLite for the simplest dev path)             |
| Search    | Postgres `SearchVector` + `SearchRank` (icontains fallback), header typeahead |
| API docs  | OpenAPI 3 via drf-spectacular — Swagger UI + ReDoc            |
| Cache     | Configurable (LocMem default; Redis via env)                 |
| Container | Docker, docker-compose                                       |
| Deploy    | Google Cloud Run + Cloud SQL + Artifact Registry            |

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000/api/ · **Interactive docs: http://localhost:8000/api/docs**
- Admin: http://localhost:8000/admin/

The backend auto-migrates and seeds sample products on first boot. Create an admin with:

```bash
docker compose exec backend python manage.py createsuperuser
```

<details>
<summary><strong>Quick start without Docker</strong></summary>

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # leave DB_ENGINE=sqlite for the simplest path
python manage.py migrate
python manage.py shell < seed.py
python manage.py runserver

# Frontend (new shell)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
</details>

## API documentation

Interactive, generated from the live code:

- **Swagger UI** — `/api/docs` (click **Authorize**, paste a JWT access token)
- **ReDoc** — `/api/redoc`
- **OpenAPI schema** — `/api/schema` (downloadable JSON/YAML; feed it to `openapi-typescript` for typed clients)

<details>
<summary><strong>REST reference (full endpoint tables)</strong></summary>

### Auth

| Method   | Path                                       | Auth | Purpose                                           |
|----------|--------------------------------------------|------|---------------------------------------------------|
| POST     | /api/auth/register/                        | —    | Create account; emails a verification link        |
| POST     | /api/auth/token/                           | —    | Login (JWT); `username` accepts username OR email |
| POST     | /api/auth/token/refresh/                   | —    | Rotate access token (refresh tokens rotate too)   |
| POST     | /api/auth/logout/                          | —    | Blacklist refresh token                           |
| GET      | /api/auth/google/config/                   | —    | `{enabled, client_id}` — whether Google sign-in is on |
| POST     | /api/auth/google/                          | —    | Exchange a Google ID token `{credential}` for our JWT pair |
| GET/PUT/PATCH | /api/auth/me/                         | JWT  | Current user; PATCH updates editable profile fields |
| POST/DELETE | /api/auth/me/avatar/                    | JWT  | Upload (multipart `avatar`) or remove profile photo |
| POST     | /api/auth/phone/send-code/                 | JWT  | `{phone}` → issue a one-time verification code     |
| POST     | /api/auth/phone/verify/                    | JWT  | `{code}` → set phone + mark verified               |
| POST     | /api/auth/verify-email/                    | —    | `{uid, token}` → mark email verified              |
| POST     | /api/auth/forgot-password/                 | —    | `{email}` → always 200 (no email-existence leak)  |
| POST     | /api/auth/reset-password/                  | —    | `{uid, token, new_password}` (revokes all sessions) |
| GET/POST | /api/auth/addresses/                       | JWT  | List my addresses / create a new one              |
| GET/PUT/PATCH/DELETE | /api/auth/addresses/{id}/      | JWT  | Address detail / update / delete                  |
| POST     | /api/auth/addresses/{id}/set-default/      | JWT  | Mark address as default shipping                  |

Auth endpoints are **rate-limited** per client IP (login 10/min; register & password flows 10/hour).

### Catalog

| Method     | Path                                          | Auth | Purpose                                                          |
|------------|-----------------------------------------------|------|------------------------------------------------------------------|
| GET        | /api/products/                                | —    | List products (paginated)                                        |
| GET        | /api/products/{slug}/                         | —    | Product detail (includes `specifications`, `images`, ratings, `variants[]`) |
| GET        | /api/products/featured/                       | —    | Top featured (cached 5 min)                                      |
| GET        | /api/products/bestsellers/                    | —    | Top by paid-order quantity (cached 5 min)                        |
| GET        | /api/products/recommended/                    | —/JWT | Personalized picks from purchase/wishlist/cart affinity; featured fallback |
| GET        | /api/products/{slug}/related/                 | —    | Up to 8 sibling products in same category (cached 5 min)         |
| GET/POST   | /api/products/{slug}/reviews/                 | —/JWT | List reviews (`?ordering=helpful`) / create (one per user; JSON or multipart with up to 5 `images`) |
| POST/DELETE | /api/reviews/{id}/helpful/                   | JWT  | Toggle "helpful" vote → `{helpful_count, helpful_by_me}`; 400 on your own review |
| GET        | /api/categories/                              | —    | Flat list                                                        |
| GET        | /api/categories/{slug}/                       | —    | By direct slug                                                   |
| GET        | /api/categories/tree/                         | —    | Full nested tree (roots → children)                              |
| GET        | /api/categories/by-path/?path=a/b/c           | —    | Category by `full_slug`, with ancestors + children               |

Product list params: `search`, `category__slug`, `category_path` (category + descendants), `price__gte`, `price__lte`, `in_stock=true`, `ordering` (`-?price`, `-?created_at`), `page`.

### Orders

| Method | Path                              | Auth | Purpose                                                                |
|--------|-----------------------------------|------|------------------------------------------------------------------------|
| GET    | /api/orders/                      | JWT  | List my orders (with structured shipping snapshot)                     |
| POST   | /api/orders/                      | JWT  | Create order — `shipping_address_id` or `shipping_address`; items may carry a `variant`; optional `coupon_code`; response has full price breakdown |
| GET    | /api/orders/{id}/                 | JWT  | Order detail (per-status timestamps, tracking, `refunded_total`, `events` audit) |
| POST   | /api/orders/{id}/create-payment-intent/ | JWT  | Start payment → `{client_secret, publishable_key, mock}` (Stripe when keyed, mock otherwise) |
| POST   | /api/orders/{id}/pay/             | JWT  | Confirm payment → paid (mock confirms immediately; live verifies the intent amount) |
| POST   | /api/payments/webhook/            | Stripe sig | `payment_intent.succeeded` marks the order paid (authoritative, signature- + amount-verified) |
| POST   | /api/orders/{id}/cancel/          | owner/staff | Cancel a pending/paid order (restock + release coupon)          |
| POST   | /api/orders/{id}/ship/            | staff | `{tracking_number, tracking_carrier}` → shipped                  |
| POST   | /api/orders/{id}/deliver/         | staff | shipped → delivered                                               |

### Coupons

| Method | Path                  | Auth | Purpose                                                                 |
|--------|-----------------------|------|-------------------------------------------------------------------------|
| POST   | /api/coupons/quote/   | JWT  | Price a cart with optional `code`; returns breakdown with `coupon_error` inline |

### Returns

| Method   | Path                           | Auth        | Purpose                                          |
|----------|--------------------------------|-------------|--------------------------------------------------|
| GET/POST | /api/returns/                  | JWT         | List my returns / request one (line items + reason) |
| GET      | /api/returns/{id}/             | owner/staff | Return detail                                    |
| POST     | /api/returns/{id}/approve/     | staff       | requested → approved                             |
| POST     | /api/returns/{id}/reject/      | staff       | → rejected (`{staff_note}`)                      |
| POST     | /api/returns/{id}/receive/     | staff       | approved → received (restock)                    |
| POST     | /api/returns/{id}/refund/      | staff       | received → refunded (proportional)              |

Returns are accepted only on delivered orders within `RETURN_WINDOW_DAYS` (default 30). Refund is proportional to the line discount + the tax charged; shipping isn't refunded; quantities can't exceed those purchased.

### Cart

| Method | Path                            | Auth | Purpose                                                        |
|--------|---------------------------------|------|----------------------------------------------------------------|
| GET    | /api/cart/                      | JWT  | My cart with nested products + computed total                  |
| DELETE | /api/cart/                      | JWT  | Clear the cart                                                 |
| POST   | /api/cart/items/                | JWT  | Add `{product, quantity, variant?}` (increments; capped at stock) |
| PATCH  | /api/cart/items/{product_id}/   | JWT  | Set quantity (≤0 removes; capped at stock)                     |
| DELETE | /api/cart/items/{product_id}/   | JWT  | Remove a line                                                  |
| POST   | /api/cart/merge/                | JWT  | Merge a guest cart — quantities **summed**, capped at stock    |

### Wishlist

| Method | Path                              | Auth | Purpose                                                |
|--------|-----------------------------------|------|--------------------------------------------------------|
| GET    | /api/wishlist/                    | JWT  | My wishlist (nested products)                          |
| POST   | /api/wishlist/items/              | JWT  | Add `{product}` (idempotent)                           |
| DELETE | /api/wishlist/items/{product_id}/ | JWT  | Remove                                                 |
| POST   | /api/wishlist/merge/              | JWT  | Merge a guest wishlist `{product_ids:[...]}` — **unioned** |

### Notifications & push

| Method | Path                                   | Auth | Purpose                                              |
|--------|----------------------------------------|------|------------------------------------------------------|
| GET    | /api/notifications/                    | JWT  | My notifications (paginated, newest first)           |
| GET    | /api/notifications/unread_count/       | JWT  | `{unread}` count for the header bell                 |
| POST   | /api/notifications/{id}/read/          | JWT  | Mark one read                                        |
| POST   | /api/notifications/read-all/           | JWT  | Mark all read                                        |
| GET    | /api/push/config/                      | —    | `{enabled, public_key}` — VAPID key for subscribing  |
| POST/DELETE | /api/push/subscribe/              | JWT  | Register / remove a browser `PushSubscription`       |

</details>

<details>
<summary><strong>Full feature list</strong> (design & UX, catalog, PDP, checkout, orders, notifications, auth, admin)</summary>

### Design & UX
- **Design system**: Indigo (brand) + Amber (deal) token palette, Inter via `next/font`, shared primitives (`Button`, `Badge`, `Price`)
- **Price-forward cards**: big price + struck-through compare-at + %-off flag, wishlist heart, "Only N left" urgency, free-shipping tag, `★ 4.5 (10) · 120 sold` meta
- **Buy box** on PDP: delivery estimate, dual CTA, quantity, trust badges — sticky on desktop
- **Homepage**: gradient hero, shop-by-category tiles, "Deals of the day" rail with live countdown
- **Mobile chrome**: trust top-bar, bottom tab nav, real footer, free-shipping progress nudge in the cart
- Route-level skeletons and rich empty states (cart / wishlist / orders)

### Catalog
- Hierarchical categories (parent / `full_slug` / `level`), category landing pages at clean URLs (`/c/electronics/audio`), mega-menu, breadcrumbs
- Faceted filtering (price range, in-stock, category-and-descendants), sort (featured/newest/price), category-scoped search
- Debounced typeahead autocomplete with thumbnail/price rows, keyboard nav, stale-response guarding
- Shareable paginated grids; personalized "Recommended for you" rail

### Product detail
- Server-rendered with `generateMetadata` + `schema.org Product` JSON-LD (aggregate rating)
- Image gallery + fullscreen lightbox; hash-driven shareable tabs; specifications table
- Reviews: summary + 5-bar histogram, **verified-purchase badge** (snapshotted at write time), **photo reviews** (≤5, server-validated bytes), **"helpful" votes** (one/user, optimistic, self-vote disallowed)
- **Product variants** (size/color/SKU): per-variant stock + optional price override; cart, checkout, stock decrement, and refunds all variant-aware
- Related + recently-viewed rails; "X sold" social proof from real orders

### Cart & checkout
- Server-persisted cart & wishlist; guest items **merge on login** (quantities summed/capped, wishlist unioned)
- Save-for-later; saved-address picker; structured shipping snapshot on orders (immutable to later edits)
- Stripe Elements + signature-verified webhook; **keyless mock payment** without keys
- Promo codes (percent / fixed / free-shipping / BOGO), flat-fee shipping waived over $50, configurable sales tax

### Orders & returns
- Full lifecycle (pay → ship w/ tracking → deliver) + customer cancel (restock + coupon release), each in a per-order audit timeline
- Line-item returns/RMA with staff approve → receive (restock) → refund

### Notifications
- Every lifecycle event fans out to in-app + email + Web Push from one `notify()` call (off the request path)
- In-app center (header bell + `/account/notifications`), console/SMTP email, VAPID Web Push — each degrades gracefully

### Auth & profile
- Register, login by username **or** email, logout (refresh-token blacklist), **Google sign-in**, JWT auto-refresh
- Email verification, forgot/reset password, account hub, profile (avatar/bio/DOB), **phone verification** (rate-limited, attempt-capped, constant-time), address book

### Admin
- Hierarchy-aware admin for the full catalog + orders/users/reviews/coupons/returns; inline image/variant editing; order/return transitions as admin actions

</details>

## Optional integrations

All three are **off by default and the app runs fine without them.** Set the env vars to switch each on.

<details>
<summary>Stripe payments · Web Push · Google sign-in — setup</summary>

**Stripe** (`backend/.env`): `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`. Forward webhooks locally with `stripe listen --forward-to localhost:8000/api/payments/webhook/`. The publishable key is served to the frontend by the API.

**Web Push**: `python -m py_vapid --gen`, then set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_ADMIN_EMAIL`. The subscribe toggle appears once configured; otherwise it's hidden.

**Google sign-in**: create an OAuth 2.0 Web client, add your frontend origin to Authorized JS origins, set `GOOGLE_OAUTH_CLIENT_ID`. The frontend fetches the client id from the API; without it the button doesn't render.

</details>

## Testing & CI

- **~250 backend tests** (DRF `APITestCase`) across auth, catalog, variants, cart, orders, coupons, tax, returns, reviews, notifications, payments, and the concurrency paths — plus a smoke test that the OpenAPI schema builds.
- **GitHub Actions** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) on every push/PR: a backend job on **Postgres 16** (exercising the full-text path) and a frontend job running `tsc --noEmit` + `next build`.

```bash
cd backend && python manage.py test        # backend suite
cd frontend && npm run build               # type-check + production build
```

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Concurrency & money-path audit](./docs/CONCURRENCY.md)
- [Deployment to Google Cloud](./docs/DEPLOYMENT.md)

## License

MIT — see [LICENSE](./LICENSE).
</content>
</invoke>
