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
    Uses PolicyRule system with support for wildcards and scope-based bindings.

    Args:
        agent: Agent instance requesting the run
        tool: Tool instance to be executed
        payload: Input payload dictionary

    Returns:
        Tuple of (is_allowed: bool, reason: str | None)
        reason is None if allowed, otherwise contains denial reason
    """
    from apps.policies.models import PolicyBinding, PolicyRule
    from fnmatch import fnmatch
    
    # Query active policies for organization/environment
    policies = Policy.objects.filter(
        organization=agent.organization,
        is_active=True,
    ).filter(
        models.Q(environment__isnull=True) | models.Q(environment=agent.environment)
    )
    
    # Helper function to match target pattern
    def matches_target(rule_target: str, tool_name: str, connection_name: str | None) -> bool:
        """Check if rule target matches tool name or connection/tool combination."""
        # Remove "tool:" prefix if present, but don't strip whitespace (exact matching)
        target_pattern = rule_target.replace("tool:", "", 1) if rule_target.startswith("tool:") else rule_target
        if fnmatch(tool_name, target_pattern):
            return True
        if connection_name and fnmatch(f"{connection_name}/{tool_name}", target_pattern):
            return True
        return False
    
    # Get bindings for different scopes
    agent_bindings = PolicyBinding.objects.filter(
        scope_type="agent",
        scope_id=str(agent.id),
    ).select_related("policy")
    
    tool_bindings = PolicyBinding.objects.filter(
        scope_type="tool",
        scope_id=str(tool.id),
    ).select_related("policy")
    
    # PHASE 1: Check all DENY rules (deny takes precedence)
    # Agent-specific bindings
    for binding in agent_bindings:
        if not binding.policy.is_active:
            continue
        deny_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action="tool.invoke",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_target(rule.target, tool.name, tool.connection.name if tool.connection else None):
                return False, f"Tool '{tool.name}' denied by policy '{binding.policy.name}' rule"
    
    # Tool-specific bindings
    for binding in tool_bindings:
        if not binding.policy.is_active:
            continue
        deny_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action="tool.invoke",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_target(rule.target, tool.name, tool.connection.name if tool.connection else None):
                return False, f"Tool '{tool.name}' denied by policy '{binding.policy.name}' rule"
    
    # Environment and Organization policies
    for policy in policies:
        deny_rules = PolicyRule.objects.filter(
            policy=policy,
            action="tool.invoke",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_target(rule.target, tool.name, tool.connection.name if tool.connection else None):
                return False, f"Tool '{tool.name}' denied by policy '{policy.name}' rule"
    
    # PHASE 2: Check ALLOW rules (only if no deny found)
    # Agent-specific bindings
    for binding in agent_bindings:
        if not binding.policy.is_active:
            continue
        allow_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action="tool.invoke",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_target(rule.target, tool.name, tool.connection.name if tool.connection else None):
                return True, None
    
    # Tool-specific bindings
    for binding in tool_bindings:
        if not binding.policy.is_active:
            continue
        allow_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action="tool.invoke",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_target(rule.target, tool.name, tool.connection.name if tool.connection else None):
                return True, None
    
    # Environment and Organization policies
    for policy in policies:
        allow_rules = PolicyRule.objects.filter(
            policy=policy,
            action="tool.invoke",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_target(rule.target, tool.name, tool.connection.name if tool.connection else None):
                return True, None
    
    # Default deny if no explicit allow
    return False, "No policy explicitly allows this tool"


def is_allowed_resource(
    agent: Agent, resource_name: str, action: str = "read"
) -> Tuple[bool, str | None]:
    """
    Check if agent is allowed to access resource with given action.

    Default deny: Only allows if a matching policy explicitly permits it.
    Uses PolicyRule system with support for wildcards and scope-based bindings.

    Args:
        agent: Agent instance requesting access
        resource_name: Resource name
        action: Action type (default: "read")

    Returns:
        Tuple of (is_allowed: bool, reason: str | None)
        reason is None if allowed, otherwise contains denial reason
    """
    from apps.policies.models import PolicyBinding, PolicyRule
    from fnmatch import fnmatch
    
    # Query active policies for organization/environment
    policies = Policy.objects.filter(
        organization=agent.organization,
        is_active=True,
    ).filter(
        models.Q(environment__isnull=True) | models.Q(environment=agent.environment)
    )
    
    # Get bindings for agent scope
    agent_bindings = PolicyBinding.objects.filter(
        scope_type="agent",
        scope_id=str(agent.id),
    ).select_related("policy")
    
    # Helper function to match target pattern
    def matches_resource(rule_target: str, resource: str) -> bool:
        """Check if rule target matches resource name."""
        # Remove "resource:" prefix if present, but don't strip whitespace (exact matching)
        target_pattern = rule_target.replace("resource:", "", 1) if rule_target.startswith("resource:") else rule_target
        return fnmatch(resource, target_pattern)
    
    # PHASE 1: Check all DENY rules
    for binding in agent_bindings:
        if not binding.policy.is_active:
            continue
        deny_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action=f"resource.{action}",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_resource(rule.target, resource_name):
                return False, f"Resource '{resource_name}' denied by policy '{binding.policy.name}' rule"
    
    for policy in policies:
        deny_rules = PolicyRule.objects.filter(
            policy=policy,
            action=f"resource.{action}",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_resource(rule.target, resource_name):
                return False, f"Resource '{resource_name}' denied by policy '{policy.name}' rule"
    
    # PHASE 2: Check ALLOW rules
    for binding in agent_bindings:
        if not binding.policy.is_active:
            continue
        allow_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action=f"resource.{action}",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_resource(rule.target, resource_name):
                return True, None
    
    for policy in policies:
        allow_rules = PolicyRule.objects.filter(
            policy=policy,
            action=f"resource.{action}",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_resource(rule.target, resource_name):
                return True, None
    
    # Default deny if no explicit allow
    return False, f"No policy explicitly allows resource '{resource_name}'"


def is_allowed_prompt(
    agent: Agent, prompt_name: str, action: str = "invoke"
) -> Tuple[bool, str | None]:
    """
    Check if agent is allowed to invoke prompt with given action.

    Default deny: Only allows if a matching policy explicitly permits it.
    Uses PolicyRule system with support for wildcards and scope-based bindings.

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
    
    # Query active policies for organization/environment
    policies = Policy.objects.filter(
        organization=agent.organization,
        is_active=True,
    ).filter(
        models.Q(environment__isnull=True) | models.Q(environment=agent.environment)
    )
    
    # Get bindings for agent scope
    agent_bindings = PolicyBinding.objects.filter(
        scope_type="agent",
        scope_id=str(agent.id),
    ).select_related("policy")
    
    # Helper function to match target pattern
    def matches_prompt(rule_target: str, prompt: str) -> bool:
        """Check if rule target matches prompt name."""
        # Remove "prompt:" prefix if present, but don't strip whitespace (exact matching)
        target_pattern = rule_target.replace("prompt:", "", 1) if rule_target.startswith("prompt:") else rule_target
        return fnmatch(prompt, target_pattern)
    
    # PHASE 1: Check all DENY rules
    for binding in agent_bindings:
        if not binding.policy.is_active:
            continue
        deny_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action=f"prompt.{action}",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_prompt(rule.target, prompt_name):
                return False, f"Prompt '{prompt_name}' denied by policy '{binding.policy.name}' rule"
    
    for policy in policies:
        deny_rules = PolicyRule.objects.filter(
            policy=policy,
            action=f"prompt.{action}",
            effect="deny",
        )
        for rule in deny_rules:
            if matches_prompt(rule.target, prompt_name):
                return False, f"Prompt '{prompt_name}' denied by policy '{policy.name}' rule"
    
    # PHASE 2: Check ALLOW rules
    for binding in agent_bindings:
        if not binding.policy.is_active:
            continue
        allow_rules = PolicyRule.objects.filter(
            policy=binding.policy,
            action=f"prompt.{action}",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_prompt(rule.target, prompt_name):
                return True, None
    
    for policy in policies:
        allow_rules = PolicyRule.objects.filter(
            policy=policy,
            action=f"prompt.{action}",
            effect="allow",
        )
        for rule in allow_rules:
            if matches_prompt(rule.target, prompt_name):
                return True, None
    
    # Default deny if no explicit allow
    return False, f"No policy explicitly allows prompt '{prompt_name}'"
