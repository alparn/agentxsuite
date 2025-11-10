"""
Unit tests for policy allow/deny logic.
"""
from __future__ import annotations

import pytest

from apps.policies.models import Policy
from apps.policies.services import is_allowed
from apps.tenants.models import Environment, Organization


@pytest.fixture
def org_env(db):
    """Create organization and environment for tests."""
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="dev", type="dev")
    return org, env


@pytest.fixture
def agent_tool(org_env):
    """Create agent and tool for tests."""
    org, env = org_env
    from apps.agents.models import Agent
    from apps.connections.models import Connection
    from apps.tools.models import Tool

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="none",
    )
    agent = Agent.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
    )
    tool = Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-tool",
        schema_json={"type": "object"},
        sync_status="synced",
    )
    return agent, tool


# ========== Helper Functions ==========


def create_policy(org, env, name, rules_json, enabled=True):
    """
    Helper to create a policy with common defaults.

    Args:
        org: Organization instance
        env: Environment instance (can be None for org-wide)
        name: Policy name
        rules_json: Rules dictionary
        enabled: Whether policy is enabled (default: True)

    Returns:
        Policy instance
    """
    return Policy.objects.create(
        organization=org,
        environment=env,
        name=name,
        rules_json=rules_json,
        enabled=enabled,
    )


def assert_allowed(agent, tool, expected_allowed=True, expected_reason_keywords=None):
    """
    Helper to assert policy check result.

    Args:
        agent: Agent instance
        tool: Tool instance
        expected_allowed: Expected allowed status (default: True)
        expected_reason_keywords: List of keywords that should be in reason (if denied)
    """
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed == expected_allowed, f"Expected allowed={expected_allowed}, got {allowed}, reason={reason}"

    if expected_allowed:
        assert reason is None, f"Expected reason=None for allowed, got: {reason}"
    else:
        assert reason is not None, "Expected reason for denied, got None"
        if expected_reason_keywords:
            reason_lower = reason.lower()
            for keyword in expected_reason_keywords:
                assert keyword.lower() in reason_lower, f"Expected '{keyword}' in reason: {reason}"


@pytest.mark.django_db
def test_deny_beats_all(agent_tool):
    """Test that deny list takes precedence over allow list."""
    agent, tool = agent_tool

    # Create policy with both deny and allow
    create_policy(
        agent.organization,
        agent.environment,
        "test-policy",
        {"deny": [tool.name], "allow": [tool.name]},
        enabled=True,
    )

    # Should be denied
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied"])


@pytest.mark.django_db
def test_allow_when_not_in_deny(agent_tool):
    """Test that tool is allowed when in allow list and not in deny list."""
    agent, tool = agent_tool

    # Create allow policy
    create_policy(
        agent.organization,
        agent.environment,
        "allow-policy",
        {"allow": [tool.name]},
        enabled=True,
    )

    # Should be allowed
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_default_deny_without_policy(agent_tool):
    """Test that default deny applies when no policy exists."""
    agent, tool = agent_tool

    # No policy created

    # Should be denied by default
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_empty_rules_default_deny(agent_tool):
    """Test that empty rules result in default deny."""
    agent, tool = agent_tool

    # Create policy with empty rules
    create_policy(agent.organization, agent.environment, "empty-policy", {}, enabled=True)

    # Should be denied (no explicit allow)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_empty_deny_list_allows_if_in_allow(agent_tool):
    """Test that empty deny list allows if tool is in allow list."""
    agent, tool = agent_tool

    # Create policy with allow list only
    create_policy(
        agent.organization,
        agent.environment,
        "allow-only-policy",
        {"allow": [tool.name], "deny": []},
        enabled=True,
    )

    # Should be allowed
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_multiple_deny_items(agent_tool):
    """Test that multiple items in deny list work correctly."""
    agent, tool = agent_tool

    # Create policy with multiple deny items
    create_policy(
        agent.organization,
        agent.environment,
        "multi-deny-policy",
        {"deny": ["tool1", tool.name, "tool3"]},
        enabled=True,
    )

    # Should be denied
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied"])


@pytest.mark.django_db
def test_disabled_policy_not_applied(agent_tool):
    """Test that disabled policies are not applied."""
    agent, tool = agent_tool

    # Create disabled deny policy
    create_policy(
        agent.organization,
        agent.environment,
        "disabled-deny-policy",
        {"deny": [tool.name]},
        enabled=False,  # Disabled
    )

    # Should be denied by default (no enabled allow policy)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


# ========== Cross-Policy-Konflikte ==========


@pytest.mark.django_db
def test_cross_policy_deny_beats_allow(agent_tool):
    """Test that deny in one policy beats allow in another policy."""
    agent, tool = agent_tool

    # Policy A allows
    create_policy(agent.organization, agent.environment, "allow-policy", {"allow": [tool.name]}, enabled=True)

    # Policy B denies
    create_policy(agent.organization, agent.environment, "deny-policy", {"deny": [tool.name]}, enabled=True)

    # Should be denied (deny beats allow across policies)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied", tool.name])


@pytest.mark.django_db
def test_multiple_policies_allow_when_no_deny(agent_tool):
    """Test that multiple allow policies work when no deny exists."""
    agent, tool = agent_tool

    # Multiple allow policies
    create_policy(agent.organization, agent.environment, "allow-policy-1", {"allow": [tool.name]}, enabled=True)
    create_policy(agent.organization, agent.environment, "allow-policy-2", {"allow": ["other-tool"]}, enabled=True)

    # Should be allowed (at least one policy allows)
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_multiple_policies_none_mention_tool(agent_tool):
    """Test that multiple enabled policies without tool mention result in default deny."""
    agent, tool = agent_tool

    # Multiple policies that don't mention this tool
    create_policy(agent.organization, agent.environment, "policy-1", {"allow": ["other-tool-1"]}, enabled=True)
    create_policy(agent.organization, agent.environment, "policy-2", {"deny": ["other-tool-2"]}, enabled=True)

    # Should be denied (no policy explicitly allows this tool)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


# ========== Scoping & Isolation ==========


@pytest.mark.django_db
def test_policy_from_different_org_not_applied(agent_tool):
    """Test that policies from different organization are not applied."""
    agent, tool = agent_tool

    # Create policy in different organization
    other_org = Organization.objects.create(name="OtherOrg")
    create_policy(other_org, None, "other-org-policy", {"allow": [tool.name]}, enabled=True)

    # Should be denied (policy from different org doesn't apply)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_policy_from_different_env_not_applied(agent_tool):
    """Test that policies from different environment are not applied."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Create different environment
    other_env = Environment.objects.create(organization=org, name="prod", type="prod")

    # Create policy in different environment
    create_policy(org, other_env, "other-env-policy", {"allow": [tool.name]}, enabled=True)

    # Should be denied (policy from different env doesn't apply)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_policy_with_null_env_applies_to_all_envs(agent_tool):
    """Test that policy with null environment applies to all environments."""
    agent, tool = agent_tool

    # Create policy with null environment (applies to all envs)
    create_policy(agent.organization, None, "org-wide-policy", {"allow": [tool.name]}, enabled=True)

    # Should be allowed (null env policy applies to all envs)
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_policy_with_specific_env_applies_only_to_that_env(agent_tool):
    """Test that policy with specific environment applies only to that environment."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Create another environment
    other_env = Environment.objects.create(organization=org, name="prod", type="prod")

    # Create policy for specific environment
    create_policy(org, env, "env-specific-policy", {"allow": [tool.name]}, enabled=True)

    # Should be allowed (policy matches agent's environment)
    assert_allowed(agent, tool, expected_allowed=True)


# ========== Case-Sensitivity ==========


@pytest.mark.django_db
def test_policy_case_sensitive_matching(agent_tool):
    """Test that policy matching is case-sensitive."""
    agent, tool = agent_tool

    # Create policy with different case
    create_policy(
        agent.organization,
        agent.environment,
        "case-policy",
        {"allow": [tool.name.upper()]},  # Uppercase version
        enabled=True,
    )

    # Should be denied (case-sensitive matching)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_policy_exact_case_match_required(agent_tool):
    """Test that exact case match is required for policy."""
    agent, tool = agent_tool

    # Create policy with exact case match
    create_policy(agent.organization, agent.environment, "exact-case-policy", {"allow": [tool.name]}, enabled=True)

    # Should be allowed (exact case match)
    assert_allowed(agent, tool, expected_allowed=True)


# ========== Leere/fehlerhafte Regeln ==========


@pytest.mark.django_db
def test_policy_with_none_rules_json(agent_tool):
    """Test that policy with None rules_json is handled gracefully."""
    agent, tool = agent_tool

    # Create policy with empty dict (Django JSONField converts None to {} by default)
    # This tests the edge case where rules_json is effectively empty
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="none-rules-policy",
        rules_json={},  # Empty dict (equivalent to None after Django's conversion)
        enabled=True,
    )

    # Should be denied (no rules means no allow)
    allowed, reason = is_allowed(agent, tool, {})
    assert allowed is False
    assert "No policy explicitly allows" in reason


@pytest.mark.django_db
def test_policy_with_allow_as_none(agent_tool):
    """Test that policy with allow=None is handled gracefully."""
    agent, tool = agent_tool

    # Create policy with allow=None (not a list)
    create_policy(agent.organization, agent.environment, "none-allow-policy", {"allow": None}, enabled=True)

    # Should be denied (allow is not a list, so it's ignored)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_policy_with_deny_as_string(agent_tool):
    """Test that policy with deny as string (not list) is handled gracefully."""
    agent, tool = agent_tool

    # Create policy with deny as string instead of list
    create_policy(agent.organization, agent.environment, "string-deny-policy", {"deny": tool.name}, enabled=True)

    # Should be denied by default (deny is not a list, so it's ignored, but no allow)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_policy_with_unknown_keys_ignored(agent_tool):
    """Test that unknown keys in rules_json are ignored."""
    agent, tool = agent_tool

    # Create policy with unknown keys
    create_policy(
        agent.organization,
        agent.environment,
        "unknown-keys-policy",
        {"unknown_key": [tool.name], "another_key": "value"},
        enabled=True,
    )

    # Should be denied (unknown keys are ignored)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


# ========== Disabled/Enabled-Mischung ==========


@pytest.mark.django_db
def test_enabled_allow_disabled_deny_allows(agent_tool):
    """Test that enabled allow policy beats disabled deny policy."""
    agent, tool = agent_tool

    # Enabled allow policy
    create_policy(agent.organization, agent.environment, "enabled-allow-policy", {"allow": [tool.name]}, enabled=True)

    # Disabled deny policy
    create_policy(agent.organization, agent.environment, "disabled-deny-policy", {"deny": [tool.name]}, enabled=False)

    # Should be allowed (enabled allow beats disabled deny)
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_disabled_allow_enabled_deny_denies(agent_tool):
    """Test that disabled allow policy doesn't override enabled deny policy."""
    agent, tool = agent_tool

    # Disabled allow policy
    create_policy(agent.organization, agent.environment, "disabled-allow-policy", {"allow": [tool.name]}, enabled=False)

    # Enabled deny policy
    create_policy(agent.organization, agent.environment, "enabled-deny-policy", {"deny": [tool.name]}, enabled=True)

    # Should be denied (enabled deny beats disabled allow)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied"])


# ========== Reihenfolge / Priorität ==========


@pytest.mark.django_db
def test_policy_order_does_not_matter_for_deny(agent_tool):
    """Test that policy order doesn't matter - deny always wins regardless of creation order."""
    agent, tool = agent_tool

    # Create allow policy first
    create_policy(agent.organization, agent.environment, "allow-policy-first", {"allow": [tool.name]}, enabled=True)

    # Create deny policy second (should still win)
    create_policy(agent.organization, agent.environment, "deny-policy-second", {"deny": [tool.name]}, enabled=True)

    # Should be denied (deny always wins, regardless of order)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied"])


@pytest.mark.django_db
def test_policy_order_does_not_matter_for_allow(agent_tool):
    """Test that policy order doesn't matter - any allow allows if no deny."""
    agent, tool = agent_tool

    # Create multiple allow policies in different orders
    create_policy(agent.organization, agent.environment, "allow-policy-1", {"allow": ["other-tool"]}, enabled=True)
    create_policy(agent.organization, agent.environment, "allow-policy-2", {"allow": [tool.name]}, enabled=True)

    # Should be allowed (any allow policy allows if no deny)
    assert_allowed(agent, tool, expected_allowed=True)


# ========== Begründungstexte ==========


@pytest.mark.django_db
def test_deny_reason_contains_tool_name_and_policy_name(agent_tool):
    """Test that deny reason contains tool name and policy name."""
    agent, tool = agent_tool

    create_policy(agent.organization, agent.environment, "test-deny-policy", {"deny": [tool.name]}, enabled=True)

    assert_allowed(
        agent, tool, expected_allowed=False, expected_reason_keywords=[tool.name, "test-deny-policy", "denied"]
    )


@pytest.mark.django_db
def test_default_deny_reason_format(agent_tool):
    """Test that default deny reason has consistent format."""
    agent, tool = agent_tool

    # No policies created

    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows", "tool"])


@pytest.mark.django_db
def test_allow_reason_is_none(agent_tool):
    """Test that allow reason is None (not empty string)."""
    agent, tool = agent_tool

    create_policy(agent.organization, agent.environment, "allow-policy", {"allow": [tool.name]}, enabled=True)

    assert_allowed(agent, tool, expected_allowed=True)  # Helper checks reason is None


# ========== Org-weit vs. Env-spezifisch ==========


@pytest.mark.django_db
def test_org_wide_allow_env_specific_deny_denies(agent_tool):
    """Test that env-specific deny beats org-wide allow."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Org-wide allow policy
    create_policy(org, None, "org-wide-allow", {"allow": [tool.name]}, enabled=True)

    # Env-specific deny policy
    create_policy(org, env, "env-specific-deny", {"deny": [tool.name]}, enabled=True)

    # Should be denied (env-specific deny beats org-wide allow)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied", tool.name])


@pytest.mark.django_db
def test_org_wide_deny_env_specific_allow_denies(agent_tool):
    """Test that org-wide deny beats env-specific allow."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Org-wide deny policy
    create_policy(org, None, "org-wide-deny", {"deny": [tool.name]}, enabled=True)

    # Env-specific allow policy
    create_policy(org, env, "env-specific-allow", {"allow": [tool.name]}, enabled=True)

    # Should be denied (org-wide deny beats env-specific allow)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied", tool.name])


@pytest.mark.django_db
def test_multiple_org_wide_policies_mixed_rules(agent_tool):
    """Test that multiple org-wide policies with mixed rules work correctly."""
    agent, tool = agent_tool
    org = agent.organization

    # Org-wide allow policy
    create_policy(org, None, "org-wide-allow", {"allow": [tool.name]}, enabled=True)

    # Org-wide deny policy
    create_policy(org, None, "org-wide-deny", {"deny": [tool.name]}, enabled=True)

    # Should be denied (deny beats allow, even both org-wide)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied", tool.name])


@pytest.mark.django_db
def test_org_wide_allow_env_specific_allow_both_allow(agent_tool):
    """Test that org-wide allow and env-specific allow both result in allow."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Org-wide allow policy
    create_policy(org, None, "org-wide-allow", {"allow": [tool.name]}, enabled=True)

    # Env-specific allow policy
    create_policy(org, env, "env-specific-allow", {"allow": [tool.name]}, enabled=True)

    # Should be allowed (both allow)
    assert_allowed(agent, tool, expected_allowed=True)


# ========== Duplikate / Whitespace / Große Listen ==========


@pytest.mark.django_db
def test_duplicate_entries_in_allow_list(agent_tool):
    """Test that duplicate entries in allow list work correctly."""
    agent, tool = agent_tool

    # Policy with duplicate entries
    create_policy(
        agent.organization,
        agent.environment,
        "duplicate-allow-policy",
        {"allow": [tool.name, tool.name, "other-tool", tool.name]},
        enabled=True,
    )

    # Should be allowed (duplicates don't break functionality)
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_duplicate_entries_in_deny_list(agent_tool):
    """Test that duplicate entries in deny list work correctly."""
    agent, tool = agent_tool

    # Policy with duplicate entries
    create_policy(
        agent.organization,
        agent.environment,
        "duplicate-deny-policy",
        {"deny": [tool.name, tool.name, "other-tool", tool.name]},
        enabled=True,
    )

    # Should be denied (duplicates don't break functionality)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied"])


@pytest.mark.django_db
def test_tool_name_with_whitespace_not_matched(agent_tool):
    """Test that tool names with whitespace are not matched (case-sensitive, exact match)."""
    agent, tool = agent_tool

    # Policy with tool name including whitespace
    create_policy(
        agent.organization,
        agent.environment,
        "whitespace-policy",
        {"allow": [f" {tool.name} ", f"  {tool.name}"]},  # With whitespace
        enabled=True,
    )

    # Should be denied (whitespace matters, exact match required)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])


@pytest.mark.django_db
def test_large_allow_list_stable(agent_tool):
    """Test that large allow lists remain stable."""
    agent, tool = agent_tool

    # Create policy with large allow list (1000 entries)
    large_list = [f"tool-{i}" for i in range(1000)]
    large_list[500] = tool.name  # Insert our tool in the middle

    create_policy(
        agent.organization,
        agent.environment,
        "large-allow-policy",
        {"allow": large_list},
        enabled=True,
    )

    # Should be allowed (large lists work correctly)
    assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.django_db
def test_large_deny_list_stable(agent_tool):
    """Test that large deny lists remain stable."""
    agent, tool = agent_tool

    # Create policy with large deny list (1000 entries)
    large_list = [f"tool-{i}" for i in range(1000)]
    large_list[500] = tool.name  # Insert our tool in the middle

    create_policy(
        agent.organization,
        agent.environment,
        "large-deny-policy",
        {"deny": large_list},
        enabled=True,
    )

    # Should be denied (large lists work correctly)
    assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["denied"])


@pytest.mark.django_db
def test_empty_string_in_lists_ignored(agent_tool):
    """Test that empty strings in allow/deny lists are handled gracefully."""
    agent, tool = agent_tool

    # Policy with empty strings in lists
    create_policy(
        agent.organization,
        agent.environment,
        "empty-string-policy",
        {"allow": ["", tool.name, ""]},
        enabled=True,
    )

    # Should be allowed (empty strings don't break, tool.name matches)
    assert_allowed(agent, tool, expected_allowed=True)


# ========== Case-Sensitivity Dokumentation ==========


@pytest.mark.django_db
def test_case_sensitivity_is_explicit_requirement(agent_tool):
    """
    Test that case-sensitivity is an explicit requirement.

    This test documents that policy matching is case-sensitive.
    If this behavior changes in the future, this test will fail and force
    explicit decision on case-sensitivity handling.
    """
    agent, tool = agent_tool

    # Create policy with lowercase tool name
    tool_lower = tool.name.lower()
    create_policy(
        agent.organization,
        agent.environment,
        "case-policy",
        {"allow": [tool_lower]},
        enabled=True,
    )

    # If tool.name is different case, should be denied
    if tool.name != tool_lower:
        assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])
    else:
        # If tool.name is already lowercase, should be allowed
        assert_allowed(agent, tool, expected_allowed=True)


@pytest.mark.parametrize(
    "tool_name_in_policy,expected_allowed",
    [
        ("test-tool", True),  # Exact match
        ("Test-Tool", False),  # Different case
        ("TEST-TOOL", False),  # Different case
        ("test-tool ", False),  # With trailing space
        (" test-tool", False),  # With leading space
    ],
)
@pytest.mark.django_db
def test_policy_matching_is_case_and_whitespace_sensitive(agent_tool, tool_name_in_policy, expected_allowed):
    """
    Parametrized test for case and whitespace sensitivity.

    Documents that policy matching requires exact string match (case and whitespace).
    """
    agent, tool = agent_tool

    # Create policy with specific tool name variant
    create_policy(
        agent.organization,
        agent.environment,
        "case-sensitive-policy",
        {"allow": [tool_name_in_policy]},
        enabled=True,
    )

    # Check if tool.name matches exactly
    if tool.name == tool_name_in_policy:
        assert_allowed(agent, tool, expected_allowed=True)
    else:
        assert_allowed(agent, tool, expected_allowed=False, expected_reason_keywords=["No policy explicitly allows"])
