"""Services for generating and executing curated tools."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from time import monotonic
from typing import Any

from django.db import transaction
from django.db.models import F

from apps.connections.models import Connection
from apps.tools.curators.base import BaseCurator, RawToolExecutor
from apps.tools.curators.registry import CuratorsRegistry
from apps.tools.models import CuratedTool, CurationMapping, Tool

logger = logging.getLogger(__name__)


class CurationService:
    """Service layer for curated tool lifecycle and execution."""

    @staticmethod
    @transaction.atomic
    def generate_curated_tools(
        *,
        connection: Connection,
        raw_tools: Sequence[Tool],
        curator: BaseCurator | None = None,
    ) -> list[CuratedTool]:
        """Create or update curated tools for a connection from raw tool definitions."""
        enabled_raw_tools = [tool for tool in raw_tools if tool.enabled]
        selected_curator = curator or CuratorsRegistry.get_curator(connection, enabled_raw_tools)
        raw_tools_by_name = {tool.name: tool for tool in enabled_raw_tools}
        curated_defs = selected_curator.generate_curated_tools(connection, enabled_raw_tools)
        curated_tools: list[CuratedTool] = []

        for curated_def in curated_defs:
            name = curated_def.get("name")
            if not name:
                logger.warning("Skipping curated tool definition without name")
                continue

            curated_tool, _created = CuratedTool.objects.update_or_create(
                organization=connection.organization,
                environment=connection.environment,
                name=name,
                defaults={
                    "connection": connection,
                    "display_name": curated_def.get("display_name") or name,
                    "description": curated_def.get("description", ""),
                    "schema_json": curated_def.get("schema_json") or {"type": "object"},
                    "curator_type": selected_curator.curator_type,
                    "orchestration_config": curated_def.get("orchestration_config", {}),
                    "enabled": curated_def.get("enabled", True),
                    "category": curated_def.get("category", ""),
                    "tags": curated_def.get("tags", []),
                },
            )
            curated_tool.full_clean()
            curated_tool.save()

            CurationService._replace_mappings(
                curated_tool=curated_tool,
                raw_tools_by_name=raw_tools_by_name,
                raw_tool_names=curated_def.get("raw_tool_names", []),
                orchestration_config=curated_def.get("orchestration_config", {}),
            )
            curated_tools.append(curated_tool)

        logger.info(
            "Generated curated tools",
            extra={
                "connection_id": str(connection.id),
                "curator_type": selected_curator.curator_type,
                "curated_tool_count": len(curated_tools),
            },
        )
        return curated_tools

    @staticmethod
    def execute_curated_tool(
        *,
        curated_tool: CuratedTool,
        input_data: dict[str, Any],
        executor_func: RawToolExecutor,
    ) -> dict[str, Any]:
        """Execute a curated tool through its configured curator and raw-tool executor."""
        curator = CuratorsRegistry.get_curator_by_type(curated_tool.curator_type)
        started = monotonic()
        result = curator.orchestrate_execution(
            curated_tool=curated_tool,
            input_data=input_data,
            executor_func=executor_func,
        )
        elapsed_ms = int((monotonic() - started) * 1000)

        CuratedTool.objects.filter(id=curated_tool.id).update(
            usage_count=F("usage_count") + 1,
            avg_execution_time_ms=elapsed_ms,
        )
        curated_tool.usage_count += 1
        curated_tool.avg_execution_time_ms = elapsed_ms
        return result

    @staticmethod
    def _replace_mappings(
        *,
        curated_tool: CuratedTool,
        raw_tools_by_name: dict[str, Tool],
        raw_tool_names: Sequence[str],
        orchestration_config: dict[str, Any],
    ) -> None:
        """Replace mappings for a curated tool according to its orchestration config."""
        curated_tool.mappings.all().delete()

        steps = orchestration_config.get("steps")
        if isinstance(steps, list) and steps:
            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                raw_tool = raw_tools_by_name.get(step.get("tool"))
                if raw_tool:
                    CurationService._create_mapping(
                        curated_tool=curated_tool,
                        raw_tool=raw_tool,
                        execution_order=index,
                        parameter_mapping=step.get("parameter_mapping", {}),
                        condition=step.get("condition", ""),
                    )
            return

        for index, raw_tool_name in enumerate(raw_tool_names):
            raw_tool = raw_tools_by_name.get(raw_tool_name)
            if raw_tool:
                CurationService._create_mapping(
                    curated_tool=curated_tool,
                    raw_tool=raw_tool,
                    execution_order=index,
                    parameter_mapping={},
                    condition="",
                )

    @staticmethod
    def _create_mapping(
        *,
        curated_tool: CuratedTool,
        raw_tool: Tool,
        execution_order: int,
        parameter_mapping: dict[str, Any],
        condition: str,
    ) -> CurationMapping:
        """Create a validated curated-to-raw mapping."""
        mapping = CurationMapping(
            curated_tool=curated_tool,
            raw_tool=raw_tool,
            execution_order=execution_order,
            parameter_mapping=parameter_mapping,
            condition=condition,
        )
        mapping.full_clean()
        mapping.save()
        return mapping

