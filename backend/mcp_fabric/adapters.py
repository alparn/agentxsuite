"""
Adapters for bridging fastmcp tool handlers to AgentxSuite Django services.
"""
from __future__ import annotations

import logging
from typing import Any

from apps.agents.models import Agent
from apps.runs.services import start_run
from apps.tools.models import Tool

logger = logging.getLogger(__name__)


def run_tool_via_agentxsuite(
    *,
    tool: Tool,
    payload: dict[str, Any],
    agent_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute a tool via AgentxSuite Django services.

    This adapter bridges fastmcp tool handlers to our Django service layer,
    ensuring all security checks (Policy, Schema Validation, Rate Limit,
    Timeout, Audit) are executed.

    Args:
        tool: Tool instance from Django ORM
        payload: Tool input arguments as dictionary
        agent_id: Optional agent ID. If not provided, uses the newest active
                  agent in the same organization/environment

    Returns:
        Dictionary with status, output/error, and optional run_id:
        - {"status": "success", "output": {...}, "run_id": "..."}
        - {"status": "error", "error": "error_code", "run_id": "..."}
    """
    # Determine agent
    if agent_id:
        agent = Agent.objects.filter(
            organization=tool.organization,
            environment=tool.environment,
            id=agent_id,
            enabled=True,
        ).first()
        if not agent:
            logger.warning(
                f"Agent {agent_id} not found for tool {tool.name}",
                extra={
                    "tool_id": str(tool.id),
                    "agent_id": agent_id,
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

    # Start run (uses our security: Policy, Schema, Rate, Timeout, Audit)
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

