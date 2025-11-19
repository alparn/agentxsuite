"""
Serializers for agents app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.agents.models import Agent, IssuedToken
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer

User = get_user_model()


class AgentSerializer(serializers.ModelSerializer):
    """Serializer for Agent model."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    connection_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    inbound_auth_method = serializers.ChoiceField(
        choices=["bearer", "mtls", "none"],
        required=False,
        default="none"
    )
    inbound_secret_ref = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    default_budget_cents = serializers.IntegerField(required=False, default=0, min_value=0)
    default_max_depth = serializers.IntegerField(required=False, default=1, min_value=1, max_value=10)
    default_ttl_seconds = serializers.IntegerField(required=False, default=600, min_value=1)

    class Meta:
        model = Agent
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "slug",
            "version",
            "enabled",
            "mode",
            "connection_id",
            "inbound_auth_method",
            "inbound_secret_ref",
            "capabilities",
            "tags",
            "service_account",
            "default_budget_cents",
            "default_max_depth",
            "default_ttl_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def validate_environment_id(self, value):
        """Ensure environment belongs to organization."""
        org_id = self.context.get("org_id")
        if not org_id:
            raise serializers.ValidationError("Organization ID required in context")

        from apps.tenants.models import Environment

        if not Environment.objects.filter(id=value, organization_id=org_id).exists():
                            raise serializers.ValidationError(
                f"Environment does not belong to organization"
            )

        return value


class IssuedTokenSerializer(serializers.ModelSerializer):
    """
    Serializer for IssuedToken model.
    
    Security: Token string is NEVER returned after creation!
    Users must save it immediately when created.
    """

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    issued_to_email = serializers.EmailField(source="issued_to.email", read_only=True)
    status = serializers.CharField(read_only=True)  # Computed property
    is_revoked = serializers.BooleanField(read_only=True)  # Computed property
    is_expired = serializers.BooleanField(read_only=True)  # Computed property

    class Meta:
        model = IssuedToken
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "name",
            "purpose",
            "issued_to",
            "issued_to_email",
            "jti",
            "expires_at",
            "revoked_at",
            "revoked_by",
            "scopes",
            "status",
            "is_revoked",
            "is_expired",
            "last_used_at",
            "use_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "issued_to",
            "jti",
            "revoked_at",
            "revoked_by",
            "last_used_at",
            "use_count",
            "created_at",
            "updated_at",
        ]

    def validate_environment_id(self, value):
        """Ensure environment belongs to organization."""
        org_id = self.context.get("org_id")
        if not org_id:
            raise serializers.ValidationError("Organization ID required in context")

        from apps.tenants.models import Environment

        if not Environment.objects.filter(id=value, organization_id=org_id).exists():
            raise serializers.ValidationError(
                f"Environment does not belong to organization"
            )

        return value


class TokenCreateSerializer(serializers.Serializer):
    """
    Serializer for creating new tokens.
    
    This is separate from IssuedTokenSerializer because:
    1. It has different input fields (expires_in_days instead of expires_at)
    2. It returns the token_string (ONLY on creation!)
    
    Note: All fields are REQUIRED for new tokens, even though the DB fields
    are nullable (for backward compatibility with old tokens).
    """

    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="User-friendly name for this token"
    )
    purpose = serializers.ChoiceField(
        choices=["claude-desktop", "api", "development", "ci-cd"],
        default="api",
        help_text="Purpose of this token"
    )
    environment_id = serializers.UUIDField(
        required=True,
        help_text="Environment this token is valid for"
    )
    expires_in_days = serializers.IntegerField(
        default=90, 
        min_value=1,
        max_value=3650,  # Max 10 years
        help_text="Token lifetime in days"
    )
    scopes = serializers.ListField(
        child=serializers.CharField(),
        default=["mcp:tools"],
        help_text="Permissions granted to this token"
    )

    def validate_name(self, value):
        """Validate name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Token name cannot be empty")
        return value.strip()

    def validate_scopes(self, value):
        """Validate scopes are known."""
        if not value:
            raise serializers.ValidationError("At least one scope is required")
        
        valid_scopes = ["mcp:tools", "mcp:resources", "mcp:prompts"]
        for scope in value:
            if scope not in valid_scopes:
                raise serializers.ValidationError(
                    f"Invalid scope: {scope}. Valid scopes: {', '.join(valid_scopes)}"
                )
        return value
    
    def validate_environment_id(self, value):
        """Ensure environment exists and belongs to organization."""
        org_id = self.context.get("org_id")
        if not org_id:
            raise serializers.ValidationError("Organization context required")
        
        from apps.tenants.models import Environment
        if not Environment.objects.filter(id=value, organization_id=org_id).exists():
            raise serializers.ValidationError(
                "Environment does not exist or does not belong to this organization"
            )
        
        return value


class TokenPurposeInfoSerializer(serializers.Serializer):
    """Serializer for token purpose metadata."""

    value = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    default_expiry_days = serializers.IntegerField()
    recommended_scopes = serializers.ListField(child=serializers.CharField())


class TokenScopeInfoSerializer(serializers.Serializer):
    """Serializer for token scope metadata."""

    value = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
