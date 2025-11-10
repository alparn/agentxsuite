"""
Serializers for mcp_ext app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.mcp_ext.models import Prompt, Resource
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

