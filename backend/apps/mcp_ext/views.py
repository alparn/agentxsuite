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
        
        Query params:
        - env_id: Environment ID (optional, uses default if not provided)
        - token: Agent Token (REQUIRED)
        
        Returns a ready-to-use claude_desktop_config.json structure including:
        1. AgentxSuite itself (with stdio adapter)
        2. All registered external MCP servers
        """
        from apps.tenants.models import Environment
        
        # Get environment
        env_id = request.query_params.get("env_id")
        if env_id:
            environment = Environment.objects.filter(
                id=env_id, organization_id=org_id
            ).first()
            if not environment:
                raise ValidationError(f"Environment {env_id} not found")
        else:
            # Use default environment (production or first available)
            environment = (
                Environment.objects.filter(organization_id=org_id, type="production").first()
                or Environment.objects.filter(organization_id=org_id).first()
            )
            if not environment:
                raise ValidationError("No environment available. Please create one first.")
        
        config = {"mcpServers": {}}
        
        # 1. Add AgentxSuite as primary MCP server (with HTTP bridge)
        # Using HTTP bridge instead of stdio adapter to avoid database/path issues
        token_string = self._get_token_from_request(request)
        
        # Get MCP Fabric Base URL
        from mcp_fabric.deps import MCP_FABRIC_BASE_URL
        mcp_fabric_url = f"{MCP_FABRIC_BASE_URL.rstrip('/')}/.well-known/mcp"
        
        # Get path to mcp-http-bridge.js (relative to project root)
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        bridge_path = project_root / "docs" / "mcp-http-bridge.js"
        
        config["mcpServers"]["agentxsuite"] = {
            "command": "node",
            "args": [
                str(bridge_path),
                mcp_fabric_url,
                "--header",
                f"Authorization: Bearer {token_string}",
            ],
            "env": {
                "DEBUG": "1",
            },
            # Optional: Add comment for user
            "_comment": "AgentxSuite MCP Server (HTTP bridge)",
        }
        
        # 2. Add registered external MCP servers
        queryset = self.get_queryset().filter(
            enabled=True,
            environment=environment
        )
        
        for server in queryset:
            server_config = {}
            
            if server.server_type == MCPServerRegistration.ServerType.STDIO:
                server_config["command"] = server.command
                server_config["args"] = server.args
                
                if server.env_vars:
                    # Resolve secrets from SecretStore
                    server_config["env"] = self._resolve_secrets(
                        server.env_vars, org_id
                    )
            
            elif server.server_type == MCPServerRegistration.ServerType.HTTP:
                # Use the mcp-http-bridge.js for HTTP servers
                from mcp_fabric.settings import MCP_HTTP_BRIDGE_PATH
                
                server_config["command"] = "node"
                server_config["args"] = [
                    MCP_HTTP_BRIDGE_PATH,
                    server.endpoint,
                ]
                
                if server.secret_ref:
                    # Resolve secret from SecretStore
                    token = self._resolve_secret(server.secret_ref, org_id)
                    server_config["args"].extend([
                        "--header",
                        f"Authorization: Bearer {token}",
                    ])
            
            config["mcpServers"][server.slug] = server_config
        
        return Response(config)
    
    def _get_token_from_request(self, request):
        """
        Get token from request query params.
        
        Requires ?token=... parameter.
        Does NOT create new tokens or look up existing ones.
        """
        token = request.query_params.get("token")
        
        if not token:
            raise ValidationError(
                "Token is required. Please provide a valid Agent Token via ?token=..."
            )
            
        return token
    
    def _resolve_secrets(self, env_vars: dict, org_id: str) -> dict:
        """
        Resolve secret references in environment variables.
        
        Transforms "secret://ref" to actual secret value.
        """
        from libs.secretstore import get_secret_store
        import logging
        
        logger = logging.getLogger(__name__)
        secret_store = get_secret_store()
        resolved = {}
        
        for key, value in env_vars.items():
            if isinstance(value, str) and value.startswith("secret://"):
                secret_ref = value.replace("secret://", "")
                try:
                    resolved[key] = secret_store.get_secret(
                        ref=secret_ref,
                        organization_id=org_id
                    )
                except Exception as e:
                    logger.error(f"Failed to resolve secret {secret_ref}: {e}")
                    resolved[key] = f"<ERROR: {secret_ref}>"
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolve_secret(self, secret_ref: str, org_id: str) -> str:
        """Resolve a single secret reference."""
        from libs.secretstore import get_secret_store
        import logging
        
        logger = logging.getLogger(__name__)
        secret_store = get_secret_store()
        
        try:
            return secret_store.get_secret(
                ref=secret_ref,
                organization_id=org_id
            )
        except Exception as e:
            logger.error(f"Failed to resolve secret {secret_ref}: {e}")
            return f"<ERROR: {secret_ref}>"
    
    @action(detail=False, methods=["get"])
    def download_config(self, request, org_id=None):
        """
        Download Claude Desktop configuration as JSON file.
        
        Same as claude_config but returns as downloadable file.
        Query params: Same as claude_config (env_id, token)
        """
        from django.http import HttpResponse
        import json
        
        # Generate config using existing endpoint logic
        config_response = self.claude_config(request, org_id)
        config = config_response.data
        
        # Return as downloadable JSON file
        response = HttpResponse(
            json.dumps(config, indent=2),
            content_type="application/json"
        )
        response["Content-Disposition"] = 'attachment; filename="claude_desktop_config.json"'
        
        return response
