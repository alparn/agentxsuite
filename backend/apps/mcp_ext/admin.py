"""
Admin interface for mcp_ext models.
"""
from django.contrib import admin

from apps.mcp_ext.models import MCPServerRegistration, Prompt, Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Admin interface for Resource model."""

    list_display = ["name", "organization", "environment", "type", "mime_type", "enabled", "created_at"]
    list_filter = ["type", "enabled", "organization", "environment"]
    search_fields = ["name", "organization__name", "environment__name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    """Admin interface for Prompt model."""

    list_display = ["name", "organization", "environment", "enabled", "created_at"]
    list_filter = ["enabled", "organization", "environment"]
    search_fields = ["name", "description", "organization__name", "environment__name"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(MCPServerRegistration)
class MCPServerRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for MCPServerRegistration model."""

    list_display = [
        "slug",
        "name",
        "organization",
        "environment",
        "server_type",
        "enabled",
        "health_status",
        "created_at",
    ]
    list_filter = ["server_type", "enabled", "health_status", "organization", "environment"]
    search_fields = ["name", "slug", "description", "organization__name", "environment__name"]
    readonly_fields = ["id", "created_at", "updated_at", "last_health_check", "health_status", "health_message"]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "organization",
                    "environment",
                    "name",
                    "slug",
                    "description",
                    "server_type",
                    "enabled",
                )
            },
        ),
        (
            "Connection Details",
            {
                "fields": (
                    "endpoint",
                    "command",
                    "args",
                    "env_vars",
                )
            },
        ),
        (
            "Authentication",
            {
                "fields": (
                    "auth_method",
                    "secret_ref",
                )
            },
        ),
        (
            "Health & Status",
            {
                "fields": (
                    "last_health_check",
                    "health_status",
                    "health_message",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "tags",
                    "metadata",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "id",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )










