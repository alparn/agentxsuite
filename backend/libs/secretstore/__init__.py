"""
SecretStore package for managing secrets.
"""
from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

# Get the backend class from settings
_backend_class = import_string(getattr(settings, "SECRETSTORE_BACKEND", "libs.secretstore.fernet.FernetSecretStore"))
_secretstore_instance = None


def get_secretstore() -> "SecretStore":  # noqa: F821
    """Get the secretstore instance (singleton)."""
    global _secretstore_instance  # noqa: PLW0603
    if _secretstore_instance is None:
        _secretstore_instance = _backend_class()
    return _secretstore_instance


__all__ = ["get_secretstore"]

