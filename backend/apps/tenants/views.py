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


class OrganizationViewSet(ModelViewSet):
    """ViewSet for Organization."""

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer

    @action(detail=True, methods=["get", "post"], url_path="environments")
    def environments(self, request, pk=None):  # noqa: ARG002
        """List or create environments for an organization."""
        org = self.get_object()
        if request.method == "POST":
            serializer = EnvironmentSerializer(data={**request.data, "organization_id": org.id})
            serializer.is_valid(raise_exception=True)
            serializer.save(organization=org)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        environments = Environment.objects.filter(organization=org)
        serializer = EnvironmentSerializer(environments, many=True)
        return Response(serializer.data)


class EnvironmentViewSet(ModelViewSet):
    """ViewSet for Environment."""

    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer

