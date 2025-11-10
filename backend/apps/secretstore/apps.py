"""
App config for secretstore.
"""
from __future__ import annotations

from django.apps import AppConfig


class SecretstoreConfig(AppConfig):
    """App configuration for secretstore."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.secretstore"

