"""
Serializers for tools app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.tools.models import Tool
from apps.tools.validators import validate_schema_json
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class ToolSerializer(serializers.ModelSerializer):
    """Serializer for Tool."""

    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.UUIDField(write_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    schema_json = serializers.JSONField(validators=[validate_schema_json])

    class Meta:
        model = Tool
        fields = [
            "id",
            "organization",
            "organization_id",
            "environment",
            "environment_id",
            "name",
            "version",
            "schema_json",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

