"""
Views for tools app.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.agents.models import Agent
from apps.connections.models import Connection
from apps.policies.models import Policy
from apps.policies.services import is_allowed
from apps.runs.services import start_run
from apps.runs.serializers import RunSerializer
from apps.tools.models import Tool
from apps.tools.schemas import ToolRunInputSchema
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
        Run a tool via Tool Registry.
        
        Note: Tools that are meant for MCP Fabric (connection points to MCP Fabric)
        should be executed via MCP Fabric API, not via this endpoint.
        """
        try:
            tool = self.get_object()
            
            # Check if tool's connection points to our own MCP Fabric service
            # If so, redirect user to use MCP Fabric API instead
            if tool.connection:
                connection_endpoint = tool.connection.endpoint.rstrip("/")
                mcp_fabric_endpoints = _get_mcp_fabric_endpoints()
                
                # Check if this is our own MCP Fabric service
                is_mcp_fabric_tool = any(
                    connection_endpoint.startswith(endpoint) 
                    for endpoint in mcp_fabric_endpoints
                )
                
                if is_mcp_fabric_tool:
                    # Tool is meant for MCP Fabric, not Tool Registry
                    return Response(
                        {
                            "error": "This tool must be executed via MCP Fabric API",
                            "mcp_fabric_endpoint": "/.well-known/mcp/run",
                            "tool_name": tool.name,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Parse input - handle both formats
            input_json = {}
            try:
                # Try Pydantic schema first
                if isinstance(request.data, dict):
                    input_schema = ToolRunInputSchema(**request.data)
                    input_json = input_schema.input_json or {}
                else:
                    return Response(
                        {"error": "Request data must be a dictionary"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                # If Pydantic validation fails, try to extract input_json directly
                if isinstance(request.data, dict):
                    if "input_json" in request.data:
                        input_json = request.data.get("input_json", {})
                    else:
                        # Use request.data as input_json (for backward compatibility)
                        input_json = request.data
                else:
                    return Response(
                        {"error": f"Invalid input format: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            
            # Validate that input_json is a dict
            if not isinstance(input_json, dict):
                return Response(
                    {"error": "input_json must be a dictionary"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get agent_id from request if provided
            agent_id = None
            try:
                if isinstance(request.data, dict):
                    input_schema = ToolRunInputSchema(**request.data)
                    agent_id = input_schema.agent_id
            except Exception:
                # If schema parsing fails, try direct access
                if isinstance(request.data, dict) and "agent_id" in request.data:
                    agent_id = request.data.get("agent_id")

            # Get agent - use provided agent_id or fall back to first enabled agent
            if agent_id:
                try:
                    agent = Agent.objects.get(
                        id=agent_id,
                        organization=tool.organization,
                        environment=tool.environment,
                        enabled=True,
                    )
                except Agent.DoesNotExist:
                    return Response(
                        {"error": f"Agent {agent_id} not found or not enabled for this tool's organization/environment"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Fall back to first enabled agent (backward compatibility)
                agent = Agent.objects.filter(
                    organization=tool.organization,
                    environment=tool.environment,
                    enabled=True,
                ).first()

            if not agent:
                return Response(
                    {"error": "No enabled agent found for this tool's organization/environment. Please specify agent_id."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Check policy using the correct signature: is_allowed(agent, tool, payload)
            allowed, reason = is_allowed(agent, tool, input_json)
            if not allowed:
                return Response(
                    {"error": reason},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Start run
            run = start_run(agent=agent, tool=tool, input_json=input_json)
            serializer = RunSerializer(run)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            # Handle validation errors from start_run
            logger.warning(f"Validation error running tool {pk}: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Catch any unexpected errors and return JSON response
            logger.exception(f"Error running tool {pk}: {e}")
            return Response(
                {"error": f"Failed to run tool: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

