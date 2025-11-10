"""
Tool registry models.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Tool(TimeStamped):
    """Tool registry model."""

    SYNC_STATUS_CHOICES = [
        ("synced", "Synced"),
        ("failed", "Sync Failed"),
        ("stale", "Stale"),
    ]

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="tools",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="tools",
    )
    connection = models.ForeignKey(
        "connections.Connection",
        on_delete=models.CASCADE,
        related_name="tools",
        null=False,
        help_text="MCP server connection this tool belongs to",
    )
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50, default="1.0.0")
    schema_json = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default="synced",
        help_text="Status of the last sync operation",
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful sync",
    )

    class Meta:
        db_table = "tools_tool"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name", "version"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"

