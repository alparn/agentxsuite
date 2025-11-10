"""
Views for agents app.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.agents.models import Agent, AgentMode
from apps.agents.serializers import AgentSerializer
from apps.connections.services import test_connection


class AgentViewSet(ModelViewSet):
    """ViewSet for Agent."""

    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset

    def perform_create(self, serializer):
        """Set organization from URL parameter."""
        org_id = self.kwargs.get("org_id")
        if org_id:
            serializer.save(organization_id=org_id)

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update."""
        org_id = self.kwargs.get("org_id")
        if org_id:
            serializer.save(organization_id=org_id)

    @action(detail=True, methods=["post"], url_path="ping")
    def ping(self, request, org_id=None, pk=None):
        """
        Ping/Test agent status and connection.
        
        Checks:
        1. Agent enabled status (disabled agents cannot execute tools)
        2. For RUNNER mode: Connection health check
        3. For CALLER mode: Agent configuration status
        
        Returns:
            Response with ping result, agent status, and connection status
        """
        agent = self.get_object()
        
        # Base response data
        response_data = {
            "agent_enabled": agent.enabled,
            "agent_mode": agent.mode,
            "agent_name": agent.name,
        }
        
        # Check if agent is enabled
        if not agent.enabled:
            response_data.update({
                "status": "warning",
                "message": "Agent is disabled - it will not be used for tool execution",
                "connection_status": None,
            })
            
            # Still test connection if RUNNER mode (for informational purposes)
            if agent.mode == AgentMode.RUNNER and agent.connection:
                try:
                    test_connection(agent.connection)
                    agent.connection.refresh_from_db()
                    response_data.update({
                        "connection_status": agent.connection.status,
                        "connection_endpoint": agent.connection.endpoint,
                        "connection_name": agent.connection.name,
                        "note": "Connection is reachable, but agent is disabled",
                    })
                except Exception:
                    response_data.update({
                        "connection_status": "unknown",
                        "connection_endpoint": agent.connection.endpoint if agent.connection else None,
                        "note": "Could not test connection (agent is disabled)",
                    })
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        # Agent is enabled - proceed with normal ping
        if agent.mode == AgentMode.RUNNER:
            if not agent.connection:
                return Response(
                    {
                        **response_data,
                        "status": "error",
                        "message": "Agent has no connection configured",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Test the connection
            try:
                test_connection(agent.connection)
                agent.connection.refresh_from_db()
                return Response(
                    {
                        **response_data,
                        "status": "success",
                        "message": f"Agent is enabled and connection '{agent.connection.name}' is reachable",
                        "connection_status": agent.connection.status,
                        "connection_endpoint": agent.connection.endpoint,
                        "connection_name": agent.connection.name,
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response(
                    {
                        **response_data,
                        "status": "error",
                        "message": f"Connection test failed: {str(e)}",
                        "connection_status": agent.connection.status,
                        "connection_endpoint": agent.connection.endpoint,
                        "connection_name": agent.connection.name,
                    },
                    status=status.HTTP_200_OK,  # 200 OK even if ping fails (to show status)
                )
        
        elif agent.mode == AgentMode.CALLER:
            # CALLER mode agents don't have connections to test
            # Return agent status
            return Response(
                {
                    **response_data,
                    "status": "success",
                    "message": "Agent is enabled and configured for CALLER mode",
                    "inbound_auth_method": agent.inbound_auth_method,
                    "connection_status": None,
                },
                status=status.HTTP_200_OK,
            )
        
        return Response(
            {
                **response_data,
                "status": "error",
                "message": f"Unknown agent mode: {agent.mode}",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

