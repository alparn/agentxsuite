"""
Base Django settings for config project.
"""
from __future__ import annotations

from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-1-r@2ht9@6knvvi%2dv#vcs+%jf@c18kb6(id3)98ia-$4dnl_",
)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    # Local apps
    "libs.common",
    "apps.accounts",
    "apps.tenants",
    "apps.connections",
    "apps.agents",
    "apps.tools",
    "apps.runs",
    "apps.policies",
    "apps.audit",
    "apps.secretstore",
    "apps.mcp_ext",
    "apps.system_tools",
    "apps.canvas",
    "apps.claude_agent",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "config.middleware.LoggingContextMiddleware",  # Context propagation for logging
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

# Cache configuration (for rate limiting)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "agentxsuite-cache",
    }
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        # SessionAuthentication removed for security: No sessions as auth replacement
        # Sessions are only for Django admin, not for API authentication
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
}

# MCP Fabric: Hard session handling - no sessions as auth replacement
# FastAPI endpoints only accept Bearer tokens, no session cookies
MCP_FABRIC_SESSION_AUTH_DISABLED = True

# SecretStore Configuration
SECRETSTORE_BACKEND = config(
    "SECRETSTORE_BACKEND",
    default="libs.secretstore.fernet.FernetSecretStore",
)
SECRETSTORE_FERNET_KEY = config("SECRETSTORE_FERNET_KEY", default=None)  # Will be generated if None

# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-request-id",  # For request ID propagation
]

# Logging Configuration
# JSON logging with context propagation and secret redaction
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "libs.logging.formatters.JSONFormatter",
        },
        "verbose": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s [trace_id=%(trace_id)s run_id=%(run_id)s request_id=%(request_id)s]",
        },
    },
    "filters": {
        "context": {
            "()": "libs.logging.filters.ContextFilter",
        },
        "secret_redaction": {
            "()": "libs.logging.filters.SecretRedactionFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["context", "secret_redaction"],
            "stream": "ext://sys.stdout",
        },
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "level": config("LOG_LEVEL", default="INFO"),
        "handlers": ["console"],
    },
    "loggers": {
        # Django loggers
        "django": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "django.request": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        "django.security": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
        # Application loggers
        "apps": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "mcp_fabric": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "libs": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        # Uvicorn/FastAPI loggers (will be configured by FastAPI middleware)
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "fastapi": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

