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
    organization_id = serializers.UUIDField(write_only=True)
    rules_json = serializers.JSONField()

    class Meta:
        model = Policy
        fields = [
            "id",
            "organization",
            "organization_id",
            "name",
            "rules_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

