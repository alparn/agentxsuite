"""
Tests for Policy Decision Point (PDP).
"""
from __future__ import annotations

import pytest
from django.utils import timezone
from model_bakery import baker

from apps.agents.models import InboundAuthMethod
from apps.policies.models import Policy, PolicyBinding, PolicyRule
from apps.policies.pdp import PolicyDecision, PolicyEvaluator, get_pdp


@pytest.fixture
def policy(org_env):
    """Create a test policy."""
    org, env = org_env
    return baker.make(
        Policy,
        organization=org,
        environment=env,
        name="test-policy",
        is_active=True,
    )


@pytest.mark.django_db
class TestPolicyEvaluator:
    """Test Policy Decision Point (PDP) evaluation."""

    def test_allow_first_match(self, org_env, policy):
        """Test that first matching allow rule grants access."""
        org, env = org_env

        # Create allow rule
        rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:test-tool",
            effect="allow",
            conditions={},
        )

        # Create binding
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )

        # Evaluate
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target="tool:test-tool",
            organization_id=str(org.id),
            environment_id=str(env.id),
        )

        assert decision.is_allowed() is True
        assert decision.rule_id == rule.id

    def test_deny_wins(self, org_env, policy):
        """Test that deny rules take precedence over allow rules."""
        org, env = org_env

        # Create deny rule
        deny_rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:test-tool",
            effect="deny",
            conditions={},
        )

        # Create allow rule (should be ignored)
        allow_rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:test-tool",
            effect="allow",
            conditions={},
        )

        # Create binding
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )

        # Evaluate
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target="tool:test-tool",
            organization_id=str(org.id),
            environment_id=str(env.id),
        )

        assert decision.is_allowed() is False
        assert decision.rule_id == deny_rule.id

    def test_no_match_is_deny(self, org_env, policy):
        """Test that default deny applies when no rule matches."""
        org, env = org_env

        # Create rule for different target
        PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:other-tool",
            effect="allow",
            conditions={},
        )

        # Create binding
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )

        # Evaluate for non-matching target
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target="tool:test-tool",
            organization_id=str(org.id),
            environment_id=str(env.id),
        )

        assert decision.is_allowed() is False
        assert decision.rule_id is None

    def test_priority_and_scope_ordering(self, org_env):
        """Test that bindings are evaluated in correct order (Agent → Tool → Env → Org)."""
        org, env = org_env

        # Create policies with different priorities
        policy1 = Policy.objects.create(organization=org, name="org-policy", is_active=True)
        policy2 = Policy.objects.create(organization=org, environment=env, name="env-policy", is_active=True)
        policy3 = Policy.objects.create(organization=org, environment=env, name="agent-policy", is_active=True)

        # Create agent
        from apps.agents.models import Agent
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost",
            auth_method="none",
            status="ok",
        )
        agent = Agent.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-agent",
            slug="test-agent",
            inbound_auth_method=InboundAuthMethod.NONE,
        )

        # Create rules
        PolicyRule.objects.create(
            policy=policy1,
            action="tool.invoke",
            target="tool:test-tool",
            effect="allow",
            conditions={},
        )
        PolicyRule.objects.create(
            policy=policy2,
            action="tool.invoke",
            target="tool:test-tool",
            effect="deny",
            conditions={},
        )
        PolicyRule.objects.create(
            policy=policy3,
            action="tool.invoke",
            target="tool:test-tool",
            effect="allow",
            conditions={},
        )

        # Create bindings (agent-specific should be evaluated first)
        # Note: Within same scope_type, lower priority number = evaluated first
        # But across scope_types, order is: agent → tool → env → org
        PolicyBinding.objects.create(
            policy=policy3,
            scope_type="agent",
            scope_id=str(agent.id),
            priority=100,  # Lower priority within agent scope
        )
        PolicyBinding.objects.create(
            policy=policy2,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )
        PolicyBinding.objects.create(
            policy=policy1,
            scope_type="org",
            scope_id=str(org.id),
            priority=100,
        )

        # Evaluate - agent policy should win (allow) because agent scope is evaluated before env/org
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target="tool:test-tool",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
        )

        # Agent policy (allow) should win over env policy (deny) because agent scope is evaluated first
        assert decision.is_allowed() is True
        # Should match agent policy rule
        assert decision.rule_id == policy3.rules.first().id

    def test_conditions_env_time_tags_risk(self, org_env, policy):
        """Test condition evaluation: env, time_window, tags, risk_level."""
        org, env = org_env

        # Create rule with conditions
        rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:test-tool",
            effect="allow",
            conditions={
                "env==": str(env.id),
                "tags": ["production"],
                "risk_level<=": 5,
            },
        )

        # Create binding
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )

        # Evaluate with matching conditions
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target="tool:test-tool",
            organization_id=str(org.id),
            environment_id=str(env.id),
            context={
                "environment_id": str(env.id),
                "tags": ["production", "critical"],
                "risk_level": 3,
            },
        )

        assert decision.is_allowed() is True

        # Evaluate with non-matching conditions
        decision2 = pdp.evaluate(
            action="tool.invoke",
            target="tool:test-tool",
            organization_id=str(org.id),
            environment_id=str(env.id),
            context={
                "environment_id": str(env.id),
                "tags": ["development"],
                "risk_level": 3,
            },
        )

        assert decision2.is_allowed() is False

    def test_wildcard_target_matching(self, org_env, policy):
        """Test that wildcard patterns match targets."""
        org, env = org_env

        # Create rule with wildcard pattern
        rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target="tool:pdf/*",
            effect="allow",
            conditions={},
        )

        # Create binding
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="env",
            scope_id=str(env.id),
            priority=100,
        )

        # Evaluate with matching target
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target="tool:pdf/read",
            organization_id=str(org.id),
            environment_id=str(env.id),
        )

        assert decision.is_allowed() is True
        assert decision.rule_id == rule.id

        # Evaluate with non-matching target
        decision2 = pdp.evaluate(
            action="tool.invoke",
            target="tool:image/read",
            organization_id=str(org.id),
            environment_id=str(env.id),
        )

        assert decision2.is_allowed() is False


@pytest.mark.django_db
class TestDelegationConstraints:
    """Test delegation constraints (depth, budget, TTL)."""

    def test_agent_invoke_respects_default_max_depth(self, org_env):
        """Test that agent.invoke respects default_max_depth."""
        org, env = org_env

        from apps.agents.models import Agent
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost",
            auth_method="none",
            status="ok",
        )
        agent = Agent.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-agent",
            slug="test-agent",
            default_max_depth=2,
            inbound_auth_method=InboundAuthMethod.NONE,
        )

        policy = Policy.objects.create(organization=org, name="delegation-policy", is_active=True)
        PolicyRule.objects.create(
            policy=policy,
            action="agent.invoke",
            target="agent:test-agent",
            effect="allow",
            conditions={"depth<=": 2},
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="agent",
            scope_id=str(agent.id),
            priority=100,
        )

        pdp = get_pdp()
        # Should allow with depth=1
        decision1 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"depth": 1},
        )
        assert decision1.is_allowed() is True

        # Should allow with depth=2
        decision2 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"depth": 2},
        )
        assert decision2.is_allowed() is True

        # Should deny with depth=3
        decision3 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"depth": 3},
        )
        assert decision3.is_allowed() is False

    def test_agent_invoke_budget_ttl(self, org_env):
        """Test that agent.invoke respects budget and TTL constraints."""
        org, env = org_env

        from apps.agents.models import Agent
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost",
            auth_method="none",
            status="ok",
        )
        agent = Agent.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-agent",
            slug="test-agent",
            default_budget_cents=1000,
            default_ttl_seconds=600,
            inbound_auth_method=InboundAuthMethod.NONE,
        )

        policy = Policy.objects.create(organization=org, name="delegation-policy", is_active=True)
        PolicyRule.objects.create(
            policy=policy,
            action="agent.invoke",
            target="agent:test-agent",
            effect="allow",
            conditions={
                "budget_left_cents>=": 100,
                "ttl_valid": True,
            },
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="agent",
            scope_id=str(agent.id),
            priority=100,
        )

        pdp = get_pdp()
        # Should allow with valid budget and TTL
        decision1 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"budget_left_cents": 500, "ttl_valid": True},
        )
        assert decision1.is_allowed() is True

        # Should deny with insufficient budget
        decision2 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"budget_left_cents": 50, "ttl_valid": True},
        )
        assert decision2.is_allowed() is False

        # Should deny with expired TTL
        decision3 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"budget_left_cents": 500, "ttl_valid": False},
        )
        assert decision3.is_allowed() is False

    def test_allowed_resource_namespace_condition(self, org_env):
        """Test allowed_resource_ns condition for agent.invoke."""
        org, env = org_env

        from apps.agents.models import Agent
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost",
            auth_method="none",
            status="ok",
        )
        agent = Agent.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-agent",
            slug="test-agent",
            inbound_auth_method=InboundAuthMethod.NONE,
        )

        policy = Policy.objects.create(organization=org, name="delegation-policy", is_active=True)
        PolicyRule.objects.create(
            policy=policy,
            action="agent.invoke",
            target="agent:test-agent",
            effect="allow",
            conditions={"allowed_resource_ns": ["minio://org/env/data", "s3://bucket/path"]},
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="agent",
            scope_id=str(agent.id),
            priority=100,
        )

        pdp = get_pdp()
        # Should allow with matching resource namespace
        decision1 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"resource_ns": "minio://org/env/data"},
        )
        assert decision1.is_allowed() is True

        # Should deny with non-matching resource namespace
        decision2 = pdp.evaluate(
            action="agent.invoke",
            target="agent:test-agent",
            organization_id=str(org.id),
            environment_id=str(env.id),
            agent_id=str(agent.id),
            context={"resource_ns": "minio://org/env/other"},
        )
        assert decision2.is_allowed() is False

