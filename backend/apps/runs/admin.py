"""
Django admin for runs app.
"""
from __future__ import annotations

from django.contrib import admin

from apps.runs.models import ModelPricing, Run, RunStep


@admin.register(ModelPricing)
class ModelPricingAdmin(admin.ModelAdmin):
    """Admin interface for ModelPricing."""
    
    list_display = [
        "model_name",
        "provider",
        "input_cost_per_1k",
        "output_cost_per_1k",
        "currency",
        "effective_from",
        "is_active",
    ]
    list_filter = [
        "provider",
        "is_active",
        "effective_from",
    ]
    search_fields = [
        "model_name",
        "provider",
    ]
    ordering = ["-effective_from", "model_name"]
    readonly_fields = ["created_at", "updated_at"]
    
    fieldsets = (
        ("Model Information", {
            "fields": ("model_name", "provider"),
        }),
        ("Pricing", {
            "fields": (
                "input_cost_per_1k",
                "output_cost_per_1k",
                "currency",
            ),
        }),
        ("Status", {
            "fields": ("is_active", "effective_from"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    """Admin interface for Run."""
    
    list_display = [
        "id",
        "agent",
        "tool",
        "status",
        "cost_total",
        "total_tokens",
        "started_at",
    ]
    list_filter = [
        "status",
        "organization",
        "environment",
        "model_name",
        "created_at",
    ]
    search_fields = [
        "id",
        "agent__name",
        "tool__name",
        "model_name",
    ]
    ordering = ["-created_at"]
    readonly_fields = [
        "id",
        "organization",
        "environment",
        "agent",
        "tool",
        "status",
        "started_at",
        "ended_at",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "model_name",
        "cost_input",
        "cost_output",
        "cost_total",
        "cost_currency",
        "created_at",
        "updated_at",
    ]
    
    fieldsets = (
        ("Context", {
            "fields": (
                "organization",
                "environment",
                "agent",
                "tool",
            ),
        }),
        ("Execution", {
            "fields": (
                "status",
                "started_at",
                "ended_at",
                "input_json",
                "output_json",
                "error_text",
            ),
        }),
        ("Token Usage", {
            "fields": (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "model_name",
            ),
        }),
        ("Costs", {
            "fields": (
                "cost_input",
                "cost_output",
                "cost_total",
                "cost_currency",
            ),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    def has_add_permission(self, request):
        """Runs are created via API, not admin."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Runs are immutable after completion."""
        return False


@admin.register(RunStep)
class RunStepAdmin(admin.ModelAdmin):
    """Admin interface for RunStep."""
    
    list_display = [
        "id",
        "run",
        "step_type",
        "message",
        "timestamp",
    ]
    list_filter = [
        "step_type",
        "timestamp",
    ]
    search_fields = [
        "run__id",
        "message",
    ]
    ordering = ["-timestamp"]
    readonly_fields = [
        "run",
        "step_type",
        "message",
        "details",
        "timestamp",
        "created_at",
        "updated_at",
    ]
    
    def has_add_permission(self, request):
        """Run steps are created programmatically."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Run steps are immutable."""
        return False

