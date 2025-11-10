"""
Serializers for policies app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.policies.models import Policy
from apps.tenants.serializers import OrganizationSerializer


class PolicySerializer(serializers.ModelSerializer):
    """Serializer for Policy."""

    organization = OrganizationSerializer(read_only=True)
    environment_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=True, max_length=255)
    rules_json = serializers.JSONField(required=False, default=dict)
    rules = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    enabled = serializers.BooleanField(default=True)

    class Meta:
        model = Policy
        fields = [
            "id",
            "organization",
            "environment_id",
            "name",
            "description",
            "rules_json",
            "rules",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_rules_json(self, value):
        """Validate rules_json structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("rules_json must be a dictionary")
        
        # Ensure allow and deny are lists if present
        validated_value = {}
        if "description" in value:
            validated_value["description"] = str(value["description"])
        if "allow" in value:
            if not isinstance(value["allow"], list):
                raise serializers.ValidationError("allow must be a list")
            validated_value["allow"] = [str(item) for item in value["allow"]]
        if "deny" in value:
            if not isinstance(value["deny"], list):
                raise serializers.ValidationError("deny must be a list")
            validated_value["deny"] = [str(item) for item in value["deny"]]
        
        return validated_value if validated_value else {}

    def get_rules(self, obj) -> list:
        """Extract rules from rules_json as a list."""
        if isinstance(obj.rules_json, dict):
            rules = []
            if "allow" in obj.rules_json:
                allow_list = obj.rules_json.get("allow", [])
                if isinstance(allow_list, list):
                    rules.extend([{"type": "allow", "value": item} for item in allow_list])
            if "deny" in obj.rules_json:
                deny_list = obj.rules_json.get("deny", [])
                if isinstance(deny_list, list):
                    rules.extend([{"type": "deny", "value": item} for item in deny_list])
            return rules
        return []

    def get_description(self, obj) -> str:
        """Get description from rules_json or return empty string."""
        if isinstance(obj.rules_json, dict):
            return obj.rules_json.get("description", "")
        return ""

