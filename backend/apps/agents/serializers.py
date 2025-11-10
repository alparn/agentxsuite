"""
Serializers for agents app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.agents.models import Agent, AgentMode
from apps.connections.serializers import ConnectionSerializer
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class AgentSerializer(serializers.ModelSerializer):
    """Serializer for Agent."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    connection = ConnectionSerializer(read_only=True)
    connection_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Agent
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "connection",
            "connection_id",
            "name",
            "version",
            "enabled",
            "mode",
            "inbound_auth_method",
            "inbound_secret_ref",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        """Validate cross-field constraints."""
        mode = attrs.get("mode", self.instance.mode if self.instance else AgentMode.RUNNER)
        connection_id = attrs.get("connection_id")
        inbound_auth_method = attrs.get(
            "inbound_auth_method",
            self.instance.inbound_auth_method if self.instance else "bearer",
        )
        inbound_secret_ref = attrs.get(
            "inbound_secret_ref",
            self.instance.inbound_secret_ref if self.instance else None,
        )

        # If connection_id is not provided, use existing connection from instance
        if connection_id is None and self.instance:
            connection_id = self.instance.connection_id if self.instance.connection else None

        if mode == AgentMode.RUNNER:
            if not connection_id:
                raise serializers.ValidationError(
                    {"connection_id": "Connection is required for RUNNER mode agents."}
                )

        if mode == AgentMode.CALLER:
            # Connection is optional for CALLER mode agents
            # (they can use it for outbound tool execution if needed)
            
            if inbound_auth_method != "none" and not inbound_secret_ref:
                raise serializers.ValidationError(
                    {
                        "inbound_secret_ref": (
                            f"Secret reference is required when "
                            f"inbound_auth_method is '{inbound_auth_method}'."
                        )
                    }
                )

        return attrs

