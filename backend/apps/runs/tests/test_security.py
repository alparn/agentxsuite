"""
Security tests for runs service.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.policies.models import Policy
from apps.runs.models import Run
from apps.runs.rate_limit import RateLimiter
from apps.runs.services import start_run
from apps.runs.timeout import TimeoutError
from apps.tenants.models import Environment, Organization

# Status constants from Run.STATUS_CHOICES
RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_SUCCEEDED = "succeeded"
RUN_STATUS_FAILED = "failed"


@pytest.mark.django_db
def test_policy_deny_blocks_run(agent_tool):
    """Test that policy deny blocks run execution."""
    agent, tool = agent_tool

    # Create deny policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="deny-policy",
        rules_json={"deny": [tool.name]},
        enabled=True,
    )

    # Attempt to start run
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "Policy denied" in run.error_text

    # Verify audit log
    audit = AuditEvent.objects.filter(event_type="run_denied_policy").first()
    assert audit is not None
    assert audit.event_data["tool_id"] == str(tool.id)


@pytest.mark.django_db
def test_policy_allow_permits_run(agent_tool):
    """Test that policy allow permits run execution."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Start run should succeed
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == RUN_STATUS_SUCCEEDED


@pytest.mark.django_db
def test_jsonschema_invalid_input_raises(agent_tool):
    """Test that invalid input raises validation error."""
    from apps.tools.models import Tool
    
    agent, _ = agent_tool

    # Create a tool with required field for this test
    tool = Tool.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        connection=agent.connection,
        name="test-tool-with-schema",
        schema_json={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
            },
            "required": ["x"],  # x is required
        },
        sync_status="synced",
        enabled=True,
    )

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Invalid input (missing required field 'x')
    with pytest.raises(ValueError, match="Input validation failed"):
        start_run(agent=agent, tool=tool, input_json={})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "validation" in run.error_text.lower()

    # Verify audit log
    audit = AuditEvent.objects.filter(event_type="run_denied_validation").first()
    assert audit is not None


@pytest.mark.django_db
def test_jsonschema_valid_input_passes(agent_tool):
    """Test that valid input passes validation."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Valid input
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == RUN_STATUS_SUCCEEDED


@pytest.mark.django_db
def test_rate_limit_blocks_after_threshold(agent_tool):
    """Test that rate limit blocks after threshold."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Clear cache
    cache.clear()

    # Create rate limiter with low threshold
    limiter = RateLimiter()

    # Create max concurrent runs
    for _ in range(5):
        Run.objects.create(
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status=RUN_STATUS_RUNNING,
            started_at=timezone.now(),
        )

    # Next run should be blocked
    allowed, reason = limiter.check_rate_limit(agent, max_concurrent_runs=5)
    assert not allowed
    assert "concurrent" in reason.lower()

    # Clean up
    Run.objects.filter(agent=agent).delete()


@pytest.mark.django_db
def test_timeout_stops_long_run_in_start_run(agent_tool):
    """Test that timeout in start_run sets run to failed and creates audit log."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Patch the tool execution to simulate timeout
    with patch("apps.runs.services.execute_with_timeout") as mock_timeout:
        mock_timeout.side_effect = TimeoutError("Run exceeded timeout of 1 seconds")

        # Attempt to start run with short timeout
        with pytest.raises(TimeoutError):
            start_run(agent=agent, tool=tool, input_json={"x": 1}, timeout_seconds=1)

        # Verify run was created and marked as failed
        run = Run.objects.get(agent=agent, tool=tool)
        assert run.status == RUN_STATUS_FAILED
        assert "timeout" in run.error_text.lower()

        # Verify audit log for timeout
        audit = AuditEvent.objects.filter(event_type="run_failed_timeout").first()
        assert audit is not None
        assert audit.event_data["run_id"] == str(run.id)


@pytest.mark.django_db
def test_audit_log_created_on_run(agent_tool):
    """Test that audit log is created on run."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Start run
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify audit logs
    started_audit = AuditEvent.objects.filter(event_type="run_started").first()
    assert started_audit is not None
    assert started_audit.event_data["run_id"] == str(run.id)

    succeeded_audit = AuditEvent.objects.filter(event_type="run_succeeded").first()
    assert succeeded_audit is not None


@pytest.mark.django_db
def test_default_deny_without_policy(agent_tool):
    """Test that default deny applies when no policy exists."""
    agent, tool = agent_tool

    # No policy created

    # Attempt to start run should fail
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "No policy explicitly allows" in run.error_text


@pytest.mark.django_db
def test_disabled_policy_not_applied(agent_tool):
    """Test that disabled policies are not applied."""
    agent, tool = agent_tool

    # Create disabled deny policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="disabled-deny-policy",
        rules_json={"deny": [tool.name]},
        enabled=False,  # Disabled
    )

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Run should succeed (disabled deny policy ignored)
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == RUN_STATUS_SUCCEEDED


# ========== Policy-Konflikte & Scoping ==========


@pytest.mark.django_db
def test_cross_policy_deny_beats_allow(agent_tool):
    """Test that deny in one policy beats allow in another policy."""
    agent, tool = agent_tool

    # Policy A allows
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Policy B denies
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="deny-policy",
        rules_json={"deny": [tool.name]},
        enabled=True,
    )

    # Should be denied (deny beats allow across policies)
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "denied" in run.error_text.lower()


@pytest.mark.django_db
def test_policy_from_different_org_not_applied(agent_tool):
    """Test that policies from different organization are not applied."""
    agent, tool = agent_tool

    # Create policy in different organization
    other_org = Organization.objects.create(name="OtherOrg")
    Policy.objects.create(
        organization=other_org,
        environment=None,
        name="other-org-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Should be denied (policy from different org doesn't apply)
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "No policy explicitly allows" in run.error_text


@pytest.mark.django_db
def test_policy_from_different_env_not_applied(agent_tool):
    """Test that policies from different environment are not applied."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Create different environment
    other_env = Environment.objects.create(organization=org, name="prod", type="prod")

    # Create policy in different environment
    Policy.objects.create(
        organization=org,
        environment=other_env,
        name="other-env-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Should be denied (policy from different env doesn't apply)
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "No policy explicitly allows" in run.error_text


@pytest.mark.django_db
def test_org_wide_allow_env_specific_deny_denies(agent_tool):
    """Test that env-specific deny beats org-wide allow."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Org-wide allow policy
    Policy.objects.create(
        organization=org,
        environment=None,
        name="org-wide-allow",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Env-specific deny policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="env-specific-deny",
        rules_json={"deny": [tool.name]},
        enabled=True,
    )

    # Should be denied (env-specific deny beats org-wide allow)
    with pytest.raises(ValueError, match="Policy denied"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "denied" in run.error_text.lower()


@pytest.mark.django_db
def test_org_wide_policy_applies_to_all_envs(agent_tool):
    """Test that org-wide policy (env=None) applies to all environments."""
    agent, tool = agent_tool

    # Create org-wide allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=None,
        name="org-wide-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Should be allowed (org-wide policy applies to all envs)
    run = start_run(agent=agent, tool=tool, input_json={"x": 1})
    assert run.status == RUN_STATUS_SUCCEEDED


# ========== Rate-Limit Entsperrung ==========


@pytest.mark.django_db
def test_rate_limit_unblocks_after_run_completes(agent_tool):
    """Test that rate limit unblocks after run completes."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Clear cache
    cache.clear()

    limiter = RateLimiter()

    # Create max concurrent runs (5)
    runs = []
    for _ in range(5):
        run = Run.objects.create(
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status=RUN_STATUS_RUNNING,
            started_at=timezone.now(),
        )
        runs.append(run)

    # Next run should be blocked
    allowed, reason = limiter.check_rate_limit(agent, max_concurrent_runs=5)
    assert not allowed
    assert "concurrent" in reason.lower()

    # Complete one run (set to succeeded)
    runs[0].status = RUN_STATUS_SUCCEEDED
    runs[0].ended_at = timezone.now()
    runs[0].save()

    # Now should be allowed (one slot freed)
    allowed, reason = limiter.check_rate_limit(agent, max_concurrent_runs=5)
    assert allowed
    assert reason is None

    # Clean up
    Run.objects.filter(agent=agent).delete()


@pytest.mark.django_db
def test_rate_limit_blocks_in_start_run(agent_tool):
    """Test that rate limit blocks run in start_run and creates audit log."""
    agent, tool = agent_tool

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Clear cache
    cache.clear()

    # Create max concurrent runs
    for _ in range(5):
        Run.objects.create(
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status=RUN_STATUS_RUNNING,
            started_at=timezone.now(),
        )

    # Attempt to start run should fail due to rate limit
    with pytest.raises(ValueError, match="Rate limit"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    runs = Run.objects.filter(agent=agent, tool=tool).order_by("-created_at")
    assert runs.count() == 6  # 5 running + 1 failed
    failed_run = runs.first()
    assert failed_run.status == RUN_STATUS_FAILED
    assert "Rate limit" in failed_run.error_text

    # Verify audit log for rate limit
    audit = AuditEvent.objects.filter(event_type="run_denied_rate_limit").first()
    assert audit is not None
    assert audit.event_data["agent_id"] == str(agent.id)
    assert audit.event_data["tool_id"] == str(tool.id)

    # Clean up
    Run.objects.filter(agent=agent).delete()


# ========== Tool/Agent-Zustände ==========


@pytest.mark.django_db
def test_tool_not_synced_blocks_run(agent_tool):
    """Test that tool with sync_status != 'synced' blocks run."""
    agent, tool = agent_tool

    # Set tool to not synced
    tool.sync_status = "failed"
    tool.save()

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Attempt to start run should fail
    with pytest.raises(ValueError, match="sync status"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "sync status" in run.error_text.lower()

    # Verify audit log
    audit = AuditEvent.objects.filter(event_type="run_denied_sync_status").first()
    assert audit is not None
    assert audit.event_data["tool_id"] == str(tool.id)
    assert audit.event_data["sync_status"] == "failed"


@pytest.mark.django_db
def test_tool_stale_status_blocks_run(agent_tool):
    """Test that tool with sync_status='stale' blocks run."""
    agent, tool = agent_tool

    # Set tool to stale
    tool.sync_status = "stale"
    tool.save()

    # Create allow policy
    Policy.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Attempt to start run should fail
    with pytest.raises(ValueError, match="sync status"):
        start_run(agent=agent, tool=tool, input_json={"x": 1})

    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "stale" in run.error_text.lower()


@pytest.mark.django_db
def test_tool_no_connection_blocks_run(agent_tool):
    """Test that tool without connection blocks run."""
    agent, tool = agent_tool
    org, env = agent.organization, agent.environment

    # Create allow policy
    Policy.objects.create(
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    # Mock tool.connection to return None to simulate no connection
    # (Can't set connection=None directly due to NOT NULL constraint in DB)
    from unittest.mock import PropertyMock
    
    with patch.object(type(tool), 'connection', PropertyMock(return_value=None)):
        # Attempt to start run should fail
        with pytest.raises(ValueError, match="no connection"):
            start_run(agent=agent, tool=tool, input_json={"x": 1})

    # Verify run was created and marked as failed
    run = Run.objects.get(agent=agent, tool=tool)
    assert run.status == RUN_STATUS_FAILED
    assert "no connection" in run.error_text.lower()

    # Verify audit log
    audit = AuditEvent.objects.filter(event_type="run_denied_no_connection").first()
    assert audit is not None
    assert audit.event_data["tool_id"] == str(tool.id)

