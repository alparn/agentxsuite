"""
Serializers for connections app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.connections.models import Connection
from apps.connections.validators import validate_secret_ref_required
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class ConnectionSerializer(serializers.ModelSerializer):
    """Serializer for Connection."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    endpoint = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    args = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    egress_allowlist = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    # Never expose secret_ref in responses
    secret_ref = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # env_ref points to SecretStore material for stdio environment variables.
    env_ref = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Connection
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "transport",
            "endpoint",
            "egress_allowlist",
            "command",
            "args",
            "env_ref",
            "auth_method",
            "secret_ref",
            "status",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "last_seen_at", "created_at", "updated_at"]

    def validate_auth_method(self, value: str) -> str:
        """Validate auth_method."""
        valid_methods = ["none", "bearer", "basic"]
        if value not in valid_methods:
            raise serializers.ValidationError(f"auth_method must be one of {valid_methods}")
        return value

    def validate(self, attrs: dict) -> dict:
        """Validate connection data."""
        transport = attrs.get(
            "transport",
            self.instance.transport if self.instance else Connection.Transport.LEGACY_HTTP,
        )
        endpoint = attrs.get("endpoint", self.instance.endpoint if self.instance else None)
        command = attrs.get("command", self.instance.command if self.instance else "")
        auth_method = attrs.get("auth_method", self.instance.auth_method if self.instance else "none")
        secret_ref = attrs.get("secret_ref", self.instance.secret_ref if self.instance else None)
        errors = {}

        if transport == Connection.Transport.STDIO:
            if not command:
                errors["command"] = "command is required for stdio connections."
        elif not endpoint:
            errors["endpoint"] = "endpoint is required for HTTP-based connections."

        try:
            validate_secret_ref_required(auth_method, secret_ref)
        except serializers.ValidationError as exc:
            errors.update(exc.detail)

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

