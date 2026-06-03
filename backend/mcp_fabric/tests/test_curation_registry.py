"""Tests for curated tool exposure through the MCP registry."""
from __future__ import annotations

import pytest
from django.test import override_settings
from model_bakery import baker

from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from apps.tools.models import CuratedTool, Tool
from mcp_fabric.registry import get_tools_list_for_org_env


@pytest.mark.django_db
@override_settings(TOOL_CURATION_ENABLED=True, AGENT_TOOL_MODE="curated_only")
def test_registry_lists_curated_tools_when_curation_enabled():
    """Agent-facing MCP lists use CuratedTool when curation is enabled."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="dev", type="dev")
    conn = baker.make(Connection, organization=org, environment=env, name="remote")
    baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="raw_search",
        enabled=True,
        is_agent_visible=True,
    )
    baker.make(
        CuratedTool,
        organization=org,
        environment=env,
        connection=conn,
        name="search_docs",
        display_name="Search Docs",
        description="Search curated docs.",
        schema_json={"type": "object", "properties": {"query": {"type": "string"}}},
        curator_type="passthrough",
        enabled=True,
    )

    tools = get_tools_list_for_org_env(org=org, env=env)
    tool_names = {tool["name"] for tool in tools}

    assert "search_docs" in tool_names
    assert "raw_search" not in tool_names


@pytest.mark.django_db
@override_settings(TOOL_CURATION_ENABLED=True, AGENT_TOOL_MODE="curated_and_raw")
def test_registry_lists_curated_and_agent_visible_raw_tools():
    """Power users can expose selected raw tools alongside curated tools."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="dev", type="dev")
    conn = baker.make(Connection, organization=org, environment=env, name="remote")
    baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="visible_raw",
        enabled=True,
        is_agent_visible=True,
    )
    baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="hidden_raw",
        enabled=True,
        is_agent_visible=False,
    )
    baker.make(
        CuratedTool,
        organization=org,
        environment=env,
        connection=conn,
        name="curated_search",
        display_name="Curated Search",
        curator_type="passthrough",
        enabled=True,
    )

    tools = get_tools_list_for_org_env(org=org, env=env)
    tool_names = {tool["name"] for tool in tools}

    assert "curated_search" in tool_names
    assert "visible_raw" in tool_names
    assert "hidden_raw" not in tool_names

