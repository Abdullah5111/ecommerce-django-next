# E-commerce — Django + Next.js

A full-stack e-commerce demo. Django REST Framework backend, Next.js 14 (App Router) frontend, PostgreSQL, JWT auth, mock checkout. Containerised and ready to deploy to Google Cloud Run.

## Stack

| Layer       | Tech                                                |
|-------------|-----------------------------------------------------|
| Frontend    | Next.js 14, React 18, TypeScript, Tailwind CSS      |
| Backend     | Django 5, Django REST Framework, SimpleJWT          |
| Database    | PostgreSQL 16                                       |
| Container   | Docker, docker-compose                              |
| Deploy      | Google Cloud Run + Cloud SQL + Artifact Registry    |

## Features

- Product catalog with categories, search, pagination
- Product detail pages
- Cart (client-side, persisted to localStorage)
- JWT auth: register, login, logout, /me
- Checkout with mock payment (creates order, decrements stock)
- Order history (per-user)
- Django admin for products, categories, orders

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
cp .env.example .env  # set DB_ENGINE=sqlite for the easiest path
python manage.py migrate
python manage.py shell < seed.py
python manage.py runserver

# Frontend (in a new shell)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## API endpoints

| Method | Path                              | Auth | Purpose                  |
|--------|-----------------------------------|------|--------------------------|
| GET    | /api/products/                    | -    | List products            |
| GET    | /api/products/{slug}/             | -    | Product detail           |
| GET    | /api/categories/                  | -    | List categories          |
| POST   | /api/auth/register/               | -    | Create account           |
| POST   | /api/auth/token/                  | -    | Login (JWT)              |
| POST   | /api/auth/token/refresh/          | -    | Refresh token            |
| GET    | /api/auth/me/                     | JWT  | Current user             |
| POST   | /api/orders/                      | JWT  | Create order             |
| GET    | /api/orders/                      | JWT  | List my orders           |
| POST   | /api/orders/{id}/pay/             | JWT  | Mock payment             |

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Deployment to Google Cloud](./docs/DEPLOYMENT.md)

## License

MIT
