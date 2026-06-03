"""Unit tests for the tool curation service and passthrough curator."""
from __future__ import annotations

import pytest
from model_bakery import baker

from apps.connections.models import Connection
from apps.tools.curators.base import BaseCurator
from apps.tools.curation_service import CurationService
from apps.tools.curators.passthrough import PassthroughCurator
from apps.tools.models import CuratedTool, CurationMapping, Tool


class StepCurator(BaseCurator):
    """Test curator that emits an explicit multi-step orchestration config."""

    curator_type = "step-test"

    def can_curate(self, connection: Connection, raw_tools: list[Tool]) -> bool:
        return True

    def generate_curated_tools(
        self,
        connection: Connection,
        raw_tools: list[Tool],
    ) -> list[dict]:
        return [
            {},
            {
                "name": "combined_search",
                "display_name": "Combined Search",
                "description": "Runs raw tools in a configured order.",
                "schema_json": {"type": "object"},
                "raw_tool_names": ["ignored_when_steps_exist"],
                "orchestration_config": {
                    "steps": [
                        {
                            "tool": "search_docs",
                            "parameter_mapping": {"query": "q"},
                            "condition": "has_query",
                        },
                        "bad-step",
                        {"tool": "missing_tool"},
                        {"tool": "fetch_doc"},
                    ],
                },
            },
        ]

    def orchestrate_execution(self, curated_tool, input_data, executor_func):
        return {"ok": True}


@pytest.mark.django_db
def test_passthrough_curator_generates_one_curated_tool_per_raw_tool(org_env_conn):
    """Unknown MCP servers fall back to one-to-one curated tool definitions."""
    org, env, conn = org_env_conn
    raw_tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="search_docs",
        schema_json={
            "type": "object",
            "description": "Search documentation.",
            "properties": {"query": {"type": "string"}},
        },
    )

    generated = PassthroughCurator().generate_curated_tools(conn, [raw_tool])

    assert generated == [
        {
            "name": "search_docs",
            "display_name": "Search Docs",
            "description": "Search documentation.",
            "schema_json": raw_tool.schema_json,
            "category": "general",
            "raw_tool_names": ["search_docs"],
            "orchestration_config": {
                "strategy": "passthrough",
                "raw_tool": "search_docs",
            },
        }
    ]


@pytest.mark.django_db
def test_curation_service_creates_curated_tool_and_mapping(org_env_conn):
    """Generated curated tools are persisted with ordered raw-tool mappings."""
    org, env, conn = org_env_conn
    raw_tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="search_docs",
        schema_json={"type": "object", "properties": {"query": {"type": "string"}}},
        enabled=True,
    )

    curated_tools = CurationService.generate_curated_tools(
        connection=conn,
        raw_tools=[raw_tool],
        curator=PassthroughCurator(),
    )

    assert len(curated_tools) == 1
    curated_tool = curated_tools[0]
    assert curated_tool.name == "search_docs"
    assert curated_tool.curator_type == "passthrough"
    assert CuratedTool.objects.filter(connection=conn, name="search_docs").exists()
    mapping = CurationMapping.objects.get(curated_tool=curated_tool)
    assert mapping.raw_tool == raw_tool
    assert mapping.execution_order == 0


@pytest.mark.django_db
def test_curation_service_executes_passthrough_mapping(org_env_conn):
    """Passthrough execution delegates to the mapped raw tool unchanged."""
    org, env, conn = org_env_conn
    raw_tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="search_docs",
    )
    curated_tool = CurationService.generate_curated_tools(
        connection=conn,
        raw_tools=[raw_tool],
        curator=PassthroughCurator(),
    )[0]
    calls = []

    def fake_executor(tool: Tool, payload: dict) -> dict:
        calls.append((tool, payload))
        return {"ok": True, "payload": payload}

    result = CurationService.execute_curated_tool(
        curated_tool=curated_tool,
        input_data={"query": "mcp"},
        executor_func=fake_executor,
    )

    assert result == {"ok": True, "payload": {"query": "mcp"}}
    assert calls == [(raw_tool, {"query": "mcp"})]
    curated_tool.refresh_from_db()
    assert curated_tool.usage_count == 1
    assert curated_tool.avg_execution_time_ms is not None


@pytest.mark.django_db
def test_curation_service_replaces_mappings_from_steps(org_env_conn):
    """Step orchestration configs create ordered mappings with parameter metadata."""
    org, env, conn = org_env_conn
    search_tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="search_docs",
        enabled=True,
    )
    fetch_tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="fetch_doc",
        enabled=True,
    )

    curated_tool = CurationService.generate_curated_tools(
        connection=conn,
        raw_tools=[search_tool, fetch_tool],
        curator=StepCurator(),
    )[0]

    mappings = list(curated_tool.mappings.order_by("execution_order"))
    assert [mapping.raw_tool for mapping in mappings] == [search_tool, fetch_tool]
    assert [mapping.execution_order for mapping in mappings] == [0, 3]
    assert mappings[0].parameter_mapping == {"query": "q"}
    assert mappings[0].condition == "has_query"


@pytest.mark.django_db
def test_passthrough_execution_requires_mapping(org_env_conn):
    """Curated tools without mappings fail clearly during passthrough execution."""
    org, env, conn = org_env_conn
    curated_tool = baker.make(
        CuratedTool,
        organization=org,
        environment=env,
        connection=conn,
        name="orphan",
        curator_type="passthrough",
    )

    with pytest.raises(ValueError, match="has no raw tool mapping"):
        CurationService.execute_curated_tool(
            curated_tool=curated_tool,
            input_data={},
            executor_func=lambda _tool, _payload: {},
        )