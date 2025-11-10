"""
Admin configuration for agents app.
"""
from __future__ import annotations

from django.contrib import admin

from apps.agents.models import Agent


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    """Admin configuration for Agent model."""

    list_display = (
        "name",
        "mode",
        "organization",
        "environment",
        "connection",
        "enabled",
    )
    list_filter = (
        "mode",
        "enabled",
        "organization",
        "environment",
    )
    search_fields = ("name",)

