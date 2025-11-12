"""
Views for audit app.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer


class AuditEventViewSet(ReadOnlyModelViewSet):
    """ViewSet for AuditEvent (read-only)."""

    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        """Filter by organization and optional filters."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)

        # Filter by subject
        subject = self.request.query_params.get("subject")
        if subject:
            queryset = queryset.filter(subject__icontains=subject)

        # Filter by action
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by target
        target = self.request.query_params.get("target")
        if target:
            queryset = queryset.filter(target__icontains=target)

        # Filter by decision
        decision = self.request.query_params.get("decision")
        if decision:
            queryset = queryset.filter(decision=decision)

        # Filter by time window
        ts_from = self.request.query_params.get("ts_from")
        ts_to = self.request.query_params.get("ts_to")
        if ts_from:
            # Use ts if set, otherwise fallback to created_at
            from django.db.models import Q, F
            queryset = queryset.filter(
                Q(ts__gte=ts_from) | Q(ts__isnull=True, created_at__gte=ts_from)
            )
        if ts_to:
            # Use ts if set, otherwise fallback to created_at
            from django.db.models import Q
            queryset = queryset.filter(
                Q(ts__lte=ts_to) | Q(ts__isnull=True, created_at__lte=ts_to)
            )

        # Default: last 24 hours if no time filter
        # Use ts if set, otherwise fallback to created_at
        if not ts_from and not ts_to:
            from django.db.models import Q
            cutoff = timezone.now() - timezone.timedelta(hours=24)
            queryset = queryset.filter(
                Q(ts__gte=cutoff) | Q(ts__isnull=True, created_at__gte=cutoff)
            )

        # Order by ts (or created_at as fallback)
        from django.db.models import F
        return queryset.order_by(
            F("ts").desc(nulls_last=True),
            "-created_at"
        )

