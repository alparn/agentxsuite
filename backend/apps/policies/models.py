"""
Policy models for access control.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Policy(models.Model):
    """Policy model for access control."""

    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="policies",
    )
    name = models.CharField(max_length=255)
    rules_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "policies_policy"
        ordering = ["-created_at"]
        unique_together = [["organization", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name}"

