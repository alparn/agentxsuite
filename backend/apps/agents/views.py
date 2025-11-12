"""
Views for agents app.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.agents.models import Agent, AgentMode, IssuedToken
from apps.agents.serializers import (
    AgentSerializer,
    IssuedTokenSerializer,
    TokenGenerateResponseSerializer,
    TokenGenerateSerializer,
)
from apps.agents.services import generate_token_for_agent
from apps.agents.services import revoke_token as revoke_token_service
from apps.connections.services import test_connection


class AgentViewSet(ModelViewSet):
    """ViewSet for Agent."""

    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        # org_id comes from URL path: /orgs/<uuid:org_id>/agents/
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
    
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests (partial updates)."""
        # DRF's partial_update already handles partial=True
        return super().partial_update(request, *args, **kwargs)

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

    @action(detail=True, methods=["get", "post"], url_path="tokens")
    def tokens(self, request, org_id=None, pk=None):
        """
        Handle token operations for the agent.
        
        GET: List all tokens issued for this agent.
        POST: Generate a new JWT token for the agent.
        """
        if request.method == "GET":
            return self._list_tokens(request, org_id, pk)
        else:  # POST
            return self._generate_token(request, org_id, pk)
    
    def _generate_token(self, request, org_id=None, pk=None):
        """
        Generate a new JWT token for the agent.
        
        Requires agent to have a ServiceAccount configured.
        
        Request body (optional):
        {
            "ttl_minutes": 30,
            "scopes": ["mcp:run", "mcp:tools"],
            "metadata": {"description": "Token for Claude Desktop"}
        }
        
        Returns:
            {
                "token": "eyJ...",
                "token_info": {...}
            }
        """
        agent = self.get_object()
        
        if not agent.service_account:
            return Response(
                {
                    "error": "agent_has_no_service_account",
                    "message": "Agent must have a ServiceAccount configured to generate tokens",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        serializer = TokenGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            token_string, issued_token = generate_token_for_agent(
                agent,
                ttl_minutes=serializer.validated_data.get("ttl_minutes"),
                scopes=serializer.validated_data.get("scopes"),
                metadata=serializer.validated_data.get("metadata"),
            )
            
            response_serializer = TokenGenerateResponseSerializer(
                {
                    "token": token_string,
                    "token_info": issued_token,
                }
            )
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {"error": "validation_error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _list_tokens(self, request, org_id=None, pk=None):
        """
        List all tokens issued for this agent.
        
        Returns:
            List of token metadata (without token values)
        """
        agent = self.get_object()
        
        tokens = IssuedToken.objects.filter(agent=agent).order_by("-created_at")
        
        serializer = IssuedTokenSerializer(tokens, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="tokens/(?P<jti>[^/.]+)/revoke")
    def revoke_token(self, request, org_id=None, pk=None, jti=None):
        """
        Revoke a token by jti.
        
        Returns:
            Updated token metadata
        """
        agent = self.get_object()
        
        try:
            token = IssuedToken.objects.get(agent=agent, jti=jti)
        except IssuedToken.DoesNotExist:
            return Response(
                {"error": "token_not_found", "message": f"Token with jti '{jti}' not found for this agent"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        if token.revoked_at:
            return Response(
                {"error": "already_revoked", "message": "Token is already revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            revoked_token = revoke_token_service(jti, revoked_by=request.user if request.user.is_authenticated else None)
            serializer = IssuedTokenSerializer(revoked_token)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {"error": "validation_error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["delete"], url_path="tokens/(?P<jti>[^/.]+)")
    def delete_token(self, request, org_id=None, pk=None, jti=None):
        """
        Delete a token (only if revoked or expired).
        
        For security, active tokens should be revoked first, not deleted.
        """
        agent = self.get_object()
        
        try:
            token = IssuedToken.objects.get(agent=agent, jti=jti)
        except IssuedToken.DoesNotExist:
            return Response(
                {"error": "token_not_found", "message": f"Token with jti '{jti}' not found for this agent"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        if not token.revoked_at and not token.is_expired:
            return Response(
                {
                    "error": "cannot_delete_active_token",
                    "message": "Cannot delete active token. Revoke it first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TokenViewSet(ModelViewSet):
    """ViewSet for Token management (list, revoke, delete)."""

    queryset = IssuedToken.objects.all()
    serializer_class = IssuedTokenSerializer
    lookup_field = "jti"
    lookup_url_kwarg = "jti"
    http_method_names = ["get", "post", "delete", "head", "options"]  # Allow GET for list

    def get_queryset(self):
        """Filter by agent if agent_id is provided."""
        queryset = super().get_queryset()
        # agent_id comes from URL path: /orgs/<uuid:org_id>/agents/<uuid:agent_id>/tokens/
        agent_id = self.kwargs.get("agent_id")
        org_id = self.kwargs.get("org_id")
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)
        if org_id:
            queryset = queryset.filter(agent__organization_id=org_id)
        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        """
        List all tokens for the agent.
        
        Returns:
            List of token metadata (without token values)
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, org_id=None, agent_id=None, jti=None):
        """
        Revoke a token by jti.
        
        Returns:
            Updated token metadata
        """
        token = self.get_object()
        
        if token.revoked_at:
            return Response(
                {"error": "already_revoked", "message": "Token is already revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            revoked_token = revoke_token_service(token.jti, revoked_by=request.user if request.user.is_authenticated else None)
            serializer = IssuedTokenSerializer(revoked_token)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response(
                {"error": "validation_error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def destroy(self, request, *args, **kwargs):
        """
        Delete a token (only if revoked or expired).
        
        For security, active tokens should be revoked first, not deleted.
        """
        token = self.get_object()
        
        if not token.revoked_at and not token.is_expired:
            return Response(
                {
                    "error": "cannot_delete_active_token",
                    "message": "Cannot delete active token. Revoke it first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        return super().destroy(request, *args, **kwargs)

