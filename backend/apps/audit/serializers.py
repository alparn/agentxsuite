"""
Serializers for audit app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    """Serializer for AuditEvent."""

    actor = serializers.SerializerMethodField()
    action_field = serializers.CharField(source="action", read_only=True)
    object_type = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    ts = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "ts",
            "created_at",
            "updated_at",
            "subject",
            "action",
            "action_field",
            "target",
            "decision",
            "rule_id",
            "context",
            "actor",
            "object_type",
            "details",
            "event_type",
            "event_data",
            "organization",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "ts"]

    def get_actor(self, obj) -> str:
        """Extract actor from event_data if available."""
        if isinstance(obj.event_data, dict):
            return obj.event_data.get("actor", obj.event_data.get("user_id", "-"))
        return "-"

    def get_object_type(self, obj) -> str:
        """Extract object type from event_data if available."""
        if isinstance(obj.event_data, dict):
            # Try to infer object type from event_data keys
            if "run_id" in obj.event_data:
                return "Run"
            elif "agent_id" in obj.event_data:
                return "Agent"
            elif "tool_id" in obj.event_data:
                return "Tool"
            elif "connection_id" in obj.event_data:
                return "Connection"
            elif "policy_id" in obj.event_data:
                return "Policy"
            return obj.event_data.get("object_type", "-")
        return "-"

    def get_details(self, obj) -> str:
        """Format event_data as readable string."""
        if isinstance(obj.event_data, dict):
            # Return a summary of the event data
            details = []
            for key, value in obj.event_data.items():
                if key not in ["actor", "user_id", "object_type"]:
                    details.append(f"{key}: {value}")
            return ", ".join(details) if details else "-"
        return str(obj.event_data) if obj.event_data else "-"

