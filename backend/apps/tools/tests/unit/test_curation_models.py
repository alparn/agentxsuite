"""
Unit tests for tool curation models.
"""
from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from model_bakery import baker

from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from apps.tools.models import CuratedTool, CurationMapping, Tool


@pytest.mark.django_db
def test_raw_tools_are_hidden_from_agents_by_default(org_env_conn):
    """Raw synced tools must not be agent-visible unless explicitly enabled."""
    org, env, conn = org_env_conn

    tool = Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="execute_query",
        schema_json={"type": "object"},
    )

    assert tool.is_agent_visible is False


@pytest.mark.django_db
def test_curated_tool_maps_raw_tools_in_execution_order(org_env_conn):
    """Curated tools can aggregate raw tools via ordered mappings."""
    org, env, conn = org_env_conn
    list_tables = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="list_tables",
    )
    execute_query = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="execute_query",
    )
    curated_tool = CuratedTool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="query_database",
        display_name="Query Database",
        description="Run safe database queries.",
        schema_json={"type": "object"},
        curator_type="postgres",
        category="database",
        orchestration_config={"strategy": "sequential"},
    )

    CurationMapping.objects.create(
        curated_tool=curated_tool,
        raw_tool=list_tables,
        execution_order=0,
    )
    CurationMapping.objects.create(
        curated_tool=curated_tool,
        raw_tool=execute_query,
        execution_order=1,
        parameter_mapping={"query": "sql"},
    )

    assert list(curated_tool.raw_tools.order_by("curation_mappings__execution_order")) == [
        list_tables,
        execute_query,
    ]
    assert list(curated_tool.mappings.values_list("raw_tool__name", flat=True)) == [
        "list_tables",
        "execute_query",
    ]


@pytest.mark.django_db
def test_curated_tool_rejects_connection_from_different_environment(org_env_conn):
    """Curated tools must stay inside one organization/environment boundary."""
    org, env, _conn = org_env_conn
    other_env = baker.make(Environment, organization=org, name="prod", type="prod")
    other_conn = baker.make(
        Connection,
        organization=org,
        environment=other_env,
        name="other-conn",
        endpoint="https://other.example.com",
        auth_method="none",
    )
    curated_tool = CuratedTool(
        organization=org,
        environment=env,
        connection=other_conn,
        name="query_database",
        display_name="Query Database",
        curator_type="postgres",
    )

    with pytest.raises(ValidationError) as exc_info:
        curated_tool.full_clean()

    assert "connection" in exc_info.value.message_dict


@pytest.mark.django_db
def test_curation_mapping_rejects_raw_tool_from_different_connection(org_env_conn):
    """Mappings cannot cross connection boundaries."""
    org, env, conn = org_env_conn
    other_conn = baker.make(
        Connection,
        organization=org,
        environment=env,
        name="other-conn",
        endpoint="https://other.example.com",
        auth_method="none",
    )
    raw_tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=other_conn,
        name="execute_query",
    )
    curated_tool = CuratedTool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="query_database",
        display_name="Query Database",
        curator_type="postgres",
    )
    mapping = CurationMapping(
        curated_tool=curated_tool,
        raw_tool=raw_tool,
        execution_order=0,
    )

    with pytest.raises(ValidationError) as exc_info:
        mapping.full_clean()

    assert "raw_tool" in exc_info.value.message_dict


@pytest.mark.django_db
def test_tool_rejects_environment_from_different_organization(org_env_conn):
    """Raw tool org/env fields must refer to the same tenant boundary."""
    org, _env, conn = org_env_conn
    other_org = baker.make(Organization, name="OtherOrg")
    other_env = baker.make(Environment, organization=other_org, name="dev", type="dev")
    tool = Tool(
        organization=org,
        environment=other_env,
        connection=conn,
        name="execute_query",
        schema_json={"type": "object"},
    )

    with pytest.raises(ValidationError) as exc_info:
        tool.full_clean()

    assert "environment" in exc_info.value.message_dict
