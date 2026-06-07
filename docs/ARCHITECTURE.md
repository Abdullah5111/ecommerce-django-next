# Architecture

## High-level

```
┌────────────────┐        HTTPS         ┌─────────────────┐
│   Next.js      │ ───────────────────► │   Django REST   │
│   (Cloud Run)  │      JSON / JWT      │   (Cloud Run)   │
└────────────────┘                      └────────┬────────┘
                                                 │
                          ┌──────────────────────┼──────────────────────┐
                          │ TCP (Cloud SQL       │                      │
                          ▼ Proxy)               ▼ (LocMem in dev,      ▼ (console in dev,
                  ┌─────────────────┐    ┌─────────────────┐   ┌─────────────────┐
                  │  Cloud SQL      │    │ Cache backend   │   │ Email backend   │
                  │  PostgreSQL 16  │    │ (LocMem/Redis)  │   │ (SMTP in prod)  │
                  └─────────────────┘    └─────────────────┘   └─────────────────┘
```

Static assets are served from each Cloud Run service directly:
- Django collects static files at build time and serves them via WhiteNoise.
- Next.js uses its `output: "standalone"` build, served by the Node runtime in the container.
- Product images are served from external URLs (Unsplash today) routed through Next.js' `/_next/image` proxy for automatic AVIF/WebP, responsive `sizes`, and lazy loading.

## Backend layout

```
backend/
├── core/                  # project settings, root urls, wsgi/asgi
├── accounts/              # custom User model + auth views (register, me, verify, reset)
├── products/
│   ├── models.py          # Category (self-FK), Product, ProductImage
│   ├── views.py           # ViewSets + tree/by-path + featured/bestsellers actions
│   ├── pagination.py      # ProductCursorPagination (opt-in)
│   └── migrations/
├── orders/                # Order, OrderItem + create/list/pay
├── seed.py                # idempotent hierarchical seeder
├── Dockerfile             # python:3.12-slim + gunicorn
└── cloudbuild.yaml        # Cloud Build pipeline to Cloud Run
```

### Data model

```
User ─< Order ─< OrderItem >─ Product >─ Category (self-FK: parent/children)
                                  │
                                  └─< ProductImage
```

- **`User`** — custom model on `accounts.User` (extends `AbstractUser`), with `email` (unique), `address`, `phone`, `email_verified`. Defined upfront so swapping later doesn't require a painful migration.
- **`Category`** — self-referential. `parent`, computed `full_slug` (e.g. `electronics/audio`), `level`. `save()` keeps the latter two coherent on writes. Indexed on the unique `full_slug` for fast path lookups.
- **`Product`** — `category` FK, pricing (`price`, `compare_at_price`, computed `is_on_sale`/`discount_percent`), `stock`, `rating_avg`/`rating_count` (denormalised), `is_featured`, `is_active`. Has many `ProductImage`s; keeps a legacy `image_url` for backward compatibility.
- **`ProductImage`** — `url`, `alt`, `sort_order`. Ordered.
- **`Order.total`** — denormalised, recalculated on item changes (`recalculate_total`).
- **Stock decrement** — done with an atomic conditional UPDATE (`Product.objects.filter(stock__gte=qty).update(stock=F("stock") - qty)`) inside `OrderSerializer.create`'s `@transaction.atomic`, eliminating the read-then-write oversell race.

### Indexes

Defined on `Product.Meta.indexes`:
- single-column on `price`, `is_active`, `is_featured`, `stock`
- compound `(category, is_active, -created_at)` — matches the dominant "newest in category" listing query

`Category.full_slug` is `unique=True`, so it gets an index for free. Product slug and user email are similarly indexed via their unique constraints.

## API surface

The product list endpoint accepts:

| Param          | Behaviour                                                                |
|----------------|--------------------------------------------------------------------------|
| `search=q`     | Postgres `SearchVector("name","description")` + `SearchRank` ordering. Falls back to `icontains` on SQLite. |
| `category__slug` | Exact category (no descendants).                                       |
| `category_path=a/b` | Matches `full_slug=path` OR `full_slug LIKE path||'/%'` — category + descendants. |
| `price__gte`/`price__lte` | Range filters.                                                  |
| `in_stock=true` | Excludes zero-stock products.                                           |
| `ordering=-?price`/`-?created_at` | Sort.                                                  |
| `page=n`        | Page-number pagination (default `PAGE_SIZE=12`).                        |

Two read-only utility endpoints surface aggregate data:

- `GET /api/products/featured/` — top 12 `is_featured=True`, cached 5 min.
- `GET /api/products/bestsellers/` — aggregates `Sum("orderitem__quantity")` over `orderitem__order__status="paid"`, cached 5 min.

Category-tree helpers:

- `GET /api/categories/tree/` — nested top-level → children recursive.
- `GET /api/categories/by-path/?path=electronics/audio` — single category with `ancestors[]` + `children[]`.

`ProductCursorPagination` is defined in `products/pagination.py` for opt-in use on viewsets where deep page-number paging would scan too many rows.

## Frontend layout

```
frontend/
├── app/                       # Next.js App Router
│   ├── layout.tsx             # AuthProvider, CartProvider, ToastProvider
│   ├── page.tsx               # home: featured rail + chip categories + product grid
│   ├── products/[id]/         # product detail (gallery + qty stepper)
│   ├── c/[...slug]/           # hierarchical category landing pages (catch-all)
│   ├── cart/, checkout/       # cart + mock checkout
│   ├── orders/                # per-user order history
│   ├── account/               # profile editor + verification badge
│   ├── login/, signup/        # auth forms (login accepts username OR email)
│   ├── forgot-password/, reset-password/, verify-email/
│   └── globals.css
├── components/
│   ├── Header.tsx, MegaMenu.tsx        # nav
│   ├── ProductCard.tsx, RailCard.tsx   # product surfaces
│   ├── Breadcrumbs.tsx, CategoryFilters.tsx, SortDropdown.tsx, ActiveFilters.tsx
│   ├── Pagination.tsx, Skeletons.tsx
│   ├── RatingStars.tsx, ToastContainer.tsx
└── lib/
    ├── api.ts                 # typed fetch wrapper with auto-refresh on 401
    ├── auth.ts                # access + refresh tokens in localStorage
    ├── useAuth.tsx            # AuthProvider, fetches /me on mount
    ├── useToast.tsx           # ToastProvider
    └── cart.tsx               # CartContext (persisted to localStorage)
```

URL-driven UI: filters, sort, pagination, search, and the active category all live in search params so pages remain shareable, server-rendered, and free of client-side state drift.

## Auth flow

```
register → email sent → /verify-email?uid&token → email_verified=true
                                                          │
login (username OR email) ─► /api/auth/token/ ─► access + refresh stored
                                                          │
                              ┌───────────── 401 on any API call ─────────────┐
                              ▼                                                │
                  POST /api/auth/token/refresh/   ──── success ──► retry once  │
                              │                                                │
                              └── failure ──► auth.clear() + redirect to /login?next=…
                                                          │
logout ─► POST /api/auth/logout/ (blacklists refresh) ─► clear local state
```

Highlights:
- **Login accepts username OR email** — `EmailOrUsernameTokenObtainPairSerializer` detects `@` in the identifier and resolves to a username before delegating to SimpleJWT.
- **Refresh rotation + blacklist** — `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`. Logout blacklists the current refresh via `TokenBlacklistView`.
- **Auto-refresh on 401** — implemented in the `request<T>` wrapper. Existing callers don't need to know.
- **Verification + password reset** use Django's `default_token_generator` + `urlsafe_base64_*` for stateless, signed tokens that don't need a DB row.

## Caching

`CACHES` is configured in `core/settings.py` and driven by `CACHE_BACKEND` / `CACHE_LOCATION` env vars (LocMem default; flip to `django.core.cache.backends.redis.RedisCache` + a Memorystore URL in production).

Today caching is only used on featured/bestsellers (5-minute TTL). Invalidation is TTL-only; a `post_save` signal that calls `cache.delete("products:featured:v1")` is the obvious next step when writes need to land instantly.

## Search

- **Postgres**: when `connection.vendor == "postgresql"` and `?search=` is present, `ProductViewSet.get_queryset()` annotates with `SearchRank(SearchVector("name","description"), SearchQuery(q))`, filters on `rank > 0`, orders by rank descending. Adding a `GinIndex` on `to_tsvector('simple', name || ' ' || description)` is the natural follow-up to make this scale past tens of thousands of rows.
- **SQLite (dev)**: DRF's `SearchFilter` handles `icontains` over the same fields. Fine for development; not for production-scale catalogs.

## Trade-offs

- **localStorage JWT** — easy demo, but XSS-vulnerable. Production should move to httpOnly cookies + same-site protection.
- **Mock payment** — `POST /orders/{id}/pay/` just flips the order status. Stripe Checkout is a small drop-in (intent + webhook → status transition).
- **Stock model is single-integer** — fine for a simple catalog. Real systems need reserved-vs-available, idempotent order creation keyed by client token, and a dedicated inventory service.
- **Denormalised ratings** — `rating_avg`/`rating_count` live on `Product` and are seeded with deterministic fake values. Adding a real `Review` model would require recomputing on write (signal or async job).
- **No CDN for product images** — Next.js' image proxy gives optimisation but the origin is still external. For production, push originals to GCS + Cloud CDN and point `next/image` at that.
- **Single-region** — Cloud Run + Cloud SQL + cache in one region. Multi-region requires read-replicas, careful cache key namespacing, and possibly an edge layer for the catalog reads.
- **Cache invalidation by TTL only** — featured/bestsellers can lag writes by up to 5 min. A signal-based invalidator is a single small file when needed.
