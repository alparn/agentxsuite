"""
Connection models for MCP server connections.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Connection(TimeStamped):
    """MCP server connection model."""

    AUTH_METHOD_CHOICES = [
        ("none", "None"),
        ("bearer", "Bearer Token"),
        ("basic", "Basic Auth"),
    ]

    STATUS_CHOICES = [
        ("unknown", "Unknown"),
        ("ok", "OK"),
        ("fail", "Failed"),
    ]

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="connections",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="connections",
    )
    name = models.CharField(max_length=255)
    endpoint = models.URLField(max_length=500)
    auth_method = models.CharField(
        max_length=10,
        choices=AUTH_METHOD_CHOICES,
        default="none",
    )
    secret_ref = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="unknown",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "connections_connection"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"

