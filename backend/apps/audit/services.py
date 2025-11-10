"""
Audit services for logging security events.
"""
from __future__ import annotations

import logging

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    tracer = trace.get_tracer(__name__)
    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False
    tracer = None

from apps.audit.models import AuditEvent
from apps.runs.models import Run

logger = logging.getLogger(__name__)


def log_run_event(
    run: Run,
    event_type: str,
    event_data: dict | None = None,
) -> AuditEvent:
    """
    Log an audit event for a run.

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

        audit_event = AuditEvent.objects.create(
            organization=run.organization,
            event_type=event_type,
            event_data=data,
        )

        if span:
            span.set_attribute("audit.event_id", str(audit_event.id))
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
        logger.error(f"Failed to log run event: {e}", exc_info=True)
        raise
    finally:
        if span:
            span.end()


def log_security_event(
    organization_id: str,
    event_type: str,
    event_data: dict,
) -> AuditEvent:
    """
    Log a security-related audit event.

    Args:
        organization_id: Organization UUID string
        event_type: Type of security event
        event_data: Event data dictionary

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
        )

        if span:
            span.set_attribute("audit.event_id", str(audit_event.id))
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
        logger.error(f"Failed to log security event: {e}", exc_info=True)
        raise
    finally:
        if span:
            span.end()

