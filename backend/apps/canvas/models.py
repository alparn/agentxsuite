"""
Canvas models for storing visual canvas state.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class CanvasState(TimeStamped):
    """Model for storing canvas visualization state (shared across organization, like Miro boards)."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="canvas_states",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.SET_NULL,
        related_name="canvas_states",
        null=True,
        blank=True,
        help_text="Optional: Canvas state for specific environment",
    )
    name = models.CharField(
        max_length=255,
        default="default",
        help_text="Canvas name (e.g., 'default', 'production', 'staging')",
    )
    state_json = models.JSONField(
        default=dict,
        help_text="Canvas state including nodes, edges, viewport, and groups",
    )

    class Meta:
        db_table = "canvas_canvasstate"
        ordering = ["-updated_at"]
        unique_together = [["organization", "environment", "name"]]
        indexes = [
            models.Index(fields=["organization", "environment", "name"]),
        ]

    def __str__(self) -> str:
        env_name = self.environment.name if self.environment else "all"
        return f"{self.organization.name}/{env_name}/{self.name}"

