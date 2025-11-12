"""
Serializers for agents app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.agents.models import Agent, IssuedToken
from apps.connections.serializers import ConnectionSerializer
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class AgentSerializer(serializers.ModelSerializer):
    """Serializer for Agent."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True, required=False)
    connection = ConnectionSerializer(read_only=True)
    connection_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "slug",
            "version",
            "enabled",
            "mode",
            "capabilities",
            "tags",
            "organization",
            "environment",
            "environment_id",
            "connection",
            "connection_id",
            "service_account",
            "default_max_depth",
            "default_budget_cents",
            "default_ttl_seconds",
            "inbound_auth_method",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        """Override update to skip validation for partial updates that don't change auth method."""
        # Handle environment_id and connection_id explicitly
        environment_id = validated_data.pop("environment_id", None)
        connection_id = validated_data.pop("connection_id", None)
        
        if environment_id is not None:
            instance.environment_id = environment_id
        if connection_id is not None:
            instance.connection_id = connection_id
        
        # If this is a partial update and inbound_auth_method is not being changed,
        # skip the model's full_clean() to avoid validation errors
        if self.partial and "inbound_auth_method" not in validated_data:
            # Save with skip_validation flag
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save(skip_validation=True)
            return instance
        # Otherwise, use default update (which calls full_clean)
        return super().update(instance, validated_data)

    def validate(self, attrs):
        """Validate agent configuration for partial updates."""
        instance = self.instance
        
        # Get current inbound_auth_method (from attrs if being changed, otherwise from instance)
        inbound_auth_method = attrs.get("inbound_auth_method")
        if not inbound_auth_method and instance:
            inbound_auth_method = instance.inbound_auth_method
        
        # Only validate if inbound_auth_method is set and not "none"
        if inbound_auth_method and inbound_auth_method != "none":
            if inbound_auth_method == "bearer":
                bearer_secret_ref = attrs.get("bearer_secret_ref")
                inbound_secret_ref = attrs.get("inbound_secret_ref")
                # Check if secret_ref exists in attrs or instance
                if not bearer_secret_ref and not inbound_secret_ref:
                    if instance:
                        bearer_secret_ref = instance.bearer_secret_ref
                        inbound_secret_ref = instance.inbound_secret_ref
                    if not bearer_secret_ref and not inbound_secret_ref:
                        # Only raise error if inbound_auth_method is being changed
                        if "inbound_auth_method" in attrs:
                            raise serializers.ValidationError(
                                {"inbound_auth_method": "Bearer authentication requires bearer_secret_ref or inbound_secret_ref"}
                            )
                        # For partial updates that don't change inbound_auth_method, skip validation
            elif inbound_auth_method == "mtls":
                mtls_cert_ref = attrs.get("mtls_cert_ref")
                mtls_key_ref = attrs.get("mtls_key_ref")
                # Check if cert/key exists in attrs or instance
                if not mtls_cert_ref or not mtls_key_ref:
                    if instance:
                        mtls_cert_ref = instance.mtls_cert_ref
                        mtls_key_ref = instance.mtls_key_ref
                    if not mtls_cert_ref or not mtls_key_ref:
                        # Only raise error if inbound_auth_method is being changed
                        if "inbound_auth_method" in attrs:
                            raise serializers.ValidationError(
                                {"inbound_auth_method": "mTLS authentication requires mtls_cert_ref and mtls_key_ref"}
                            )
        
        return attrs


class IssuedTokenSerializer(serializers.ModelSerializer):
    """Serializer for IssuedToken (read-only, no token value)."""

    agent_name = serializers.CharField(source="agent.name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)

    class Meta:
        model = IssuedToken
        fields = [
            "id",
            "jti",
            "agent",
            "agent_name",
            "expires_at",
            "revoked_at",
            "revoked_by",
            "scopes",
            "metadata",
            "created_at",
            "is_expired",
            "is_revoked",
        ]
        read_only_fields = [
            "id",
            "jti",
            "agent",
            "expires_at",
            "revoked_at",
            "revoked_by",
            "scopes",
            "metadata",
            "created_at",
        ]


class TokenGenerateSerializer(serializers.Serializer):
    """Serializer for token generation request."""

    ttl_minutes = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1440,  # Max 24 hours
        help_text="Token TTL in minutes (default: 30)",
    )
    scopes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of scopes to grant (default: ['mcp:run', 'mcp:tools', 'mcp:manifest'])",
    )
    metadata = serializers.DictField(
        required=False,
        help_text="Additional metadata (e.g., {'description': 'Token for Claude Desktop'})",
    )


class TokenGenerateResponseSerializer(serializers.Serializer):
    """Serializer for token generation response."""

    token = serializers.CharField(help_text="JWT token string (only shown once)")
    token_info = IssuedTokenSerializer(help_text="Token metadata")
