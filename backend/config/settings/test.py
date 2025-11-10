"""
Test settings.
"""
from __future__ import annotations

from .base import *  # noqa: F403, F401

DEBUG = False

ALLOWED_HOSTS = []

# Database
# Use in-memory SQLite for tests (each test gets its own DB)
# Note: For parallel tests with pytest-xdist, each worker gets its own DB
# SQLite in-memory DBs don't support WAL mode, but each test isolation prevents locks
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            # Allow pytest-django to create separate test DBs per worker
            "NAME": None,  # Use in-memory DB
        },
    }
}

# Ensure connections are closed properly after each test
# This prevents connection leaks that can cause locks
from django.db import connections  # noqa: E402


def close_db_connections():
    """Close all DB connections to prevent leaks."""
    for conn in connections.all():
        conn.close()


# Register cleanup hook (pytest-django handles this automatically, but explicit is better)
import atexit  # noqa: E402

atexit.register(close_db_connections)

# Password hashers for faster tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable migrations in tests for speed
class DisableMigrations:  # noqa: N801
    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str) -> None:
        return None


MIGRATION_MODULES = DisableMigrations()

# SecretStore test key (deterministic for tests)
SECRETSTORE_FERNET_KEY = b"test-key-32-bytes-long!!!"  # noqa: S105

