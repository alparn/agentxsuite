"""
Serializers for tools app.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.connections.serializers import ConnectionSerializer
from apps.tools.models import Tool
from apps.tools.validators import validate_schema_json
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer


class ToolSerializer(serializers.ModelSerializer):
    """Serializer for Tool."""

    organization = OrganizationSerializer(read_only=True)
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.UUIDField(write_only=True)
    connection = ConnectionSerializer(read_only=True)
    connection_id = serializers.UUIDField(write_only=True, required=False)
    schema_json = serializers.JSONField(validators=[validate_schema_json])

    class Meta:
        model = Tool
        fields = [
            "id",
            "organization",
            "environment",
            "environment_id",
            "connection",
            "connection_id",
            "name",
            "version",
            "schema_json",
            "enabled",
            "sync_status",
            "synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "connection",
            "sync_status",
            "synced_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """
        Validate that name/version combination is unique within organization/environment.
        
        Note: organization_id is set by perform_create/perform_update from URL parameter,
        so we use instance.organization_id for validation.
        """
        # Get organization and environment from instance (set by ViewSet) or validated data
        organization_id = None
        environment_id = None
        
        if self.instance:
            # Update: use existing org/env (organization is set by ViewSet, not in attrs)
            organization_id = self.instance.organization_id
            environment_id = attrs.get("environment_id") or self.instance.environment_id
        else:
            # Create: environment_id must be provided
            environment_id = attrs.get("environment_id")
            if not environment_id:
                raise serializers.ValidationError({"environment_id": "environment_id is required"})
            # organization_id will be set by perform_create from URL parameter
        
        # Get name and version from validated data or instance
        name = attrs.get("name")
        version = attrs.get("version", "1.0.0")
        
        if self.instance:
            # Update: use new values or keep existing
            name = name if name is not None else self.instance.name
            version = version if version is not None else self.instance.version
        
        if not name:
            raise serializers.ValidationError({"name": "name is required"})
        
        # For create: organization_id will be set by ViewSet, so we can't validate uniqueness here
        # The database constraint will catch duplicates
        # For update: validate uniqueness excluding current instance
        if self.instance and organization_id:
            queryset = Tool.objects.filter(
                organization_id=organization_id,
                environment_id=environment_id,
                name=name,
                version=version,
            ).exclude(id=self.instance.id)
            
            if queryset.exists():
                raise serializers.ValidationError(
                    {
                        "name": f"A tool with name '{name}' and version '{version}' already exists "
                        f"in this organization/environment."
                    }
                )
        
        return attrs

