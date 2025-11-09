"""
Run models for tool execution.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Run(models.Model):
    """Run model for tool execution."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    ]

    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    tool = models.ForeignKey(
        "tools.Tool",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    input_json = models.JSONField(default=dict)
    output_json = models.JSONField(default=dict, null=True, blank=True)
    error_text = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "runs_run"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.id} - {self.tool.name} ({self.status})"

