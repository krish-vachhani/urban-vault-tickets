"""Django settings for the Urban Vault ticketing backend.

All environment-specific values come from environment variables (see the
repository's .env.example). Secrets have no defaults: the application refuses
to start without them.
"""

from datetime import timedelta
from pathlib import Path

from config.env import (
    get_bool_env,
    get_int_env,
    get_list_env,
    get_optional_env,
    get_required_env,
)

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core security -----------------------------------------------------------

SECRET_KEY = get_required_env("SECRET_KEY")
DEBUG = get_bool_env("DEBUG", default=False)
ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# The browser reaches Django through the Vite dev-server proxy (local) or
# CloudFront (production), so the page origin must be trusted for CSRF checks.
CSRF_TRUSTED_ORIGINS = get_list_env("CSRF_TRUSTED_ORIGINS", default=[])

# --- Applications ---------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
]

PROJECT_APPS = [
    "apps.accounts",
    "apps.organizations",
    "apps.tickets",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + PROJECT_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# --- Authentication ---------------------------------------------------------------

# One custom user model for all four roles. Must be set before the first migration.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# SimpleJWT: short-lived access token in React memory, rotating refresh token in an
# HttpOnly cookie (readmes/README-authentication.md §2 and §7).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": get_required_env("JWT_SIGNING_KEY"),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REFRESH_COOKIE_NAME = "uv_refresh"
# The browser sends the refresh cookie only to the auth endpoints, never to ticket endpoints.
REFRESH_COOKIE_PATH = "/api/v1/auth/"
# Secure by default; only local plain-HTTP development turns it off in .env.
REFRESH_COOKIE_SECURE = get_bool_env("REFRESH_COOKIE_SECURE", default=True)
# Django's CSRF cookie follows the refresh cookie: HTTPS-only wherever HTTPS is used.
CSRF_COOKIE_SECURE = REFRESH_COOKIE_SECURE

# --- Database (PostgreSQL only; tests also run on PostgreSQL) -------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_required_env("DB_NAME"),
        "USER": get_required_env("DB_USER"),
        "PASSWORD": get_required_env("DB_PASSWORD"),
        "HOST": get_optional_env("DB_HOST", default="localhost"),
        "PORT": get_int_env("DB_PORT", default=5432),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework ---------------------------------------------------------------

REST_FRAMEWORK = {
    # Bearer access tokens only; the refresh cookie never authenticates an API request.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "EXCEPTION_HANDLER": "config.exception_handler.api_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# --- Celery (Redis is the broker only; PostgreSQL holds notification state) -----------------

CELERY_BROKER_URL = get_required_env("REDIS_URL")
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = "UTC"

# --- Internationalization ------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static files (Django admin assets only; the React app is served separately) ------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Logging -----------------------------------------------------------------------------------

LOG_LEVEL = get_optional_env("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}
