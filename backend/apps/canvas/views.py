"""
Views for canvas app.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.canvas.models import CanvasState
from apps.canvas.serializers import CanvasStateSerializer
from apps.audit.mixins import AuditLoggingMixin


class CanvasStateViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for CanvasState."""

    queryset = CanvasState.objects.all()
    serializer_class = CanvasStateSerializer

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

    @action(detail=False, methods=["get", "post"], url_path="default")
    def default(self, request, org_id=None):
        """Get or save default canvas state for organization."""
        if request.method == "GET":
            # Get default canvas state
            try:
                canvas_state = CanvasState.objects.get(
                    organization_id=org_id,
                    environment__isnull=True,
                    name="default",
                )
                serializer = self.get_serializer(canvas_state)
                return Response(serializer.data)
            except CanvasState.DoesNotExist:
                return Response(
                    {"detail": "Default canvas state not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            # POST: Save default canvas state
            # Handle both direct state_json and nested state_json
            state_json = request.data.get("state_json") or request.data.get("state", request.data)
            
            serializer = self.get_serializer(data={
                "state_json": state_json,
                "organization_id": org_id,
                "name": "default",
            })
            serializer.is_valid(raise_exception=True)
            
            # Get or create default canvas state
            canvas_state, created = CanvasState.objects.update_or_create(
                organization_id=org_id,
                environment__isnull=True,
                name="default",
                defaults={
                    "state_json": serializer.validated_data["state_json"],
                },
            )
            
            response_serializer = self.get_serializer(canvas_state)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

