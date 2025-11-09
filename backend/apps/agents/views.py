"""
Views for agents app.
"""
from __future__ import annotations

from rest_framework.viewsets import ModelViewSet

from apps.agents.models import Agent
from apps.agents.serializers import AgentSerializer


class AgentViewSet(ModelViewSet):
    """ViewSet for Agent."""

    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

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

