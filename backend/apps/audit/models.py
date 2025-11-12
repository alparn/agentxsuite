"""
Audit event models (stub).
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class AuditEvent(TimeStamped):
    """Audit event model for policy decisions and security events."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=100)
    event_data = models.JSONField(default=dict)
    # Policy-specific audit fields
    ts = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the event (synced with created_at)",
    )
    subject = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Calling identity (Agent/User/Client)",
    )
    action = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Action performed, e.g., 'tool.invoke', 'agent.invoke'",
    )
    target = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        help_text="Target of the action, e.g., 'tool:pdf/read', 'agent:ocr'",
    )
    decision = models.CharField(
        max_length=8,
        choices=[("allow", "Allow"), ("deny", "Deny")],
        null=True,
        blank=True,
        help_text="Policy decision: allow or deny",
    )
    rule_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of the matching policy rule (if any)",
    )
    context = models.JSONField(
        default=dict,
        help_text="Additional context for the audit event",
    )

    class Meta:
        db_table = "audit_auditevent"
        ordering = ["-ts", "-created_at"]
        indexes = [
            models.Index(fields=["subject", "action", "decision"]),
            models.Index(fields=["ts"]),
            models.Index(fields=["organization", "ts"]),
            models.Index(fields=["rule_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} at {self.ts or self.created_at}"

    def save(self, *args, **kwargs):
        """Ensure ts is set from created_at if not explicitly set."""
        # Set ts from created_at if not set (for new instances)
        if not self.ts:
            if self.created_at:
                self.ts = self.created_at
            else:
                from django.utils import timezone
                self.ts = timezone.now()
        
        # Save first time
        super().save(*args, **kwargs)
        
        # Ensure ts is synced after save (only if different and not in update_fields)
        if self.ts != self.created_at and "update_fields" not in kwargs:
            self.ts = self.created_at
            # Use update_fields to avoid recursion
            super().save(update_fields=["ts"])

