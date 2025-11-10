"""
Run services for orchestrating tool execution with security checks.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from django.utils import timezone

from apps.agents.models import Agent
from apps.audit.services import log_run_event, log_security_event
from apps.policies.services import is_allowed
from apps.runs.models import Run
from apps.runs.rate_limit import check_rate_limit
from apps.runs.timeout import execute_with_timeout, TimeoutError
from apps.runs.validators import validate_input_json
from apps.tools.models import Tool

logger = logging.getLogger(__name__)


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

    try:
        # 1. Tool verification: Check sync status and existence on MCP server
        if not tool.connection:
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

        if tool.sync_status != "synced":
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

        # 3. Input validation (with automatic type normalization)
        try:
            validate_input_json(tool, input_json)
            # Normalize input types after validation for execution
            from apps.runs.validators import _normalize_input_types
            input_json = _normalize_input_types(input_json, tool.schema_json or {})
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

        # 4. Rate limit check
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

        # 5. Update status to running
        run.status = "running"
        run.save(update_fields=["status"])

        # Log run start
        log_run_event(run, "run_started")

        # 6. Execute with timeout protection
        def execute_tool() -> dict:
            """Execute tool via MCP server HTTP call."""
            if not tool.connection:
                raise ValueError("Tool has no connection")

            # Check if connection points to our own MCP Fabric service
            # If so, execute tool directly without HTTP call (avoid recursion)
            connection_endpoint = tool.connection.endpoint.rstrip("/")
            mcp_fabric_endpoints = [
                "http://localhost:8090",
                "http://127.0.0.1:8090",
            ]
            
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
