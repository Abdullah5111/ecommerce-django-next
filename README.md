# E-commerce — Django + Next.js

A full-stack e-commerce app built as a portfolio piece. Django REST Framework backend, Next.js 14 (App Router) frontend, PostgreSQL, JWT auth with email verification and password reset, hierarchical categories with faceted search, server-rendered product pages with reviews and structured data, saved-address book with immutable shipping snapshots on orders, and a scale-aware data layer (DB indexes, Postgres full-text search, atomic stock decrement, cached featured/bestsellers/related endpoints). Containerised and ready to deploy to Google Cloud Run.

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

### Catalog
- Hierarchical categories (multi-level, with parent / `full_slug` / `level`)
- Category landing pages at clean URLs (`/c/electronics/audio`)
- Mega-menu in the header, breadcrumbs on category and product pages
- Faceted filtering: price range, in-stock, category-and-descendants
- Sort: featured, newest, price ↑ / ↓
- Search (Postgres full-text when available, icontains otherwise) scoped to category when on a category page
- Paginated grid with shareable URLs (`?page=2&priceMin=20&inStock=true&ordering=-price`)

### Product detail
- Server-rendered with `generateMetadata` (title, description, og:image) and `schema.org Product` JSON-LD including aggregate rating
- Image gallery with thumbnail strip + fullscreen lightbox (prev / next / Escape)
- Hash-driven tabs (`#description`, `#specifications`, `#reviews`) — shareable, scrollable on deep link
- Specifications table from `Product.specifications` (flat key→value)
- Reviews block with summary number, 5-bar rating histogram, review list, and "Write a review" form (auth-gated)
- Related products rail ("More from {category}") and recently viewed rail (localStorage)
- Wishlist heart icon; saved items shown at `/wishlist`
- Contextual stock urgency ("Only 3 left — order soon", "Selling fast")
- Mobile sticky bottom-bar with quantity stepper + Add to cart

### Cart & checkout
- Client-side cart persisted to `localStorage`
- Inline "Add to cart" with toast (no navigation)
- Saved-address picker at checkout (default pre-selected) plus inline "use a different address" form
- Mock checkout that creates the order and atomically decrements stock (concurrent-safe `F()` UPDATE)
- Orders snapshot a structured shipping address at write time — editing the saved address later doesn't mutate order history
- Per-user order history with the structured shipping snapshot rendered per order
- Promo codes at checkout: percent, fixed-amount, free-shipping, and buy-X-get-Y; one per order, validated and priced server-side with a live breakdown
- Flat-fee shipping ($5) waived over $50 subtotal or by a free-shipping coupon

### Orders & returns
- Full order lifecycle: pay → ship (with tracking) → deliver, plus customer cancel (restock + coupon release), each recorded in a per-order audit timeline
- Line-item returns/RMA: request specific items + reasons within a return window; staff approve → receive (restock) → refund (proportional to discount, shipping excluded, mock payment); orders reflect partial/full refunded status

### Auth & profile
- Register, login (by username **or** email), logout (server-side refresh-token blacklist)
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
- Django admin for products, categories (hierarchy-aware), orders, users, reviews, addresses
- Inline `ProductImage` editing on products

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

## API reference

### Auth

| Method   | Path                                       | Auth | Purpose                                           |
|----------|--------------------------------------------|------|---------------------------------------------------|
| POST     | /api/auth/register/                        | —    | Create account; emails a verification link        |
| POST     | /api/auth/token/                           | —    | Login (JWT); `username` accepts username OR email |
| POST     | /api/auth/token/refresh/                   | —    | Rotate access token (refresh tokens rotate too)   |
| POST     | /api/auth/logout/                          | —    | Blacklist refresh token                           |
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
| POST   | /api/orders/{id}/pay/             | JWT  | Mock payment                                                           |
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

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Deployment to Google Cloud](./docs/DEPLOYMENT.md)

## License

MIT
