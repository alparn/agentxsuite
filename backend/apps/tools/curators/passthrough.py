"""Fallback curator that exposes raw tools one-to-one."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from apps.tools.curators.base import BaseCurator, RawToolExecutor

if TYPE_CHECKING:
    from apps.connections.models import Connection
    from apps.tools.models import CuratedTool, Tool


class PassthroughCurator(BaseCurator):
    """Fallback curator for unknown MCP servers or explicit passthrough mode."""

    curator_type = "passthrough"

    def can_curate(self, connection: Connection, raw_tools: Sequence[Tool]) -> bool:
        """Always return true so this curator can act as the registry fallback."""
        return True

    def generate_curated_tools(
        self,
        connection: Connection,
        raw_tools: Sequence[Tool],
    ) -> list[dict[str, Any]]:
        """Expose every enabled raw tool as a 1:1 curated tool."""
        curated_tools: list[dict[str, Any]] = []

        for tool in raw_tools:
            schema = tool.schema_json or {"type": "object", "properties": {}}
            description = schema.get("description") if isinstance(schema, dict) else None
            curated_tools.append(
                {
                    "name": tool.name,
                    "display_name": tool.name.replace("_", " ").title(),
                    "description": description or f"Tool: {tool.name}",
                    "schema_json": schema,
                    "category": "general",
                    "raw_tool_names": [tool.name],
                    "orchestration_config": {
                        "strategy": "passthrough",
                        "raw_tool": tool.name,
                    },
                }
            )

        return curated_tools

    def orchestrate_execution(
        self,
        curated_tool: CuratedTool,
        input_data: dict[str, Any],
        executor_func: RawToolExecutor,
    ) -> dict[str, Any]:
        """Execute the single mapped raw tool with the curated input unchanged."""
        mapping = curated_tool.mappings.select_related("raw_tool").order_by("execution_order").first()
        if not mapping:
            raise ValueError(f"Curated tool '{curated_tool.name}' has no raw tool mapping")

        return executor_func(mapping.raw_tool, input_data)

