"""
Unit tests for runs service happy path.
"""
from __future__ import annotations

import pytest
from django.test import override_settings
from freezegun import freeze_time

from apps.runs.services import start_run
from apps.runs.tests.conftest import create_policy_with_rules
from apps.tools.curation_service import CurationService
from apps.tools.curators.passthrough import PassthroughCurator


@pytest.mark.django_db
def test_start_run_success(org_env, agent_tool, mock_outbound_mcp_call):
    """Test that start_run creates a run with correct status and timestamps."""
    org, env = org_env
    agent, tool = agent_tool
    
    with freeze_time("2024-01-01 12:00:00"):
        # Create allow policy (required for default deny)
        create_policy_with_rules(
            org=org,
            env=env,
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
        assert mock_outbound_mcp_call == [
            {
                "connection_id": str(tool.connection.id),
                "name": tool.name,
                "arguments": {"x": 1},
            }
        ]


@pytest.mark.django_db
def test_start_run_with_empty_input(org_env, agent_tool):
    """Test that start_run handles empty input correctly."""
    org, env = org_env
    agent, tool = agent_tool

    # Create allow policy (required for default deny)
    create_policy_with_rules(
        org=org,
        env=env,
        name="allow-policy",
        rules_json={"allow": [tool.name]},
        enabled=True,
    )

    run = start_run(agent=agent, tool=tool, input_json={})

    assert run.status == "succeeded"
    assert run.input_json == {}
    # For MCP Fabric own service, output_json contains status and message
    assert run.output_json.get("status") == "success" or run.output_json.get("ok") is True


@pytest.mark.django_db
@override_settings(TOOL_CURATION_ENABLED=True, AGENT_TOOL_MODE="curated_only")
def test_start_run_success_with_curated_tool(
    org_env,
    agent_tool,
    mock_outbound_mcp_call,
):
    """Curated runs pass through the normal security gates and execute mapped raw tools."""
    org, env = org_env
    agent, raw_tool = agent_tool
    curated_tool = CurationService.generate_curated_tools(
        connection=raw_tool.connection,
        raw_tools=[raw_tool],
        curator=PassthroughCurator(),
    )[0]
    create_policy_with_rules(
        org=org,
        env=env,
        name="allow-curated-policy",
        rules_json={"allow": [curated_tool.name]},
        enabled=True,
    )

    run = start_run(agent=agent, tool=curated_tool, input_json={"x": 1})

    assert run.status == "succeeded"
    assert run.tool is None
    assert run.curated_tool == curated_tool
    assert run.output_json.get("ok") is True
    assert mock_outbound_mcp_call == [
        {
            "connection_id": str(raw_tool.connection.id),
            "name": raw_tool.name,
            "arguments": {"x": 1},
        }
    ]

