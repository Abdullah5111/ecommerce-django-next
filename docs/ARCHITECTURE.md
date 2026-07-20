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
│   ├── models.py          # Category (self-FK), Product, ProductImage, Review, ReviewImage, ReviewVote
│   ├── signals.py         # Review post_save/post_delete → rating recompute
│   ├── views.py           # ViewSets + tree/by-path/featured/bestsellers/reviews/related/helpful
│   ├── pagination.py      # ProductCursorPagination (opt-in)
│   └── migrations/
├── orders/                # Order, OrderItem + create/list/pay (with shipping snapshot)
├── payments/              # Stripe gateway (mock fallback) + PaymentIntent action + webhook
├── notifications/         # in-app feed + email + Web Push fan-out on order events
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
                                    ├─< ReviewImage
                                    └─< ReviewVote >─ User
```

- **`User`** — custom model on `accounts.User` (extends `AbstractUser`), with `email` (unique), `email_verified`, and profile fields: `avatar` (ImageField → MEDIA; local disk by default, GCS when `GS_BUCKET_NAME` is set), `display_name`, `bio`, `date_of_birth`, `gender`, plus `phone` + `phone_verified`. Defined upfront so swapping later doesn't require a painful migration. `phone`/`phone_verified` are read-only via `me` and only set through the phone-verification flow; legacy `address` text kept for backward compat (new code uses the address book).
- **`Address`** — `user` FK, `recipient`, `phone`, `line1/2`, `city`, `state`, `postal_code`, `country` (ISO-2), `label`, `is_default_shipping`, `is_default_billing`. `save()` enforces a single default-shipping (and default-billing) per user by demoting siblings atomically.
- **`Category`** — self-referential. `parent`, computed `full_slug` (e.g. `electronics/audio`), `level`. `save()` keeps the latter two coherent on writes. Indexed on the unique `full_slug` for fast path lookups.
- **`Product`** — `category` FK, pricing (`price`, `compare_at_price`, computed `is_on_sale`/`discount_percent`), `stock`, `rating_avg`/`rating_count` (denormalised — driven by Review signals), `specifications` (JSONField, flat key→value), `is_featured`, `is_active`. Has many `ProductImage`s and `Review`s; keeps a legacy `image_url` for backward compat.
- **`ProductImage`** — `url`, `alt`, `sort_order`. Ordered.
- **`Review`** — `product` FK, `user` FK (nullable for seeded/anonymous reviews; `author_name` snapshot for survivability), `rating` (1-5, CHECK constraint), `title`, `body`, `created_at`, plus `verified_purchase` and `helpful_count`. Partial unique on `(product, user)` when `user IS NOT NULL`. Indexed on `(product, -created_at)` and `(product, -helpful_count)`.
  - `verified_purchase` is **snapshotted at write time** from whether the reviewer has an order for the product in `SOLD_STATUSES` — the same definition that powers the "X sold" badge. Frozen deliberately: a later cancellation must not retract the badge.
  - `helpful_count` is denormalised from `ReviewVote` and recomputed by `post_save`/`post_delete` receivers on the vote — the same source-of-truth pattern `Review` uses to drive the product's rating fields. Counting the rows rather than incrementing a counter is what keeps it correct when votes disappear without passing through the endpoint (deleting a user cascades their votes; an incremented counter would stay inflated forever).
- **`ReviewImage`** — `review` FK, `image` (ImageField → MEDIA, same storage as avatars), `sort_order`. Ordered. Capped at 5 per review by the view. Uploads are validated by `ReviewImageUploadSerializer` before anything is written: Pillow must accept the bytes, the extension must be in `ALLOWED_REVIEW_IMAGE_EXTENSIONS` (SVG deliberately excluded — it is an image to a browser but can carry `<script>`, and MEDIA is same-origin), and each file must be under 5 MB. A model `ImageField` only validates under `full_clean()`, which the API path never calls, so this cannot be left to the model. A `post_delete` receiver drops the stored file when its row goes — deleting a review cascades the rows, and the files would otherwise outlive them (clutter on local disk, unbounded paid storage in GCS).
- **`ReviewVote`** — `review` FK, `user` FK, `created_at`. Unique on `(review, user)`, which is what makes the helpful toggle idempotent.
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

- `GET /api/products/{slug}/reviews/` — paginated review list. `?ordering=helpful` sorts by `-helpful_count` (default is `-created_at`). For signed-in callers the viewer's own vote is resolved with an `Exists()` annotation, so `helpful_by_me` costs no extra query per row; `is_mine` lets the UI hide the helpful control on your own review.
- `POST /api/products/{slug}/reviews/` — auth required. One review per user per product; 400 on duplicate. Accepts JSON, or **multipart** with up to 5 `images` files (`ReviewImage` rows written in the same transaction as the review). `verified_purchase` is computed server-side here.
- `POST|DELETE /api/reviews/{id}/helpful/` — auth required. Toggles the caller's helpful vote and returns `{helpful_count, helpful_by_me}`. Voting on your own review is rejected with 400.

Category-tree helpers:

- `GET /api/categories/tree/` — nested top-level → children recursive.
- `GET /api/categories/by-path/?path=electronics/audio` — single category with `ancestors[]` + `children[]`.

Profile & account (auth):

- `GET/PUT/PATCH /api/auth/me/` — current user; PATCH writes editable profile fields (name, display name, bio, DOB, gender).
- `POST/DELETE /api/auth/me/avatar/` — multipart upload (validated: image, ≤2 MB) / remove; replaces the previous file.
- `POST /api/auth/phone/send-code/` → issues a 6-digit code (cache-backed, 10-min TTL, 30s resend cooldown), "sent" via console in dev.
- `POST /api/auth/phone/verify/` → constant-time check, attempt-capped (5), rejects a number already verified by another user, then sets `phone` + `phone_verified`.

Address book (auth):

- `GET/POST /api/auth/addresses/` and standard `GET/PUT/PATCH/DELETE /{id}/`.
- `POST /api/auth/addresses/{id}/set-default/` — atomically demotes other defaults.

`ProductCursorPagination` is defined in `products/pagination.py` for opt-in use on viewsets where deep page-number paging would scan too many rows.

## Frontend layout

```
frontend/
├── app/                                  # Next.js App Router
│   ├── layout.tsx                        # Inter font + providers + TopBar, Footer, MobileTabBar
│   ├── page.tsx                          # home: hero + category tiles + deals rail + product grid
│   ├── loading.tsx                       # route-level skeleton on navigation
│   ├── products/[id]/                    # product detail — SSR + JSON-LD + tabs
│   ├── c/[...slug]/                      # hierarchical category landing pages (catch-all)
│   ├── cart/, checkout/                  # cart (+ save-for-later) + checkout (Stripe Elements / mock)
│   ├── orders/                           # per-user order history (structured shipping)
│   ├── account/                          # account hub (card grid) + shared layout
│   ├── account/profile/                  # profile editor: avatar, name, bio, DOB, gender, phone verify
│   ├── account/security/                 # email/phone status + change-password entry
│   ├── account/notifications/            # in-app notification feed + browser-push toggle
│   ├── account/payment/                  # roadmap stub
│   ├── account/addresses/                # address book CRUD
│   ├── wishlist/                         # saved-products grid
│   ├── login/, signup/                   # auth forms (username/email + Google sign-in)
│   ├── forgot-password/, reset-password/, verify-email/
│   └── globals.css
├── components/
│   ├── ui/                               # design-system primitives: Button, Badge, Price
│   ├── TopBar.tsx, Footer.tsx           # global chrome (trust bar + footer)
│   ├── MobileTabBar.tsx                  # mobile bottom tab nav (Home/Wishlist/Cart/Account)
│   ├── home/                             # Hero, CategoryTiles, DealsRail (homepage-only)
│   ├── CountdownTimer.tsx                # client countdown to midnight (deals rail)
│   ├── FreeShippingBar.tsx              # cart progress toward free shipping
│   ├── EmptyState.tsx                    # reusable empty state (icon + copy + CTA)
│   ├── Header.tsx, MegaMenu.tsx          # nav; primary links desktop-only (mobile uses bottom nav)
│   ├── NotificationBell.tsx              # unread badge + dropdown (polls unread count)
│   ├── ProductCard.tsx, RailCard.tsx     # price-forward card, wishlist heart, urgency, "X sold"
│   ├── RecommendedRail.tsx               # personalized rail (logged-in)
│   ├── StripePaymentForm.tsx             # Stripe Elements card form (live mode)
│   ├── GoogleSignInButton.tsx            # Google Identity Services button (feature-detected)
│   ├── PushToggle.tsx                    # browser-push opt-in (hidden without VAPID)
│   ├── Breadcrumbs.tsx, CategoryFilters.tsx, SortDropdown.tsx, ActiveFilters.tsx
│   ├── Pagination.tsx, Skeletons.tsx
│   ├── AddressForm.tsx
│   ├── RatingStars.tsx, ToastContainer.tsx
│   └── product-detail/
│       ├── Gallery.tsx                   # thumbs + main image + lightbox
│       ├── PurchasePanel.tsx             # buy box: dual CTA (Add/Buy now), delivery est., trust badges
│       ├── Tabs.tsx                      # hash-driven Description / Specifications / Reviews
│       ├── SpecsTable.tsx
│       ├── ReviewsSection.tsx, ReviewCta.tsx, WriteReviewForm.tsx
│       ├── HelpfulButton.tsx             # optimistic helpful vote, rolls back on failure
│       ├── ReviewPhotos.tsx              # reviewer photo strip + fullscreen lightbox
│       ├── RelatedRail.tsx, RecentlyViewedRail.tsx
│       └── StickyCta.tsx                 # md:hidden bottom CTA bar
└── lib/
    ├── api.ts                            # typed fetch wrapper with auto-refresh on 401
    ├── auth.ts                           # access + refresh tokens in localStorage
    ├── useAuth.tsx                       # AuthProvider, fetches /me on mount
    ├── useToast.tsx                      # ToastProvider
    ├── useWishlist.tsx                   # WishlistProvider (server-backed when authed; localStorage for guests)
    ├── push.ts                           # Web Push: service-worker register + subscribe helpers
    ├── format.ts                         # small formatters (e.g. "1.2k sold")
    ├── cn.ts                             # tiny classnames helper
    ├── constants.ts                      # FREE_SHIPPING_THRESHOLD (mirrors backend)
    ├── recentlyViewed.ts                 # localStorage queue helper
    └── cart.tsx                          # CartContext (server-backed when authed; localStorage for guests)
```

### Design system

Tokens live in `tailwind.config.ts` — **brand** (indigo) for CTAs/links/trust and
**deal** (amber) for prices/%-off/urgency, plus semantic colors, `card`/`card-hover`
shadows, and a `shimmer` keyframe. `globals.css` sets the Inter font, a consistent
`:focus-visible` ring, and a `.skeleton` shimmer utility (reduced-motion respected).
Three primitives in `components/ui/` keep surfaces consistent: `Button`
(primary/secondary/ghost/deal + a `buttonClasses` helper for links), `Badge`
(soft/solid tones), and `Price` — the single price treatment (current + struck-through
compare-at + %-off flag).

A service worker at `public/sw.js` handles `push` / `notificationclick` for Web Push.

URL-driven UI: filters, sort, pagination, search, and the active category all live in search params so pages remain shareable, server-rendered, and free of client-side state drift.

### Product detail rendering model

- The page is a **server component** that fetches `getProduct`, `getCategoryByPath` (for breadcrumbs ancestors), `listReviews`, and `getRelated` in parallel via `Promise.allSettled`.
- `generateMetadata` returns `<title>`, description, and an Open Graph image from the first product image.
- `schema.org Product` JSON-LD is embedded inline. `aggregateRating` is included only when `rating_count > 0`.
- Interactive pieces are extracted into client islands under `components/product-detail/` (Gallery, PurchasePanel, Tabs, WriteReviewForm, etc.). Recently viewed stays in `localStorage`; the wishlist toggle is server-backed when signed in and falls back to `localStorage` for guests (merged on login).

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
- **Google sign-in** — the frontend gets a Google ID token via Google Identity Services and POSTs it to `/api/auth/google/`; `accounts/google.py` verifies the token's signature, audience, and issuer with `google-auth`, then we get-or-link a user **by verified email** and mint our own SimpleJWT pair (so the rest of the app is auth-method-agnostic). New Google users get an unusable password. Enabled only when `GOOGLE_OAUTH_CLIENT_ID` is set — the frontend feature-detects via `/api/auth/google/config/` and hides the button otherwise.

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
              POST /api/orders/{id}/create-payment-intent/
                          │
            ┌─────────────┴─────────────┐
        mock mode                    live mode
            │                            │
   POST /orders/{id}/pay/      Stripe Elements confirms card
   (immediate confirm)                  │
            │              ┌────────────┴────────────┐
            │       webhook → mark_paid    POST /pay/ (verifies intent)
            └─────────────┬─────────────┘
                          │
                 toast + clear cart + redirect home
```

Whether a checkout is live or mock is decided server-side by the presence of
`STRIPE_SECRET_KEY` — the `create-payment-intent` response carries a `mock` flag
and the publishable key, so the frontend needs no Stripe config of its own. The
webhook is the authoritative paid-signal in live mode; the synchronous `pay`
call (which verifies the PaymentIntent actually succeeded) is a UX backstop and
is idempotent with it.

The legacy free-text `shipping_address` path on `POST /api/orders/` still works for backward compatibility, but the UI never sends it now.

## Caching

`CACHES` is configured in `core/settings.py` and driven by `CACHE_BACKEND` / `CACHE_LOCATION` env vars (LocMem default; flip to `django.core.cache.backends.redis.RedisCache` + a Memorystore URL in production).

Caching is used on `featured`, `bestsellers`, and per-product `related` (5-minute TTL). Invalidation is TTL-only; a `post_save` signal that calls `cache.delete(...)` per affected product is the obvious next step when writes need to land instantly.

## Search

- **Postgres**: when `connection.vendor == "postgresql"` and `?search=` is present, `ProductViewSet.get_queryset()` annotates with `SearchRank(SearchVector("name","description"), SearchQuery(q))`, filters on `rank > 0`, orders by rank descending. Adding a `GinIndex` on `to_tsvector('simple', name || ' ' || description)` is the natural follow-up to make this scale past tens of thousands of rows.
- **SQLite (dev)**: DRF's `SearchFilter` handles `icontains` over the same fields. Fine for development; not for production-scale catalogs.

## Trade-offs

- **localStorage JWT** — easy demo, but XSS-vulnerable. Production should move to httpOnly cookies + same-site protection.
- **Payments** — Stripe (test mode): a `payments` app wraps the SDK behind a gateway that **degrades to mock mode when `STRIPE_SECRET_KEY` is unset**, so the demo runs key-free. Live mode uses PaymentIntent + Elements, a signature-verified webhook for the authoritative paid signal, and real `stripe.Refund.create` on cancel/return. The SDK is imported lazily so mock paths never need it. A production hardening step is webhook event de-duplication (store processed event IDs) — today idempotency rests on the `PENDING`-only `mark_paid` guard.
- **Notifications** — order transitions call `notifications.service.notify_order()` from `transaction.on_commit`, so an alert is only sent after the status change durably commits (never on rollback). One `notify()` fans out to three channels: an in-app `Notification` row, an email, and Web Push. Email and push are best-effort — a failure never breaks the transition. Web Push uses VAPID and **degrades to a no-op when keys are unset** (`pywebpush` imported lazily); the in-app feed + emails still work. Synchronous (in-request) fan-out is fine at this scale; a queue (Celery / Pub/Sub) is the natural step when push fan-out grows or third-party latency matters.
- **Stock model is single-integer** — fine for a simple catalog. Real systems need reserved-vs-available, idempotent order creation keyed by client token, and a dedicated inventory service.
- **Denormalised ratings, kept honest by signals** — works at our scale and is testable; at very high write volumes you'd switch to an async pipeline (Celery / Pub/Sub) so the API doesn't pay the recompute cost.
- **No variants** — `Product` is the saleable unit. Adding size/color requires a `ProductVariant` model and pushes through cart, stock, images, and order serializers.
- **No CDN for product images** — Next.js' image proxy gives optimisation but the origin is still external. For production, push originals to GCS + Cloud CDN and point `next/image` at that.
- **Single-region** — Cloud Run + Cloud SQL + cache in one region. Multi-region requires read-replicas, careful cache key namespacing, and possibly an edge layer for the catalog reads.
- **Cache invalidation by TTL only** — featured/bestsellers/related can lag writes by up to 5 min. A signal-based invalidator is a single small file when needed.
- **Wishlist + recently viewed live in localStorage** — instantly responsive, no auth required, but doesn't sync across devices. Promoting to server-side is a small model + endpoint pair when needed.
