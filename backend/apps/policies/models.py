"""
Policy models for access control.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from libs.common.models import TimeStamped


class Policy(TimeStamped):
    """Policy model for access control."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="policies",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="policies",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    # Legacy field for backward compatibility
    enabled = models.BooleanField(default=True)
    rules_json = models.JSONField(default=dict)

    class Meta:
        db_table = "policies_policy"
        ordering = ["-created_at"]
        unique_together = [["organization", "name"]]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["organization", "environment", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.name}"

    def clean(self) -> None:
        """Validate policy configuration."""
        super().clean()
        # Keep enabled in sync with is_active for backward compatibility
        if hasattr(self, "is_active"):
            self.enabled = self.is_active


class PolicyRule(TimeStamped):
    """Policy rule defining action, target, effect, and conditions."""

    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    action = models.CharField(
        max_length=64,
        help_text='Action type, e.g., "tool.invoke", "agent.invoke", "resource.read", "resource.write"',
    )
    target = models.CharField(
        max_length=256,
        help_text='Target pattern, e.g., "tool:pdf/*", "agent:ocr", "resource:minio://org/env/path/*"',
    )
    effect = models.CharField(
        max_length=8,
        choices=[("allow", "Allow"), ("deny", "Deny")],
        help_text="Effect: allow or deny",
    )
    conditions = models.JSONField(
        default=dict,
        help_text=(
            "Conditions: env==, time_window, tags contains, risk_level<=, "
            "content_type in, max_size_mb<=, allowed_tools, allowed_resource_ns"
        ),
    )

    class Meta:
        db_table = "policies_policyrule"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["policy", "action"]),
            models.Index(fields=["policy", "effect"]),
        ]

    def __str__(self) -> str:
        return f"{self.policy.name}/{self.action}/{self.target} -> {self.effect}"


class PolicyBinding(TimeStamped):
    """Binding of a policy to a scope (org/env/agent/tool/role/user/resource_ns)."""

    SCOPE_TYPES = [
        ("org", "Organization"),
        ("env", "Environment"),
        ("agent", "Agent"),
        ("tool", "Tool"),
        ("role", "Role"),
        ("user", "User"),
        ("resource_ns", "Resource Namespace"),
    ]

    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name="bindings",
    )
    scope_type = models.CharField(
        max_length=24,
        choices=SCOPE_TYPES,
        help_text="Scope type: org, env, agent, tool, role, user, resource_ns",
    )
    scope_id = models.CharField(
        max_length=64,
        help_text="Scope identifier: UUID, slug, or path",
    )
    priority = models.IntegerField(
        default=100,
        help_text="Priority: smaller number = more specific (evaluated first)",
    )

    class Meta:
        db_table = "policies_policybinding"
        ordering = ["priority", "-created_at"]
        indexes = [
            models.Index(fields=["scope_type", "scope_id", "priority"]),
            models.Index(fields=["policy", "scope_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.policy.name} -> {self.scope_type}:{self.scope_id} (priority={self.priority})"

