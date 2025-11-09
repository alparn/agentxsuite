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
        """Sync tools from a connection."""
        conn = self.get_object()
        tools = sync_connection(conn)
        response_data = ConnectionSyncResponse(
            tools_created=len(tools),
            tool_ids=[tool.id for tool in tools],
        )
        return Response(response_data.model_dump(), status=status.HTTP_200_OK)

