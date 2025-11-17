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
        """Get or save default canvas state for organization (shared across team, like Miro)."""
        if request.method == "GET":
            # Get default canvas state (shared across organization)
            # Handle case where multiple entries exist (take the newest one)
            try:
                canvas_state = CanvasState.objects.get(
                    organization_id=org_id,
                    environment__isnull=True,
                    name="default",
                )
            except CanvasState.DoesNotExist:
                return Response(
                    {"detail": "Default canvas state not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            except CanvasState.MultipleObjectsReturned:
                # If multiple exist, take the newest one (most recently updated)
                canvas_state = CanvasState.objects.filter(
                    organization_id=org_id,
                    environment__isnull=True,
                    name="default",
                ).order_by("-updated_at").first()
            
            serializer = self.get_serializer(canvas_state)
            return Response(serializer.data)
        else:
            # POST: Save default canvas state (shared across organization)
            # Handle both direct state_json and nested state_json
            state_json = request.data.get("state_json") or request.data.get("state", request.data)
            
            # Validate that state_json contains nodes and edges with positions
            if not isinstance(state_json, dict):
                return Response(
                    {"error": "state_json must be a dictionary"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if "nodes" not in state_json or not isinstance(state_json["nodes"], list):
                return Response(
                    {"error": "state_json must contain 'nodes' array"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Validate that all nodes have positions
            for idx, node in enumerate(state_json["nodes"]):
                if not isinstance(node, dict):
                    return Response(
                        {"error": f"Node at index {idx} must be a dictionary"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if "position" not in node:
                    return Response(
                        {"error": f"Node at index {idx} missing 'position' field"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                pos = node["position"]
                if not isinstance(pos, dict) or "x" not in pos or "y" not in pos:
                    return Response(
                        {"error": f"Node at index {idx} has invalid position format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            
            serializer = self.get_serializer(data={
                "state_json": state_json,
                "organization_id": org_id,
                "name": "default",
            })
            serializer.is_valid(raise_exception=True)
            
            # Clean up duplicates first: delete older duplicates, keep the newest one
            duplicates = CanvasState.objects.filter(
                organization_id=org_id,
                environment__isnull=True,
                name="default",
            ).order_by("-updated_at")
            
            if duplicates.count() > 1:
                # Keep the newest one, delete the rest
                newest = duplicates.first()
                duplicates.exclude(id=newest.id).delete()
                # Update the newest one with new state
                newest.state_json = serializer.validated_data["state_json"]
                newest.save(update_fields=["state_json", "updated_at"])
                canvas_state = newest
                created = False
            else:
                # Normal update_or_create if no duplicates
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

