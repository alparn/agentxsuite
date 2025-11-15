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

    # AxCore-Flag (read-only, basierend auf tags)
    is_axcore = serializers.SerializerMethodField()

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
            "is_axcore",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "is_axcore"]
    
    def get_is_axcore(self, obj) -> bool:
        """Check if agent is an AxCore agent."""
        return "axcore" in (obj.tags or [])

    def update(self, instance, validated_data):
        """
        Override update to handle validation safely.
        
        Validation is skipped only if:
        - Auth method is not being changed AND
        - Secret refs are not being explicitly removed (set to None/empty)
        
        This ensures:
        1. New agents must have valid auth config
        2. Changing auth method requires valid config
        3. Removing secret refs requires changing auth method first
        4. Other fields can be updated without touching auth config
        """
        # Handle environment_id and connection_id explicitly
        environment_id = validated_data.pop("environment_id", None)
        connection_id = validated_data.pop("connection_id", None)
        
        if environment_id is not None:
            instance.environment_id = environment_id
        if connection_id is not None:
            instance.connection_id = connection_id
        
        # Check if auth-related fields are being changed
        auth_method_changed = (
            "inbound_auth_method" in validated_data
            and validated_data.get("inbound_auth_method") != instance.inbound_auth_method
        )
        
        # Check if secret refs are being explicitly removed (set to None or empty string)
        bearer_secret_removed = (
            "bearer_secret_ref" in validated_data
            and validated_data.get("bearer_secret_ref") in (None, "")
            and instance.bearer_secret_ref not in (None, "")
        )
        inbound_secret_removed = (
            "inbound_secret_ref" in validated_data
            and validated_data.get("inbound_secret_ref") in (None, "")
            and instance.inbound_secret_ref not in (None, "")
        )
        
        # Check if mTLS cert/key are being removed
        mtls_cert_removed = (
            "mtls_cert_ref" in validated_data
            and validated_data.get("mtls_cert_ref") in (None, "")
            and instance.mtls_cert_ref not in (None, "")
        )
        mtls_key_removed = (
            "mtls_key_ref" in validated_data
            and validated_data.get("mtls_key_ref") in (None, "")
            and instance.mtls_key_ref not in (None, "")
        )
        
        # Skip validation only if auth config is not being changed
        # This allows updating other fields (name, enabled, etc.) without validation errors
        skip_validation = (
            not auth_method_changed
            and not bearer_secret_removed
            and not inbound_secret_removed
            and not mtls_cert_removed
            and not mtls_key_removed
        )
        
        if skip_validation:
            # Save with skip_validation flag to avoid model-level validation
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save(skip_validation=True)
            return instance
        
        # Otherwise, use default update (which calls full_clean via model.save)
        # The validate() method will catch any auth config issues
        return super().update(instance, validated_data)

    def validate(self, attrs):
        """
        Validate agent configuration.
        
        This validation ensures:
        1. New agents must have valid auth config
        2. Changing auth method requires valid config
        3. Removing secret refs is only allowed if auth method is changed to NONE first
        """
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
                    
                    # If still no secret ref, check if auth method is being changed
                    if not bearer_secret_ref and not inbound_secret_ref:
                        # For new instances, always require secret ref
                        if not instance:
                            raise serializers.ValidationError(
                                {"bearer_secret_ref": "Bearer authentication requires bearer_secret_ref or inbound_secret_ref"}
                            )
                        # For updates, only require if auth method is being changed TO bearer
                        if "inbound_auth_method" in attrs:
                            raise serializers.ValidationError(
                                {"inbound_auth_method": "Bearer authentication requires bearer_secret_ref or inbound_secret_ref"}
                            )
                        # Check if secret refs are being removed
                        if "bearer_secret_ref" in attrs or "inbound_secret_ref" in attrs:
                            raise serializers.ValidationError(
                                {"bearer_secret_ref": "Cannot remove secret refs while auth method is bearer. Change auth method to 'none' first."}
                            )
                            
            elif inbound_auth_method == "mtls":
                mtls_cert_ref = attrs.get("mtls_cert_ref")
                mtls_key_ref = attrs.get("mtls_key_ref")
                
                # Check if cert/key exists in attrs or instance
                if not mtls_cert_ref or not mtls_key_ref:
                    if instance:
                        mtls_cert_ref = instance.mtls_cert_ref if not mtls_cert_ref else mtls_cert_ref
                        mtls_key_ref = instance.mtls_key_ref if not mtls_key_ref else mtls_key_ref
                    
                    # If still missing cert or key, check if auth method is being changed
                    if not mtls_cert_ref or not mtls_key_ref:
                        # For new instances, always require cert and key
                        if not instance:
                            raise serializers.ValidationError(
                                {"mtls_cert_ref": "mTLS authentication requires mtls_cert_ref and mtls_key_ref"}
                            )
                        # For updates, only require if auth method is being changed TO mtls
                        if "inbound_auth_method" in attrs:
                            raise serializers.ValidationError(
                                {"inbound_auth_method": "mTLS authentication requires mtls_cert_ref and mtls_key_ref"}
                            )
                        # Check if cert/key are being removed
                        if "mtls_cert_ref" in attrs or "mtls_key_ref" in attrs:
                            raise serializers.ValidationError(
                                {"mtls_cert_ref": "Cannot remove mTLS cert/key while auth method is mtls. Change auth method to 'none' first."}
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
