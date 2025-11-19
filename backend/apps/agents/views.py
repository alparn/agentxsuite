"""
Views for agents app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from apps.agents.models import Agent, IssuedToken
from apps.agents.serializers import AgentSerializer, IssuedTokenSerializer
from apps.agents.services import generate_token_for_agent, revoke_token as revoke_token_service
from apps.tenants.models import Environment
from apps.audit.mixins import AuditLoggingMixin


class AgentViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
    """ViewSet for Agent model."""

    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

    def get_queryset(self):
        """Filter by organization."""
        org_id = self.kwargs.get("org_id")
        return (
            Agent.objects.filter(organization_id=org_id)
            .select_related("organization", "environment")
            .order_by("-created_at")
        )
    
    def get_serializer_context(self):
        """Add org_id to serializer context."""
        context = super().get_serializer_context()
        context["org_id"] = self.kwargs.get("org_id")
        return context
    
    def perform_create(self, serializer):
        """Set organization from URL parameter and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if not environment_id:
            raise ValidationError("environment_id is required")
        
        if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
            raise ValidationError(
                f"Environment {environment_id} does not belong to organization {org_id}"
            )
        
        # Validate connection_id if provided (for RUNNER mode)
        connection_id = serializer.validated_data.get("connection_id")
        if connection_id:
            from apps.connections.models import Connection
            if not Connection.objects.filter(
                id=connection_id,
                organization_id=org_id,
                environment_id=environment_id
            ).exists():
                raise ValidationError(
                    f"Connection {connection_id} does not belong to organization {org_id} and environment {environment_id}"
                )

        serializer.save(organization_id=org_id, environment_id=environment_id)
    
    @action(detail=True, methods=["get", "post"], url_path="tokens")
    def tokens(self, request, org_id=None, pk=None):
        """
        List or generate tokens for an agent.
        
        GET /orgs/{org_id}/agents/{agent_id}/tokens/ - List all tokens
        POST /orgs/{org_id}/agents/{agent_id}/tokens/ - Generate new token
        """
        agent = self.get_object()
        
        if request.method == "GET":
            # List tokens
            tokens = IssuedToken.objects.filter(agent=agent).order_by("-created_at")
            serializer = IssuedTokenSerializer(tokens, many=True)
            return Response(serializer.data)
        
        elif request.method == "POST":
            # Generate token
            if not agent.service_account:
                raise ValidationError("Agent must have a ServiceAccount to generate tokens")
            
            if not request.user.is_authenticated:
                raise ValidationError("Authentication required to generate tokens")
            
            # Parse request data
            ttl_minutes = request.data.get("ttl_minutes")
            scopes = request.data.get("scopes")
            metadata = request.data.get("metadata")
            name = request.data.get("name")
            purpose = request.data.get("purpose", "api")
            
            try:
                token_string, issued_token = generate_token_for_agent(
                    agent,
                    user=request.user,
                    name=name,
                    purpose=purpose,
                    ttl_minutes=ttl_minutes,
                    scopes=scopes,
                    metadata=metadata,
                )
                
                token_serializer = IssuedTokenSerializer(issued_token)
                
                return Response(
                    {
                        "token": token_string,
                        "token_info": token_serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            except ValueError as e:
                raise ValidationError(str(e))
    
    @action(detail=True, methods=["post"], url_path="tokens/(?P<jti>[^/.]+)/revoke")
    def revoke_token(self, request, org_id=None, pk=None, jti=None):
        """
        Revoke a token by JTI.
        
        POST /orgs/{org_id}/agents/{agent_id}/tokens/{jti}/revoke/
        """
        agent = self.get_object()
        
        try:
            token = IssuedToken.objects.get(jti=jti, agent=agent)
        except IssuedToken.DoesNotExist:
            raise ValidationError(f"Token with jti '{jti}' not found for this agent")
        
        if token.is_revoked:
            return Response(
                {"error": "Token is already revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        revoked_token = revoke_token_service(jti, revoked_by=request.user if request.user.is_authenticated else None)
        serializer = IssuedTokenSerializer(revoked_token)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=["delete"], url_path="tokens/(?P<jti>[^/.]+)")
    def delete_token(self, request, org_id=None, pk=None, jti=None):
        """
        Delete a token by JTI (hard delete).
        
        DELETE /orgs/{org_id}/agents/{agent_id}/tokens/{jti}/
        """
        agent = self.get_object()
        
        try:
            token = IssuedToken.objects.get(jti=jti, agent=agent)
        except IssuedToken.DoesNotExist:
            raise ValidationError(f"Token with jti '{jti}' not found for this agent")
        
        token.delete()
        
        return Response(
            {"message": f"Token '{jti}' deleted"},
            status=status.HTTP_204_NO_CONTENT,
        )
