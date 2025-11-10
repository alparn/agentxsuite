"""
Tenant models: Organization and Environment.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Organization(TimeStamped):
    """Organization model."""

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "tenants_organization"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Environment(TimeStamped):
    """Environment model."""

    TYPE_CHOICES = [
        ("dev", "Development"),
        ("stage", "Staging"),
        ("prod", "Production"),
    ]

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="environments",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="dev")

    class Meta:
        db_table = "tenants_environment"
        ordering = ["-created_at"]
        unique_together = [["organization", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name}"


class OrganizationMembership(TimeStamped):
    """Model for user-organization membership."""

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tenants_organizationmembership"
        ordering = ["-created_at"]
        unique_together = [["user", "organization"]]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.organization.name} ({self.role})"

