"""
Audit event models (stub).
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    """Audit event model stub."""

    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=100)
    event_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_auditevent"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} at {self.created_at}"

