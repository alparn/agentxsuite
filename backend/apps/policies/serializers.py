"""
Serializers for policies app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.policies.models import Policy, PolicyBinding, PolicyRule
from apps.tenants.serializers import OrganizationSerializer


class PolicySerializer(serializers.ModelSerializer):
    """Serializer for Policy."""

    organization = OrganizationSerializer(read_only=True)
    environment_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=True, max_length=120)
    version = serializers.IntegerField(default=1, read_only=True)
    is_active = serializers.BooleanField(default=True)
    enabled = serializers.BooleanField(default=True, read_only=True)  # Legacy, synced with is_active
    rules_json = serializers.JSONField(required=False, default=dict)  # Legacy field
    rules = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        fields = [
            "id",
            "organization",
            "environment_id",
            "name",
            "version",
            "is_active",
            "enabled",
            "description",
            "rules_json",
            "rules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "version", "created_at", "updated_at", "enabled"]

    def validate_rules_json(self, value):
        """Validate rules_json structure (legacy field)."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("rules_json must be a dictionary")
        return value

    def validate(self, attrs):
        """Validate policy name uniqueness within organization."""
        # Sync is_active with enabled for backward compatibility
        if "is_active" in attrs:
            attrs["enabled"] = attrs["is_active"]

        # Check name uniqueness within organization
        name = attrs.get("name")
        if name:
            # Get organization_id from context (set by ViewSet)
            org_id = self.context.get("org_id")
            if not org_id:
                # Try to get from instance if updating
                if self.instance:
                    org_id = str(self.instance.organization.id)
                else:
                    # If creating and no org_id in context, skip validation
                    # (will be caught by perform_create)
                    return attrs

            # Check if policy with same name exists in organization
            queryset = Policy.objects.filter(organization_id=org_id, name=name)
            # Exclude current instance if updating
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError(
                    {"name": f"A policy with the name '{name}' already exists in this organization."}
                )

        return attrs

    def get_rules(self, obj) -> list:
        """Get rules from PolicyRule objects."""
        return [
            {
                "id": rule.id,
                "action": rule.action,
                "target": rule.target,
                "effect": rule.effect,
                "conditions": rule.conditions,
            }
            for rule in obj.rules.all()
        ]

    def get_description(self, obj) -> str:
        """Get description from rules_json or return empty string."""
        if isinstance(obj.rules_json, dict):
            return obj.rules_json.get("description", "")
        return ""


class PolicyRuleSerializer(serializers.ModelSerializer):
    """Serializer for PolicyRule."""

    policy_id = serializers.UUIDField(write_only=True, required=False)
    policy_name = serializers.CharField(source="policy.name", read_only=True)

    class Meta:
        model = PolicyRule
        fields = [
            "id",
            "policy_id",
            "policy_name",
            "action",
            "target",
            "effect",
            "conditions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_action(self, value):
        """Validate action format."""
        valid_actions = ["tool.invoke", "agent.invoke", "resource.read", "resource.write"]
        if value not in valid_actions:
            # Allow custom actions but warn
            pass
        return value

    def validate_effect(self, value):
        """Validate effect."""
        if value not in ["allow", "deny"]:
            raise serializers.ValidationError("effect must be 'allow' or 'deny'")
        return value

    def validate_conditions(self, value):
        """Validate conditions structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("conditions must be a dictionary")
        return value


class PolicyBindingSerializer(serializers.ModelSerializer):
    """Serializer for PolicyBinding."""

    policy_id = serializers.UUIDField(write_only=True)
    policy_name = serializers.CharField(source="policy.name", read_only=True)

    class Meta:
        model = PolicyBinding
        fields = [
            "id",
            "policy_id",
            "policy_name",
            "scope_type",
            "scope_id",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_scope_type(self, value):
        """Validate scope_type."""
        valid_scopes = ["org", "env", "agent", "tool", "role", "user", "resource_ns"]
        if value not in valid_scopes:
            raise serializers.ValidationError(f"scope_type must be one of: {', '.join(valid_scopes)}")
        return value


class PolicyEvaluateSerializer(serializers.Serializer):
    """Serializer for policy evaluation request."""

    action = serializers.CharField(required=True, max_length=64)
    target = serializers.CharField(required=True, max_length=256)
    subject = serializers.CharField(required=False, allow_null=True, max_length=128)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    environment_id = serializers.UUIDField(required=False, allow_null=True)
    agent_id = serializers.UUIDField(required=False, allow_null=True)
    tool_id = serializers.UUIDField(required=False, allow_null=True)
    resource_ns = serializers.CharField(required=False, allow_null=True, max_length=256)
    context = serializers.JSONField(required=False, default=dict)
    explain = serializers.BooleanField(required=False, default=False)
