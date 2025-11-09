"""
Serializers for runs app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.agents.serializers import AgentSerializer
from apps.runs.models import Run
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer
from apps.tools.serializers import ToolSerializer


class RunSerializer(serializers.ModelSerializer):
    """Serializer for Run."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    agent = AgentSerializer(read_only=True)
    tool = ToolSerializer(read_only=True)

    class Meta:
        model = Run
        fields = [
            "id",
            "organization",
            "environment",
            "agent",
            "tool",
            "status",
            "started_at",
            "ended_at",
            "input_json",
            "output_json",
            "error_text",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "started_at",
            "ended_at",
            "output_json",
            "error_text",
            "created_at",
            "updated_at",
        ]

    def validate_status(self, value: str) -> str:
        """Validate status."""
        valid_statuses = ["pending", "running", "succeeded", "failed"]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"status must be one of {valid_statuses}")
        return value

