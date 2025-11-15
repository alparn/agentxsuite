"""
Audit services for logging security events.

MCP-specific event types:
- TOOL_INVOKED: Tool execution started/completed
- RESOURCE_READ: Resource read operation
- RESOURCE_WRITE: Resource write operation
- POLICY_DECISION: Policy allow/deny decision
- AGENT_INVOKED: Agent-to-agent delegation
"""
from __future__ import annotations

import logging
from typing import Any

from libs.logging.context import get_context_ids

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode, format_trace_id

    tracer = trace.get_tracer(__name__)
    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False
    tracer = None

from apps.audit.models import AuditEvent
from apps.runs.models import Run

logger = logging.getLogger(__name__)

# MCP-specific event types
MCP_EVENT_TYPES = {
    "TOOL_INVOKED": "mcp.tool.invoked",
    "RESOURCE_READ": "mcp.resource.read",
    "RESOURCE_WRITE": "mcp.resource.write",
    "POLICY_DECISION": "mcp.policy.decision",
    "AGENT_INVOKED": "mcp.agent.invoked",
}


def log_run_event(
    run: Run,
    event_type: str,
    event_data: dict | None = None,
) -> AuditEvent:
    """
    Log an audit event for a run.

    Automatically injects context IDs (trace_id, request_id) from logging context.

    Args:
        run: Run instance
        event_type: Type of event (e.g., "run_started", "run_denied", "run_failed")
        event_data: Additional event data

    Returns:
        Created AuditEvent instance
    """
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        # Get current span context if available (to link audit events to parent traces)
        current_span = trace.get_current_span()
        span = tracer.start_span(
            f"audit.run.{event_type}",
            context=current_span.get_span_context() if current_span else None,
        )
        span.set_attribute("audit.event_type", event_type)
        span.set_attribute("run.id", str(run.id))
        span.set_attribute("agent.id", str(run.agent.id))
        span.set_attribute("tool.id", str(run.tool.id))
        span.set_attribute("organization.id", str(run.organization.id))
        span.set_attribute("environment.id", str(run.environment.id))

    try:
        # Get context IDs from logging context
        context_ids = get_context_ids()
        trace_id = context_ids.get("trace_id")
        request_id = context_ids.get("request_id")

        data = event_data or {}
        data.update(
            {
                "run_id": str(run.id),
                "agent_id": str(run.agent.id),
                "tool_id": str(run.tool.id),
                "organization_id": str(run.organization.id),
                "environment_id": str(run.environment.id),
            }
        )

        # Inject context IDs
        if trace_id:
            data["trace_id"] = trace_id
        if request_id:
            data["request_id"] = request_id

        # Set subject, action, target for all run events
        # Subject: agent identity
        subject = data.get("subject")
        if not subject:
            subject = f"agent:{run.agent.name}@{run.organization.name}/{run.environment.name}"
            data["subject"] = subject

        # Action: map event_type to action
        action = data.get("action")
        if not action:
            if event_type.startswith("mcp."):
                if event_type == MCP_EVENT_TYPES["TOOL_INVOKED"]:
                    action = "tool.invoke"
                else:
                    action = event_type.replace("mcp.", "").replace("_", ".")
            elif event_type == "run_started":
                action = "tool.run"
            elif event_type == "run_succeeded":
                action = "tool.run.success"
            elif event_type.startswith("run_failed"):
                action = "tool.run.failed"
            elif event_type == "run_denied":
                action = "tool.run.denied"
            else:
                action = event_type.replace("_", ".")
            data["action"] = action

        # Target: tool identity
        target = data.get("target")
        if not target:
            target = f"tool:{run.tool.name}"
            data["target"] = target

        # Decision: infer from event_type
        decision = data.get("decision")
        if not decision:
            if event_type == "run_denied":
                decision = "deny"
            elif event_type in ("run_started", "run_succeeded"):
                decision = "allow"
            elif event_type.startswith("run_failed"):
                # Failed runs were allowed but failed during execution
                decision = "allow"
            # For other event types, leave decision as None

        # Rule ID: extract from event_data if available
        rule_id = data.get("rule_id")

        audit_event = AuditEvent.objects.create(
            organization=run.organization,
            event_type=event_type,
            event_data=data,
            subject=subject,
            action=action,
            target=target,
            decision=decision,
            rule_id=rule_id,
        )

        if span:
            span.set_attribute("audit.event_id", str(audit_event.id))
            if trace_id:
                span.set_attribute("trace.id", trace_id)
            span.set_status(Status(StatusCode.OK))
            # Add additional event data as attributes (limit to avoid huge spans)
            if event_data:
                for key, value in list(event_data.items())[:10]:  # Limit to first 10 items
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"audit.data.{key}", str(value))

        return audit_event
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        logger.error(
            f"Failed to log run event: {e}",
            extra={
                "run_id": str(run.id),
                "event_type": event_type,
                "trace_id": context_ids.get("trace_id"),
                "request_id": context_ids.get("request_id"),
            },
            exc_info=True,
        )
        raise
    finally:
        if span:
            span.end()


def log_api_event(
    organization: "Organization | None" = None,
    event_type: str = "api.request",
    event_data: dict | None = None,
    *,
    user: "User | None" = None,
    subject: str | None = None,
    action: str | None = None,
    target: str | None = None,
) -> AuditEvent:
    """
    Log a generic API event (CRUD operations, etc.).

    Automatically injects context IDs (trace_id, request_id) from logging context.

    Args:
        organization: Organization instance (optional)
        event_type: Type of API event (e.g., "api.agent.create", "api.tool.update")
        event_data: Event data dictionary
        user: User instance who performed the action (optional)
        subject: Subject identifier (e.g., "user:admin@example.com")
        action: Action performed (e.g., "agent.create", "tool.update")
        target: Target of the action (e.g., "agent:my-agent")

    Returns:
        Created AuditEvent instance
    """
    from apps.accounts.models import User
    from apps.tenants.models import Organization

    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        current_span = trace.get_current_span()
        span = tracer.start_span(
            f"audit.api.{event_type}",
            context=current_span.get_span_context() if current_span else None,
        )
        span.set_attribute("audit.event_type", event_type)
        if organization:
            span.set_attribute("organization.id", str(organization.id))

    try:
        # Get context IDs from logging context
        context_ids = get_context_ids()
        trace_id = context_ids.get("trace_id")
        request_id = context_ids.get("request_id")

        data = event_data or {}

        # Inject context IDs
        if trace_id:
            data["trace_id"] = trace_id
        if request_id:
            data["request_id"] = request_id

        # Add user information
        if user:
            data["user_id"] = str(user.id)
            data["user_email"] = user.email
            if not subject:
                subject = f"user:{user.email}"

        # Set subject if not provided
        if not subject and user:
            subject = f"user:{user.email}"
        elif not subject:
            subject = "system"

        # Set action if not provided (extract from event_type)
        if not action:
            # Extract action from event_type (e.g., "api.agent.create" -> "agent.create")
            if event_type.startswith("api."):
                action = event_type.replace("api.", "")
            else:
                action = event_type

        # Set target if not provided (extract from event_data)
        if not target:
            object_type = data.get("object_type", "")
            object_id = data.get("object_id", "")
            if object_type and object_id:
                target = f"{object_type}:{object_id}"
            elif object_type:
                target = object_type

        # Get organization ID
        org_id = None
        if organization:
            org_id = str(organization.id)
        elif "organization_id" in data:
            org_id = data["organization_id"]

        # Get or create organization instance
        org = organization
        if not org and org_id:
            try:
                org = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                org = None

        audit_event = AuditEvent.objects.create(
            organization=org,
            event_type=event_type,
            event_data=data,
            subject=subject,
            action=action,
            target=target,
        )

        if span:
            span.set_attribute("audit.event_id", str(audit_event.id))
            if trace_id:
                span.set_attribute("trace.id", trace_id)
            span.set_status(Status(StatusCode.OK))
            # Add event data as attributes (limit to avoid huge spans)
            for key, value in list(data.items())[:10]:
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"audit.data.{key}", str(value))

        return audit_event
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        logger.error(
            f"Failed to log API event: {e}",
            extra={
                "organization_id": org_id,
                "event_type": event_type,
                "trace_id": context_ids.get("trace_id"),
                "request_id": context_ids.get("request_id"),
            },
            exc_info=True,
        )
        raise
    finally:
        if span:
            span.end()


def log_security_event(
    organization_id: str,
    event_type: str,
    event_data: dict,
    *,
    subject: str | None = None,
    action: str | None = None,
    target: str | None = None,
    decision: str | None = None,
    rule_id: int | None = None,
) -> AuditEvent:
    """
    Log a security-related audit event.

    Automatically injects context IDs (trace_id, request_id) from logging context.

    Args:
        organization_id: Organization UUID string
        event_type: Type of security event
        event_data: Event data dictionary
        subject: Subject identifier (e.g., "agent:ingest@org/env")
        action: Action performed (e.g., "tool.invoke", "resource.read")
        target: Target of the action (e.g., "tool:pdf/*")
        decision: Policy decision ("allow" or "deny")
        rule_id: ID of matching policy rule

    Returns:
        Created AuditEvent instance
    """
    from apps.tenants.models import Organization

    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        # Get current span context if available (to link audit events to parent traces)
        current_span = trace.get_current_span()
        span = tracer.start_span(
            f"audit.security.{event_type}",
            context=current_span.get_span_context() if current_span else None,
        )
        span.set_attribute("audit.event_type", event_type)
        span.set_attribute("organization.id", organization_id)

    try:
        # Get context IDs from logging context
        context_ids = get_context_ids()
        trace_id = context_ids.get("trace_id")
        request_id = context_ids.get("request_id")
        run_id = context_ids.get("run_id")

        # Inject context IDs into event_data
        if trace_id:
            event_data["trace_id"] = trace_id
        if request_id:
            event_data["request_id"] = request_id
        if run_id:
            event_data["run_id"] = run_id

        try:
            org = Organization.objects.get(id=organization_id)
            if span:
                span.set_attribute("organization.name", org.name)
        except Organization.DoesNotExist:
            org = None
            if span:
                span.set_attribute("organization.exists", False)

        audit_event = AuditEvent.objects.create(
            organization=org,
            event_type=event_type,
            event_data=event_data,
            subject=subject,
            action=action,
            target=target,
            decision=decision,
            rule_id=rule_id,
        )

        if span:
            span.set_attribute("audit.event_id", str(audit_event.id))
            if trace_id:
                span.set_attribute("trace.id", trace_id)
            span.set_status(Status(StatusCode.OK))
            # Add event data as attributes (limit to avoid huge spans)
            for key, value in list(event_data.items())[:15]:  # Limit to first 15 items
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"audit.data.{key}", str(value))
                elif isinstance(value, dict):
                    # For nested dicts, flatten key names
                    for nested_key, nested_value in list(value.items())[:5]:
                        if isinstance(nested_value, (str, int, float, bool)):
                            span.set_attribute(
                                f"audit.data.{key}.{nested_key}", str(nested_value)
                            )

        return audit_event
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        logger.error(
            f"Failed to log security event: {e}",
            extra={
                "organization_id": organization_id,
                "event_type": event_type,
                "trace_id": context_ids.get("trace_id"),
                "request_id": context_ids.get("request_id"),
            },
            exc_info=True,
        )
        raise
    finally:
        if span:
            span.end()


def log_api_event(
    organization: "Organization | None" = None,
    event_type: str = "api.request",
    event_data: dict | None = None,
    *,
    user: "User | None" = None,
    subject: str | None = None,
    action: str | None = None,
    target: str | None = None,
) -> AuditEvent:
    """
    Log a generic API event (CRUD operations, etc.).

    Automatically injects context IDs (trace_id, request_id) from logging context.

    Args:
        organization: Organization instance (optional)
        event_type: Type of API event (e.g., "api.agent.create", "api.tool.update")
        event_data: Event data dictionary
        user: User instance who performed the action (optional)
        subject: Subject identifier (e.g., "user:admin@example.com")
        action: Action performed (e.g., "agent.create", "tool.update")
        target: Target of the action (e.g., "agent:my-agent")

    Returns:
        Created AuditEvent instance
    """
    from apps.accounts.models import User
    from apps.tenants.models import Organization

    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        current_span = trace.get_current_span()
        span = tracer.start_span(
            f"audit.api.{event_type}",
            context=current_span.get_span_context() if current_span else None,
        )
        span.set_attribute("audit.event_type", event_type)
        if organization:
            span.set_attribute("organization.id", str(organization.id))

    try:
        # Get context IDs from logging context
        context_ids = get_context_ids()
        trace_id = context_ids.get("trace_id")
        request_id = context_ids.get("request_id")

        data = event_data or {}

        # Inject context IDs
        if trace_id:
            data["trace_id"] = trace_id
        if request_id:
            data["request_id"] = request_id

        # Add user information
        if user:
            data["user_id"] = str(user.id)
            data["user_email"] = user.email
            if not subject:
                subject = f"user:{user.email}"

        # Set subject if not provided
        if not subject and user:
            subject = f"user:{user.email}"
        elif not subject:
            subject = "system"

        # Set action if not provided (extract from event_type)
        if not action:
            # Extract action from event_type (e.g., "api.agent.create" -> "agent.create")
            if event_type.startswith("api."):
                action = event_type.replace("api.", "")
            else:
                action = event_type

        # Set target if not provided (extract from event_data)
        if not target:
            object_type = data.get("object_type", "")
            object_id = data.get("object_id", "")
            if object_type and object_id:
                target = f"{object_type}:{object_id}"
            elif object_type:
                target = object_type

        # Get organization ID
        org_id = None
        if organization:
            org_id = str(organization.id)
        elif "organization_id" in data:
            org_id = data["organization_id"]

        # Get or create organization instance
        org = organization
        if not org and org_id:
            try:
                org = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                org = None

        audit_event = AuditEvent.objects.create(
            organization=org,
            event_type=event_type,
            event_data=data,
            subject=subject,
            action=action,
            target=target,
        )

        if span:
            span.set_attribute("audit.event_id", str(audit_event.id))
            if trace_id:
                span.set_attribute("trace.id", trace_id)
            span.set_status(Status(StatusCode.OK))
            # Add event data as attributes (limit to avoid huge spans)
            for key, value in list(data.items())[:10]:
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"audit.data.{key}", str(value))

        return audit_event
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        logger.error(
            f"Failed to log API event: {e}",
            extra={
                "organization_id": org_id,
                "event_type": event_type,
                "trace_id": context_ids.get("trace_id"),
                "request_id": context_ids.get("request_id"),
            },
            exc_info=True,
        )
        raise
    finally:
        if span:
            span.end()

