"""
Serializers for runs app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.agents.serializers import AgentSerializer
from apps.runs.models import Run, RunStep
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer
from apps.tools.serializers import ToolSerializer


class RunListSerializer(serializers.ModelSerializer):
    """Optimized serializer for Run list views (reduces nesting)."""

    organization_id = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    environment_id = serializers.UUIDField(source="environment.id", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    agent_id = serializers.UUIDField(source="agent.id", read_only=True)
    agent_name = serializers.CharField(source="agent.name", read_only=True)
    tool_id = serializers.UUIDField(source="tool.id", read_only=True)
    tool_name = serializers.CharField(source="tool.name", read_only=True)

    class Meta:
        model = Run
        fields = [
            "id",
            "organization_id",
            "organization_name",
            "environment_id",
            "environment_name",
            "agent_id",
            "agent_name",
            "tool_id",
            "tool_name",
            "status",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization_id",
            "organization_name",
            "environment_id",
            "environment_name",
            "agent_id",
            "agent_name",
            "tool_id",
            "tool_name",
            "status",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]


class RunSerializer(serializers.ModelSerializer):
    """Serializer for Run detail views (full nested objects)."""

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


class RunStepSerializer(serializers.ModelSerializer):
    """Serializer for RunStep."""

    class Meta:
        model = RunStep
        fields = [
            "id",
            "step_type",
            "message",
            "details",
            "timestamp",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "timestamp",
            "created_at",
        ]

