"""
Run models for tool execution.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Run(TimeStamped):
    """Run model for tool execution."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    ]

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
        help_text="Tool instance",
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

    class Meta:
        db_table = "runs_run"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.id} - {self.tool.name} ({self.status})"


class RunStep(TimeStamped):
    """Run step model for tracking individual steps during execution."""

    STEP_TYPE_CHOICES = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("check", "Check"),
        ("execution", "Execution"),
    ]

    run = models.ForeignKey(
        Run,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    step_type = models.CharField(
        max_length=20,
        choices=STEP_TYPE_CHOICES,
        default="info",
    )
    message = models.TextField()
    details = models.JSONField(default=dict, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "runs_runstep"
        ordering = ["timestamp"]

    def __str__(self) -> str:
        return f"Step {self.id} - {self.step_type} - {self.message[:50]}"

