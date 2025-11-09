"""
Policy services for access control checks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from django.db import models

from apps.policies.models import Policy

if TYPE_CHECKING:
    from apps.agents.models import Agent
    from apps.tools.models import Tool


def is_allowed(agent: Agent, tool: Tool, payload: dict) -> Tuple[bool, str | None]:
    """
    Check if agent is allowed to run tool with given payload.

    Default deny: Only allows if a matching policy explicitly permits it.

    Args:
        agent: Agent instance requesting the run
        tool: Tool instance to be executed
        payload: Input payload dictionary

    Returns:
        Tuple of (is_allowed: bool, reason: str | None)
        reason is None if allowed, otherwise contains denial reason
    """
    # Query policies matching organization and optionally environment
    policies = Policy.objects.filter(
        organization=agent.organization,
        enabled=True,
    )

    # Filter by environment if policy has environment set
    policies = policies.filter(
        models.Q(environment__isnull=True) | models.Q(environment=agent.environment)
    )

    # Check deny list first (most restrictive)
    for policy in policies:
        deny_list = policy.rules_json.get("deny", [])
        if isinstance(deny_list, list):
            if tool.name in deny_list:
                return False, f"Tool '{tool.name}' denied by policy '{policy.name}'"

    # Check allow list (explicit allow)
    for policy in policies:
        allow_list = policy.rules_json.get("allow", [])
        if isinstance(allow_list, list):
            if tool.name in allow_list:
                return True, None

    # Default deny if no explicit allow
    return False, "No policy explicitly allows this tool"
