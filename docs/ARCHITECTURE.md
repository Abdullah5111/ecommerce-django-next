# Architecture

## High-level

```
┌────────────────┐        HTTPS         ┌─────────────────┐
│   Next.js      │ ───────────────────► │   Django REST   │
│   (Cloud Run)  │      JSON / JWT      │   (Cloud Run)   │
└────────────────┘                      └────────┬────────┘
                                                 │
                                                 │ TCP (Cloud SQL Proxy)
                                                 ▼
                                        ┌─────────────────┐
                                        │  Cloud SQL      │
                                        │  PostgreSQL 16  │
                                        └─────────────────┘
```

Static assets are served from each Cloud Run service directly:
- Django collects static files at build time and serves them via WhiteNoise.
- Next.js uses its `output: "standalone"` build, served by the Node runtime in the container.

## Backend layout

```
backend/
├── core/             # project settings, root urls, wsgi/asgi
├── accounts/         # custom User model + register/me endpoints
├── products/         # Category, Product models + read-only viewsets
├── orders/           # Order, OrderItem + create/list/pay actions
├── seed.py           # sample data seeder
├── Dockerfile        # python:3.12-slim + gunicorn
└── cloudbuild.yaml   # Cloud Build pipeline to Cloud Run
```

### Data model

```
User ──< Order ──< OrderItem >── Product >── Category
```

- `User` is a custom model on `accounts.User` (extends `AbstractUser`) with extra address/phone fields. Defined upfront so swapping later doesn't require a painful migration.
- `Order.total` is denormalised and recalculated on item changes (`recalculate_total`).
- Stock is decremented atomically inside `OrderSerializer.create` (`@transaction.atomic`).

## Frontend layout

```
frontend/
├── app/              # Next.js App Router pages
│   ├── page.tsx           # product grid
│   ├── products/[id]/     # product detail
│   ├── cart/              # cart
│   ├── checkout/          # checkout + mock payment trigger
│   ├── login/, signup/
│   └── layout.tsx         # root layout, CartProvider, header
├── components/       # Header, ProductCard
└── lib/
    ├── api.ts        # typed fetch wrapper
    ├── auth.ts       # JWT in localStorage
    └── cart.tsx      # CartContext (persisted to localStorage)
```

## Auth flow

1. User submits login → `POST /api/auth/token/` returns `{ access, refresh }`.
2. Access token stored in `localStorage` (simple for a demo; a httpOnly cookie + refresh rotation would be the production choice).
3. Authenticated requests send `Authorization: Bearer <access>`.
4. Order creation/payment requires a valid access token; the backend re-resolves `request.user` for every request.

## Trade-offs

- **localStorage JWT** — easy demo, but XSS-vulnerable. Production should use httpOnly cookies.
- **Mock payment** — `POST /orders/{id}/pay/` just flips the order status. Stripe integration is a small drop-in (intent + webhook).
- **Stock model is simple** — single integer per product. Real systems need inventory locks, reserved-vs-available stock, and idempotent order creation.
- **Single-region** — Cloud Run + Cloud SQL in one region. Add Memorystore + Cloud CDN for caching at scale.
