"""
System tools app configuration.
"""
from django.apps import AppConfig


class SystemToolsConfig(AppConfig):
    """System tools app configuration."""
    
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.system_tools"
    verbose_name = "System Tools"

