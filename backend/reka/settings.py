"""Reka commerce platform settings.

Aligned with ADR-0001 (DRF), ADR-0004 (JWT), ADR-0005 (cart session),
ADR-0006 (URL versioning), ADR-0007 (Postgres + Redis), ADR-0009 (Decimal money).
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-change-me-reka-northbound-local-secret-key-32b",
)
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,testserver"
    ).split(",")
    if h.strip()
]

CART_SESSION_HMAC_SECRET = os.getenv("CART_SESSION_HMAC_SECRET", SECRET_KEY)
MFA_ENCRYPTION_KEY = os.getenv("MFA_ENCRYPTION_KEY", SECRET_KEY[:32].ljust(32, "0"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # local
    "apps.core",
    "apps.accounts",
    "apps.catalogue",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.pricing",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.core.middleware.CartSessionMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.ratelimit.RateLimitMiddleware",
]

ROOT_URLCONF = "reka.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "reka.wsgi.application"

# Database — SQLite for local zero-config; Postgres via DATABASE_URL / env.
if os.getenv("POSTGRES_HOST") or os.getenv("DATABASE_URL"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "reka"),
            "USER": os.getenv("POSTGRES_USER", "reka"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "reka"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
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
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-za"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS — prototype / Flutter web on local ports
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500,null",
    ).split(",")
    if o.strip() and o.strip() != "null"
]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-cart-session",
    "x-app-version",
    "x-request-id",
    "idempotency-key",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.RekaJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.reka_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Reka / Northbound API",
    "DESCRIPTION": "Commerce platform API — /api/v1/",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# App version gate (ADR-0006)
APP_MIN_SUPPORTED = os.getenv("APP_MIN_SUPPORTED", "1.0.0")
APP_LATEST = os.getenv("APP_LATEST", "1.0.0")
APP_FORCE_UPDATE = os.getenv("APP_FORCE_UPDATE", "false").lower() in ("1", "true")

# Email (console in local; SMTP → Mailpit in Compose)
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "orders@northbound.test")
REKA_SITE_BRAND_NAME = os.getenv("REKA_SITE_BRAND_NAME", "Northbound")
MERCHANT_LEGAL_NAME = os.getenv(
    "MERCHANT_LEGAL_NAME", f"{REKA_SITE_BRAND_NAME} Outdoor (Pty) Ltd"
)
MERCHANT_VAT_NUMBER = os.getenv("MERCHANT_VAT_NUMBER", "4123456789")
MERCHANT_ADDRESS = os.getenv(
    "MERCHANT_ADDRESS", "1 Dock Road, V&A Waterfront, Cape Town, 8001"
)

# Celery (optional — emails send inline when broker unset / eager)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", ""))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL or None)
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() in (
    "1",
    "true",
    "yes",
)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TRACK_STARTED = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "release-stale-pending-payments": {
        "task": "payments.release_stale_pending",
        "schedule": 900.0,  # every 15 minutes
        "kwargs": {"hours": 2},
    },
    "daily-payment-reconciliation": {
        "task": "payments.run_daily_reconciliation",
        "schedule": 86400.0,  # daily
    },
}
STALE_PAYMENT_HOURS = int(os.getenv("STALE_PAYMENT_HOURS", "2"))

# Inventory
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "3"))

# Currency
DEFAULT_CURRENCY = "ZAR"

# Payments (ADR-0011)
PAYMENT_WEBHOOK_SECRET = os.getenv(
    "PAYMENT_WEBHOOK_SECRET", "dev-webhook-secret-change-me"
)
PUBLIC_API_BASE = os.getenv("PUBLIC_API_BASE", "http://127.0.0.1:8000")
# sandbox | payfast — card/EFT hosted provider
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "sandbox").lower()
PAYFAST_MERCHANT_ID = os.getenv("PAYFAST_MERCHANT_ID", "")
PAYFAST_MERCHANT_KEY = os.getenv("PAYFAST_MERCHANT_KEY", "")
PAYFAST_PASSPHRASE = os.getenv("PAYFAST_PASSPHRASE", "")
PAYFAST_SANDBOX = os.getenv("PAYFAST_SANDBOX", "true").lower() in ("1", "true", "yes")

# Push (optional — dry-run when unset)
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

# TLS / proxy (enable when behind nginx with HTTPS)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() in (
    "1",
    "true",
    "yes",
)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Fail closed if someone deploys with DEBUG and a weak secret
if not DEBUG:
    if SECRET_KEY.startswith("dev-") or "change-me" in SECRET_KEY:
        raise RuntimeError(
            "DJANGO_SECRET_KEY must be set to a strong value when DEBUG is False."
        )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s",
        },
    },
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIDFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
}
