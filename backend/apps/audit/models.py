"""
Audit event models (stub).
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class AuditEvent(TimeStamped):
    """Audit event model stub."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=100)
    event_data = models.JSONField(default=dict)

    class Meta:
        db_table = "audit_auditevent"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} at {self.created_at}"

