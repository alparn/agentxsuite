"""
Run services for orchestrating tool execution.
"""
from __future__ import annotations

from django.utils import timezone

from apps.agents.models import Agent
from apps.runs.models import Run
from apps.tools.models import Tool


def start_run(*, agent: Agent, tool: Tool, input_json: dict) -> Run:
    """
    Start a run (stub implementation).

    Creates a Run, sets status to succeeded immediately, and returns output.

    Args:
        agent: Agent instance
        tool: Tool instance
        input_json: Input data as dictionary

    Returns:
        Created Run instance with status=succeeded
    """
    started = timezone.now()

    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=tool,
        status="running",
        started_at=started,
        input_json=input_json or {},
    )

    # Stub: immediately succeed
    run.output_json = {"ok": True}
    run.status = "succeeded"
    run.ended_at = timezone.now()
    run.save(update_fields=["output_json", "status", "ended_at"])

    return run

