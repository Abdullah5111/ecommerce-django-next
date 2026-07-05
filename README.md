# E-commerce — Django + Next.js

A full-stack e-commerce app built as a portfolio piece. Django REST Framework backend, Next.js 14 (App Router) frontend, PostgreSQL, JWT auth with email verification and password reset, hierarchical categories with faceted search, server-rendered product pages with reviews and structured data, saved-address book with immutable shipping snapshots on orders, server-persisted cart & wishlist with guest-merge on login, personalized product recommendations, Stripe payments, multi-channel order notifications (in-app, email, web push), a polished conversion-focused storefront UI (token-based design system, price-forward cards, a product buy box, deals rail, and a mobile bottom nav), and a scale-aware data layer (DB indexes, Postgres full-text search, atomic stock decrement, cached featured/bestsellers/related endpoints). Containerised and ready to deploy to Google Cloud Run.

## Stack

| Layer        | Tech                                                          |
|--------------|---------------------------------------------------------------|
| Frontend     | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS   |
| Backend      | Django 5, Django REST Framework, SimpleJWT (+ token blacklist)|
| Database     | PostgreSQL 16 (SQLite for the simplest dev path)              |
| Search       | Postgres `SearchVector` + `SearchRank` (icontains fallback)   |
| Cache        | Configurable backend (LocMem default; Redis via env)          |
| Container    | Docker, docker-compose                                        |
| Deploy       | Google Cloud Run + Cloud SQL + Artifact Registry              |

## Features

### Design & UX
- **Design system**: Indigo (brand) + Amber (deal) token palette in `tailwind.config.ts`, Inter via `next/font`, elevation/`shimmer` tokens, and shared primitives (`Button`, `Badge`, `Price`) so surfaces stay consistent
- **Price-forward product cards**: big price + struck-through compare-at + %-off flag, wishlist heart, "Only N left" urgency, free-shipping tag, and a compact "★ 4.5 (10) · 120 sold" meta line
- **Buy box** on product detail: delivery-date estimate, dual CTA (Add to cart + Buy now), quantity, and trust badges — sticky on desktop
- **Homepage**: gradient hero, shop-by-category tiles, and a **"Deals of the day" rail with a live countdown**
- **Mobile-first chrome**: trust top-bar, mobile bottom tab nav (Home / Wishlist / Cart / Account), and a real footer
- **Free-shipping progress nudge** in the cart ("Add $X more for free shipping")
- Dense 2-col mobile grids, route-level skeletons on navigation, and rich empty states (cart / wishlist / orders)

### Catalog
- Hierarchical categories (multi-level, with parent / `full_slug` / `level`)
- Category landing pages at clean URLs (`/c/electronics/audio`)
- Mega-menu in the header, breadcrumbs on category and product pages
- Faceted filtering: price range, in-stock, category-and-descendants
- Sort: featured, newest, price ↑ / ↓
- Search (Postgres full-text when available, icontains otherwise) scoped to category when on a category page
- Paginated grid with shareable URLs (`?page=2&priceMin=20&inStock=true&ordering=-price`)
- Personalized **"Recommended for you"** rail (logged-in users): products from the categories you've purchased / wishlisted / carted, ranked featured-first; guests see the Featured rail

### Product detail
- Server-rendered with `generateMetadata` (title, description, og:image) and `schema.org Product` JSON-LD including aggregate rating
- Image gallery with thumbnail strip + fullscreen lightbox (prev / next / Escape)
- Hash-driven tabs (`#description`, `#specifications`, `#reviews`) — shareable, scrollable on deep link
- Specifications table from `Product.specifications` (flat key→value)
- Reviews block with summary number, 5-bar rating histogram, review list, and "Write a review" form (auth-gated)
- Related products rail ("More from {category}") and recently viewed rail (localStorage)
- Wishlist heart icon; saved items shown at `/wishlist` (server-backed when logged in)
- Contextual stock urgency ("Only 3 left — order soon", "Selling fast")
- **"X sold" social proof** on product cards and detail, aggregated from real order data (paid-and-not-cancelled), compacted as `1.2k sold`; also powers the bestsellers ranking
- Mobile sticky bottom-bar with quantity stepper + Add to cart

### Cart & checkout
- Server-persisted cart & wishlist for logged-in users (REST-backed, optimistic UI); guests use `localStorage` and their items **merge into the server on login** — cart quantities summed (capped at stock), wishlist unioned
- Inline "Add to cart" with toast (no navigation)
- **Save for later**: move a cart line into a saved (wishlist-backed) section and move it back with "Move to cart" — right on the cart page
- Saved-address picker at checkout (default pre-selected) plus inline "use a different address" form
- Stripe card payments (test mode): server creates a PaymentIntent, the frontend confirms via Stripe Elements, and a signature-verified webhook marks the order paid; checkout atomically decrements stock (concurrent-safe `F()` UPDATE). **Without Stripe keys it falls back to a one-click mock payment**, so the demo runs key-free
- Orders snapshot a structured shipping address at write time — editing the saved address later doesn't mutate order history
- Per-user order history with the structured shipping snapshot rendered per order
- Promo codes at checkout: percent, fixed-amount, free-shipping, and buy-X-get-Y; one per order, validated and priced server-side with a live breakdown
- Flat-fee shipping ($5) waived over $50 subtotal or by a free-shipping coupon

### Orders & returns
- Full order lifecycle: pay → ship (with tracking) → deliver, plus customer cancel (restock + coupon release), each recorded in a per-order audit timeline
- Line-item returns/RMA: request specific items + reasons within a return window; staff approve → receive (restock) → refund (proportional to discount, shipping excluded — issued through Stripe when keys are set, mock otherwise); orders reflect partial/full refunded status

### Notifications & alerts
- Every order lifecycle event (paid, shipped, delivered, cancelled, refunded) fans out to three channels from one `notify()` call: an in-app notification row, an email, and a browser push
- **In-app notification center**: a header bell with an unread badge (polled) and dropdown, plus a full feed at `/account/notifications` with mark-read / mark-all-read
- **Email**: order-confirmation and shipping notifications (with tracking) on the existing email backend — console in dev, SMTP via env in prod
- **Web Push** (VAPID + service worker): opt-in toggle; works with the tab closed. **Disabled gracefully without VAPID keys** — the in-app center and emails still work, the subscribe UI just hides
- Notifications fire from `transaction.on_commit`, so a rolled-back transition never sends a false alert

### Auth & profile
- Register, login (by username **or** email), logout (server-side refresh-token blacklist)
- **Google sign-in** (Google Identity Services): the frontend gets a Google ID token, the backend verifies it against Google's keys and issues our own JWT; accounts link by email (a Google login into an existing password account just signs in). **Hidden gracefully when no client ID is configured**
- JWT with auto-refresh on 401 and global redirect when both tokens expire
- Email verification (`/verify-email?uid&token`) with verified badge on the account page
- Forgot / reset password (`/forgot-password`, `/reset-password?uid&token`) via Django's password-reset token generator
- **Account hub** at `/account` — Amazon-style card grid linking profile, orders, addresses, wishlist, security, and payment/notification preferences
- **Profile** (`/account/profile`): avatar upload (with initials fallback), display name + bio, date of birth + gender, and editable name
- **Phone verification**: one-time code flow (rate-limited, attempt-capped, constant-time check); code is printed to the console in dev, swap for an SMS provider in prod
- **Login & security** (`/account/security`): email + phone verification status and change-password entry point
- Address book at `/account/addresses`: list, add, edit, delete, set default
- Password-strength hints on the signup form
- Console email backend for dev; SMTP via env for production

### Scale & performance
- DB indexes on `price`, `is_active`, `is_featured`, `stock`, plus compound `(category, is_active, -created_at)`
- Postgres-conditional full-text search with `SearchVector` + `SearchRank`; SQLite gets the existing `icontains` fallback
- Atomic stock decrement (`Product.objects.filter(stock__gte=q).update(stock=F("stock") - q)`) — no oversell race
- Featured + bestsellers + per-product `related` endpoints cached for 5 minutes (`CACHES` configurable per-env)
- Reviews drive `Product.rating_avg` / `rating_count` via `post_save` / `post_delete` signals — single source of truth
- Cursor-pagination class defined for opt-in use on large catalogs
- All product images served via `next/image` (lazy loading, responsive `sizes`, AVIF/WebP)

### Admin
- Django admin for products, categories (hierarchy-aware), orders, users, reviews, addresses, coupons, returns, carts, wishlists, notifications, push subscriptions
- Inline `ProductImage` editing on products; order/return transitions exposed as admin actions

## Quick start (local, with Docker)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/
- Django admin: http://localhost:8000/admin/

The backend auto-runs migrations and seeds sample products on first boot.
Create an admin user with:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Quick start (local, without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # leave DB_ENGINE=sqlite for the simplest path
python manage.py migrate
python manage.py shell < seed.py
python manage.py runserver

# Frontend (in a new shell)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### Enabling real Stripe payments (optional)

Checkout runs in **mock mode** out of the box — no keys needed. To switch on real
card payments, set these in `backend/.env` (test-mode keys from the Stripe dashboard):

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...      # from `stripe listen` or a dashboard endpoint
```

The publishable key is handed to the frontend by the API, so no frontend env is
required. Forward webhooks locally with
`stripe listen --forward-to localhost:8000/api/payments/webhook/`.

### Enabling browser push (optional)

In-app notifications and emails work with no setup. To also send **Web Push**
(browser notifications with the tab closed), generate a VAPID keypair and set it
in `backend/.env`:

```bash
python -m py_vapid --gen          # writes private_key.pem / public_key.pem
# put the base64 keys (urlsafe) into:
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_ADMIN_EMAIL=you@example.com
```

The public key is served to the frontend via `/api/push/config/`; the subscribe
toggle then appears at `/account/notifications`. Without keys, push stays hidden.

### Enabling Google sign-in (optional)

Login/signup work with username + password out of the box. To add **Google
sign-in**, create an OAuth 2.0 Client ID (Web application) in the Google Cloud
console, add your frontend origin to *Authorized JavaScript origins*, and set it
in `backend/.env`:

```bash
GOOGLE_OAUTH_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
```

The frontend fetches the client ID from `/api/auth/google/config/`, so there's no
frontend env to set. Without it, the Google button simply doesn't render.

## API reference

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
| POST     | /api/auth/reset-password/                  | —    | `{uid, token, new_password}`                      |
| GET/POST | /api/auth/addresses/                       | JWT  | List my addresses / create a new one              |
| GET/PUT/PATCH/DELETE | /api/auth/addresses/{id}/      | JWT  | Address detail / update / delete                  |
| POST     | /api/auth/addresses/{id}/set-default/      | JWT  | Mark address as default shipping                  |

### Catalog

| Method     | Path                                          | Auth | Purpose                                                          |
|------------|-----------------------------------------------|------|------------------------------------------------------------------|
| GET        | /api/products/                                | —    | List products (paginated)                                        |
| GET        | /api/products/{slug}/                         | —    | Product detail (includes `specifications`, `images`, ratings)    |
| GET        | /api/products/featured/                       | —    | Top featured (cached 5 min)                                      |
| GET        | /api/products/bestsellers/                    | —    | Top by paid-order quantity (cached 5 min)                        |
| GET        | /api/products/recommended/                    | —/JWT | Personalized picks from purchase/wishlist/cart affinity; featured fallback for guests/new users |
| GET        | /api/products/{slug}/related/                 | —    | Up to 8 sibling products in same category (cached 5 min)         |
| GET/POST   | /api/products/{slug}/reviews/                 | —/JWT | List reviews (paginated) / create one (one per user per product) |
| GET        | /api/categories/                              | —    | Flat list                                                        |
| GET        | /api/categories/{slug}/                       | —    | By direct slug                                                   |
| GET        | /api/categories/tree/                         | —    | Full nested tree (roots → children)                              |
| GET        | /api/categories/by-path/?path=a/b/c           | —    | Category by `full_slug`, with ancestors + children               |

Product list query params:
`search`, `category__slug`, `category_path` (matches category and all descendants),
`price__gte`, `price__lte`, `in_stock=true`, `ordering` (`-?price`, `-?created_at`), `page`.

### Orders

| Method | Path                              | Auth | Purpose                                                                |
|--------|-----------------------------------|------|------------------------------------------------------------------------|
| GET    | /api/orders/                      | JWT  | List my orders (with structured shipping snapshot)                     |
| POST   | /api/orders/                      | JWT  | Create order — body accepts `shipping_address_id` or legacy `shipping_address` text; optional `coupon_code` applies a promo; response includes `subtotal`, `discount_total`, `shipping_total`, and `coupon_code` |
| GET    | /api/orders/{id}/                 | JWT  | Order detail                                                           |
| POST   | /api/orders/{id}/create-payment-intent/ | JWT  | Start payment for a pending order → `{client_secret, publishable_key, mock}` (Stripe when keyed, mock stub otherwise) |
| POST   | /api/orders/{id}/pay/             | JWT  | Confirm payment → paid. Mock mode confirms immediately; live mode requires a succeeded PaymentIntent |
| POST   | /api/payments/webhook/            | Stripe sig | Stripe webhook — `payment_intent.succeeded` marks the order paid (authoritative, signature-verified) |
| POST   | /api/orders/{id}/cancel/          | owner/staff | Cancel a pending/paid order (restock + release coupon)          |
| POST   | /api/orders/{id}/ship/            | staff | Body `{tracking_number, tracking_carrier}` → shipped              |
| POST   | /api/orders/{id}/deliver/         | staff | shipped → delivered                                               |

Order detail now includes per-status timestamps (`paid_at`, `shipped_at`, `delivered_at`, `cancelled_at`), `tracking_number`, `tracking_carrier`, `refunded_total`, and an `events` audit timeline. Staff users see all orders; ship/deliver/cancel (staff path) are also available as Django admin actions.

### Coupons

| Method | Path                  | Auth | Purpose                                                                                              |
|--------|-----------------------|------|------------------------------------------------------------------------------------------------------|
| POST   | /api/coupons/quote/   | JWT  | Price a cart with an optional `code`; returns the breakdown (subtotal, discount, shipping, total) with `coupon_error` inline for an invalid code |

### Returns

| Method   | Path                           | Auth        | Purpose                                                          |
|----------|--------------------------------|-------------|------------------------------------------------------------------|
| GET/POST | /api/returns/                  | JWT         | List my returns / request a return (line items + reason)         |
| GET      | /api/returns/{id}/             | owner/staff | Return detail                                                    |
| POST     | /api/returns/{id}/approve/     | staff       | requested → approved                                             |
| POST     | /api/returns/{id}/reject/      | staff       | → rejected (`{staff_note}`)                                      |
| POST     | /api/returns/{id}/receive/     | staff       | approved → received (restock)                                    |
| POST     | /api/returns/{id}/refund/      | staff       | received → refunded (proportional, mock)                         |

Return requests are accepted only on delivered orders within the return window (default 30 days, configurable via `RETURN_WINDOW_DAYS`). The refund is proportional to the line-item discount; shipping is not refunded. Quantities cannot exceed the original purchased quantity. Order status reflects `partially_refunded` or `refunded` once refunds are issued.

### Cart

| Method | Path                            | Auth | Purpose                                                        |
|--------|---------------------------------|------|----------------------------------------------------------------|
| GET    | /api/cart/                      | JWT  | My cart with nested products + computed total                  |
| DELETE | /api/cart/                      | JWT  | Clear the cart                                                 |
| POST   | /api/cart/items/                | JWT  | Add `{product, quantity}` (increments; capped at stock)        |
| PATCH  | /api/cart/items/{product_id}/   | JWT  | Set quantity (≤0 removes; capped at stock)                     |
| DELETE | /api/cart/items/{product_id}/   | JWT  | Remove a line                                                  |
| POST   | /api/cart/merge/                | JWT  | Merge a guest cart `{items:[{product, quantity}]}` — quantities **summed**, capped at stock |

### Wishlist

| Method | Path                              | Auth | Purpose                                                |
|--------|-----------------------------------|------|--------------------------------------------------------|
| GET    | /api/wishlist/                    | JWT  | My wishlist (nested products)                          |
| POST   | /api/wishlist/items/              | JWT  | Add `{product}` (idempotent)                           |
| DELETE | /api/wishlist/items/{product_id}/ | JWT  | Remove                                                 |
| POST   | /api/wishlist/merge/              | JWT  | Merge a guest wishlist `{product_ids:[...]}` — **unioned** |

Logged-in cart/wishlist are server-backed; guests use `localStorage` and merge into the server on login.

### Notifications & push

| Method | Path                                   | Auth | Purpose                                              |
|--------|----------------------------------------|------|------------------------------------------------------|
| GET    | /api/notifications/                    | JWT  | My notifications (paginated, newest first)           |
| GET    | /api/notifications/unread_count/       | JWT  | `{unread}` count for the header bell                 |
| POST   | /api/notifications/{id}/read/          | JWT  | Mark one read                                        |
| POST   | /api/notifications/read-all/           | JWT  | Mark all read                                        |
| GET    | /api/push/config/                      | —    | `{enabled, public_key}` — VAPID key for subscribing  |
| POST   | /api/push/subscribe/                   | JWT  | Register a browser `PushSubscription` (upsert)       |
| DELETE | /api/push/subscribe/                   | JWT  | Remove a subscription by `{endpoint}`                |

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Deployment to Google Cloud](./docs/DEPLOYMENT.md)

## License

MIT
