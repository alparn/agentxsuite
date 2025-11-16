"""
Views for tenants app.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.tenants.models import Environment, Organization
from apps.tenants.serializers import EnvironmentSerializer, OrganizationSerializer
from apps.audit.mixins import AuditLoggingMixin


class OrganizationViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Organization."""

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    @action(detail=True, methods=["get", "post"], url_path="environments")
    def environments(self, request, pk=None):  # noqa: ARG002
        """List or create environments for an organization."""
        org = self.get_object()
        if request.method == "POST":
            serializer = EnvironmentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(organization=org)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        environments = Environment.objects.filter(organization=org)
        serializer = EnvironmentSerializer(environments, many=True)
        return Response(serializer.data)


class EnvironmentViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Environment."""

    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer

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

