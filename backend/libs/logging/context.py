"""
Context variables for request-scoped IDs (trace_id, run_id, request_id).

These ContextVars are set by middleware and automatically injected into logs.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

# Context variables for request-scoped IDs
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_org_id: ContextVar[str | None] = ContextVar("org_id", default=None)
_env_id: ContextVar[str | None] = ContextVar("env_id", default=None)
_agent_id: ContextVar[str | None] = ContextVar("agent_id", default=None)
_tool_id: ContextVar[str | None] = ContextVar("tool_id", default=None)


def set_context_ids(
    *,
    trace_id: str | None = None,
    run_id: str | None = None,
    request_id: str | None = None,
    org_id: str | None = None,
    env_id: str | None = None,
    agent_id: str | None = None,
    tool_id: str | None = None,
) -> None:
    """
    Set context IDs for the current request context.

    These values will be automatically included in all log records
    within this context (via ContextFilter).

    Args:
        trace_id: OpenTelemetry trace ID
        run_id: Run UUID
        request_id: Request ID (from header or generated)
        org_id: Organization UUID
        env_id: Environment UUID
        agent_id: Agent UUID
        tool_id: Tool UUID
    """
    if trace_id:
        _trace_id.set(trace_id)
    if run_id:
        _run_id.set(run_id)
    if request_id:
        _request_id.set(request_id)
    if org_id:
        _org_id.set(org_id)
    if env_id:
        _env_id.set(env_id)
    if agent_id:
        _agent_id.set(agent_id)
    if tool_id:
        _tool_id.set(tool_id)


def get_context_ids() -> dict[str, str | None]:
    """
    Get all context IDs from the current request context.

    Returns:
        Dictionary with trace_id, run_id, request_id, org_id, env_id, agent_id, tool_id
    """
    return {
        "trace_id": _trace_id.get(),
        "run_id": _run_id.get(),
        "request_id": _request_id.get(),
        "org_id": _org_id.get(),
        "env_id": _env_id.get(),
        "agent_id": _agent_id.get(),
        "tool_id": _tool_id.get(),
    }


def clear_context_ids() -> None:
    """Clear all context IDs (useful for testing or cleanup)."""
    _trace_id.set(None)
    _run_id.set(None)
    _request_id.set(None)
    _org_id.set(None)
    _env_id.set(None)
    _agent_id.set(None)
    _tool_id.set(None)

