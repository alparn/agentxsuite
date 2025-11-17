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
    """Inbound authentication method for agents."""

    BEARER = "bearer", "Bearer Token"
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
    service_account = models.OneToOneField(
        "accounts.ServiceAccount",
        on_delete=models.PROTECT,
        related_name="agent",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=80,
        null=True,
        blank=True,
        help_text="URL-friendly identifier (case-insensitive unique per org/env)",
    )
    version = models.CharField(max_length=50, default="1.0.0")
    enabled = models.BooleanField(default=True)
    mode = models.CharField(
        max_length=10,
        choices=AgentMode.choices,
        default=AgentMode.RUNNER,
    )
    capabilities = models.JSONField(
        default=list,
        blank=True,  # Allow empty lists
        help_text="List of agent capabilities",
    )
    tags = models.JSONField(
        default=list,
        blank=True,  # Allow empty lists
        help_text="Tags for filtering and grouping",
    )
    # Delegation defaults
    default_max_depth = models.PositiveSmallIntegerField(
        default=1,
        help_text="Default maximum delegation depth",
    )
    default_budget_cents = models.PositiveIntegerField(
        default=0,
        help_text="Default budget in cents (0 = unlimited)",
    )
    default_ttl_seconds = models.PositiveIntegerField(
        default=600,
        help_text="Default TTL in seconds for delegation",
    )
    # Inbound authentication
    inbound_auth_method = models.CharField(
        max_length=20,
        choices=InboundAuthMethod.choices,
        default=InboundAuthMethod.BEARER,
    )
    inbound_secret_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for bearer token (legacy field name)",
    )
    bearer_secret_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for bearer token authentication",
    )
    mtls_cert_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for mTLS certificate",
    )
    mtls_key_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for mTLS private key",
    )
    mtls_ca_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for mTLS CA certificate",
    )

    class Meta:
        db_table = "agents_agent"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "environment", "slug"],
                name="unique_agent_slug_per_org_env",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "environment", "enabled"]),
            models.Index(fields=["mode"]),
            models.Index(fields=["organization", "environment", "slug"]),
        ]

    def clean(self) -> None:
        """
        Validate agent configuration based on mode and auth method.
        
        This validation is only enforced for new instances (_state.adding is True).
        For updates, validation is handled in the serializer to allow partial updates
        that don't change auth configuration.
        """
        # Only validate for new instances to ensure they are created with valid config
        # Use _state.adding instead of pk is None because UUIDField sets pk before clean()
        if self._state.adding:
            # RUNNER mode requires connection
            # Compare mode value (handle both enum and string)
            mode_value = self.mode.value if isinstance(self.mode, AgentMode) else self.mode
            if mode_value == AgentMode.RUNNER.value:
                if not self.connection:
                    raise ValidationError(
                        {"connection": ["RUNNER mode requires a connection"]}
                    )
            
            # Validate inbound auth method
            if self.inbound_auth_method:
                auth_value = (
                    self.inbound_auth_method.value 
                    if isinstance(self.inbound_auth_method, InboundAuthMethod) 
                    else self.inbound_auth_method
                )
                if auth_value == InboundAuthMethod.BEARER.value:
                    if not self.bearer_secret_ref and not self.inbound_secret_ref:
                        raise ValidationError(
                            {"inbound_secret_ref": [f"{InboundAuthMethod.BEARER.label} authentication requires bearer_secret_ref or inbound_secret_ref"]}
                        )
                elif auth_value == InboundAuthMethod.MTLS.value:
                    if not self.mtls_cert_ref or not self.mtls_key_ref:
                        raise ValidationError(
                            {"inbound_secret_ref": [f"{InboundAuthMethod.MTLS.label} authentication requires mtls_cert_ref and mtls_key_ref"]}
                        )

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided."""
        if not self.slug and self.name:
            from django.utils.text import slugify

            self.slug = slugify(self.name)
        # Skip validation if explicitly requested (for partial updates that don't change auth method)
        if not kwargs.pop("skip_validation", False):
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name}"


class IssuedToken(TimeStamped):
    """
    Model for tracking issued JWT tokens (for revocation and forensics).

    Stores jti (JWT ID) and metadata for tokens issued by AgentxSuite.
    """

    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="issued_tokens",
    )
    jti = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="JWT ID (jti claim) - unique identifier for the token",
    )
    expires_at = models.DateTimeField(
        help_text="Token expiration timestamp (from exp claim)",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when token was revoked (null = active)",
    )
    revoked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_tokens",
        help_text="User who revoked the token",
    )
    scopes = models.JSONField(
        default=list,
        help_text="List of scopes granted to this token",
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata (client_ip, user_agent, etc.)",
    )

    class Meta:
        db_table = "agents_issuedtoken"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["agent", "revoked_at"]),
            models.Index(fields=["jti"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        status = "revoked" if self.revoked_at else "active"
        return f"{self.agent.name}/{self.jti[:8]}... ({status})"

    @property
    def is_revoked(self) -> bool:
        """Check if token is revoked."""
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        from django.utils import timezone

        return timezone.now() > self.expires_at
