"""
Serializers for agents app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.agents.models import Agent
from apps.connections.serializers import ConnectionSerializer
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class AgentSerializer(serializers.ModelSerializer):
    """Serializer for Agent."""

    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.IntegerField(write_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.IntegerField(write_only=True)
    connection = ConnectionSerializer(read_only=True)
    connection_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Agent
        fields = [
            "id",
            "organization",
            "organization_id",
            "environment",
            "environment_id",
            "connection",
            "connection_id",
            "name",
            "version",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

