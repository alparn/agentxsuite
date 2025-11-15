"""
Views for runs app.
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.runs.models import Run
from apps.runs.serializers import RunListSerializer, RunSerializer, RunStepSerializer


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

