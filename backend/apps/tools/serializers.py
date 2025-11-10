"""
Serializers for tools app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.connections.serializers import ConnectionSerializer
from apps.tools.models import Tool
from apps.tools.validators import validate_schema_json
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class ToolSerializer(serializers.ModelSerializer):
    """Serializer for Tool."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    connection = ConnectionSerializer(read_only=True)
    connection_id = serializers.UUIDField(write_only=True, required=False)
    schema_json = serializers.JSONField(validators=[validate_schema_json])

    class Meta:
        model = Tool
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "connection",
            "connection_id",
            "name",
            "version",
            "schema_json",
            "enabled",
            "sync_status",
            "synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "connection",
            "sync_status",
            "synced_at",
            "created_at",
            "updated_at",
        ]

