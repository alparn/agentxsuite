"""
Admin configuration for audit app.
"""
from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Admin interface for AuditEvent model."""

    list_display = [
        "ts",
        "subject",
        "action",
        "target",
        "decision",
        "rule_id",
        "organization",
    ]
    list_filter = ["decision", "action", "organization", "ts"]
    search_fields = ["subject", "action", "target", "event_type"]
    ordering = ["-ts", "-created_at"]
    readonly_fields = ["id", "created_at", "updated_at", "ts"]
    date_hierarchy = "ts"

