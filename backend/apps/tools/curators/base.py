"""Base interfaces for transforming raw MCP tools into curated tools."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.connections.models import Connection
    from apps.tools.models import CuratedTool, Tool

CuratedToolDefinition = dict[str, Any]
RawToolExecutor = Callable[[Any, dict[str, Any]], dict[str, Any]]


class BaseCurator(ABC):
    """Base class for connection-specific tool curation and execution."""

    curator_type = "base"

    @abstractmethod
    def can_curate(self, connection: Connection, raw_tools: Sequence[Tool]) -> bool:
        """Return whether this curator can handle the given connection."""

    @abstractmethod
    def generate_curated_tools(
        self,
        connection: Connection,
        raw_tools: Sequence[Tool],
    ) -> list[CuratedToolDefinition]:
        """Generate agent-facing tool definitions from raw MCP tools."""

    @abstractmethod
    def orchestrate_execution(
        self,
        curated_tool: CuratedTool,
        input_data: dict[str, Any],
        executor_func: RawToolExecutor,
    ) -> dict[str, Any]:
        """Execute a curated tool by invoking one or more raw tools."""

