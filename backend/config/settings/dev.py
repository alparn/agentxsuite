"""
Development settings.
"""
from __future__ import annotations

from decouple import config

from .base import *  # noqa: F403, F401

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

# Database
DATABASES = {
    "default": {
        "ENGINE": config(
            "DATABASE_ENGINE",
            default="django.db.backends.sqlite3",
        ),
        "NAME": config(
            "DATABASE_NAME",
            default=str(BASE_DIR / "db.sqlite3"),  # noqa: F405
        ),
        "USER": config("DATABASE_USER", default=""),
        "PASSWORD": config("DATABASE_PASSWORD", default=""),
        "HOST": config("DATABASE_HOST", default=""),
        "PORT": config("DATABASE_PORT", default=""),
    }
}

# CORS Configuration for Development
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

CORS_ALLOW_CREDENTIALS = True

