"""
Tests for Policy REST APIs.
"""
from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from apps.policies.models import Policy, PolicyBinding, PolicyRule


@pytest.mark.django_db
class TestPolicyAPI:
    """Test Policy REST API endpoints."""

    def test_create_list_update_delete_policy(self, api_client, org_env, user_token):
        """Test creating, listing, updating, and deleting policies."""
        org, env = org_env
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {user_token.key}")

        # Create policy (with org_id in URL)
        url = reverse("policy-list", kwargs={"org_id": str(org.id)})
        data = {
            "name": "test-policy",
            "is_active": True,
            "environment_id": str(env.id),
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, f"Response: {response.data}"
        policy_id = response.data["id"]

        # List policies
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Handle both paginated and non-paginated responses
        policies = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(policies) >= 1

        # Filter by name
        response = api_client.get(f"{url}?name=test-policy")
        assert response.status_code == status.HTTP_200_OK
        policies = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(policies) >= 1

        # Filter by is_active
        response = api_client.get(f"{url}?is_active=true")
        assert response.status_code == status.HTTP_200_OK

        # Get policy
        url_detail = reverse("policy-detail", kwargs={"org_id": str(org.id), "pk": policy_id})
        response = api_client.get(url_detail)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "test-policy"

        # Update policy
        response = api_client.patch(url_detail, {"is_active": False}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

        # Delete policy (should fail if has bindings)
        response = api_client.delete(url_detail)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_create_rule_and_binding(self, api_client, org_env, user_token):
        """Test creating rules and bindings."""
        org, env = org_env
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {user_token.key}")

        # Create policy
        policy = Policy.objects.create(organization=org, environment=env, name="test-policy", is_active=True)

        # Add rule via API (with org_id in URL)
        url = reverse("policy-add-rule", kwargs={"org_id": str(org.id), "pk": policy.id})
        data = {
            "action": "tool.invoke",
            "target": "tool:test-tool",
            "effect": "allow",
            "conditions": {},
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        rule_id = response.data["id"]

        # Create binding
        url_binding = reverse("policy-binding-list")
        data_binding = {
            "policy_id": str(policy.id),
            "scope_type": "env",
            "scope_id": str(env.id),
            "priority": 100,
        }
        response = api_client.post(url_binding, data_binding, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Filter bindings by scope
        response = api_client.get(f"{url_binding}?scope_type=env&scope_id={env.id}")
        assert response.status_code == status.HTTP_200_OK
        bindings = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(bindings) >= 1

    def test_evaluate_endpoint_with_explain(self, api_client, org_env, user_token):
        """Test policy evaluation endpoint with explain mode."""
        org, env = org_env
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {user_token.key}")

        # Create policy with rule
        policy = Policy.objects.create(organization=org, environment=env, name="test-policy", is_active=True)
        rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:test-tool",
            effect="allow",
            conditions={},
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )

        # Evaluate without explain (as action on policy-list endpoint)
        url = reverse("policy-evaluate")
        data = {
            "action": "tool.invoke",
            "target": "tool:test-tool",
            "organization_id": str(org.id),
            "environment_id": str(env.id),
        }
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["decision"] == "allow"
        assert response.data["rule_id"] == rule.id
        assert "matched_rules" not in response.data

        # Evaluate with explain
        response = api_client.post(f"{url}?explain=true", data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["decision"] == "allow"
        assert "matched_rules" in response.data
        assert "bindings_order" in response.data


@pytest.mark.django_db
class TestAuditAPI:
    """Test Audit REST API endpoints."""

    def test_audit_list_filters(self, api_client, org_env, user_token):
        """Test audit event listing with filters."""
        org, env = org_env
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {user_token.key}")

        from apps.audit.models import AuditEvent

        # Create audit events
        AuditEvent.objects.create(
            organization=org,
            event_type="pep_decision",
            subject="agent:test@org/env",
            action="tool.invoke",
            target="tool:test-tool",
            decision="allow",
        )
        AuditEvent.objects.create(
            organization=org,
            event_type="pep_decision",
            subject="agent:test@org/env",
            action="tool.invoke",
            target="tool:other-tool",
            decision="deny",
        )

        url = reverse("audit-list", kwargs={"org_id": str(org.id)})
        # Filter by subject
        response = api_client.get(f"{url}?subject=agent:test")
        assert response.status_code == status.HTTP_200_OK
        events = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(events) >= 2

        # Filter by action
        response = api_client.get(f"{url}?action=tool.invoke")
        assert response.status_code == status.HTTP_200_OK
        events = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(events) >= 2

        # Filter by decision
        response = api_client.get(f"{url}?decision=allow")
        assert response.status_code == status.HTTP_200_OK
        events = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(events) >= 1

        # Filter by target
        response = api_client.get(f"{url}?target=test-tool")
        assert response.status_code == status.HTTP_200_OK
        events = response.data.get("results", response.data) if isinstance(response.data, dict) and "results" in response.data else response.data
        assert len(events) >= 1

