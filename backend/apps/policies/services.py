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


def is_allowed_resource(
    agent: Agent, resource_name: str, action: str = "read"
) -> Tuple[bool, str | None]:
    """
    Check if agent is allowed to access resource with given action.

    Default deny: Only allows if a matching policy explicitly permits it.

    Args:
        agent: Agent instance requesting access
        resource_name: Resource name
        action: Action type (default: "read")

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
        deny_resources = policy.rules_json.get("deny_resources", [])
        if isinstance(deny_resources, list):
            if resource_name in deny_resources:
                return (
                    False,
                    f"Resource '{resource_name}' denied by policy '{policy.name}'",
                )

    # Check allow list (explicit allow)
    for policy in policies:
        allow_resources = policy.rules_json.get("allow_resources", [])
        if isinstance(allow_resources, list):
            if resource_name in allow_resources:
                return True, None

    # Default deny if no explicit allow
    return False, f"No policy explicitly allows resource '{resource_name}'"


def is_allowed_prompt(
    agent: Agent, prompt_name: str, action: str = "invoke"
) -> Tuple[bool, str | None]:
    """
    Check if agent is allowed to invoke prompt with given action.

    Default deny: Only allows if a matching policy explicitly permits it.
    Checks both new PolicyRule system and legacy rules_json.

    Args:
        agent: Agent instance requesting access
        prompt_name: Prompt name
        action: Action type (default: "invoke")

    Returns:
        Tuple of (is_allowed: bool, reason: str | None)
        reason is None if allowed, otherwise contains denial reason
    """
    from apps.policies.models import PolicyBinding, PolicyRule
    from fnmatch import fnmatch
    
    # Query policies matching organization and optionally environment
    policies = Policy.objects.filter(
        organization=agent.organization,
        enabled=True,
    )

    # Filter by environment if policy has environment set
    policies = policies.filter(
        models.Q(environment__isnull=True) | models.Q(environment=agent.environment)
    )
    
    # NEW: Check PolicyRule system first (takes precedence)
    # Get bindings for this agent
    agent_bindings = PolicyBinding.objects.filter(
        scope_type="agent",
        scope_id=str(agent.id),
    ).select_related("policy")
    
    # Check all rules from bound policies
    for binding in agent_bindings:
        policy = binding.policy
        if not policy.is_active:
            continue
            
        # Get rules for this policy with action="prompt.invoke"
        rules = PolicyRule.objects.filter(
            policy=policy,
            action=f"prompt.{action}",
        ).order_by("-created_at")
        
        for rule in rules:
            # Match target pattern (e.g., "prompt:customer-*", "prompt:*")
            target_pattern = rule.target.replace("prompt:", "")
            if fnmatch(prompt_name, target_pattern):
                if rule.effect == "deny":
                    return False, f"Prompt '{prompt_name}' denied by policy '{policy.name}' rule"
                elif rule.effect == "allow":
                    return True, None
    
    # LEGACY: Check deny list first (most restrictive)
    for policy in policies:
        deny_prompts = policy.rules_json.get("deny_prompts", [])
        if isinstance(deny_prompts, list):
            if prompt_name in deny_prompts:
                return (
                    False,
                    f"Prompt '{prompt_name}' denied by policy '{policy.name}'",
                )

    # LEGACY: Check allow list (explicit allow)
    for policy in policies:
        allow_prompts = policy.rules_json.get("allow_prompts", [])
        if isinstance(allow_prompts, list):
            if prompt_name in allow_prompts:
                return True, None

    # Default deny if no explicit allow
    return False, f"No policy explicitly allows prompt '{prompt_name}'"
