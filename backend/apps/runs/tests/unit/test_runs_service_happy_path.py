"""
Unit tests for runs service happy path.
"""
from __future__ import annotations

import pytest
from freezegun import freeze_time
from model_bakery import baker

from apps.policies.models import Policy
from apps.runs.services import start_run


@pytest.mark.django_db
def test_start_run_success(org_env, agent_tool):
    """Test that start_run creates a run with correct status and timestamps."""
    org, env = org_env
    agent, tool = agent_tool
    
    with freeze_time("2024-01-01 12:00:00"):
        # Create allow policy (required for default deny)
        baker.make(
            Policy,
            organization=org,
            environment=env,
            name="allow-policy",
            rules_json={"allow": [tool.name]},
            enabled=True,
        )

        # Run service
        run = start_run(agent=agent, tool=tool, input_json={"x": 1})

        # Assertions
        assert run.status == "succeeded"
        # For MCP Fabric own service, output_json contains status and message
        assert run.output_json.get("status") == "success" or run.output_json.get("ok") is True
        assert run.started_at is not None
        assert run.ended_at is not None
        assert run.input_json == {"x": 1}
        assert run.organization == org
        assert run.environment == env
        assert run.agent == agent
        assert run.tool == tool


@pytest.mark.django_db
def test_start_run_with_empty_input(org_env, agent_tool):
    """Test that start_run handles empty input correctly."""
    org, env = org_env
    agent, tool = agent_tool

    # Create allow policy (required for default deny)
    baker.make(
        Policy,
        organization=org,
        environment=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    run = start_run(agent=agent, tool=tool, input_json={})

    assert run.status == "succeeded"
    assert run.input_json == {}
    # For MCP Fabric own service, output_json contains status and message
    assert run.output_json.get("status") == "success" or run.output_json.get("ok") is True

