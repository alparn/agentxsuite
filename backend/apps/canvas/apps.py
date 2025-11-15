"""
Canvas app configuration.
"""
from django.apps import AppConfig


class CanvasConfig(AppConfig):
    """Canvas app configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.canvas"

