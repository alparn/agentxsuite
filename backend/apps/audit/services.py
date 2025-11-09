"""
Audit services for logging security events.
"""
from __future__ import annotations

from apps.audit.models import AuditEvent
from apps.runs.models import Run


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

    return AuditEvent.objects.create(
        organization=run.organization,
        event_type=event_type,
        event_data=data,
    )


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

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        org = None

    return AuditEvent.objects.create(
        organization=org,
        event_type=event_type,
        event_data=event_data,
    )

