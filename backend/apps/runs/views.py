"""
Views for runs app.
"""
from __future__ import annotations

from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.runs.models import Run
from apps.runs.serializers import RunSerializer


class RunViewSet(ReadOnlyModelViewSet):
    """ViewSet for Run (read-only)."""

    queryset = Run.objects.all()
    serializer_class = RunSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset

