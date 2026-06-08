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
├── accounts/              # custom User + Address + auth views
├── products/
│   ├── models.py          # Category (self-FK), Product, ProductImage, Review
│   ├── signals.py         # Review post_save/post_delete → rating recompute
│   ├── views.py           # ViewSets + tree/by-path/featured/bestsellers/reviews/related
│   ├── pagination.py      # ProductCursorPagination (opt-in)
│   └── migrations/
├── orders/                # Order, OrderItem + create/list/pay (with shipping snapshot)
├── seed.py                # idempotent hierarchical seeder + reviews + specs
├── Dockerfile             # python:3.12-slim + gunicorn
└── cloudbuild.yaml        # Cloud Build pipeline to Cloud Run
```

### Data model

```
User ─< Address                                Category (self-FK: parent/children)
  └─< Order ─< OrderItem >─ Product ────────────┘
                              │
                              ├─< ProductImage
                              └─< Review
```

- **`User`** — custom model on `accounts.User` (extends `AbstractUser`), with `email` (unique), `email_verified`. Defined upfront so swapping later doesn't require a painful migration. Legacy `address`/`phone` fields kept for backward compat; new code uses the address book.
- **`Address`** — `user` FK, `recipient`, `phone`, `line1/2`, `city`, `state`, `postal_code`, `country` (ISO-2), `label`, `is_default_shipping`, `is_default_billing`. `save()` enforces a single default-shipping (and default-billing) per user by demoting siblings atomically.
- **`Category`** — self-referential. `parent`, computed `full_slug` (e.g. `electronics/audio`), `level`. `save()` keeps the latter two coherent on writes. Indexed on the unique `full_slug` for fast path lookups.
- **`Product`** — `category` FK, pricing (`price`, `compare_at_price`, computed `is_on_sale`/`discount_percent`), `stock`, `rating_avg`/`rating_count` (denormalised — driven by Review signals), `specifications` (JSONField, flat key→value), `is_featured`, `is_active`. Has many `ProductImage`s and `Review`s; keeps a legacy `image_url` for backward compat.
- **`ProductImage`** — `url`, `alt`, `sort_order`. Ordered.
- **`Review`** — `product` FK, `user` FK (nullable for seeded/anonymous reviews; `author_name` snapshot for survivability), `rating` (1-5, CHECK constraint), `title`, `body`, `created_at`. Partial unique on `(product, user)` when `user IS NOT NULL`. Indexed on `(product, -created_at)`.
- **`Order`** — `user` FK, `status` (`pending`/`paid`/`shipped`/`delivered`/`cancelled`), `shipping_address` (composed text for backward compat), plus structured `ship_*` snapshot fields (`recipient`, `phone`, `line1/2`, `city`, `state`, `postal_code`, `country`) populated from the chosen Address at create time. **Immutable thereafter** — editing the Address row later does not mutate past orders.
- **`Order.total`** — denormalised, recalculated on item changes (`recalculate_total`).
- **Stock decrement** — done with an atomic conditional UPDATE (`Product.objects.filter(stock__gte=qty).update(stock=F("stock") - qty)`) inside `OrderSerializer.create`'s `@transaction.atomic`, eliminating the read-then-write oversell race.

### Indexes

Defined on `Product.Meta.indexes`:
- single-column on `price`, `is_active`, `is_featured`, `stock`
- compound `(category, is_active, -created_at)` — matches the dominant "newest in category" listing query

`Category.full_slug` is `unique=True`, so it gets an index for free. Review has `(product, -created_at)`. Product slug and user email are similarly indexed via their unique constraints.

### Rating aggregation

`Product.rating_avg` / `rating_count` are denormalised but kept honest by signals in `products/signals.py`:
- `post_save` and `post_delete` on `Review` call `_recompute(product)`, which runs `reviews.aggregate(avg=Avg("rating"), n=Count("id"))` and writes back with `update_fields=["rating_avg","rating_count"]`.
- Bulk operations bypass signals; the seeder compensates with an explicit recompute pass after `bulk_create`.

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

Aggregate / cached endpoints:

- `GET /api/products/featured/` — top 12 `is_featured=True`, cached 5 min.
- `GET /api/products/bestsellers/` — aggregates `Sum("orderitem__quantity")` over `orderitem__order__status="paid"`, cached 5 min.
- `GET /api/products/{slug}/related/` — top 8 siblings in the same category, ordered by `-rating_avg, -created_at`, cached 5 min.

Product-detail companions:

- `GET /api/products/{slug}/reviews/` — paginated review list.
- `POST /api/products/{slug}/reviews/` — auth required. One review per user per product; 400 on duplicate.

Category-tree helpers:

- `GET /api/categories/tree/` — nested top-level → children recursive.
- `GET /api/categories/by-path/?path=electronics/audio` — single category with `ancestors[]` + `children[]`.

Address book (auth):

- `GET/POST /api/auth/addresses/` and standard `GET/PUT/PATCH/DELETE /{id}/`.
- `POST /api/auth/addresses/{id}/set-default/` — atomically demotes other defaults.

`ProductCursorPagination` is defined in `products/pagination.py` for opt-in use on viewsets where deep page-number paging would scan too many rows.

## Frontend layout

```
frontend/
├── app/                                  # Next.js App Router
│   ├── layout.tsx                        # AuthProvider, CartProvider, WishlistProvider, ToastProvider
│   ├── page.tsx                          # home: featured rail + chip categories + product grid
│   ├── products/[id]/                    # product detail — SSR + JSON-LD + tabs
│   ├── c/[...slug]/                      # hierarchical category landing pages (catch-all)
│   ├── cart/, checkout/                  # cart + checkout (saved-address picker)
│   ├── orders/                           # per-user order history (structured shipping)
│   ├── account/                          # profile editor + verification badge
│   ├── account/addresses/                # address book CRUD
│   ├── wishlist/                         # saved-products grid
│   ├── login/, signup/                   # auth forms (login accepts username OR email)
│   ├── forgot-password/, reset-password/, verify-email/
│   └── globals.css
├── components/
│   ├── Header.tsx, MegaMenu.tsx          # nav (with cart + wishlist counts)
│   ├── ProductCard.tsx, RailCard.tsx     # product surfaces
│   ├── Breadcrumbs.tsx, CategoryFilters.tsx, SortDropdown.tsx, ActiveFilters.tsx
│   ├── Pagination.tsx, Skeletons.tsx
│   ├── AddressForm.tsx
│   ├── RatingStars.tsx, ToastContainer.tsx
│   └── product-detail/
│       ├── Gallery.tsx                   # thumbs + main image + lightbox
│       ├── PurchasePanel.tsx             # qty stepper + add-to-cart + wishlist + stock urgency
│       ├── Tabs.tsx                      # hash-driven Description / Specifications / Reviews
│       ├── SpecsTable.tsx
│       ├── ReviewsSection.tsx, ReviewCta.tsx, WriteReviewForm.tsx
│       ├── RelatedRail.tsx, RecentlyViewedRail.tsx
│       └── StickyCta.tsx                 # md:hidden bottom CTA bar
└── lib/
    ├── api.ts                            # typed fetch wrapper with auto-refresh on 401
    ├── auth.ts                           # access + refresh tokens in localStorage
    ├── useAuth.tsx                       # AuthProvider, fetches /me on mount
    ├── useToast.tsx                      # ToastProvider
    ├── useWishlist.tsx                   # WishlistProvider (localStorage)
    ├── recentlyViewed.ts                 # localStorage queue helper
    └── cart.tsx                          # CartContext (persisted to localStorage)
```

URL-driven UI: filters, sort, pagination, search, and the active category all live in search params so pages remain shareable, server-rendered, and free of client-side state drift.

### Product detail rendering model

- The page is a **server component** that fetches `getProduct`, `getCategoryByPath` (for breadcrumbs ancestors), `listReviews`, and `getRelated` in parallel via `Promise.allSettled`.
- `generateMetadata` returns `<title>`, description, and an Open Graph image from the first product image.
- `schema.org Product` JSON-LD is embedded inline. `aggregateRating` is included only when `rating_count > 0`.
- Interactive pieces are extracted into client islands under `components/product-detail/` (Gallery, PurchasePanel, Tabs, WriteReviewForm, etc.). Recently viewed and wishlist toggles use `localStorage` and never touch the server.

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

## Checkout flow

```
cart ─► /checkout ─► fetch saved addresses
                          │
                          ├─ default-shipping pre-selected (radio cards)
                          └─ "Use a different address" → inline AddressForm
                          │
              POST /api/orders/ { shipping_address_id, items }
                          │
              Order serializer snapshots ship_* fields from the Address
                          │
              POST /api/orders/{id}/pay/   (mock)
                          │
                 toast + clear cart + redirect home
```

The legacy free-text `shipping_address` path on `POST /api/orders/` still works for backward compatibility, but the UI never sends it now.

## Caching

`CACHES` is configured in `core/settings.py` and driven by `CACHE_BACKEND` / `CACHE_LOCATION` env vars (LocMem default; flip to `django.core.cache.backends.redis.RedisCache` + a Memorystore URL in production).

Caching is used on `featured`, `bestsellers`, and per-product `related` (5-minute TTL). Invalidation is TTL-only; a `post_save` signal that calls `cache.delete(...)` per affected product is the obvious next step when writes need to land instantly.

## Search

- **Postgres**: when `connection.vendor == "postgresql"` and `?search=` is present, `ProductViewSet.get_queryset()` annotates with `SearchRank(SearchVector("name","description"), SearchQuery(q))`, filters on `rank > 0`, orders by rank descending. Adding a `GinIndex` on `to_tsvector('simple', name || ' ' || description)` is the natural follow-up to make this scale past tens of thousands of rows.
- **SQLite (dev)**: DRF's `SearchFilter` handles `icontains` over the same fields. Fine for development; not for production-scale catalogs.

## Trade-offs

- **localStorage JWT** — easy demo, but XSS-vulnerable. Production should move to httpOnly cookies + same-site protection.
- **Mock payment** — `POST /orders/{id}/pay/` just flips the order status. Stripe Checkout is a small drop-in (intent + webhook → status transition).
- **Stock model is single-integer** — fine for a simple catalog. Real systems need reserved-vs-available, idempotent order creation keyed by client token, and a dedicated inventory service.
- **Denormalised ratings, kept honest by signals** — works at our scale and is testable; at very high write volumes you'd switch to an async pipeline (Celery / Pub/Sub) so the API doesn't pay the recompute cost.
- **No variants** — `Product` is the saleable unit. Adding size/color requires a `ProductVariant` model and pushes through cart, stock, images, and order serializers.
- **No CDN for product images** — Next.js' image proxy gives optimisation but the origin is still external. For production, push originals to GCS + Cloud CDN and point `next/image` at that.
- **Single-region** — Cloud Run + Cloud SQL + cache in one region. Multi-region requires read-replicas, careful cache key namespacing, and possibly an edge layer for the catalog reads.
- **Cache invalidation by TTL only** — featured/bestsellers/related can lag writes by up to 5 min. A signal-based invalidator is a single small file when needed.
- **Wishlist + recently viewed live in localStorage** — instantly responsive, no auth required, but doesn't sync across devices. Promoting to server-side is a small model + endpoint pair when needed.
