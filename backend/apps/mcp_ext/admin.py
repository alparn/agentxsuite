"""
Admin interface for mcp_ext models.
"""
from django.contrib import admin

from apps.mcp_ext.models import Prompt, Resource


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

