"""
Test settings.
"""
from __future__ import annotations

from .base import *  # noqa: F403, F401

DEBUG = False

ALLOWED_HOSTS = []

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

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

