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
    rules_json = serializers.JSONField()
    rules = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        fields = [
            "id",
            "organization",
            "name",
            "description",
            "rules_json",
            "rules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

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

