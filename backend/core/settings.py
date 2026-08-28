from pathlib import Path
from datetime import timedelta
from decimal import Decimal

from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())

INSTALLED_APPS = [
    # daphne must be first so its runserver (ASGI) wins over staticfiles'.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "accounts",
    "products",
    "orders",
    "coupons",
    "returns",
    "cart",
    "wishlist",
    "payments",
    "notifications",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DB_ENGINE = config("DB_ENGINE", default="sqlite")
if DB_ENGINE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="db"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Uploaded media (avatars, review photos). Local disk by default; set
# GS_BUCKET_NAME to use Google Cloud Storage — required on Cloud Run, whose
# filesystem is ephemeral and per-instance.
GS_BUCKET_NAME = config("GS_BUCKET_NAME", default="")

# STORAGES and the legacy STATICFILES_STORAGE settings are mutually exclusive
# (Django raises ImproperlyConfigured), so whitenoise is configured here.
STORAGES = {
    "default": {
        "BACKEND": (
            "storages.backends.gcloud.GoogleCloudStorage"
            if GS_BUCKET_NAME
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if GS_BUCKET_NAME:
    GS_DEFAULT_ACL = "publicRead"     # media is public; URLs are unguessable
    GS_QUERYSTRING_AUTH = False       # stable URLs, no expiring signatures
    GS_FILE_OVERWRITE = False         # keep Django's uniquifying suffixes

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": config(
            "CACHE_BACKEND",
            default="django.core.cache.backends.locmem.LocMemCache",
        ),
        "LOCATION": config("CACHE_LOCATION", default="ecommerce-cache"),
    }
}

ASGI_APPLICATION = "core.asgi.application"

# Realtime fan-out: Redis when REDIS_URL is set (multi-process safe), else the
# per-process InMemory layer (dev, tests, and single-process deploys).
REDIS_URL = config("REDIS_URL", default="")
CHANNEL_LAYERS = {
    "default": (
        {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}
        if REDIS_URL
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    )
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Applied per-view via throttle_classes. State lives in the cache, so with
    # the default LocMemCache limits are per-instance (use Redis for cluster-wide).
    "DEFAULT_THROTTLE_RATES": {
        "review-write": "10/hour",
        "review-vote": "60/hour",
        # Unauthenticated auth endpoints — keyed per client IP by ScopedRateThrottle.
        "auth-login": "10/min",
        "auth-register": "10/hour",
        "auth-password": "10/hour",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Commerce API",
    "DESCRIPTION": (
        "REST API for a full-stack storefront: catalog & search, cart, coupons, "
        "orders with a state machine, returns/refunds, Stripe payments (with a "
        "keyless mock mode), and notifications. JWT auth via the /api/auth/token/ "
        "endpoints — click Authorize and paste an access token."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,  # don't list the schema endpoint in itself
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
    "TAGS": [
        {"name": "auth", "description": "Registration, login, tokens, profile, addresses."},
        {"name": "products", "description": "Catalog, search, categories, reviews."},
        {"name": "orders", "description": "Checkout, order lifecycle, payments."},
        {"name": "coupons", "description": "Discount quoting and validation."},
        {"name": "returns", "description": "Return requests and refunds."},
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# Deliver notification email + web push off the request path via a small thread
# pool. Off by default so tests (and local dev) deliver inline and deterministically;
# turn on in production so order transitions don't block on SMTP / push endpoints.
NOTIFICATIONS_ASYNC = config("NOTIFICATIONS_ASYNC", default=False, cast=bool)
NOTIFICATIONS_WORKERS = config("NOTIFICATIONS_WORKERS", default=4, cast=int)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)

# Shipping (used by orders.pricing)
SHIPPING_FLAT_FEE = Decimal(config("SHIPPING_FLAT_FEE", default="5.00"))
FREE_SHIPPING_THRESHOLD = Decimal(config("FREE_SHIPPING_THRESHOLD", default="50.00"))

# Sales tax as a percent applied to discounted merchandise (8.25 → 8.25%).
# Defaults to 0 (no tax line) so nothing changes until a rate is configured.
TAX_RATE = Decimal(config("TAX_RATE", default="0"))

RETURN_WINDOW_DAYS = config("RETURN_WINDOW_DAYS", default=30, cast=int)

# Pending orders reserve stock at creation; the release_expired_orders command
# cancels (restocks + releases the coupon) any left unpaid past this window.
PENDING_ORDER_TTL_MINUTES = config("PENDING_ORDER_TTL_MINUTES", default=30, cast=int)

# Stripe payments. Leave the secret key blank to run checkout in mock mode
# (the demo default — no SDK calls, no network, no keys required).
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_CURRENCY = config("STRIPE_CURRENCY", default="usd")

# Web Push (VAPID). Leave the keys blank to disable browser push — the in-app
# notification center and emails still work; the subscribe UI is just hidden.
# Generate a keypair with: python -m py_vapid --gen  (or the `vapid` CLI).
VAPID_PUBLIC_KEY = config("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = config("VAPID_PRIVATE_KEY", default="")
VAPID_ADMIN_EMAIL = config("VAPID_ADMIN_EMAIL", default="admin@example.com")

# Google Sign-In. Leave blank to disable — the Google button hides and the
# endpoint returns "not configured". This is the OAuth client ID (public).
GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID", default="")
