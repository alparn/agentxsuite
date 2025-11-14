"""
MCP Resources endpoints.
"""
from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async
from fastapi import APIRouter, Depends, Path

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    tracer = trace.get_tracer(__name__)
    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False
    tracer = None

from apps.agents.models import Agent
from apps.mcp_ext.models import Resource
from apps.mcp_ext.services import fetch_resource
from apps.policies.services import is_allowed_resource
from apps.runs.rate_limit import check_rate_limit
from apps.tenants.models import Environment, Organization
from mcp_fabric.deps import create_token_validator, get_or_create_mcp_agent
from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/{org_id}/{env_id}/.well-known/mcp", tags=["mcp-resources"])


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


@router.get("/resources")
async def list_resources(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:resources"])
    ),
) -> list[dict]:
    """
    List available resources for organization/environment.

    Requires scope: mcp:resources

    Returns:
        List of resource definitions (name, type, mimeType, schema_json)
        Following MCP standard with CamelCase field names.
    """
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        span = tracer.start_span("mcp.resources.list")
        span.set_attribute("org_id", str(org_id))
        span.set_attribute("env_id", str(env_id))

    try:
        org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

        resources_raw = await sync_to_async(list)(
            Resource.objects.filter(
                organization=org, environment=env, enabled=True
            ).values("name", "type", "mime_type", "schema_json")
        )

        # Convert to MCP standard format: mime_type -> mimeType (CamelCase)
        resources = []
        for r in resources_raw:
            resource_dict = {
                "name": r["name"],
                "type": r["type"],
                "mimeType": r["mime_type"],  # MCP standard: CamelCase
                "schema_json": r["schema_json"],
            }
            resources.append(resource_dict)

        if span:
            span.set_attribute("resource_count", len(resources))
            span.set_status(Status(StatusCode.OK))

        return resources
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        raise
    finally:
        if span:
            span.end()


@router.get("/resources/{resource_name}")
async def get_resource(
    org_id: UUID = Path(..., description="Organization ID"),
    env_id: UUID = Path(..., description="Environment ID"),
    resource_name: str = Path(..., description="Resource name"),
    token_claims: dict = Depends(
        create_token_validator(required_scopes=["mcp:resource:read"])
    ),
) -> dict:
    """
    Get resource content.

    Requires scope: mcp:resource:read

    Returns:
        Resource content dictionary with name, mimeType, and content
        Following MCP standard with CamelCase field names.
    """
    span = None
    if OTELEMETRY_AVAILABLE and tracer:
        span = tracer.start_span("mcp.resources.read")
        span.set_attribute("org_id", str(org_id))
        span.set_attribute("env_id", str(env_id))
        span.set_attribute("resource_name", resource_name)

    try:
        org, env = await sync_to_async(_resolve_org_env)(str(org_id), str(env_id))

        # Get resource
        try:
            resource = await sync_to_async(Resource.objects.get)(
                organization=org,
                environment=env,
                name=resource_name,
                enabled=True,
            )
            if span:
                span.set_attribute("resource_type", resource.type)
        except Resource.DoesNotExist:
            if span:
                span.set_status(Status(StatusCode.ERROR, "Resource not found"))
            raise raise_mcp_http_exception(
                ErrorCodes.RESOURCE_NOT_FOUND,
                f"Resource '{resource_name}' not found",
                404,
            )

        # Get or create agent for policy check
        agent = await get_or_create_mcp_agent(org, env)

        # Policy check
        allowed, reason = await sync_to_async(is_allowed_resource)(
            agent, resource_name, action="read"
        )
        if not allowed:
            if span:
                span.set_status(Status(StatusCode.ERROR, "Permission denied"))
            raise raise_mcp_http_exception(
                ErrorCodes.FORBIDDEN,
                reason or f"Access to resource '{resource_name}' denied",
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

        # Fetch resource content
        try:
            content = await sync_to_async(fetch_resource)(resource, agent=agent)
            if span:
                content_size = len(str(content)) if content else 0
                span.set_attribute("content_size", content_size)
                span.set_status(Status(StatusCode.OK))
        except ValueError as e:
            if span:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise raise_mcp_http_exception(
                ErrorCodes.EXECUTION_FAILED,
                str(e),
                500,
            )

        return {
            "name": resource.name,
            "mimeType": resource.mime_type,  # MCP standard: CamelCase
            "content": content,
        }
    except Exception as e:
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        raise
    finally:
        if span:
            span.end()

