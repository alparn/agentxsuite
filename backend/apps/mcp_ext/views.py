"""
Views for mcp_ext app.
"""
from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from apps.mcp_ext.models import Prompt, Resource
from apps.mcp_ext.serializers import PromptSerializer, ResourceSerializer
from apps.tenants.models import Environment
from apps.audit.mixins import AuditLoggingMixin


class ResourceViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Resource."""

    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """Set organization from URL parameter and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )
        else:
            raise ValidationError("environment_id is required")

        serializer.save(organization_id=org_id)

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        serializer.save(organization_id=org_id)


class PromptViewSet(AuditLoggingMixin, ModelViewSet):
    """ViewSet for Prompt."""

    queryset = Prompt.objects.all()
    serializer_class = PromptSerializer

    def get_queryset(self):
        """Filter by organization if org_id is provided."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """Set organization from URL parameter and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )
        else:
            raise ValidationError("environment_id is required")

        serializer.save(organization_id=org_id)

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update and validate environment."""
        org_id = self.kwargs.get("org_id")
        if not org_id:
            raise ValidationError("Organization ID is required")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        serializer.save(organization_id=org_id)

