"""
Views for agents app.
"""
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.shortcuts import get_object_or_404

from apps.agents.models import Agent, IssuedToken
from apps.agents.serializers import (
    AgentSerializer,
    IssuedTokenSerializer,
    TokenCreateSerializer,
    TokenPurposeInfoSerializer,
    TokenScopeInfoSerializer,
)
from apps.tenants.models import Environment
from apps.audit.mixins import AuditLoggingMixin


class IssuedTokenViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing user tokens.
    
    Endpoints:
    - POST   /api/orgs/{org_id}/tokens/              - Create new token
    - GET    /api/orgs/{org_id}/tokens/              - List tokens
    - GET    /api/orgs/{org_id}/tokens/{id}/         - Get token details
    - DELETE /api/orgs/{org_id}/tokens/{id}/         - Hard delete token
    - POST   /api/orgs/{org_id}/tokens/{id}/revoke/  - Revoke token (soft delete)
    - GET    /api/orgs/{org_id}/tokens/purposes/     - Get purpose metadata
    - GET    /api/orgs/{org_id}/tokens/scopes/       - Get scope metadata
    """

    queryset = IssuedToken.objects.all()
    serializer_class = IssuedTokenSerializer

    def get_queryset(self):
        """Filter by organization and show only active tokens by default."""
        org_id = self.kwargs.get("org_id")
        queryset = IssuedToken.objects.filter(organization_id=org_id)

        # Filter by status if requested
        show_revoked = self.request.query_params.get("show_revoked") == "true"
        if not show_revoked:
            queryset = queryset.filter(revoked_at__isnull=True)

        return queryset.select_related(
            "organization", "environment", "issued_to", "revoked_by"
        ).order_by("-created_at")

    def get_serializer_context(self):
        """Add org_id to serializer context."""
        context = super().get_serializer_context()
        context["org_id"] = self.kwargs.get("org_id")
        return context

    def create(self, request, org_id=None):
        """
        Create a new token.
        
        ⚠️ Token string is returned ONLY ONCE on creation!
        Users must save it immediately.
        
        Request body:
        {
            "name": "My Claude Desktop Token",
            "purpose": "claude-desktop",
            "environment_id": "uuid",
            "expires_in_days": 365,
            "scopes": ["mcp:tools", "mcp:resources"]
        }
        
        Response:
        {
            "id": "uuid",
            "name": "My Claude Desktop Token",
            "token": "eyJhbGc...",  # ⚠️ ONLY shown once!
            "expires_at": "2025-11-18T...",
            "warning": "⚠️ Save this token now! It will not be shown again."
        }
        """
        # Validate input with org_id context
        serializer = TokenCreateSerializer(
            data=request.data,
            context={"org_id": org_id, "request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Get environment
        environment = get_object_or_404(
            Environment, id=data["environment_id"], organization_id=org_id
        )

        # Generate token
        from apps.agents.services import generate_mcp_token
        import uuid

        jti = str(uuid.uuid4())
        expires_at = timezone.now() + timedelta(days=data["expires_in_days"])

        token_claims = {
            "org_id": str(org_id),  # ✅ Convert UUID to string!
            "env_id": str(environment.id),
            "sub": f"user:{request.user.id}",
            "iss": "agentxsuite",
            "jti": jti,
            "scope": data["scopes"],
            "purpose": data["purpose"],
        }

        token_string = generate_mcp_token(
            claims=token_claims,
            expires_in=timedelta(days=data["expires_in_days"]),
        )

        # Store token metadata (NOT the token itself!)
        # Note: All required fields MUST be set for new tokens
        issued_token = IssuedToken.objects.create(
            organization_id=org_id,  # REQUIRED
            environment=environment,  # REQUIRED
            name=data["name"],  # REQUIRED
            purpose=data["purpose"],  # REQUIRED
            issued_to=request.user,  # REQUIRED
            jti=jti,
            expires_at=expires_at,
            scopes=data["scopes"],
            metadata={
                "created_via": "api",
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )

        # Return token ONLY on creation
        return Response(
            {
                "id": str(issued_token.id),
                "token_id": str(issued_token.id),  # For frontend compatibility
                "jti": jti,  # JWT ID
                "name": data["name"],
                "purpose": data["purpose"],
                "token": token_string,  # ⚠️ Only shown once!
                "expires_at": expires_at.isoformat(),
                "scopes": data["scopes"],
                "environment": {
                    "id": str(environment.id),
                    "name": environment.name,
                },
                "created_at": issued_token.created_at.isoformat(),
                "warning": "⚠️ Save this token now! It will not be shown again.",
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, org_id=None, pk=None):
        """
        Hard delete a token.
        
        ⚠️ This permanently deletes the token from the database.
        Use the 'revoke' action for soft delete instead.
        """
        token = self.get_object()

        # Only owner or admin can delete
        if token.issued_to != request.user and not request.user.is_staff:
            raise ValidationError("You can only delete your own tokens")

        token_name = token.name
        token.delete()

        return Response(
            {"message": f"Token '{token_name}' permanently deleted"},
            status=status.HTTP_204_NO_CONTENT,
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request, org_id=None, pk=None):
        """
        Revoke a token (soft delete).
        
        This marks the token as revoked without deleting it from the database.
        Revoked tokens cannot be used but remain visible in the audit log.
        
        This is the recommended way to disable tokens.
        """
        token = self.get_object()

        # Check if already revoked
        if token.is_revoked:
            return Response(
                {"error": "Token is already revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only owner or admin can revoke
        if token.issued_to != request.user and not request.user.is_staff:
            raise ValidationError("You can only revoke your own tokens")

        # Revoke token
        token.revoked_at = timezone.now()
        token.revoked_by = request.user
        token.save(update_fields=["revoked_at", "revoked_by", "updated_at"])

        return Response(
            {
                "message": f"Token '{token.name}' revoked successfully",
                "revoked_at": token.revoked_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def purposes(self, request, org_id=None):
        """
        Get available token purposes with metadata.
        
        Returns information about each purpose type including:
        - Recommended expiry time
        - Recommended scopes
        - Description
        """
        purposes_data = [
            {
                "value": "claude-desktop",
                "label": "Claude Desktop",
                "description": "Long-lived token for local Claude Desktop MCP integration",
                "default_expiry_days": 365,
                "recommended_scopes": ["mcp:tools", "mcp:resources", "mcp:prompts"],
            },
            {
                "value": "api",
                "label": "API Integration",
                "description": "For external tools and integrations",
                "default_expiry_days": 90,
                "recommended_scopes": ["mcp:tools"],
            },
            {
                "value": "development",
                "label": "Development",
                "description": "Short-lived token for testing",
                "default_expiry_days": 30,
                "recommended_scopes": ["mcp:tools", "mcp:resources"],
            },
            {
                "value": "ci-cd",
                "label": "CI/CD",
                "description": "For automated pipelines and deployments",
                "default_expiry_days": 365,
                "recommended_scopes": ["mcp:tools"],
            },
        ]

        serializer = TokenPurposeInfoSerializer(purposes_data, many=True)
        return Response({"purposes": serializer.data})

    @action(detail=False, methods=["get"])
    def scopes(self, request, org_id=None):
        """
        Get available token scopes with descriptions.
        """
        scopes_data = [
            {
                "value": "mcp:tools",
                "label": "MCP Tools",
                "description": "Execute MCP tools and run agents",
            },
            {
                "value": "mcp:resources",
                "label": "MCP Resources",
                "description": "Access MCP resources (files, data, etc.)",
            },
            {
                "value": "mcp:prompts",
                "label": "MCP Prompts",
                "description": "Use MCP prompt templates",
            },
        ]

        serializer = TokenScopeInfoSerializer(scopes_data, many=True)
        return Response({"scopes": serializer.data})


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
