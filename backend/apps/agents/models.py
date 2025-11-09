"""
Agent models.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Agent(models.Model):
    """Agent model."""

    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="agents",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="agents",
    )
    connection = models.ForeignKey(
        "connections.Connection",
        on_delete=models.CASCADE,
        related_name="agents",
    )
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50, default="1.0.0")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agents_agent"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"

