"""
MCP Prompts endpoints.
"""
from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async
from fastapi import APIRouter, Body, Depends, Path

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    tracer = trace.get_tracer(__name__)
    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False
    tracer = None

from apps.agents.models import Agent
from apps.mcp_ext.models import Prompt
from apps.mcp_ext.services import render_prompt
from apps.policies.services import is_allowed_prompt
from apps.runs.rate_limit import check_rate_limit
from apps.tenants.models import Environment, Organization
from mcp_fabric.deps import create_token_validator, get_or_create_mcp_agent
from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/{org_id}/{env_id}/.well-known/mcp", tags=["mcp-prompts"])


def _resolve_org_env(org_id: str, env_id: str) -> tuple[Organization, Environment]:
    """
    Resolve organization and environment by ID.

    Args:
        org_id: Organization UUID string
        env_id: Environment UUID string

    Returns:
        Tuple of (Organization, Environment) instances

    Raises:
        HTTPException: 404 if organization or environment not found
    """
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.ORGANIZATION_NOT_FOUND,
            f"Organization {org_id} not found",
            404,
        )

    try:
        env = Environment.objects.get(id=env_id, organization=org)
    except Environment.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.ENVIRONMENT_NOT_FOUND,
            f"Environment {env_id} not found or doesn't belong to organization",
            404,
        )

    return org, env


@router.get("/prompts")
async def list_prompts(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:prompts"])
    ),
) -> list[dict]:
    """
    List available prompts for organization/environment.

    Requires scope: mcp:prompts

    Returns:
        List of prompt definitions (name, description, inputSchema)
        Following MCP standard with CamelCase field names.
    """
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        span = tracer.start_span("mcp.prompts.list")
        span.set_attribute("org_id", str(org_id))
        span.set_attribute("env_id", str(env_id))

    try:
        org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

        prompts_raw = await sync_to_async(list)(
            Prompt.objects.filter(organization=org, environment=env, enabled=True).values(
                "name", "description", "input_schema"
            )
        )

        # Convert to MCP standard format: input_schema -> inputSchema (CamelCase)
        prompts = []
        for p in prompts_raw:
            prompt_dict = {
                "name": p["name"],
                "description": p["description"],
                "inputSchema": p["input_schema"],  # MCP standard: CamelCase
            }
            prompts.append(prompt_dict)

        if span:
            span.set_attribute("prompt_count", len(prompts))
            span.set_status(Status(StatusCode.OK))

        return prompts
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        raise
    finally:
        if span:
            span.end()


@router.post("/prompts/{prompt_name}/invoke")
async def invoke_prompt(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    prompt_name: str = Path(..., description="Prompt name"),
    body: dict = Body(..., description="Request body with input variables"),
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:prompt:invoke"])
    ),
) -> dict:
    """
    Invoke a prompt with input variables.

    Requires scope: mcp:prompt:invoke

    Body format (supports both MCP standard and compatibility):
        {
            "arguments": {  # MCP standard format
                "variable1": "value1",
                "variable2": "value2"
            }
        }
        OR
        {
            "input": {  # Compatibility format
                "variable1": "value1",
                "variable2": "value2"
            }
        }

    Returns:
        Dictionary with "messages" list
    """
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        span = tracer.start_span("mcp.prompts.invoke")
        span.set_attribute("org_id", str(org_id))
        span.set_attribute("env_id", str(env_id))
        span.set_attribute("prompt_name", prompt_name)

    try:
        org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

        # Get prompt
        try:
            prompt = await sync_to_async(Prompt.objects.get)(
                organization=org,
                environment=env,
                name=prompt_name,
                enabled=True,
            )
        except Prompt.DoesNotExist:
            if span:
                span.set_status(Status(StatusCode.ERROR, "Prompt not found"))
            raise raise_mcp_http_exception(
                ErrorCodes.PROMPT_NOT_FOUND,
                f"Prompt '{prompt_name}' not found",
                404,
            )

        # Get input variables - support both MCP standard (arguments) and compatibility (input)
        input_vars = body.get("arguments") or body.get("input", {})
        if not isinstance(input_vars, dict):
            if span:
                span.set_status(Status(StatusCode.ERROR, "Invalid input format"))
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_REQUEST,
                "Input must be a dictionary. Use 'arguments' (MCP standard) or 'input' (compatibility).",
                400,
            )

        if span:
            span.set_attribute("input_keys", ",".join(input_vars.keys()))

        # Get or create agent for policy check
        agent = await get_or_create_mcp_agent(org, env)

        # Policy check
        allowed, reason = await sync_to_async(is_allowed_prompt)(
            agent, prompt_name, action="invoke"
        )
        if not allowed:
            if span:
                span.set_status(Status(StatusCode.ERROR, "Permission denied"))
            raise raise_mcp_http_exception(
                ErrorCodes.FORBIDDEN,
                reason or f"Access to prompt '{prompt_name}' denied",
                403,
            )

        # Rate limit check
        rate_allowed, rate_reason = await sync_to_async(check_rate_limit)(agent)
        if not rate_allowed:
            if span:
                span.set_status(Status(StatusCode.ERROR, "Rate limit exceeded"))
            raise raise_mcp_http_exception(
                ErrorCodes.FORBIDDEN,
                rate_reason or "Rate limit exceeded",
                429,
            )

        # Render prompt
        try:
            result = await sync_to_async(render_prompt)(
                prompt, input_vars, agent=agent
            )
            if span:
                message_count = len(result.get("messages", []))
                span.set_attribute("message_count", message_count)
                span.set_status(Status(StatusCode.OK))
        except ValueError as e:
            if span:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_SCHEMA,
                str(e),
                400,
            )

        return result
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        raise
    finally:
        if span:
            span.end()

