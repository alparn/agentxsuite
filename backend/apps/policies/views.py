"""
Views for policies app.
"""
from __future__ import annotations

from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.policies.models import Policy, PolicyBinding, PolicyRule
from apps.policies.pdp import get_pdp
from apps.policies.serializers import (
    PolicyBindingSerializer,
    PolicyEvaluateSerializer,
    PolicyRuleSerializer,
    PolicySerializer,
)
from apps.tenants.models import Environment


class PolicyViewSet(ModelViewSet):
    """ViewSet for Policy."""

    queryset = Policy.objects.all()
    serializer_class = PolicySerializer

    def get_queryset(self):
        """Filter by organization and optionally by name/is_active."""
        queryset = super().get_queryset()
        org_id = self.kwargs.get("org_id")
        if org_id:
            queryset = queryset.filter(organization_id=org_id)

        # Filter by name
        name = self.request.query_params.get("name")
        if name:
            queryset = queryset.filter(name__icontains=name)

        # Filter by is_active
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("-created_at")

    def get_serializer_context(self):
        """Add org_id to serializer context."""
        context = super().get_serializer_context()
        context["org_id"] = self.kwargs.get("org_id")
        return context

    def perform_create(self, serializer):
        """Set organization from URL parameter or request data and validate environment."""
        org_id = self.kwargs.get("org_id") or serializer.validated_data.get("organization_id")
        if not org_id:
            raise ValidationError("Organization ID is required (from URL or request data)")

        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        try:
            serializer.save(organization_id=org_id)
        except IntegrityError as e:
            # Catch UNIQUE constraint violations and provide user-friendly error
            if "UNIQUE constraint failed" in str(e) and "organization_id" in str(e) and "name" in str(e):
                name = serializer.validated_data.get("name", "unknown")
                raise ValidationError(
                    {"name": f"A policy with the name '{name}' already exists in this organization."}
                )
            raise

    def perform_update(self, serializer):
        """Ensure organization cannot be changed via update and validate environment."""
        instance = self.get_object()
        org_id = self.kwargs.get("org_id") or str(instance.organization.id)
        
        # Validate environment_id belongs to organization if provided
        environment_id = serializer.validated_data.get("environment_id")
        if environment_id:
            if not Environment.objects.filter(id=environment_id, organization_id=org_id).exists():
                raise ValidationError(
                    f"Environment {environment_id} does not belong to organization {org_id}"
                )

        try:
            serializer.save()
        except IntegrityError as e:
            # Catch UNIQUE constraint violations and provide user-friendly error
            if "UNIQUE constraint failed" in str(e) and "organization_id" in str(e) and "name" in str(e):
                name = serializer.validated_data.get("name", instance.name)
                raise ValidationError(
                    {"name": f"A policy with the name '{name}' already exists in this organization."}
                )
            raise

    def perform_destroy(self, instance):
        """Prevent deletion if policy has bindings."""
        if instance.bindings.exists():
            raise ValidationError("Cannot delete policy with active bindings. Remove bindings first.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="rules")
    def add_rule(self, request, pk=None, org_id=None):
        """Add a rule to a policy."""
        policy = self.get_object()
        serializer = PolicyRuleSerializer(data={**request.data, "policy_id": str(policy.id)})
        serializer.is_valid(raise_exception=True)
        serializer.save(policy=policy)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="evaluate")
    def evaluate(self, request, org_id=None):
        """Evaluate policy for an action on a target."""
        serializer = PolicyEvaluateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        explain = serializer.validated_data.pop("explain", False)
        if "explain" in request.query_params:
            explain = request.query_params.get("explain", "false").lower() == "true"

        # Convert UUIDs to strings
        data = serializer.validated_data
        for key in ["organization_id", "environment_id", "agent_id", "tool_id"]:
            if data.get(key):
                data[key] = str(data[key])

        # Call PDP
        pdp = get_pdp()
        decision = pdp.evaluate(explain=explain, **data)

        response_data = {
            "decision": decision.decision,
            "rule_id": decision.rule_id,
        }

        if explain:
            response_data["matched_rules"] = decision.matched_rules
            response_data["bindings_order"] = decision.bindings_order

        return Response(response_data, status=status.HTTP_200_OK)


class PolicyRuleViewSet(ModelViewSet):
    """ViewSet for PolicyRule."""

    queryset = PolicyRule.objects.all()
    serializer_class = PolicyRuleSerializer

    def get_queryset(self):
        """Filter by policy if policy_id is provided."""
        queryset = super().get_queryset()
        policy_id = self.request.query_params.get("policy_id")
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        """Set policy from policy_id."""
        policy_id = serializer.validated_data.get("policy_id")
        if not policy_id:
            raise ValidationError("policy_id is required")
        try:
            policy = Policy.objects.get(id=policy_id)
        except Policy.DoesNotExist:
            raise ValidationError(f"Policy {policy_id} not found")
        serializer.save(policy=policy)


class PolicyBindingViewSet(ModelViewSet):
    """ViewSet for PolicyBinding."""

    queryset = PolicyBinding.objects.all()
    serializer_class = PolicyBindingSerializer

    def get_queryset(self):
        """Filter by scope_type, scope_id, or policy_id if provided."""
        queryset = super().get_queryset()
        scope_type = self.request.query_params.get("scope_type")
        scope_id = self.request.query_params.get("scope_id")
        policy_id = self.request.query_params.get("policy_id")
        if scope_type:
            queryset = queryset.filter(scope_type=scope_type)
        if scope_id:
            queryset = queryset.filter(scope_id=scope_id)
        if policy_id:
            queryset = queryset.filter(policy_id=policy_id)
        return queryset.order_by("priority", "-created_at")

    def perform_create(self, serializer):
        """Set policy from policy_id."""
        policy_id = serializer.validated_data.get("policy_id")
        if not policy_id:
            raise ValidationError("policy_id is required")
        try:
            policy = Policy.objects.get(id=policy_id)
        except Policy.DoesNotExist:
            raise ValidationError(f"Policy {policy_id} not found")
        serializer.save(policy=policy)


@api_view(["POST"])
def policy_evaluate(request):
    """Evaluate policy for an action on a target."""
    serializer = PolicyEvaluateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    explain = serializer.validated_data.pop("explain", False)
    if "explain" in request.query_params:
        explain = request.query_params.get("explain", "false").lower() == "true"

    # Convert UUIDs to strings
    data = serializer.validated_data
    for key in ["organization_id", "environment_id", "agent_id", "tool_id"]:
        if data.get(key):
            data[key] = str(data[key])

    # Call PDP
    pdp = get_pdp()
    decision = pdp.evaluate(explain=explain, **data)

    response_data = {
        "decision": decision.decision,
        "rule_id": decision.rule_id,
    }

    if explain:
        response_data["matched_rules"] = decision.matched_rules
        response_data["bindings_order"] = decision.bindings_order

    return Response(response_data, status=status.HTTP_200_OK)
