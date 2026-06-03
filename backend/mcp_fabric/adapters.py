"""
Adapters for bridging fastmcp tool handlers to AgentxSuite Django services.
"""
from __future__ import annotations

import logging
from typing import Any

from apps.runs.services import ExecutionContext, execute_tool_run
from apps.tools.models import Tool

logger = logging.getLogger(__name__)


def run_tool_via_agentxsuite(
    *,
    tool: Tool,
    payload: dict[str, Any],
    agent_id: str | None = None,
    token_agent_id: str | None = None,
    jti: str | None = None,
    client_ip: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute a tool via AgentxSuite Django services.

    This adapter bridges fastmcp tool handlers to our Django service layer,
    ensuring all security checks (Policy, Schema Validation, Rate Limit,
    Timeout, Audit) are executed.

    Args:
        tool: Tool instance from Django ORM
        payload: Tool input arguments as dictionary
        agent_id: Optional agent ID from payload/query. If provided, must match token_agent_id.
        token_agent_id: Agent ID from token claims (Session-Lock). If set, agent_id must match.

    Returns:
        Dictionary with status, output/error, and optional run_id:
        - {"status": "success", "output": {...}, "run_id": "..."}
        - {"status": "error", "error": "error_code", "run_id": "..."}
    """
    # If agent_id provided in payload/query, it must match resolved agent_id
    if agent_id and token_agent_id and agent_id != token_agent_id:
        logger.warning(
            f"Agent ID mismatch: resolved agent_id is '{token_agent_id}' but request specifies '{agent_id}'",
            extra={
                "tool_id": str(tool.id),
                "resolved_agent_id": token_agent_id,
                "request_agent_id": agent_id,
                "org_id": str(tool.organization.id),
                "env_id": str(tool.environment.id),
            },
        )
        return {
            "status": "error",
            "error": "agent_session_mismatch",
            "error_description": (
                f"Agent ID mismatch: resolved agent_id is '{token_agent_id}' but request specifies '{agent_id}'. "
                "Agent cannot be changed during session."
            ),
        }

    # Execute through the unified service; start_run is the single PDP-backed gate.
    try:
        result = execute_tool_run(
            organization=tool.organization,
            environment=tool.environment,
            tool_identifier=str(tool.id),
            agent_identifier=agent_id,
            input_data=payload,
            context=ExecutionContext(
                token_agent_id=token_agent_id,
                jti=jti,
                client_ip=client_ip,
                request_id=request_id,
            ),
            timeout_seconds=30,
        )

        if result["status"] == "succeeded":
            return {
                "status": "success",
                "output": result,
                "run_id": result["run_id"],
            }

        return {
            "status": "error",
            "error": result["content"][0]["text"] if result.get("content") else "execution_failed",
            "run_id": result.get("run_id"),
        }
    except Exception as e:
        # Don't leak internal details
        error_text = str(e)
        if "Agent mismatch" in error_text:
            return {
                "status": "error",
                "error": "agent_session_mismatch",
                "error_description": error_text,
            }
        if "not found" in error_text:
            return {"status": "error", "error": "agent_not_found"}
        if "Policy denied" in error_text:
            return {
                "status": "error",
                "error": "policy_denied",
                "error_description": error_text,
            }

        logger.error(
            f"Error executing tool {tool.name} via AgentxSuite",
            extra={
                "tool_id": str(tool.id),
                "agent_id": token_agent_id or agent_id,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return {"status": "error", "error": "execution_failed"}

