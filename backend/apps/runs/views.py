"""
Views for runs app.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.runs.models import Run
from apps.runs.serializers import RunListSerializer, RunSerializer, RunStepSerializer
from apps.runs.services import (
    ExecutionContext,
    execute_tool_run,
)
from apps.tenants.models import Environment, Organization

logger = logging.getLogger(__name__)


class RunViewSet(ReadOnlyModelViewSet):
    """ViewSet for Run (read-only)."""

    queryset = Run.objects.all()
    serializer_class = RunSerializer

    def get_serializer_class(self):
        """Use optimized list serializer for list action."""
        if self.action == "list":
            return RunListSerializer
        return RunSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided and optimize queries."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        
        # Optimize queries: select_related for ForeignKeys to avoid N+1 queries
        queryset = queryset.select_related(
            "organization",
            "environment",
            "environment__organization",  # For nested organization in environment
            "agent",
            "agent__organization",
            "agent__environment",
            "agent__environment__organization",
            "agent__connection",
            "agent__connection__organization",
            "agent__connection__environment",
            "agent__connection__environment__organization",
            "tool",
            "tool__organization",
            "tool__environment",
            "tool__environment__organization",
            "tool__connection",
            "tool__connection__organization",
            "tool__connection__environment",
            "tool__connection__environment__organization",
        )
        return queryset

    @action(detail=True, methods=["get"])
    def steps(self, request, pk=None, org_id=None):  # noqa: ARG002
        """Get all steps for a run."""
        run = self.get_object()
        steps = run.steps.all()
        serializer = RunStepSerializer(steps, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def execute(self, request, org_id=None):
        """
        Unified tool execution endpoint.
        
        Request:
        {
          "tool": "uuid-or-name",      // Tool UUID or Name
          "agent": "uuid",              // Optional if Agent-Token is used
          "input": {...},               // Input data
          "environment": "uuid",        // Environment UUID (optional, derived from tool)
          "timeout_seconds": 30         // Optional
        }
        
        Response: MCP-compatible format
        {
          "run_id": "uuid",
          "status": "succeeded",
          "content": [{"type": "text", "text": "..."}],
          "isError": false,
          "agent": {"id": "...", "name": "..."},
          "tool": {"id": "...", "name": "..."},
          "execution": {...}
        }
        """
        # 1. Parse Input
        tool_identifier = request.data.get("tool")
        agent_identifier = request.data.get("agent")
        input_data = request.data.get("input", {})
        timeout = request.data.get("timeout_seconds", 30)
        env_id = request.data.get("environment")
        
        if not tool_identifier:
            return Response(
                {"error": "Field 'tool' is required (UUID or name)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # 2. Get Organization
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # 3. Get Environment (from Request or derive from Tool)
        if not env_id:
            # Try to get from tool
            try:
                from uuid import UUID
                from apps.tools.models import Tool
                
                try:
                    UUID(tool_identifier)
                    tool_temp = Tool.objects.get(id=tool_identifier, organization=organization)
                    env_id = tool_temp.environment_id
                except (ValueError, Tool.DoesNotExist):
                    tool_temp = Tool.objects.filter(
                        name=tool_identifier,
                        organization=organization
                    ).first()
                    if tool_temp:
                        env_id = tool_temp.environment_id
            except Exception as e:
                logger.debug(f"Could not derive environment from tool: {e}")
        
        if not env_id:
            return Response(
                {"error": "Field 'environment' is required (or tool must exist to derive environment)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            environment = Environment.objects.get(id=env_id, organization=organization)
        except Environment.DoesNotExist:
            return Response(
                {"error": "Environment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # 4. Create Execution Context
        context = ExecutionContext.from_django_request(request)
        
        # TODO: If JWT-Auth is used, also extract Token-Claims
        # For now: Only Django Token Auth
        
        # 5. Execute (Service-Layer!)
        try:
            result = execute_tool_run(
                organization=organization,
                environment=environment,
                tool_identifier=tool_identifier,
                agent_identifier=agent_identifier,
                input_data=input_data,
                context=context,
                timeout_seconds=timeout,
            )
            return Response(result, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            # Validation/Security Errors
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception(f"Unexpected error executing tool: {e}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

