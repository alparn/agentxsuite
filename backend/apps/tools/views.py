"""
Views for tools app.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.agents.models import Agent
from apps.policies.models import Policy
from apps.policies.services import is_allowed
from apps.runs.services import start_run
from apps.runs.serializers import RunSerializer
from apps.tools.models import Tool
from apps.tools.schemas import ToolRunInputSchema
from apps.tools.serializers import ToolSerializer


class ToolViewSet(ModelViewSet):
    """ViewSet for Tool."""

    queryset = Tool.objects.all()
    serializer_class = ToolSerializer

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

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):  # noqa: ARG002
        """Run a tool (orchestrator stub)."""
        tool = self.get_object()

        # Parse input
        input_schema = ToolRunInputSchema(**request.data)
        input_json = input_schema.input_json or {}

        # Get agent (stub: use first agent for tool's org/env)
        agent = Agent.objects.filter(
            organization=tool.organization,
            environment=tool.environment,
        ).first()

        if not agent:
            return Response(
                {"error": "No agent found for this tool's organization/environment"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check policy (stub: use first policy for org)
        policy = Policy.objects.filter(organization=tool.organization).first()
        if policy:
            allowed, reason = is_allowed(policy.rules_json, tool.name)
            if not allowed:
                return Response(
                    {"error": reason},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Start run
        run = start_run(agent=agent, tool=tool, input_json=input_json)
        serializer = RunSerializer(run)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

