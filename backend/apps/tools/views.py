"""
Views for tools app.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.connections.models import Connection
from apps.policies.models import Policy
from apps.tools.models import Tool
from apps.tools.serializers import ToolSerializer
from apps.audit.mixins import AuditLoggingMixin

logger = logging.getLogger(__name__)


def _get_mcp_fabric_base_url() -> str:
    """
    Get MCP Fabric base URL from configuration.
    
    Returns:
        MCP Fabric base URL, defaults to http://localhost:8090 if not configured.
    """
    try:
        from mcp_fabric.deps import MCP_FABRIC_BASE_URL
        return MCP_FABRIC_BASE_URL
    except ImportError:
        logger.warning("Could not import MCP_FABRIC_BASE_URL, using default")
        return "http://localhost:8090"


def _get_mcp_fabric_endpoints() -> list[str]:
    """
    Get list of MCP Fabric endpoints for own service detection.
    
    Returns both localhost and 127.0.0.1 variants of the configured MCP Fabric URL.
    """
    try:
        from mcp_fabric.deps import MCP_FABRIC_BASE_URL
        
        endpoints = [MCP_FABRIC_BASE_URL.rstrip("/")]
        
        # Also add 127.0.0.1 variant if URL contains localhost
        if "localhost" in MCP_FABRIC_BASE_URL:
            endpoints.append(MCP_FABRIC_BASE_URL.replace("localhost", "127.0.0.1").rstrip("/"))
        
        return endpoints
    except ImportError:
        # Fallback if mcp_fabric is not available
        logger.warning("Could not import MCP_FABRIC_BASE_URL, using defaults")
        return ["http://localhost:8090", "http://127.0.0.1:8090"]


class ToolViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Tool."""

    queryset = Tool.objects.all()
    serializer_class = ToolSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset

    def perform_create(self, serializer):
        """Set organization from URL parameter and create/find local connection if needed."""
        from apps.connections.models import Connection
        from django.utils import timezone

        org_id = self.kwargs.get("org_id")
        if not org_id:
            return

        validated_data = serializer.validated_data
        environment_id = validated_data.get("environment_id")

        # If no connection_id provided, create or find a local MCP Fabric connection
        if "connection_id" not in validated_data or not validated_data.get("connection_id"):
            if environment_id:
                # Find or create a local connection for MCP Fabric
                mcp_fabric_url = _get_mcp_fabric_base_url()
                connection, _ = Connection.objects.get_or_create(
                    organization_id=org_id,
                    environment_id=environment_id,
                    name="mcp-fabric-local",
                    defaults={
                        "endpoint": mcp_fabric_url,  # MCP Fabric endpoint from ENV
                        "auth_method": "none",
                        "status": "ok",
                    },
                )
                serializer.validated_data["connection_id"] = connection.id

        # Save with organization and set sync_status to synced for manually created tools
        tool = serializer.save(organization_id=org_id)
        
        # If tool was created without connection_id (manually created), mark as synced
        if not self.request.data.get("connection_id"):
            tool.sync_status = "synced"
            tool.synced_at = timezone.now()
            tool.save(update_fields=["sync_status", "synced_at"])

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update."""
        org_id = self.kwargs.get("org_id")
        if org_id:
            serializer.save(organization_id=org_id)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None, org_id=None):  # noqa: ARG002
        """
        Run a tool via Tool Registry (legacy).
        
        DEPRECATED: Use POST /api/v1/runs/execute/ instead.
        This endpoint will be removed in v2.0.
        
        Supports legacy format:
        {
          "input_json": {...},  // or "input"
          "agent_id": "uuid"     // optional
        }
        """
        tool = self.get_object()
        
        # Parse legacy format (backward compatibility)
        input_json = request.data.get("input_json") or request.data.get("input", {})
        agent_id = request.data.get("agent_id")
        
        # Validate input_json is a dict
        if not isinstance(input_json, dict):
            return Response(
                {"error": "input_json must be a dictionary"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Use unified execution service
        from apps.runs.services import ExecutionContext, execute_tool_run
        
        context = ExecutionContext.from_django_request(request)
        
        try:
            result = execute_tool_run(
                organization=tool.organization,
                environment=tool.environment,
                tool_identifier=str(tool.id),
                agent_identifier=agent_id,
                input_data=input_json,
                context=context,
            )
            
            # Return MCP format (for consistency)
            return Response(result, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            # Validation/Security Errors
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception(f"Error running tool {pk}: {e}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

