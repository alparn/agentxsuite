"""Django app configuration for Claude Agent SDK integration."""

from django.apps import AppConfig


class ClaudeAgentConfig(AppConfig):
    """Configuration for the Claude Agent SDK integration app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.claude_agent"
    verbose_name = "Claude Agent SDK Integration"

    def ready(self):
        """Initialize app when Django starts."""
        # Import signal handlers if needed
        pass

