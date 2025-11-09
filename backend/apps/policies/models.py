"""
Policy models for access control.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Policy(TimeStamped):
    """Policy model for access control."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="policies",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="policies",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    rules_json = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "policies_policy"
        ordering = ["-created_at"]
        unique_together = [["organization", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name}"

