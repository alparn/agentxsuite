"""
User model for authentication.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from libs.common.models import TimeStamped


class UserManager(BaseUserManager):
    """Custom user manager where email is the unique identifier."""

    def create_user(self, email: str, password: str | None = None, **extra_fields):  # noqa: ANN001, ANN003
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):  # noqa: ANN001, ANN003
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model with email as username."""

    username = None  # Remove username field
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email is already required as USERNAME_FIELD

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"


class ServiceAccount(TimeStamped):
    """
    Service Account model for MCP authentication.

    Service Accounts represent non-human identities (agents, services) that
    authenticate via OIDC/OAuth2 tokens with specific audience, issuer, and scope constraints.
    """

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.PROTECT,
        related_name="service_accounts",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.PROTECT,
        related_name="service_accounts",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, help_text="Human-readable name for the service account")
    subject = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Subject identifier, e.g., "agent:ingest@org/env"',
    )
    credential_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Path in SecretStore for credentials",
    )
    audience = models.CharField(
        max_length=255,
        help_text="Canonical MCP URI for audience validation",
    )
    issuer = models.CharField(
        max_length=255,
        help_text="Expected issuer (iss) claim in tokens",
    )
    scope_allowlist = models.JSONField(
        default=list,
        help_text="List of allowed scopes. Empty list means all scopes are allowed.",
    )
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Expiration timestamp")
    rotated_at = models.DateTimeField(null=True, blank=True, help_text="Last credential rotation timestamp")
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "accounts_serviceaccount"
        ordering = ["-created_at"]
        unique_together = [
            ["organization", "name"],  # Name unique per org
            ["subject", "issuer"],  # P0: (subject, issuer) is source of truth
        ]
        indexes = [
            models.Index(fields=["organization", "environment", "enabled"]),
            models.Index(fields=["audience", "issuer"]),
            models.Index(fields=["subject", "issuer"]),  # Composite index for lookup
            models.Index(fields=["subject"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name} ({self.subject})"
