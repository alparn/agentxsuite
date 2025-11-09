"""
Run services for orchestrating tool execution with security checks.
"""
from __future__ import annotations

from django.utils import timezone

from apps.agents.models import Agent
from apps.audit.services import log_run_event, log_security_event
from apps.policies.services import is_allowed
from apps.runs.models import Run
from apps.runs.rate_limit import check_rate_limit
from apps.runs.timeout import execute_with_timeout, TimeoutError
from apps.runs.validators import validate_input_json
from apps.tools.models import Tool


def start_run(
    *,
    agent: Agent,
    tool: Tool,
    input_json: dict,
    timeout_seconds: int = 30,
) -> Run:
    """
    Start a run with comprehensive security checks.

    Security checks performed:
    1. Policy check (is_allowed)
    2. Input validation (JSONSchema)
    3. Rate limiting
    4. Timeout protection
    5. Audit logging

    Args:
        agent: Agent instance
        tool: Tool instance
        input_json: Input data as dictionary
        timeout_seconds: Maximum execution time in seconds

    Returns:
        Created Run instance

    Raises:
        ValueError: If security check fails or validation error
        TimeoutError: If execution exceeds timeout
    """
    started = timezone.now()

    # Create run record first (for audit trail)
    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=tool,
        status="pending",
        started_at=started,
        input_json=input_json or {},
    )

    try:
        # 1. Policy check
        allowed, deny_reason = is_allowed(agent, tool, input_json)
        if not allowed:
            run.status = "failed"
            run.error_text = f"Policy denied: {deny_reason}"
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_security_event(
                str(agent.organization.id),
                "run_denied_policy",
                {
                    "agent_id": str(agent.id),
                    "tool_id": str(tool.id),
                    "reason": deny_reason,
                },
            )
            raise ValueError(f"Policy denied: {deny_reason}")

        # 2. Input validation
        try:
            validate_input_json(tool, input_json)
        except ValueError as e:
            run.status = "failed"
            run.error_text = str(e)
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_security_event(
                str(agent.organization.id),
                "run_denied_validation",
                {
                    "agent_id": str(agent.id),
                    "tool_id": str(tool.id),
                    "error": str(e),
                },
            )
            raise

        # 3. Rate limit check
        rate_allowed, rate_reason = check_rate_limit(agent)
        if not rate_allowed:
            run.status = "failed"
            run.error_text = f"Rate limit: {rate_reason}"
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_security_event(
                str(agent.organization.id),
                "run_denied_rate_limit",
                {
                    "agent_id": str(agent.id),
                    "tool_id": str(tool.id),
                    "reason": rate_reason,
                },
            )
            raise ValueError(f"Rate limit: {rate_reason}")

        # 4. Update status to running
        run.status = "running"
        run.save(update_fields=["status"])

        # Log run start
        log_run_event(run, "run_started")

        # 5. Execute with timeout protection
        def execute_tool() -> dict:
            """Execute tool (stub implementation)."""
            # In real implementation, this would call the actual tool
            # For now, return success
            return {"ok": True, "result": "Tool executed successfully"}

        try:
            output = execute_with_timeout(execute_tool, timeout_seconds=timeout_seconds)
            if output is None:
                raise TimeoutError(f"Run exceeded timeout of {timeout_seconds} seconds")

            run.output_json = output
            run.status = "succeeded"
            run.ended_at = timezone.now()
            run.save(update_fields=["output_json", "status", "ended_at"])

            # Log success
            log_run_event(run, "run_succeeded")

        except TimeoutError as e:
            run.status = "failed"
            run.error_text = str(e)
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_run_event(run, "run_failed_timeout")
            raise

        except Exception as e:
            run.status = "failed"
            run.error_text = str(e)
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_run_event(run, "run_failed_error")
            raise

    except (ValueError, TimeoutError) as e:
        # Re-raise security/validation errors
        raise
    except Exception as e:
        # Log unexpected errors
        run.status = "failed"
        run.error_text = f"Unexpected error: {str(e)}"
        run.ended_at = timezone.now()
        run.save(update_fields=["status", "error_text", "ended_at"])
        log_run_event(run, "run_failed_unexpected")
        raise

    return run
