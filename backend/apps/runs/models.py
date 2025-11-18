"""
Run models for tool execution.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models

from libs.common.models import TimeStamped


class ModelPricing(TimeStamped):
    """
    Model pricing table for LLM token cost calculation.
    
    Stores cost per 1000 tokens for different models.
    Supports versioning via effective_from date.
    """
    
    model_name = models.CharField(
        max_length=100,
        help_text="Model identifier (e.g., 'gpt-4', 'claude-3-opus')",
    )
    provider = models.CharField(
        max_length=50,
        default="openai",
        help_text="Provider name (e.g., 'openai', 'anthropic', 'groq')",
    )
    input_cost_per_1k = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Cost per 1000 input tokens in USD",
    )
    output_cost_per_1k = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Cost per 1000 output tokens in USD",
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency code (ISO 4217)",
    )
    effective_from = models.DateTimeField(
        auto_now_add=True,
        help_text="When this pricing becomes effective",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this pricing is currently active",
    )
    
    class Meta:
        db_table = "runs_modelpricing"
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["model_name", "-effective_from"]),
            models.Index(fields=["provider", "model_name"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["model_name", "effective_from"]]
    
    def __str__(self) -> str:
        return f"{self.provider}/{self.model_name} - ${self.input_cost_per_1k}/{self.output_cost_per_1k} per 1K tokens"


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
    
    # Token tracking fields
    input_tokens = models.IntegerField(
        default=0,
        help_text="Number of input/prompt tokens consumed",
    )
    output_tokens = models.IntegerField(
        default=0,
        help_text="Number of output/completion tokens consumed",
    )
    total_tokens = models.IntegerField(
        default=0,
        help_text="Total tokens consumed (input + output)",
    )
    model_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Model used for execution (if applicable)",
    )
    
    # Cost fields (calculated from tokens × pricing)
    cost_input = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Cost for input tokens in USD",
    )
    cost_output = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Cost for output tokens in USD",
    )
    cost_total = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total cost in USD (input + output)",
    )
    cost_currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency for cost fields",
    )

    class Meta:
        db_table = "runs_run"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["environment", "created_at"]),
            models.Index(fields=["agent", "created_at"]),
            models.Index(fields=["model_name", "created_at"]),
            models.Index(fields=["cost_total"]),
        ]

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

