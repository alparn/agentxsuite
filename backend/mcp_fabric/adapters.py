"""
Adapters for bridging fastmcp tool handlers to AgentxSuite Django services.
"""
from __future__ import annotations

import logging
from typing import Any

from apps.agents.models import Agent
from apps.runs.services import start_run
from apps.tools.models import Tool
from mcp_fabric.pep import check_policy_before_tool_call

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
    # P0: Use resolved agent_id (from token via subject/issuer mapping)
    # token_agent_id is now the resolved agent_id from deps (source of truth)
    # agent_id from payload/query must match or be None
    
    final_agent_id = token_agent_id  # Use resolved agent_id (source of truth)
    
    # If agent_id provided in payload/query, it must match resolved agent_id
    if agent_id and agent_id != token_agent_id:
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
    
    # Determine agent (must use resolved agent_id)
    if final_agent_id:
        agent = Agent.objects.filter(
            organization=tool.organization,
            environment=tool.environment,
            id=final_agent_id,
            enabled=True,
        ).first()
        if not agent:
            logger.warning(
                f"Agent {final_agent_id} not found for tool {tool.name}",
                extra={
                    "tool_id": str(tool.id),
                    "agent_id": final_agent_id,
                    "org_id": str(tool.organization.id),
                    "env_id": str(tool.environment.id),
                },
            )
            return {"status": "error", "error": "agent_not_found"}
    else:
        agent = (
            Agent.objects.filter(
                organization=tool.organization,
                environment=tool.environment,
                enabled=True,
            )
            .order_by("-created_at")
            .first()
        )
        if not agent:
            logger.warning(
                f"No active agent found for tool {tool.name}",
                extra={
                    "tool_id": str(tool.id),
                    "org_id": str(tool.organization.id),
                    "env_id": str(tool.environment.id),
                },
            )
            return {"status": "error", "error": "no_active_agent"}

    # PEP: Policy Enforcement Point - check policy BEFORE tool execution (deny-by-default)
    # P0: Pass audit metadata (jti, ip, request_id) for forensics
    allowed, deny_reason = check_policy_before_tool_call(
        agent_id=str(agent.id),
        tool=tool,
        payload=payload,
        jti=jti,
        client_ip=client_ip,
        request_id=request_id,
    )
    if not allowed:
        logger.warning(
            f"PEP denied tool execution: {tool.name}",
            extra={
                "agent_id": str(agent.id),
                "tool_id": str(tool.id),
                "reason": deny_reason,
            },
        )
        return {
            "status": "error",
            "error": "policy_denied",
            "error_description": deny_reason or "Policy denied",
        }

    # Start run (uses our security: Policy, Schema, Rate, Timeout, Audit)
    # Note: start_run also checks policy, but PEP check is explicit for MCP calls
    try:
        run = start_run(agent=agent, tool=tool, input_json=payload, timeout_seconds=30)

        if run.status == "succeeded":
            return {
                "status": "success",
                "output": run.output_json,
                "run_id": str(run.id),
            }

        return {
            "status": "error",
            "error": run.error_text or "execution_failed",
            "run_id": str(run.id),
        }
    except Exception as e:
        # Don't leak internal details
        logger.error(
            f"Error executing tool {tool.name} via AgentxSuite",
            extra={
                "tool_id": str(tool.id),
                "agent_id": str(agent.id),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return {"status": "error", "error": "execution_failed"}

