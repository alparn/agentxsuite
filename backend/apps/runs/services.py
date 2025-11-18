"""
Run services for orchestrating tool execution with security checks.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from urllib.parse import urljoin

import httpx
from django.utils import timezone

from apps.agents.models import Agent
from apps.audit.services import log_run_event, log_security_event
from apps.policies.services import is_allowed
from apps.runs.models import Run, RunStep
from apps.runs.rate_limit import check_rate_limit
from apps.runs.timeout import execute_with_timeout, TimeoutError
from apps.runs.validators import validate_input_json
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool
from libs.logging.context import set_context_ids

logger = logging.getLogger(__name__)


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
        except Agent.DoesNotExist:
            raise ValueError(
                f"Agent {context.token_agent_id} from token not found, "
                "disabled, or doesn't belong to this org/env"
            )
    
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
        except Agent.DoesNotExist:
            raise ValueError(
                f"Agent {requested_agent_id} not found, disabled, "
                "or doesn't belong to this org/env"
            )
    
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
) -> Tool:
    """
    Find tool - supports UUID and Name.
    
    Args:
        organization: Organization instance
        environment: Environment instance
        tool_identifier: Tool UUID or Name
    
    Returns:
        Tool instance
    
    Raises:
        ValueError: If tool not found
    """
    # Check if UUID
    try:
        UUID(tool_identifier)
        is_uuid = True
    except ValueError:
        is_uuid = False
    
    try:
        if is_uuid:
            return Tool.objects.get(
                id=tool_identifier,
                organization=organization,
                environment=environment,
                enabled=True,
            )
        else:
            return Tool.objects.get(
                name=tool_identifier,
                organization=organization,
                environment=environment,
                enabled=True,
            )
    except Tool.DoesNotExist:
        identifier_type = "ID" if is_uuid else "name"
        raise ValueError(
            f"Tool with {identifier_type} '{tool_identifier}' not found "
            "or not enabled in this org/env"
        )


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
    
    return {
        "run_id": str(run.id),
        "status": run.status,
        "content": content,
        "isError": run.status == "failed",
        "agent": {
            "id": str(run.agent.id),
            "name": run.agent.name,
        },
        "tool": {
            "id": str(run.tool.id),
            "name": run.tool.name,
        },
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


def _get_mcp_fabric_endpoints() -> list[str]:
    """
    Get list of MCP Fabric endpoints for own service detection.
    
    Returns both localhost and 127.0.0.1 variants of the configured MCP Fabric URL.
    """
    try:
        from mcp_fabric.deps import MCP_FABRIC_BASE_URL
        
        endpoints = [MCP_FABRIC_BASE_URL.rstrip("/")]
        
        # Also add 127.0.0.1 variant if URL contains localhost
        if "localhost" in MCP_FABRIC_BASE_URL:
            endpoints.append(MCP_FABRIC_BASE_URL.replace("localhost", "127.0.0.1").rstrip("/"))
        
        return endpoints
    except ImportError:
        # Fallback if mcp_fabric is not available
        logger.warning("Could not import MCP_FABRIC_BASE_URL, using defaults")
        return ["http://localhost:8090", "http://127.0.0.1:8090"]


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
    1. Tool verification (exists on MCP server, sync status)
    2. Policy check (is_allowed)
    3. Input validation (JSONSchema)
    4. Rate limiting
    5. Timeout protection
    6. Audit logging

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
        if not tool.connection:
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
                    "reason": "Tool has no connection",
                },
            )
            raise ValueError(f"Tool '{tool.name}' has no connection. Please sync tools first.")
        _add_run_step(run, "success", f"Connection found: {tool.connection.name}")

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
                    "sync_status": tool.sync_status,
                },
            )
            raise ValueError(
                f"Tool '{tool.name}' sync status is '{tool.sync_status}'. "
                "Please sync tools first."
            )
        _add_run_step(run, "success", "Tool is synced")

        # Verify tool exists on MCP server
        # Skip verification if tool is already synced (trust the sync status)
        # This is especially important for MCP Fabric where tools are already validated during sync
        if tool.sync_status == "synced":
            # Tool is synced, trust the sync status and skip verification
            pass
        elif not _verify_tool_exists(tool):
            run.status = "failed"
            run.error_text = (
                f"Tool '{tool.name}' does not exist on connection '{tool.connection.name}'. "
                "Please sync tools first."
            )
            run.ended_at = timezone.now()
            run.save(update_fields=["status", "error_text", "ended_at"])
            log_security_event(
                str(agent.organization.id),
                "run_denied_tool_not_found",
                {
                    "agent_id": str(agent.id),
                    "tool_id": str(tool.id),
                    "connection_id": str(tool.connection.id),
                    "reason": "Tool not found on MCP server",
                },
            )
            raise ValueError(
                f"Tool '{tool.name}' does not exist on connection '{tool.connection.name}'. "
                "Please sync tools first."
            )

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
            """Execute tool via MCP server HTTP call or system tool handler."""
            if not tool.connection:
                raise ValueError("Tool has no connection")

            # Check if this is a system tool (agentxsuite://system)
            # System tools are executed directly via handler functions, not HTTP
            if tool.is_system_tool:
                from apps.system_tools.services import TOOL_HANDLERS
                
                handler = TOOL_HANDLERS.get(tool.name)
                if not handler:
                    raise ValueError(f"System tool '{tool.name}' has no handler registered")
                
                logger.info(f"Executing system tool '{tool.name}' via handler")
                
                # Execute handler with token context
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
                
                # Convert system tool result to MCP-compatible format
                if result.get("status") == "success":
                    return result
                else:
                    raise ValueError(result.get("error_description", "System tool execution failed"))

            # Check if connection points to our own MCP Fabric service
            # If so, execute tool directly without HTTP call (avoid recursion)
            connection_endpoint = tool.connection.endpoint.rstrip("/")
            mcp_fabric_endpoints = _get_mcp_fabric_endpoints()
            
            # Check if this is our own MCP Fabric service
            is_own_service = any(
                connection_endpoint.startswith(endpoint) 
                for endpoint in mcp_fabric_endpoints
            )
            
            if is_own_service:
                # Tool is already being executed via our MCP Fabric service
                # Return a success response (the actual execution happens in mcp_fabric/routers/mcp.py)
                # This avoids recursion and HTTP 405 errors
                logger.info(
                    f"Tool '{tool.name}' executed via MCP Fabric service - "
                    "execution handled by mcp_fabric adapter"
                )
                return {
                    "status": "success",
                    "message": "Tool executed via MCP Fabric service",
                }

            # Get run endpoint from manifest or use default
            from apps.connections.services import (
                _fetch_mcp_manifest,
                _get_endpoints_from_manifest,
            )

            manifest = _fetch_mcp_manifest(tool.connection)
            run_urls = []

            if manifest:
                endpoints = _get_endpoints_from_manifest(
                    manifest, tool.connection.endpoint
                )
                if "run" in endpoints:
                    run_urls.append(endpoints["run"])

            # Add default run endpoint variants
            base = tool.connection.endpoint.rstrip("/")
            run_urls.extend([
                urljoin(base + "/", ".well-known/mcp/run"),  # Standard MCP endpoint
                urljoin(base + "/", "run"),
                urljoin(base + "/", "mcp/run"),
            ])

            # Prepare auth headers
            headers = {"Content-Type": "application/json"}
            if tool.connection.auth_method == "bearer" and tool.connection.secret_ref:
                from libs.secretstore import get_secretstore

                try:
                    secret_store = get_secretstore()
                    # Agent-Service is authorized to retrieve secrets (check_permissions=False)
                    token = secret_store.get_secret(tool.connection.secret_ref, check_permissions=False)
                    headers["Authorization"] = f"Bearer {token}"
                except Exception as e:
                    logger.warning(
                        f"Could not retrieve auth token for connection {tool.connection.name}: {e}"
                    )
                    # Don't add Authorization header - connection will fail with 401
                    # This is expected behavior: secrets must be properly configured
            elif tool.connection.auth_method == "basic" and tool.connection.secret_ref:
                from libs.secretstore import get_secretstore
                import base64

                try:
                    secret_store = get_secretstore()
                    # Agent-Service is authorized to retrieve secrets (check_permissions=False)
                    credentials = secret_store.get_secret(tool.connection.secret_ref, check_permissions=False)
                    # Assume format "username:password"
                    encoded = base64.b64encode(credentials.encode()).decode()
                    headers["Authorization"] = f"Basic {encoded}"
                except Exception as e:
                    logger.warning(
                        f"Could not retrieve auth credentials for connection {tool.connection.name}: {e}"
                    )

            # Try each run URL
            last_error = None
            for run_url in run_urls:
                try:
                    with httpx.Client(timeout=timeout_seconds) as client:
                        response = client.post(
                            run_url,
                            json={"tool": tool.name, "input": input_json},
                            headers=headers,
                        )
                        if response.status_code == 200:
                            result = response.json()
                            logger.info(
                                f"Tool '{tool.name}' executed successfully via {run_url}"
                            )
                            return result
                        elif response.status_code == 404:
                            # Tool not found - try next URL
                            continue
                        else:
                            # Other error - try next URL but log it
                            last_error = f"HTTP {response.status_code}: {response.text}"
                            logger.debug(
                                f"Error executing tool via {run_url}: {last_error}"
                            )
                            continue
                except httpx.TimeoutException:
                    last_error = f"Timeout calling {run_url}"
                    logger.debug(last_error)
                    continue
                except httpx.RequestError as e:
                    last_error = f"Request error: {e}"
                    logger.debug(f"Error calling {run_url}: {last_error}")
                    continue
                except Exception as e:
                    last_error = f"Unexpected error: {e}"
                    logger.debug(f"Unexpected error calling {run_url}: {last_error}")
                    continue

            # If we get here, all URLs failed
            raise ValueError(
                f"Could not execute tool '{tool.name}' on connection '{tool.connection.name}'. "
                f"Last error: {last_error or 'Unknown error'}"
            )

        try:
            output = execute_with_timeout(execute_tool, timeout_seconds=timeout_seconds)
            if output is None:
                _add_run_step(run, "error", f"Timeout after {timeout_seconds} seconds")
                raise TimeoutError(f"Run exceeded timeout of {timeout_seconds} seconds")

            _add_run_step(run, "success", "Tool executed successfully", {"output": output})
            run.output_json = output
            run.status = "succeeded"
            run.ended_at = timezone.now()
            run.save(update_fields=["output_json", "status", "ended_at"])

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


def _verify_tool_exists(tool: Tool) -> bool:
    """
    Verify that tool exists on MCP server.

    Checks if the tool name is present in the tools list from the connection's endpoint.

    Args:
        tool: Tool instance to verify

    Returns:
        True if tool exists on MCP server, False otherwise
    """
    if not tool.connection:
        return False

    try:
        # Try to get endpoints from manifest first
        from apps.connections.services import _fetch_mcp_manifest, _get_endpoints_from_manifest
        
        manifest = _fetch_mcp_manifest(tool.connection)
        tools_urls = []
        
        if manifest:
            endpoints = _get_endpoints_from_manifest(manifest, tool.connection.endpoint)
            if "tools" in endpoints:
                tools_urls.append(endpoints["tools"])
        
        # Add default tool endpoint variants
        tools_urls.extend([
            urljoin(tool.connection.endpoint.rstrip("/") + "/", "tools"),
            urljoin(tool.connection.endpoint.rstrip("/") + "/", "mcp/tools"),
        ])

        for tools_url in tools_urls:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(tools_url)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            tools_list = data.get("tools", [])
                            if isinstance(tools_list, list):
                                tool_names = [
                                    t.get("name")
                                    for t in tools_list
                                    if isinstance(t, dict) and "name" in t
                                ]
                                if tool.name in tool_names:
                                    logger.debug(
                                        f"Tool '{tool.name}' verified on {tools_url}"
                                    )
                                    return True
                        except ValueError:
                            logger.debug(f"Invalid JSON response from {tools_url}")
                            continue
            except httpx.TimeoutException:
                logger.debug(f"Timeout verifying tool on {tools_url}")
                continue
            except httpx.RequestError as e:
                logger.debug(f"Request error verifying tool on {tools_url}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Unexpected error verifying tool on {tools_url}: {e}")
                continue

        logger.warning(
            f"Tool '{tool.name}' not found on connection '{tool.connection.name}'"
        )
        return False
    except Exception as e:
        logger.error(f"Error verifying tool existence: {e}")
        return False
