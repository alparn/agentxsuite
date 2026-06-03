"""
Connection models for MCP server connections.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from libs.common.models import TimeStamped


class Connection(TimeStamped):
    """MCP server connection model."""

    class Transport(models.TextChoices):
        STDIO = "stdio", "stdio"
        STREAMABLE_HTTP = "streamable_http", "Streamable HTTP"
        SSE = "sse", "SSE"
        LEGACY_HTTP = "legacy_http", "Legacy HTTP"

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
    transport = models.CharField(
        max_length=20,
        choices=Transport.choices,
        default=Transport.LEGACY_HTTP,
        db_index=True,
    )
    endpoint = models.URLField(max_length=500, blank=True, null=True)
    egress_allowlist = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed outbound hostnames, wildcard host patterns, or CIDR ranges for HTTP MCP transports.",
    )
    command = models.CharField(max_length=500, blank=True)
    args = models.JSONField(default=list, blank=True)
    env_ref = models.CharField(max_length=255, blank=True, null=True)
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

    def clean(self) -> None:
        """Validate transport details and organization/environment consistency."""
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.organization_id
            and self.environment_id
            and self.environment.organization_id != self.organization_id
        ):
            errors["environment"] = "Environment must belong to the connection organization."

        if self.transport == self.Transport.STDIO:
            if not self.command:
                errors["command"] = "command is required for stdio connections."
        elif not self.endpoint:
            errors["endpoint"] = "endpoint is required for HTTP-based connections."

        if not isinstance(self.args, list):
            errors["args"] = "args must be a list."

        if not isinstance(self.egress_allowlist, list) or not all(
            isinstance(entry, str) for entry in self.egress_allowlist
        ):
            errors["egress_allowlist"] = "egress_allowlist must be a list of strings."

        if errors:
            raise ValidationError(errors)

