"""
Policy Enforcement Point (PEP) for MCP Fabric.

PEP middleware that enforces policy checks before every tool/agent call.
Implements deny-by-default: Only allows if policy explicitly permits.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    tracer = trace.get_tracer(__name__)
    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False
    tracer = None

from apps.audit.models import AuditEvent
from apps.audit.services import log_security_event
from apps.policies.pdp import get_pdp
from apps.tools.models import Tool
from libs.logging.context import set_context_ids

logger = logging.getLogger(__name__)


def check_policy_before_tool_call(
    *,
    agent_id: str,
    tool: Tool,
    payload: dict[str, Any],
    subject: str | None = None,
    context: dict[str, Any] | None = None,
    jti: str | None = None,
    client_ip: str | None = None,
    request_id: str | None = None,
) -> tuple[bool, str | None]:
    """
    PEP: Check policy before tool execution (deny-by-default).

    This function implements the Policy Enforcement Point (PEP) pattern:
    - Calls Policy Decision Point (PDP) via get_pdp().evaluate()
    - Logs audit events for all decisions (allow/deny)
    - Returns (allowed, reason) tuple

    Args:
        agent_id: Agent ID string
        tool: Tool instance
        payload: Tool input payload
        subject: Subject identifier (e.g., "agent:ingest@org/env")
        context: Additional context (depth, budget_left_cents, ttl_valid, tags, etc.)

    Returns:
        Tuple of (is_allowed: bool, reason: str | None)
        reason is None if allowed, otherwise contains denial reason
    """
    from apps.agents.models import Agent

    try:
        # Get agent
        agent = Agent.objects.get(
            id=agent_id,
            organization=tool.organization,
            environment=tool.environment,
            enabled=True,
        )
    except Agent.DoesNotExist:
        log_security_event(
            str(tool.organization.id),
            "pep_denied_agent_not_found",
            {
                "agent_id": agent_id,
                "tool_id": str(tool.id),
                "tool_name": tool.name,
                "reason": "Agent not found or disabled",
            },
        )
        return False, "Agent not found or disabled"

    # Set context IDs for logging (agent_id, tool_id, org_id, env_id)
    set_context_ids(
        agent_id=str(agent.id),
        tool_id=str(tool.id),
        org_id=str(tool.organization.id),
        env_id=str(tool.environment.id),
    )

    # Build context for PDP
    pdp_context = context or {}
    pdp_context.update(
        {
            "environment_id": str(tool.environment.id),
            "tool_name": tool.name,
            "tags": agent.tags or [],
        }
    )

    # Determine subject
    if not subject and agent.service_account:
        subject = agent.service_account.subject
    elif not subject:
        subject = f"agent:{agent.slug}@{tool.organization.name}/{tool.environment.id}"

    # OpenTelemetry span for PEP decision
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        # Get current span context if available (to link PEP to parent traces)
        # Note: start_span() context parameter expects OpenTelemetry Context, not SpanContext
        # If we want to link to parent, we should use set_parent() after creation
        # For now, create span without parent context (will be linked via trace_id if in same trace)
        span = tracer.start_span("pep.tool.invoke")
        span.set_attribute("pep.agent_id", agent_id)
        span.set_attribute("pep.tool_id", str(tool.id))
        span.set_attribute("pep.tool_name", tool.name)
        span.set_attribute("pep.organization_id", str(tool.organization.id))
        span.set_attribute("pep.environment_id", str(tool.environment.id))
        if jti:
            span.set_attribute("pep.jti", jti)
        if client_ip:
            span.set_attribute("pep.client_ip", client_ip)
        if request_id:
            span.set_attribute("pep.request_id", request_id)

    try:
        # Call PDP (Policy Decision Point)
        pdp = get_pdp()
        decision = pdp.evaluate(
            action="tool.invoke",
            target=f"tool:{tool.name}",
            subject=subject,
            organization_id=str(tool.organization.id),
            environment_id=str(tool.environment.id),
            agent_id=str(agent.id),
            tool_id=str(tool.id),
            context=pdp_context,
        )

        # Audit log for policy decision using log_security_event (includes context IDs automatically)
        audit_context = {
            "agent_id": str(agent.id),
            "tool_id": str(tool.id),
            "tool_name": tool.name,
            "matched_rules": decision.matched_rules or [],
        }
        # Store rule_id in context (PolicyRule.id is UUID, not compatible with IntegerField)
        if decision.rule_id:
            audit_context["rule_id"] = str(decision.rule_id)
        # Add security metadata (P0 requirement)
        if jti:
            audit_context["jti"] = jti
        if client_ip:
            audit_context["client_ip"] = client_ip
        if request_id:
            audit_context["request_id"] = request_id
        
        from apps.audit.services import log_security_event
        
        # Use log_security_event for consistent MCP event logging
        audit_event = log_security_event(
            organization_id=str(tool.organization.id),
            event_type="mcp.policy.decision",
            event_data=audit_context,
            subject=subject,
            action="tool.invoke",
            target=f"tool:{tool.name}",
            decision=decision.decision,
            rule_id=None,  # PolicyRule.id is UUID, not compatible with IntegerField; stored in context instead
        )
        # Update OpenTelemetry span with decision and audit event ID
        if span:
            span.set_attribute("pep.decision", decision.decision)
            if decision.rule_id:
                span.set_attribute("pep.rule_id", str(decision.rule_id))  # Convert UUID to string
            span.set_attribute("pep.audit_event_id", str(audit_event.id))
            span.set_status(Status(StatusCode.OK))

        if decision.is_allowed():
            return True, None
        else:
            reason = (
                f"Policy denied (rule_id={decision.rule_id})"
                if decision.rule_id
                else "Default deny (no explicit allow)"
            )
            return False, reason
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        logger.error(f"PEP error during policy check: {e}", exc_info=True)
        raise
    finally:
        if span:
            span.end()


def check_policy_before_agent_call(
    *,
    caller_agent_id: str,
    target_agent_id: str,
    action: str = "agent.invoke",
    context: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """
    PEP: Check policy before agent-to-agent call (delegation).

    Validates delegation constraints: depth, budget, TTL.

    Args:
        caller_agent_id: Calling agent ID
        target_agent_id: Target agent ID
        action: Action type (default: "agent.invoke")
        context: Context with depth, budget_left_cents, ttl_valid, etc.

    Returns:
        Tuple of (is_allowed: bool, reason: str | None)
    """
    from apps.agents.models import Agent

    try:
        caller_agent = Agent.objects.get(id=caller_agent_id, enabled=True)
        target_agent = Agent.objects.get(id=target_agent_id, enabled=True)
    except Agent.DoesNotExist as e:
        return False, f"Agent not found: {e}"

    # Check delegation constraints
    context = context or {}
    depth = context.get("depth", 0)

    # Check max_depth
    if depth > target_agent.default_max_depth:
        return False, f"Delegation depth {depth} exceeds max_depth {target_agent.default_max_depth}"

    # Check budget
    budget_left = context.get("budget_left_cents", 0)
    if target_agent.default_budget_cents > 0 and budget_left < 0:
        return False, "Delegation budget exhausted"

    # Check TTL
    ttl_valid = context.get("ttl_valid", True)
    if not ttl_valid:
        return False, "Delegation TTL expired"

    # Build context for PDP
    pdp_context = context.copy()
    pdp_context.update(
        {
            "environment_id": str(target_agent.environment.id),
            "depth": depth,
            "budget_left_cents": budget_left,
            "ttl_valid": ttl_valid,
            "tags": target_agent.tags or [],
        }
    )

    # Determine subject
    subject = None
    if caller_agent.service_account:
        subject = caller_agent.service_account.subject
    else:
        subject = f"agent:{caller_agent.slug}@{caller_agent.organization.name}/{caller_agent.environment.name}"

    # OpenTelemetry span for PEP decision
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        # Get current span context if available (to link PEP to parent traces)
        # Note: start_span() context parameter expects OpenTelemetry Context, not SpanContext
        # If we want to link to parent, we should use set_parent() after creation
        # For now, create span without parent context (will be linked via trace_id if in same trace)
        span = tracer.start_span("pep.agent.invoke")
        span.set_attribute("pep.caller_agent_id", caller_agent_id)
        span.set_attribute("pep.target_agent_id", target_agent_id)
        span.set_attribute("pep.organization_id", str(target_agent.organization.id))
        span.set_attribute("pep.environment_id", str(target_agent.environment.id))
        span.set_attribute("pep.depth", depth)
        span.set_attribute("pep.budget_left_cents", budget_left)
        span.set_attribute("pep.ttl_valid", ttl_valid)

    try:
        # Call PDP
        pdp = get_pdp()
        decision = pdp.evaluate(
            action=action,
            target=f"agent:{target_agent.slug}",
            subject=subject,
            organization_id=str(target_agent.organization.id),
            environment_id=str(target_agent.environment.id),
            agent_id=str(target_agent.id),
            context=pdp_context,
        )

        # Audit log
        from django.utils import timezone
        
        audit_context = {
            "caller_agent_id": str(caller_agent.id),
            "target_agent_id": str(target_agent.id),
            "depth": depth,
            "budget_left_cents": budget_left,
            "ttl_valid": ttl_valid,
            "matched_rules": decision.matched_rules or [],
        }
        # Store rule_id in context (PolicyRule.id is UUID, not compatible with IntegerField)
        if decision.rule_id:
            audit_context["rule_id"] = str(decision.rule_id)
        
        audit_event = AuditEvent.objects.create(
            organization=target_agent.organization,
            event_type="pep_decision",
            subject=subject,
            action=action,
            target=f"agent:{target_agent.slug}",
            decision=decision.decision,
            rule_id=None,  # PolicyRule.id is UUID, not compatible with IntegerField; stored in context instead
            context=audit_context,
            ts=timezone.now(),  # Explicitly set ts for filtering
        )
        # Update OpenTelemetry span with decision and audit event ID
        if span:
            span.set_attribute("pep.decision", decision.decision)
            if decision.rule_id:
                span.set_attribute("pep.rule_id", str(decision.rule_id))  # Convert UUID to string
            span.set_attribute("pep.audit_event_id", str(audit_event.id))
            span.set_status(Status(StatusCode.OK))

        if decision.is_allowed():
            return True, None
        else:
            reason = (
                f"Policy denied (rule_id={decision.rule_id})"
                if decision.rule_id
                else "Default deny (no explicit allow)"
            )
            return False, reason
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        logger.error(f"PEP error during agent policy check: {e}", exc_info=True)
        raise
    finally:
        if span:
            span.end()

