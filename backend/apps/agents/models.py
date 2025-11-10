"""
Agent models.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from libs.common.models import TimeStamped


class AgentMode(models.TextChoices):
    """Agent execution mode."""

    RUNNER = "runner", "Runner"
    CALLER = "caller", "Caller"


class InboundAuthMethod(models.TextChoices):
    """Inbound authentication method."""

    BEARER = "bearer", "Bearer"
    MTLS = "mtls", "mTLS"
    NONE = "none", "None"


class Agent(TimeStamped):
    """Agent model."""

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
        on_delete=models.SET_NULL,
        related_name="agents",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50, default="1.0.0")
    enabled = models.BooleanField(default=True)
    mode = models.CharField(
        max_length=10,
        choices=AgentMode.choices,
        default=AgentMode.RUNNER,
    )
    inbound_auth_method = models.CharField(
        max_length=20,
        choices=InboundAuthMethod.choices,
        default=InboundAuthMethod.BEARER,
    )
    inbound_secret_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "agents_agent"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def clean(self) -> None:
        """Validate agent configuration based on mode."""
        super().clean()

        if self.mode == AgentMode.RUNNER:
            if not self.connection:
                raise ValidationError(
                    {"connection": "Connection is required for RUNNER mode agents."}
                )

        if self.mode == AgentMode.CALLER:
            # Connection is optional for CALLER mode agents
            # (they can use it for outbound tool execution if needed)
            
            if (
                self.inbound_auth_method != InboundAuthMethod.NONE
                and not self.inbound_secret_ref
            ):
                raise ValidationError(
                    {
                        "inbound_secret_ref": (
                            f"Secret reference is required when "
                            f"inbound_auth_method is '{self.inbound_auth_method}'."
                        )
                    }
                )

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"

