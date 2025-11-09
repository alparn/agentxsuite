"""
Views for audit app.
"""
from __future__ import annotations

from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer


class AuditEventViewSet(ReadOnlyModelViewSet):
    """ViewSet for AuditEvent (read-only)."""

    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset.order_by("-created_at")

