"""
Views for mcp_ext app.
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.mcp_ext.models import MCPServerRegistration, Prompt, Resource
from apps.mcp_ext.serializers import (
    MCPServerRegistrationSerializer,
    PromptSerializer,
    ResourceSerializer,
)
from apps.tenants.models import Environment
from apps.audit.mixins import AuditLoggingMixin


class ResourceViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Resource."""

    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """Set organization from URL parameter and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )
        else:
            raise ValidationError("environment_id is required")

        serializer.save(organization_id=org_id)

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        serializer.save(organization_id=org_id)


class PromptViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Prompt."""

    queryset = Prompt.objects.all()
    serializer_class = PromptSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """Set organization from URL parameter and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )
        else:
            raise ValidationError("environment_id is required")

        serializer.save(organization_id=org_id)

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        serializer.save(organization_id=org_id)


class MCPServerRegistrationViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for MCPServerRegistration."""

    queryset = MCPServerRegistration.objects.all()
    serializer_class = MCPServerRegistrationSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """Set organization from URL parameter and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )
        else:
            raise ValidationError("environment_id is required")

        serializer.save(organization_id=org_id)

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        serializer.save(organization_id=org_id)

    @action(detail=True, methods=["post"])
    def health_check(self, request, org_id=None, pk=None):
        """
        Perform health check on a specific MCP server.
        
        This will update the health_status, health_message, and last_health_check fields.
        """
        server = self.get_object()
        
        # TODO: Implement actual health check logic based on server_type
        # For now, just mark as pending implementation
        return Response(
            {
                "id": str(server.id),
                "slug": server.slug,
                "health_status": server.health_status,
                "health_message": "Health check not yet implemented",
                "last_health_check": server.last_health_check,
            }
        )

    @action(detail=False, methods=["get"])
    def claude_config(self, request, org_id=None):
        """
        Generate Claude Desktop configuration for all enabled MCP servers.
        
        Returns a ready-to-use claude_desktop_config.json structure.
        """
        queryset = self.get_queryset().filter(enabled=True)
        
        config = {"mcpServers": {}}
        
        for server in queryset:
            server_config = {}
            
            if server.server_type == MCPServerRegistration.ServerType.STDIO:
                server_config["command"] = server.command
                server_config["args"] = server.args
                
                if server.env_vars:
                    # TODO: Resolve secrets from SecretStore
                    server_config["env"] = server.env_vars
            
            elif server.server_type == MCPServerRegistration.ServerType.HTTP:
                # Use the mcp-http-bridge.js
                # TODO: Make bridge path configurable
                server_config["command"] = "node"
                server_config["args"] = [
                    "/path/to/mcp-http-bridge.js",
                    server.endpoint,
                ]
                
                if server.secret_ref:
                    # TODO: Resolve secret from SecretStore
                    server_config["args"].extend([
                        "--header",
                        f"Authorization: Bearer <{server.secret_ref}>",
                    ])
            
            config["mcpServers"][server.slug] = server_config
        
        return Response(config)

