"""
Tenant models: Organization and Environment.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """Organization model."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tenants_organization"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Environment(models.Model):
    """Environment model."""

    TYPE_CHOICES = [
        ("dev", "Development"),
        ("stage", "Staging"),
        ("prod", "Production"),
    ]

    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="environments",
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="dev")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tenants_environment"
        ordering = ["-created_at"]
        unique_together = [["organization", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name}"

