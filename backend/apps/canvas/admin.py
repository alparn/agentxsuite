"""
Admin for canvas app.
"""
from django.contrib import admin

from apps.canvas.models import CanvasState


@admin.register(CanvasState)
class CanvasStateAdmin(admin.ModelAdmin):
    """Admin for CanvasState."""

    list_display = ["id", "organization", "environment", "name", "updated_at"]
    list_filter = ["organization", "environment", "name"]
    search_fields = ["organization__name", "environment__name", "name"]
    readonly_fields = ["id", "created_at", "updated_at"]

