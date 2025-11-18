"""
Serializers for mcp_ext app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.mcp_ext.models import MCPServerRegistration, Prompt, Resource
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class ResourceSerializer(serializers.ModelSerializer):
    """Serializer for Resource (list/read)."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True, required=False)
    config_json = serializers.JSONField()
    schema_json = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Resource
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "type",
            "config_json",
            "mime_type",
            "schema_json",
            "secret_ref",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        """Add environment_id to representation for filtering."""
        representation = super().to_representation(instance)
        if instance.environment:
            representation["environment_id"] = str(instance.environment.id)
        return representation


class PromptSerializer(serializers.ModelSerializer):
    """Serializer for Prompt (list)."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True, required=False)
    input_schema = serializers.JSONField()
    uses_resources = serializers.JSONField()
    output_hints = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Prompt
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "description",
            "input_schema",
            "template_system",
            "template_user",
            "uses_resources",
            "output_hints",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        """Add environment_id to representation for filtering."""
        representation = super().to_representation(instance)
        if instance.environment:
            representation["environment_id"] = str(instance.environment.id)
        return representation


class MCPServerRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for MCPServerRegistration."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True, required=False)
    args = serializers.JSONField(required=False, allow_null=False)
    env_vars = serializers.JSONField(required=False, allow_null=False)
    tags = serializers.JSONField(required=False, allow_null=False)
    metadata = serializers.JSONField(required=False, allow_null=False)

    class Meta:
        model = MCPServerRegistration
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "slug",
            "description",
            "server_type",
            "endpoint",
            "command",
            "args",
            "env_vars",
            "auth_method",
            "secret_ref",
            "enabled",
            "last_health_check",
            "health_status",
            "health_message",
            "tags",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "last_health_check",
            "health_status",
            "health_message",
        ]

    def to_representation(self, instance):
        """Add environment_id to representation for filtering."""
        representation = super().to_representation(instance)
        if instance.environment:
            representation["environment_id"] = str(instance.environment.id)
        return representation

    def validate(self, attrs):
        """Cross-field validation."""
        server_type = attrs.get("server_type")
        
        # Validate required fields based on server type
        if server_type == MCPServerRegistration.ServerType.STDIO:
            if not attrs.get("command"):
                raise serializers.ValidationError(
                    {"command": "Command is required for stdio servers"}
                )
        elif server_type in [
            MCPServerRegistration.ServerType.HTTP,
            MCPServerRegistration.ServerType.WEBSOCKET,
        ]:
            if not attrs.get("endpoint"):
                raise serializers.ValidationError(
                    {"endpoint": "Endpoint is required for HTTP/WebSocket servers"}
                )

        return attrs

