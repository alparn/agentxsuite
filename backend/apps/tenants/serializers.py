"""
Serializers for tenants app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.tenants.models import Environment, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization."""

    class Meta:
        model = Organization
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class EnvironmentSerializer(serializers.ModelSerializer):
    """Serializer for Environment."""

    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Environment
        fields = ["id", "organization", "name", "type", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_type(self, value: str) -> str:
        """Validate environment type."""
        valid_types = ["dev", "stage", "prod"]
        if value not in valid_types:
            raise serializers.ValidationError(f"type must be one of {valid_types}")
        return value

