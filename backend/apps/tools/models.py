"""
Tool registry models.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
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
        help_text="MCP server connection this tool belongs to",
    )
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50, default="1.0.0")
    schema_json = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)
    is_agent_visible = models.BooleanField(
        default=False,
        help_text="Whether this raw tool can be exposed directly to agents.",
    )
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
        indexes = [
            models.Index(fields=["organization", "environment", "is_agent_visible"]),
            models.Index(fields=["connection", "enabled"]),
        ]

    @property
    def is_system_tool(self) -> bool:
        """Check if this is a system tool (belongs to system connection)."""
        return self.connection.endpoint == "agentxsuite://system"

    def clean(self) -> None:
        """Validate organization/environment consistency for raw tools."""
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.organization_id
            and self.environment_id
            and self.environment.organization_id != self.organization_id
        ):
            errors["environment"] = "Environment must belong to the tool organization."

        if self.connection_id:
            if self.organization_id and self.connection.organization_id != self.organization_id:
                errors["connection"] = "Connection must belong to the tool organization."
            if self.environment_id and self.connection.environment_id != self.environment_id:
                errors["connection"] = "Connection must belong to the tool environment."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"


class CuratedTool(TimeStamped):
    """Agent-facing high-level tool generated from one or more raw tools."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="curated_tools",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="curated_tools",
    )
    connection = models.ForeignKey(
        "connections.Connection",
        on_delete=models.CASCADE,
        related_name="curated_tools",
        help_text="Source MCP server connection for this curated tool.",
    )
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    schema_json = models.JSONField(default=dict)
    curator_type = models.CharField(max_length=100)
    raw_tools = models.ManyToManyField(
        "tools.Tool",
        through="tools.CurationMapping",
        related_name="curated_parents",
        blank=True,
    )
    orchestration_config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    category = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    avg_execution_time_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "tools_curated_tool"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]
        indexes = [
            models.Index(fields=["connection", "enabled"]),
            models.Index(fields=["curator_type"]),
            models.Index(fields=["category"]),
        ]

    def clean(self) -> None:
        """Validate organization/environment consistency for curated tools."""
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.organization_id
            and self.environment_id
            and self.environment.organization_id != self.organization_id
        ):
            errors["environment"] = "Environment must belong to the curated tool organization."

        if self.connection_id:
            if self.organization_id and self.connection.organization_id != self.organization_id:
                errors["connection"] = "Connection must belong to the curated tool organization."
            if self.environment_id and self.connection.environment_id != self.environment_id:
                errors["connection"] = "Connection must belong to the curated tool environment."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"


class CurationMapping(TimeStamped):
    """Ordered mapping from an agent-facing curated tool to a raw tool."""

    curated_tool = models.ForeignKey(
        "tools.CuratedTool",
        on_delete=models.CASCADE,
        related_name="mappings",
    )
    raw_tool = models.ForeignKey(
        "tools.Tool",
        on_delete=models.CASCADE,
        related_name="curation_mappings",
    )
    execution_order = models.PositiveIntegerField(default=0)
    parameter_mapping = models.JSONField(default=dict, blank=True)
    condition = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "tools_curation_mapping"
        ordering = ["execution_order", "created_at"]
        unique_together = [["curated_tool", "raw_tool", "execution_order"]]
        indexes = [
            models.Index(fields=["curated_tool", "execution_order"]),
            models.Index(fields=["raw_tool"]),
        ]

    def clean(self) -> None:
        """Validate that mapped raw tools stay in the curated tool scope."""
        super().clean()
        errors: dict[str, str] = {}

        if self.curated_tool_id and self.raw_tool_id:
            if self.raw_tool.organization_id != self.curated_tool.organization_id:
                errors["raw_tool"] = "Raw tool must belong to the curated tool organization."
            if self.raw_tool.environment_id != self.curated_tool.environment_id:
                errors["raw_tool"] = "Raw tool must belong to the curated tool environment."
            if self.raw_tool.connection_id != self.curated_tool.connection_id:
                errors["raw_tool"] = "Raw tool must belong to the curated tool connection."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.curated_tool.name} -> {self.raw_tool.name} "
            f"({self.execution_order})"
        )

