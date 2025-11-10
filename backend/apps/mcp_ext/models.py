"""
MCP Extensions models: Resources and Prompts.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Resource(TimeStamped):
    """Resource model for MCP resources."""

    TYPE_CHOICES = [
        ("static", "Static"),
        ("http", "HTTP"),
        ("sql", "SQL"),
        ("s3", "S3"),
        ("file", "File"),
    ]

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="resources",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="resources",
    )
    name = models.CharField(max_length=120)
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="static",
    )
    config_json = models.JSONField(
        default=dict,
        help_text="Configuration for resource type (e.g., URL for HTTP, value for static)",
    )
    mime_type = models.CharField(
        max_length=80,
        default="application/json",
        help_text="MIME type of the resource content",
    )
    schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON Schema describing the resource structure",
    )
    secret_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for authentication (e.g., API keys)",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mcp_ext_resource"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"


class Prompt(TimeStamped):
    """Prompt model for MCP prompts."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="prompts",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="prompts",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    input_schema = models.JSONField(
        default=dict,
        help_text="JSON Schema for prompt input variables",
    )
    template_system = models.TextField(
        blank=True,
        help_text="System message template (Jinja2)",
    )
    template_user = models.TextField(
        blank=True,
        help_text="User message template (Jinja2)",
    )
    uses_resources = models.JSONField(
        default=list,
        help_text="List of resource names used by this prompt",
    )
    output_hints = models.JSONField(
        default=dict,
        blank=True,
        help_text="Hints for expected output format",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mcp_ext_prompt"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"

