"""
Admin configuration for policies app.
"""
from django.contrib import admin

from apps.policies.models import Policy, PolicyBinding, PolicyRule


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    """Admin interface for Policy model."""

    list_display = ["name", "organization", "environment", "version", "is_active", "created_at"]
    list_filter = ["is_active", "organization", "environment", "version"]
    search_fields = ["name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    filter_horizontal = []


@admin.register(PolicyRule)
class PolicyRuleAdmin(admin.ModelAdmin):
    """Admin interface for PolicyRule model."""

    list_display = ["policy", "action", "target", "effect", "created_at"]
    list_filter = ["effect", "action", "policy"]
    search_fields = ["policy__name", "target", "action"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(PolicyBinding)
class PolicyBindingAdmin(admin.ModelAdmin):
    """Admin interface for PolicyBinding model."""

    list_display = ["policy", "scope_type", "scope_id", "priority", "created_at"]
    list_filter = ["scope_type", "policy"]
    search_fields = ["policy__name", "scope_id"]
    ordering = ["priority", "-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]

