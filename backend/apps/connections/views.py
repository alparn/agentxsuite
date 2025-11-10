"""
Views for connections app.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.connections.models import Connection
from apps.connections.schemas import ConnectionSyncResponse, ConnectionTestResponse
from apps.connections.serializers import ConnectionSerializer
from apps.connections.services import sync_connection, test_connection
from libs.secretstore import get_secretstore


class ConnectionViewSet(ModelViewSet):
    """ViewSet for Connection."""

    queryset = Connection.objects.all()
    serializer_class = ConnectionSerializer

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

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):  # noqa: ARG002
        """Test a connection."""
        conn = self.get_object()
        test_connection(conn)
        conn.refresh_from_db()
        response_data = ConnectionTestResponse(
            status=conn.status,
            last_seen_at=conn.last_seen_at.isoformat() if conn.last_seen_at else None,
        )
        return Response(response_data.model_dump(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):  # noqa: ARG002
        """Sync tools from a connection with strict MCP validation."""
        conn = self.get_object()
        try:
            created_tools, updated_tools = sync_connection(conn)
            
            all_tools = created_tools + updated_tools
            message = None
            if created_tools and updated_tools:
                message = f"Created {len(created_tools)} and updated {len(updated_tools)} tools"
            elif created_tools:
                message = f"Created {len(created_tools)} new tools"
            elif updated_tools:
                message = f"Updated {len(updated_tools)} existing tools"
            else:
                message = "No changes needed"
            
            response_data = ConnectionSyncResponse(
                tools_created=len(created_tools),
                tools_updated=len(updated_tools),
                tool_ids=[str(tool.id) for tool in all_tools],
                message=message,
            )
            return Response(response_data.model_dump(), status=status.HTTP_200_OK)
        except Exception as e:
            # Handle ValidationError and other sync errors
            error_message = str(e)
            return Response(
                {"error": error_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"], url_path="store-secret")
    def store_secret(self, request, org_id=None):
        """
        Store a secret in the SecretStore and return the reference.
        
        This endpoint allows clients to store secrets before creating connections.
        The returned secret_ref can then be used when creating/updating connections.
        
        Request body:
        {
            "environment_id": "uuid",
            "key": "connection_token",
            "value": "actual-secret-value"
        }
        
        Returns:
        {
            "secret_ref": "base64-encoded-reference"
        }
        """
        if not org_id:
            return Response(
                {"error": "organization_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        environment_id = request.data.get("environment_id")
        key = request.data.get("key")
        value = request.data.get("value")

        if not environment_id or not key or not value:
            return Response(
                {"error": "environment_id, key, and value are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            secret_store = get_secretstore()
            scope = {"org": str(org_id), "env": str(environment_id)}
            secret_ref = secret_store.put_secret(scope, key, value)

            # Security: Never return secret value, only reference and metadata
            from apps.secretstore.models import StoredSecret
            stored_secret = StoredSecret.objects.get(ref=secret_ref)
            
            return Response(
                {
                    "secret_ref": secret_ref,
                    "created_at": stored_secret.created_at.isoformat() if stored_secret.created_at else None,
                    "expires_at": stored_secret.expires_at.isoformat() if stored_secret.expires_at else None,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to store secret: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

