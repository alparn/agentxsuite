"""
Serializers for canvas app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.canvas.models import CanvasState
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class CanvasStateSerializer(serializers.ModelSerializer):
    """Serializer for CanvasState."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True, allow_null=True)
    environment_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = CanvasState
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "state_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_state_json(self, value):
        """Validate canvas state structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("state_json must be a dictionary")
        
        # Basic validation
        required_keys = ["nodes", "edges"]
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"state_json must contain '{key}' key")
            if not isinstance(value[key], list):
                raise serializers.ValidationError(f"state_json.{key} must be a list")
        
        return value

