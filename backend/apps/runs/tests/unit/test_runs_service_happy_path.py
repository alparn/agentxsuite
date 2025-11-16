"""
Unit tests for runs service happy path.
"""
from __future__ import annotations

import pytest
from freezegun import freeze_time

from apps.agents.models import Agent
from apps.policies.models import Policy
from apps.runs.services import start_run
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


@pytest.mark.django_db
def test_start_run_success():
    """Test that start_run creates a run with correct status and timestamps."""
    with freeze_time("2024-01-01 12:00:00"):
        # Create test data
        org = Organization.objects.create(name="TestOrg")
        env = Environment.objects.create(organization=org, name="dev", type="dev")
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost:8090",  # Use localhost to trigger "own service" path
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

        # Create allow policy (required for default deny)
        Policy.objects.create(
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
def test_start_run_with_empty_input():
    """Test that start_run handles empty input correctly."""
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="dev", type="dev")
    from apps.connections.models import Connection

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="http://localhost:8090",  # Use localhost to trigger "own service" path
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

    # Create allow policy (required for default deny)
    Policy.objects.create(
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

