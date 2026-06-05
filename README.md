# E-commerce — Django + Next.js

A full-stack e-commerce app built as a portfolio piece. Django REST Framework backend, Next.js 14 (App Router) frontend, PostgreSQL, JWT auth with email verification and password reset, hierarchical categories with faceted search, image gallery, paginated catalog, and a scale-aware data layer (DB indexes, Postgres full-text search, atomic stock decrement, cached featured/bestsellers). Containerised and ready to deploy to Google Cloud Run.

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
- Mega-menu in the header, breadcrumbs on category pages
- Faceted filtering: price range, in-stock, category-and-descendants
- Sort: featured, newest, price ↑ / ↓
- Search (Postgres full-text when available, icontains otherwise) scoped to category when on a category page
- Paginated grid with shareable URLs (`?page=2&priceMin=20&inStock=true&ordering=-price`)
- Product detail with image gallery, rating stars, sale pricing (struck-through compare price + discount badge), quantity stepper

### Cart & checkout
- Client-side cart persisted to `localStorage`
- Inline "Add to cart" with toast (no navigation)
- Mock checkout that creates the order and atomically decrements stock (concurrent-safe `F()` UPDATE)
- Per-user order history

### Auth
- Register, login (by username **or** email), logout (server-side refresh-token blacklist)
- JWT with auto-refresh on 401 and global redirect when both tokens expire
- Email verification (`/verify-email?uid&token`) with verified badge on the account page
- Forgot / reset password (`/forgot-password`, `/reset-password?uid&token`) via Django's password-reset token generator
- Account page: profile editing (PUT `/api/auth/me/`) + verification status + change-password link
- Password-strength hints on the signup form
- Console email backend for dev; SMTP via env for production

### Scale & performance
- DB indexes on `price`, `is_active`, `is_featured`, `stock`, plus compound `(category, is_active, -created_at)`
- Postgres-conditional full-text search with `SearchVector` + `SearchRank`; SQLite gets the existing `icontains` fallback
- Atomic stock decrement (`Product.objects.filter(stock__gte=q).update(stock=F("stock") - q)`) — no oversell race
- Featured + bestsellers endpoints cached for 5 minutes (`CACHES` configurable per-env)
- Cursor-pagination class defined for opt-in use on large catalogs
- All product images served via `next/image` (lazy loading, responsive `sizes`, AVIF/WebP)

### Admin
- Django admin for products, categories (drag-into-place hierarchy), orders, users
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

| Method | Path                              | Auth | Purpose                                           |
|--------|-----------------------------------|------|---------------------------------------------------|
| POST   | /api/auth/register/               | —    | Create account; emails a verification link        |
| POST   | /api/auth/token/                  | —    | Login (JWT); `username` accepts username OR email |
| POST   | /api/auth/token/refresh/          | —    | Rotate access token (refresh tokens rotate too)   |
| POST   | /api/auth/logout/                 | —    | Blacklist refresh token                           |
| GET/PUT| /api/auth/me/                     | JWT  | Current user; PUT updates profile fields          |
| POST   | /api/auth/verify-email/           | —    | `{uid, token}` → mark email verified              |
| POST   | /api/auth/forgot-password/        | —    | `{email}` → always 200 (no email-existence leak)  |
| POST   | /api/auth/reset-password/         | —    | `{uid, token, new_password}`                      |

### Catalog

| Method | Path                                       | Auth | Purpose                                        |
|--------|--------------------------------------------|------|------------------------------------------------|
| GET    | /api/products/                             | —    | List products (paginated)                      |
| GET    | /api/products/{slug}/                      | —    | Product detail                                 |
| GET    | /api/products/featured/                    | —    | Top featured (cached 5 min)                    |
| GET    | /api/products/bestsellers/                 | —    | Top by paid-order quantity (cached 5 min)      |
| GET    | /api/categories/                           | —    | Flat list                                      |
| GET    | /api/categories/{slug}/                    | —    | By direct slug                                 |
| GET    | /api/categories/tree/                      | —    | Full nested tree (roots → children)            |
| GET    | /api/categories/by-path/?path=a/b/c        | —    | Category by `full_slug`, with ancestors + children |

Product list query params:
`search`, `category__slug`, `category_path` (matches category and all descendants),
`price__gte`, `price__lte`, `in_stock=true`, `ordering` (`-?price`, `-?created_at`), `page`.

### Orders

| Method | Path                              | Auth | Purpose                                  |
|--------|-----------------------------------|------|------------------------------------------|
| GET    | /api/orders/                      | JWT  | List my orders                           |
| POST   | /api/orders/                      | JWT  | Create order (atomic stock decrement)    |
| GET    | /api/orders/{id}/                 | JWT  | Order detail                             |
| POST   | /api/orders/{id}/pay/             | JWT  | Mock payment                             |

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Deployment to Google Cloud](./docs/DEPLOYMENT.md)

## License

MIT
