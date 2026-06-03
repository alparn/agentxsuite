"""
Run services for orchestrating tool execution with security checks.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from apps.agents.models import Agent
from apps.audit.services import log_run_event, log_security_event
from apps.connections import mcp_client
from apps.policies.services import is_allowed
from apps.runs.models import Run, RunStep
from apps.runs.rate_limit import check_rate_limit
from apps.runs.timeout import TimeoutError, execute_with_timeout
from apps.runs.validators import validate_input_json
from apps.tenants.models import Environment, Organization
from apps.tools.models import CuratedTool, Tool
from libs.logging.context import set_context_ids

logger = logging.getLogger(__name__)

ExecutableTool = Tool | CuratedTool


def _tool_curation_enabled() -> bool:
    """Return whether curated tools should be exposed and executable."""
    return bool(getattr(settings, "TOOL_CURATION_ENABLED", False))


def _agent_tool_mode() -> str:
    """Return the configured agent-facing tool exposure mode."""
    return getattr(settings, "AGENT_TOOL_MODE", "raw_only")


@dataclass
class ExecutionContext:
    """
    Execution context for Audit & Security.
    
    Contains information about the execution context:
    - User-ID (for Django Auth)
    - Agent-ID from Token (highest priority)
    - Audit metadata (JTI, Client-IP, Request-ID)
    """
    user_id: str | None = None
    token_agent_id: str | None = None  # Agent from JWT Token
    jti: str | None = None
    client_ip: str | None = None
    request_id: str | None = None

    @classmethod
    def from_django_request(cls, request) -> ExecutionContext:
        """
        Create from Django REST Framework Request.
        
        Args:
            request: DRF Request object
        
        Returns:
            ExecutionContext instance
        """
        return cls(
            user_id=str(request.user.id) if request.user.is_authenticated else None,
            client_ip=request.META.get("REMOTE_ADDR"),
        )
    
    @classmethod
    def from_token_claims(cls, claims: dict) -> ExecutionContext:
        """
        Create from JWT Token Claims.
        
        Args:
            claims: Dictionary with Token Claims
        
        Returns:
            ExecutionContext instance
        """
        return cls(
            token_agent_id=claims.get("_resolved_agent_id") or claims.get("agent_id"),
            jti=claims.get("_jti"),
            client_ip=claims.get("_client_ip"),
            request_id=claims.get("_request_id"),
        )


def resolve_agent(
    *,
    organization: Organization,
    environment: Environment,
    requested_agent_id: str | None = None,
    context: ExecutionContext,
) -> Agent:
    """
    STANDARDIZED AGENT SELECTION.
    
    Rules (in this order):
    1. Agent from Token (highest priority) - Source of Truth
    2. Agent from Request (only if no Token-Agent)
    3. ERROR - NO Fallback!
    
    Args:
        organization: Organization instance
        environment: Environment instance
        requested_agent_id: Agent-ID from Request Body/Query
        context: ExecutionContext with token_agent_id
    
    Returns:
        Agent instance
    
    Raises:
        ValueError: If no agent found or mismatch
    """
    # Rule 1: Token has priority
    if context.token_agent_id:
        # Session-Lock: If request also has agent_id, it must match
        if requested_agent_id and requested_agent_id != context.token_agent_id:
            raise ValueError(
                f"Agent mismatch: Token contains agent_id={context.token_agent_id}, "
                f"but request specifies agent_id={requested_agent_id}. "
                "Agent cannot be changed within a session."
            )
        
        # Load agent from token
        try:
            agent = Agent.objects.get(
                id=context.token_agent_id,
                organization=organization,
                environment=environment,
                enabled=True,
            )
            logger.info(
                f"Agent resolved from token: {agent.name}",
                extra={"agent_id": str(agent.id), "source": "token"},
            )
            return agent
        except Agent.DoesNotExist as exc:
            raise ValueError(
                f"Agent {context.token_agent_id} from token not found, "
                "disabled, or doesn't belong to this org/env"
            ) from exc
    
    # Rule 2: Request-Agent (only if no Token-Agent)
    if requested_agent_id:
        try:
            agent = Agent.objects.get(
                id=requested_agent_id,
                organization=organization,
                environment=environment,
                enabled=True,
            )
            logger.info(
                f"Agent resolved from request: {agent.name}",
                extra={"agent_id": str(agent.id), "source": "request"},
            )
            return agent
        except Agent.DoesNotExist as exc:
            raise ValueError(
                f"Agent {requested_agent_id} not found, disabled, "
                "or doesn't belong to this org/env"
            ) from exc
    
    # Rule 3: NO FALLBACK - explicitly required
    raise ValueError(
        "Agent selection required. "
        "Provide 'agent' in request body or use an agent token. "
        "For security reasons, automatic agent selection is not allowed."
    )


def resolve_tool(
    *,
    organization: Organization,
    environment: Environment,
    tool_identifier: str,
) -> ExecutableTool:
    """
    Find executable tool - supports UUID and Name.
    
    Args:
        organization: Organization instance
        environment: Environment instance
        tool_identifier: Tool UUID or Name
    
    Returns:
        Tool or CuratedTool instance
    
    Raises:
        ValueError: If tool not found
    """
    # Check if UUID
    try:
        UUID(tool_identifier)
        is_uuid = True
    except ValueError:
        is_uuid = False
    
    if _tool_curation_enabled() and _agent_tool_mode() != "raw_only":
        try:
            if is_uuid:
                curated_tool = CuratedTool.objects.select_related("connection").get(
                    id=tool_identifier,
                    organization=organization,
                    environment=environment,
                )
            else:
                curated_tool = CuratedTool.objects.select_related("connection").get(
                    name=tool_identifier,
                    organization=organization,
                    environment=environment,
                )

            if not curated_tool.enabled:
                raise ValueError(f"Tool '{curated_tool.name}' is disabled")
            return curated_tool
        except CuratedTool.DoesNotExist as exc:
            if _agent_tool_mode() == "curated_only":
                identifier_type = "ID" if is_uuid else "name"
                raise ValueError(
                    f"Tool with {identifier_type} '{tool_identifier}' not found in this org/env"
                ) from exc

    try:
        if is_uuid:
            tool = Tool.objects.select_related("connection").get(
                id=tool_identifier,
                organization=organization,
                environment=environment,
            )
        else:
            raw_filter = {
                "name": tool_identifier,
                "organization": organization,
                "environment": environment,
            }
            if _tool_curation_enabled() and _agent_tool_mode() == "curated_and_raw":
                raw_filter["is_agent_visible"] = True
            tool = Tool.objects.select_related("connection").get(**raw_filter)

        if not tool.enabled:
            raise ValueError(f"Tool '{tool.name}' is disabled")

        return tool

    except Tool.DoesNotExist as exc:
        identifier_type = "ID" if is_uuid else "name"
        raise ValueError(
            f"Tool with {identifier_type} '{tool_identifier}' not found in this org/env"
        ) from exc


def format_run_response(run: Run) -> dict:
    """
    Format Run as MCP-compatible Response.
    
    Unified format for Tool Registry and MCP Fabric.
    
    Args:
        run: Run instance
    
    Returns:
        Dictionary with MCP-compatible format
    """
    # Format output as MCP Content
    content = []
    if run.status == "succeeded" and run.output_json:
        if isinstance(run.output_json, str):
            content.append({"type": "text", "text": run.output_json})
        else:
            # Format JSON as text
            content.append({
                "type": "text",
                "text": json.dumps(run.output_json, indent=2)
            })
    elif run.status == "failed" and run.error_text:
        content.append({"type": "text", "text": run.error_text})
    
    duration_ms = None
    if run.ended_at and run.started_at:
        duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
    
    executable_tool = run.executable_tool
    tool_payload = (
        {
            "id": str(executable_tool.id),
            "name": executable_tool.name,
            "kind": "curated" if run.curated_tool_id else "raw",
        }
        if executable_tool
        else None
    )

    return {
        "run_id": str(run.id),
        "status": run.status,
        "content": content,
        "isError": run.status == "failed",
        "agent": {
            "id": str(run.agent.id),
            "name": run.agent.name,
        },
        "tool": tool_payload,
        "execution": {
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "duration_ms": duration_ms,
        },
    }


def execute_tool_run(
    *,
    organization: Organization,
    environment: Environment,
    tool_identifier: str,
    agent_identifier: str | None,
    input_data: dict,
    context: ExecutionContext,
    timeout_seconds: int = 30,
) -> dict:
    """
    UNIFIED TOOL EXECUTION.
    
    Used by both APIs:
    - Tool Registry API (legacy)
    - MCP Fabric API (standard)
    
    Args:
        organization: Organization instance
        environment: Environment instance
        tool_identifier: Tool UUID or Name
        agent_identifier: Agent UUID (optional, can come from Token)
        input_data: Input data as Dictionary
        context: ExecutionContext with Token info
        timeout_seconds: Timeout in seconds
    
    Returns:
        Unified response dictionary (MCP-compatible)
    
    Raises:
        ValueError: On Validation/Security Errors
    """
    # 1. Resolve Tool
    tool = resolve_tool(
        organization=organization,
        environment=environment,
        tool_identifier=tool_identifier,
    )
    
    # 2. Resolve Agent (standardisiert!)
    agent = resolve_agent(
        organization=organization,
        environment=environment,
        requested_agent_id=agent_identifier,
        context=context,
    )
    
    # 3. Execute via start_run (existing security checks)
    run = start_run(
        agent=agent,
        tool=tool,
        input_json=input_data,
        timeout_seconds=timeout_seconds,
    )
    
    # 4. Format Response (MCP-compatible)
    return format_run_response(run)


def _add_run_step(
    run: Run,
    step_type: str,
    message: str,
    details: dict | None = None,
) -> RunStep:
    """
    Add a step to a run for tracking progress.
    
    Args:
        run: Run instance
        step_type: Type of step (info, success, warning, error, check, execution)
        message: Human-readable message
        details: Optional additional details as dict
        
    Returns:
        Created RunStep instance
    """
    return RunStep.objects.create(
        run=run,
        step_type=step_type,
        message=message,
        details=details or {},
    )


def _execute_raw_tool(
    *,
    agent: Agent,
    tool: Tool,
    input_json: dict,
    context_input_json: dict | None = None,
) -> dict:
    """Execute a raw or system tool after start_run has completed its gates."""
    if not tool.connection_id or not tool.connection:
        raise ValueError("Tool has no connection")

    if tool.is_system_tool:
        from apps.system_tools.services import TOOL_HANDLERS

        handler = TOOL_HANDLERS.get(tool.name)
        if not handler:
            raise ValueError(f"System tool '{tool.name}' has no handler registered")

        logger.info(f"Executing system tool '{tool.name}' via handler")

        from libs.logging.context import get_context_ids

        context_ids = get_context_ids()
        result = handler(
            organization_id=str(agent.organization.id),
            environment_id=str(agent.environment.id),
            **input_json,
            _token_agent_id=str(agent.id),
            _jti=context_ids.get("jti"),
            _client_ip=context_ids.get("client_ip"),
            _request_id=context_ids.get("request_id"),
        )

        if result.get("status") == "success":
            return result
        raise ValueError(result.get("error_description", "System tool execution failed"))

    try:
        return mcp_client.call_tool(tool.connection, tool.name, context_input_json or input_json)
    except mcp_client.MCPClientError as exc:
        raise ValueError(str(exc)) from exc


def start_run(
    *,
    agent: Agent,
    tool: ExecutableTool,
    input_json: dict,
    timeout_seconds: int = 30,
) -> Run:
    """
    Start a run with comprehensive security checks.

    Security checks performed:
    1. Tool verification (exists on MCP server, sync status)
    2. Policy check (is_allowed)
    3. Input validation (JSONSchema)
    4. Rate limiting
    5. Timeout protection
    6. Audit logging

    Args:
        agent: Agent instance
        tool: Tool or CuratedTool instance
        input_json: Input data as dictionary
        timeout_seconds: Maximum execution time in seconds

    Returns:
        Created Run instance

    Raises:
        ValueError: If security check fails or validation error
        TimeoutError: If execution exceeds timeout
    """
    started = timezone.now()
    is_curated = isinstance(tool, CuratedTool)
    if is_curated and not _tool_curation_enabled():
        raise ValueError("Tool curation is disabled")

    # Create run record first (for audit trail)
    run = Run.objects.create(
        organization=agent.organization,
        environment=agent.environment,
        agent=agent,
        tool=None if is_curated else tool,
        curated_tool=tool if is_curated else None,
        status="pending",
        started_at=started,
        input_json=input_json or {},
    )

    # Set run_id in logging context for automatic log injection
    set_context_ids(
        run_id=str(run.id),
        agent_id=str(agent.id),
        tool_id=str(tool.id),
        org_id=str(agent.organization.id),
        env_id=str(agent.environment.id),
    )

    # Initial step: Run created
    _add_run_step(run, "info", f"Run created for tool '{tool.name}' with agent '{agent.name}'")

    try:
        # 1. Tool verification: Check sync status and existence on MCP server
        _add_run_step(run, "check", "Checking tool connection...")
        if not tool.connection_id or not tool.connection:
            _add_run_step(run, "error", f"Tool '{tool.name}' has no connection. Please sync tools first.")
            run.status = "failed"
            run.error_text = f"Tool '{tool.name}' has no connection. Please sync tools first."
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_security_event(
                str(agent.organization.id),
                "run_denied_no_connection",
                {
                    "agent_id": str(agent.id),
                    "tool_id": str(tool.id),
                    "tool_kind": "curated" if is_curated else "raw",
                    "reason": "Tool has no connection",
                },
            )
            raise ValueError(f"Tool '{tool.name}' has no connection. Please sync tools first.")
        _add_run_step(run, "success", f"Connection found: {tool.connection.name}")

        if not is_curated:
            _add_run_step(run, "check", f"Checking sync status... (current: {tool.sync_status})")
            if tool.sync_status != "synced":
                _add_run_step(run, "error", f"Tool '{tool.name}' is not synced (status: {tool.sync_status}). Please sync tools first.")
                run.status = "failed"
                run.error_text = (
                    f"Tool '{tool.name}' sync status is '{tool.sync_status}'. "
                    "Please sync tools first."
                )
                run.ended_at = timezone.now()
                run.save(update_fields=["status", "error_text", "ended_at"])
                log_security_event(
                    str(agent.organization.id),
                    "run_denied_sync_status",
                    {
                        "agent_id": str(agent.id),
                        "tool_id": str(tool.id),
                        "tool_kind": "raw",
                        "sync_status": tool.sync_status,
                    },
                )
                raise ValueError(
                    f"Tool '{tool.name}' sync status is '{tool.sync_status}'. "
                    "Please sync tools first."
                )
            _add_run_step(run, "success", "Tool is synced")

        # 2. Policy check
        _add_run_step(run, "check", "Checking policy permissions...")
        allowed, deny_reason = is_allowed(agent, tool, input_json)
        if not allowed:
            _add_run_step(run, "error", f"Policy denied: {deny_reason}")
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
                    "tool_kind": "curated" if is_curated else "raw",
                    "reason": deny_reason,
                },
            )
            raise ValueError(f"Policy denied: {deny_reason}")
        _add_run_step(run, "success", "Policy permission granted")

        # 3. Input validation (with automatic type normalization)
        _add_run_step(run, "check", "Validating input parameters...")
        try:
            validate_input_json(tool, input_json)
            # Normalize input types after validation for execution
            from apps.runs.validators import _normalize_input_types
            input_json = _normalize_input_types(input_json, tool.schema_json or {})
            _add_run_step(run, "success", "Input parameters validated", {"input": input_json})
        except ValueError as e:
            _add_run_step(run, "error", f"Validation error: {str(e)}")
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
                    "tool_kind": "curated" if is_curated else "raw",
                    "error": str(e),
                },
            )
            raise

        # 4. Rate limit check
        _add_run_step(run, "check", "Checking rate limit...")
        rate_allowed, rate_reason = check_rate_limit(agent)
        if not rate_allowed:
            _add_run_step(run, "error", f"Rate limit exceeded: {rate_reason}")
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
                    "tool_kind": "curated" if is_curated else "raw",
                    "reason": rate_reason,
                },
            )
            raise ValueError(f"Rate limit: {rate_reason}")
        _add_run_step(run, "success", "Rate limit OK")

        # 5. Update status to running
        run.status = "running"
        run.save(update_fields=["status"])

        # Log run start
        log_run_event(run, "run_started")
        _add_run_step(run, "execution", "Starting tool execution...")

        # 6. Execute with timeout protection
        def execute_tool() -> dict:
            """Execute tool via the configured MCP client or system tool handler."""
            if is_curated:
                from apps.tools.curation_service import CurationService

                def raw_executor(raw_tool: Tool, raw_input: dict) -> dict:
                    return _execute_raw_tool(
                        agent=agent,
                        tool=raw_tool,
                        input_json=raw_input,
                    )

                return CurationService.execute_curated_tool(
                    curated_tool=tool,
                    input_data=input_json,
                    executor_func=raw_executor,
                )

            return _execute_raw_tool(agent=agent, tool=tool, input_json=input_json)

        try:
            output = execute_with_timeout(execute_tool, timeout_seconds=timeout_seconds)
            if output is None:
                _add_run_step(run, "error", f"Timeout after {timeout_seconds} seconds")
                raise TimeoutError(f"Run exceeded timeout of {timeout_seconds} seconds")

            _add_run_step(run, "success", "Tool executed successfully", {"output": output})
            run.output_json = output
            run.status = "succeeded"
            run.ended_at = timezone.now()
            
            # Extract token usage from response (if available)
            # This allows tracking LLM costs when tools make LLM calls
            if output and isinstance(output, dict):
                usage = output.get("usage") or output.get("token_usage")
                if usage and isinstance(usage, dict):
                    from apps.runs.cost_services import update_run_with_usage
                    _add_run_step(run, "info", "Extracting token usage for cost calculation", {"usage": usage})
                    try:
                        # update_run_with_usage will update run fields and calculate costs
                        # save=False because we save once at the end
                        update_run_with_usage(run, usage, save=False)
                        _add_run_step(run, "success", f"Token usage recorded: {run.input_tokens} input + {run.output_tokens} output tokens, cost: {run.cost_total} {run.cost_currency}")
                    except Exception as e:
                        # Don't fail the run if cost calculation fails
                        logger.warning(f"Failed to calculate token usage/cost for run {run.id}: {e}")
                        _add_run_step(run, "warning", f"Cost calculation failed: {str(e)}")
            
            # Save all fields once
            run.save(update_fields=["output_json", "status", "ended_at", "input_tokens", "output_tokens", "total_tokens", "model_name", "cost_input", "cost_output", "cost_total", "cost_currency"])

            # Log success
            log_run_event(run, "run_succeeded")
            _add_run_step(run, "success", f"Run completed successfully in {(timezone.now() - started).total_seconds():.2f} seconds")

        except TimeoutError as e:
            _add_run_step(run, "error", f"Timeout error: {str(e)}")
            run.status = "failed"
            run.error_text = str(e)
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_run_event(run, "run_failed_timeout")
            raise

        except Exception as e:
            _add_run_step(run, "error", f"Execution error: {str(e)}")
            run.status = "failed"
            run.error_text = str(e)
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_run_event(run, "run_failed_error")
            raise

    except (ValueError, TimeoutError):
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
