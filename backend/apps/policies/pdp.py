"""
Policy Decision Point (PDP) for evaluating access control policies.

Implements deny-by-default: Only allows if a matching policy explicitly permits.
Supports multi-scope bindings with priority ordering.

Evaluation order:
1. Group bindings by scope specificity (Agent → Tool → Env → Org)
2. Within each group: check deny first (immediate deny), then allow
3. Fall-through: only if a group yields neither allow nor deny, proceed to next group
4. This ensures more specific scopes (Agent) override less specific ones (Env/Org)
"""
from __future__ import annotations

import fnmatch
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from django.db import models
from django.utils import timezone as django_timezone

from apps.policies.models import Policy, PolicyBinding, PolicyRule

logger = logging.getLogger(__name__)

# Scope order: lower number = more specific, evaluated first
SCOPE_ORDER = {
    "agent": 1,
    "tool": 2,
    "resource_ns": 2,
    "env": 3,
    "org": 4,
}


class PolicyDecision:
    """Result of a policy evaluation."""

    def __init__(
        self,
        decision: str,
        rule_id: int | None = None,
        matched_rules: list[dict[str, Any]] | None = None,
        bindings_order: list[dict[str, Any]] | None = None,
    ):
        self.decision = decision  # "allow" or "deny"
        self.rule_id = rule_id
        self.matched_rules = matched_rules or []
        self.bindings_order = bindings_order or []

    def is_allowed(self) -> bool:
        """Check if decision is allow."""
        return self.decision == "allow"


class PolicyEvaluator:
    """
    Policy Decision Point (PDP) for evaluating access control.

    Evaluates policies in order:
    1. Agent-specific bindings (priority)
    2. Tool/Resource-specific bindings (priority)
    3. Environment-specific bindings (priority)
    4. Organization-specific bindings (priority)

    Within each scope, rules are evaluated by priority (lower = more specific).
    Deny rules take precedence over allow rules.
    """

    def evaluate(
        self,
        *,
        action: str,
        target: str,
        subject: str | None = None,
        organization_id: str | None = None,
        environment_id: str | None = None,
        agent_id: str | None = None,
        tool_id: str | None = None,
        resource_ns: str | None = None,
        context: dict[str, Any] | None = None,
        explain: bool = False,
    ) -> PolicyDecision:
        """
        Evaluate policy for an action on a target.

        Args:
            action: Action type (e.g., "tool.invoke", "agent.invoke", "resource.read")
            target: Target pattern (e.g., "tool:pdf/*", "agent:ocr", "resource:minio://org/env/path/*")
            subject: Subject identifier (e.g., "agent:ingest@org/env")
            organization_id: Organization UUID
            environment_id: Environment UUID
            agent_id: Agent UUID
            tool_id: Tool UUID
            resource_ns: Resource namespace
            context: Additional context (depth, budget_left_cents, ttl_valid, tags, etc.)
            explain: If True, include matched_rules and bindings_order in result

        Returns:
            PolicyDecision with decision, rule_id, and optionally matched_rules/bindings_order
        """
        context = context or {}
        matched_rules: list[dict[str, Any]] = []
        bindings_order: list[dict[str, Any]] = []

        # Collect relevant bindings
        bindings = self._collect_bindings(
            organization_id=organization_id,
            environment_id=environment_id,
            agent_id=agent_id,
            tool_id=tool_id,
            resource_ns=resource_ns,
        )

        if explain:
            bindings_order = [
                {
                    "policy_id": str(b.policy.id),
                    "policy_name": b.policy.name,
                    "scope_type": b.scope_type,
                    "scope_id": b.scope_id,
                    "priority": b.priority,
                }
                for b in bindings
            ]

        # Group bindings by scope type (Agent → Tool → Env → Org)
        bindings_by_scope = defaultdict(list)
        for binding in bindings:
            if binding.policy.is_active:
                bindings_by_scope[binding.scope_type].append(binding)

        # Sort scope groups by specificity (Agent first, Org last)
        scope_groups = sorted(
            bindings_by_scope.items(),
            key=lambda x: SCOPE_ORDER.get(x[0], 99),
        )

        # Evaluate each scope group in order
        for scope_type, scope_bindings in scope_groups:
            # Sort bindings within group by priority (lower = more specific)
            scope_bindings.sort(key=lambda b: b.priority)

            # Within group: first check deny (immediate deny), then allow
            group_deny_rule = None
            group_allow_rule = None
            group_allow_binding = None

            for binding in scope_bindings:
                # Check deny rules first (most restrictive)
                if group_deny_rule is None:  # Only check if no deny found yet
                    deny_rules = binding.policy.rules.filter(
                        action=action, effect="deny"
                    ).order_by("created_at")

                    for rule in deny_rules:
                        if self._matches_target(rule.target, target):
                            if self._evaluate_conditions(rule.conditions, context):
                                matched_rules.append(
                                    {
                                        "rule_id": rule.id,
                                        "policy_id": str(binding.policy.id),
                                        "policy_name": binding.policy.name,
                                        "effect": "deny",
                                        "target": rule.target,
                                        "scope_type": binding.scope_type,
                                        "priority": binding.priority,
                                    }
                                )
                                group_deny_rule = rule
                                break  # Found deny, stop checking denies in this group

                # Check allow rules (remember first match)
                if group_allow_rule is None:  # Only check if no allow found yet
                    allow_rules = binding.policy.rules.filter(
                        action=action, effect="allow"
                    ).order_by("created_at")

                    for rule in allow_rules:
                        if self._matches_target(rule.target, target):
                            if self._evaluate_conditions(rule.conditions, context):
                                matched_rules.append(
                                    {
                                        "rule_id": rule.id,
                                        "policy_id": str(binding.policy.id),
                                        "policy_name": binding.policy.name,
                                        "effect": "allow",
                                        "target": rule.target,
                                        "scope_type": binding.scope_type,
                                        "priority": binding.priority,
                                    }
                                )
                                group_allow_rule = rule
                                group_allow_binding = binding
                                break  # Found allow, stop checking allows in this group

            # Group decision: deny wins, then allow, then fall-through to next group
            if group_deny_rule:
                return PolicyDecision(
                    decision="deny",
                    rule_id=group_deny_rule.id,
                    matched_rules=matched_rules if explain else None,
                    bindings_order=bindings_order if explain else None,
                )

            if group_allow_rule:
                return PolicyDecision(
                    decision="allow",
                    rule_id=group_allow_rule.id,
                    matched_rules=matched_rules if explain else None,
                    bindings_order=bindings_order if explain else None,
                )

            # Neither deny nor allow in this group: fall through to next (less specific) group

        # Default deny if no explicit allow in any group
        return PolicyDecision(
            decision="deny",
            rule_id=None,
            matched_rules=matched_rules if explain else None,
            bindings_order=bindings_order if explain else None,
        )

    def _collect_bindings(
        self,
        *,
        organization_id: str | None = None,
        environment_id: str | None = None,
        agent_id: str | None = None,
        tool_id: str | None = None,
        resource_ns: str | None = None,
    ) -> list[PolicyBinding]:
        """
        Collect relevant policy bindings filtered by scope IDs.

        Returns bindings filtered by provided scope IDs, ready for grouping by scope_type.
        Performance: Uses prefetch_related to avoid N+1 queries.
        """
        bindings = []

        # Agent-specific bindings
        if agent_id:
            agent_bindings = PolicyBinding.objects.filter(
                scope_type="agent", scope_id=str(agent_id)
            ).select_related("policy").prefetch_related("policy__rules")
            bindings.extend(agent_bindings)

        # Tool-specific bindings
        if tool_id:
            tool_bindings = PolicyBinding.objects.filter(
                scope_type="tool", scope_id=str(tool_id)
            ).select_related("policy").prefetch_related("policy__rules")
            bindings.extend(tool_bindings)

        # Resource namespace bindings
        if resource_ns:
            resource_bindings = PolicyBinding.objects.filter(
                scope_type="resource_ns", scope_id=resource_ns
            ).select_related("policy").prefetch_related("policy__rules")
            bindings.extend(resource_bindings)

        # Environment-specific bindings
        if environment_id:
            env_bindings = PolicyBinding.objects.filter(
                scope_type="env", scope_id=str(environment_id)
            ).select_related("policy").prefetch_related("policy__rules")
            bindings.extend(env_bindings)

        # Organization-specific bindings
        if organization_id:
            org_bindings = PolicyBinding.objects.filter(
                scope_type="org", scope_id=str(organization_id)
            ).select_related("policy").prefetch_related("policy__rules")
            bindings.extend(org_bindings)

        return bindings

    def _matches_target(self, pattern: str, target: str) -> bool:
        """
        Check if target matches pattern (supports wildcards).

        Examples:
            "tool:pdf/*" matches "tool:pdf/read"
            "agent:ocr" matches "agent:ocr"
            "resource:minio://org/env/path/*" matches "resource:minio://org/env/path/file.txt"
        """
        # Use fnmatch for wildcard matching
        return fnmatch.fnmatch(target, pattern)

    def _evaluate_conditions(
        self, conditions: dict[str, Any], context: dict[str, Any]
    ) -> bool:
        """
        Evaluate rule conditions against context.

        Supported conditions:
        - env==: Environment ID must match
        - time_window: Current time must be within window
        - tags contains: Context tags must contain specified tags
        - risk_level<=: Context risk_level must be <= condition value
        - content_type in: Context content_type must be in list
        - max_size_mb<=: Context size_mb must be <= condition value
        - allowed_tools: For agent.invoke, allowed tool patterns
        - allowed_resource_ns: For agent.invoke, allowed resource namespaces
        - depth<=: Delegation depth must be <= condition value
        - budget_left_cents>=: Budget must be >= condition value
        - ttl_valid: TTL must be valid (boolean)
        """
        if not conditions:
            return True

        # env==
        if "env==" in conditions:
            if context.get("environment_id") != conditions["env=="]:
                return False

        # time_window: {"start": "HH:MM", "end": "HH:MM", "days": [0,1,2,3,4]}
        if "time_window" in conditions:
            window = conditions["time_window"]
            now = django_timezone.now()
            current_hour = now.hour
            current_minute = now.minute
            current_time = current_hour * 60 + current_minute

            if "start" in window and "end" in window:
                start_parts = window["start"].split(":")
                end_parts = window["end"].split(":")
                start_time = int(start_parts[0]) * 60 + int(start_parts[1])
                end_time = int(end_parts[0]) * 60 + int(end_parts[1])

                if "days" in window:
                    if now.weekday() not in window["days"]:
                        return False

                if start_time <= end_time:
                    if not (start_time <= current_time <= end_time):
                        return False
                else:  # Crosses midnight
                    if not (current_time >= start_time or current_time <= end_time):
                        return False

        # tags contains
        if "tags" in conditions:
            context_tags = set(context.get("tags", []))
            required_tags = set(conditions["tags"])
            if not required_tags.issubset(context_tags):
                return False

        # risk_level<=
        if "risk_level<=" in conditions:
            context_risk = context.get("risk_level", 0)
            if context_risk > conditions["risk_level<="]:
                return False

        # content_type in
        if "content_type" in conditions:
            context_content_type = context.get("content_type")
            allowed_types = conditions["content_type"]
            if isinstance(allowed_types, str):
                allowed_types = [allowed_types]
            if context_content_type not in allowed_types:
                return False

        # max_size_mb<=
        if "max_size_mb<=" in conditions:
            context_size_mb = context.get("size_mb", 0)
            if context_size_mb > conditions["max_size_mb<="]:
                return False

        # allowed_tools (for agent.invoke)
        if "allowed_tools" in conditions:
            tool_name = context.get("tool_name")
            if tool_name:
                allowed_patterns = conditions["allowed_tools"]
                if isinstance(allowed_patterns, str):
                    allowed_patterns = [allowed_patterns]
                if not any(
                    self._matches_target(pattern, f"tool:{tool_name}")
                    for pattern in allowed_patterns
                ):
                    return False

        # allowed_resource_ns (for agent.invoke)
        if "allowed_resource_ns" in conditions:
            resource_ns = context.get("resource_ns")
            if resource_ns:
                allowed_ns = conditions["allowed_resource_ns"]
                if isinstance(allowed_ns, str):
                    allowed_ns = [allowed_ns]
                if resource_ns not in allowed_ns:
                    return False

        # depth<= (delegation depth)
        if "depth<=" in conditions:
            context_depth = context.get("depth", 0)
            if context_depth > conditions["depth<="]:
                return False

        # budget_left_cents>= (delegation budget)
        if "budget_left_cents>=" in conditions:
            context_budget = context.get("budget_left_cents", 0)
            if context_budget < conditions["budget_left_cents>="]:
                return False

        # ttl_valid (delegation TTL)
        if "ttl_valid" in conditions:
            if conditions["ttl_valid"]:
                ttl_valid = context.get("ttl_valid", False)
                if not ttl_valid:
                    return False

        return True


# Singleton instance
_pdp_instance: PolicyEvaluator | None = None


def get_pdp() -> PolicyEvaluator:
    """Get singleton Policy Decision Point instance."""
    global _pdp_instance
    if _pdp_instance is None:
        _pdp_instance = PolicyEvaluator()
    return _pdp_instance
