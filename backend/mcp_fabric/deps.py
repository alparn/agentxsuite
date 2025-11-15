"""
Dependencies for MCP Fabric FastAPI service.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

import django
from asgiref.sync import sync_to_async
from decouple import config
from fastapi import Depends, HTTPException, Path, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from apps.agents.models import Agent
from apps.tenants.models import Environment, Organization
from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception
from mcp_fabric.oidc import validate_token

if TYPE_CHECKING:
    from django.contrib.auth.models import User

User = get_user_model()
security = HTTPBearer(auto_error=False)

# Configuration
MCP_FABRIC_BASE_URL = config("MCP_FABRIC_BASE_URL", default="http://localhost:8090")
OIDC_ISSUER = config("OIDC_ISSUER", default=None)


def get_prm_url() -> str:
    """Get Protected Resource Metadata URL."""
    return f"{MCP_FABRIC_BASE_URL.rstrip('/')}/.well-known/oauth-protected-resource"


def get_www_authenticate_header(
    resource: str | None = None,
    scope: str | None = None,
) -> dict[str, str]:
    """
    Get WWW-Authenticate header with PRM URL and optional resource/scope.

    Args:
        resource: Resource identifier (for resource parameter)
        scope: Required scope (for scope parameter)

    Returns:
        Dictionary with WWW-Authenticate header including resource_metadata
    """
    from mcp_fabric.settings import AUTHORIZATION_SERVERS, MCP_CANONICAL_URI

    prm_url = get_prm_url()
    resource_uri = resource or MCP_CANONICAL_URI or MCP_FABRIC_BASE_URL.rstrip("/") + "/mcp"

    # Build WWW-Authenticate header
    params = [f'realm="{prm_url}"']
    
    # Add authorization servers
    auth_servers = AUTHORIZATION_SERVERS.copy() if AUTHORIZATION_SERVERS else []
    if OIDC_ISSUER and OIDC_ISSUER not in auth_servers:
        auth_servers.append(OIDC_ISSUER)
    
    if auth_servers:
        # Use first authorization server as as_uri
        params.append(f'as_uri="{auth_servers[0]}"')
    
    # Add resource parameter
    params.append(f'resource="{resource_uri}"')
    
    # Add scope if provided
    if scope:
        params.append(f'scope="{scope}"')

    return {
        "WWW-Authenticate": f"Bearer {', '.join(params)}",
    }


def init_django() -> None:
    """
    Initialize Django (idempotent).

    This function ensures Django is set up before importing models.
    It's safe to call multiple times.
    """
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    """
    Extract Bearer token from Authorization header.

    Raises 401 with WWW-Authenticate header if token is missing.

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        Token string

    Raises:
        HTTPException: 401 if token is missing (with WWW-Authenticate header)
    """
    if not credentials:
        raise raise_mcp_http_exception(
            ErrorCodes.MISSING_TOKEN,
            "Missing Authorization header",
            status.HTTP_401_UNAUTHORIZED,
            headers=get_www_authenticate_header(),
        )
    return credentials.credentials


def get_validated_token(
    token: str,
    *,
    required_scopes: list[str] | None = None,
    required_org_id: str | None = None,
    required_env_id: str | None = None,
    resource: str | None = None,
) -> dict:
    """
    Validate token with OIDC/JWKS and check scopes/claims.

    Args:
        token: Bearer token string
        required_scopes: Required scopes (e.g., ["mcp:tools"])
        required_org_id: Required org_id in token claims
        required_env_id: Required env_id in token claims
        resource: Expected resource/audience identifier (for strict audience check)

    Returns:
        Decoded token claims

    Raises:
        HTTPException: 401/403 with WWW-Authenticate header
    """
    try:
        return validate_token(
            token,
            required_scopes=required_scopes,
            required_org_id=required_org_id,
            required_env_id=required_env_id,
            resource=resource,
        )
    except HTTPException as e:
        # Add WWW-Authenticate header to 401 errors
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            headers = get_www_authenticate_header()
            if e.headers:
                headers.update(e.headers)
            raise HTTPException(
                status_code=e.status_code,
                detail=e.detail,
                headers=headers,
            )
        raise


def require_scope(scopes: set[str], required: str) -> None:
    """
    Check if required scope is present in token scopes.

    Args:
        scopes: Set of scopes from token claims
        required: Required scope string

    Raises:
        HTTPException: 403 if scope is missing
    """
    if required not in scopes:
        raise raise_mcp_http_exception(
            ErrorCodes.INSUFFICIENT_SCOPE,
            f"Missing required scope: {required}",
            status.HTTP_403_FORBIDDEN,
        )


def create_token_validator(required_scopes: list[str] | None = None):
    """
    Create a token validator dependency with required scopes.

    Args:
        required_scopes: Required scopes for this endpoint

    Returns:
        Dependency function that validates token with scopes and org/env checks
    """

    async def validate_token_dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Security(security),
    ) -> dict:
        """
        Get and validate Bearer token with scope and org/env checks.

        This dependency:
        1. Extracts Bearer token from Authorization header
        2. Validates token with OIDC/JWKS (if configured)
        3. Checks required scopes
        4. Extracts org_id/env_id from token claims (no URL parameters - secure multi-tenant)
        5. Validates audience matches resource parameter (if provided) or MCP_CANONICAL_URI

        Args:
            request: FastAPI Request object (for extracting resource parameter)
            credentials: HTTP Bearer credentials

        Returns:
            Decoded token claims with org_id/env_id from token

        Raises:
            HTTPException: 401 if token missing/invalid, 403 if scopes/claims mismatch
        """
        from mcp_fabric.settings import MCP_CANONICAL_URI

        token = get_bearer_token(credentials)
        
        # Extract resource parameter from query string or use default
        resource = request.query_params.get("resource")
        if not resource:
            resource = MCP_CANONICAL_URI

        # Validate token and get claims (without requiring org_id/env_id in URL)
        claims = get_validated_token(
            token,
            required_scopes=required_scopes,
            required_org_id=None,  # Will be extracted from token claims
            required_env_id=None,  # Will be extracted from token claims
            resource=resource,
        )
        
        # Extract org_id/env_id from token claims (source of truth)
        org_id = claims.get("org_id")
        env_id = claims.get("env_id")
        
        if not org_id or not env_id:
            raise raise_mcp_http_exception(
                ErrorCodes.AGENT_NOT_FOUND,
                "Token missing org_id or env_id claims. Token must be issued for a specific organization/environment.",
                status.HTTP_403_FORBIDDEN,
        )
        
        # P0: Resolve Agent via (subject, issuer) mapping - Source of Truth
        # NEVER trust agent_id from token directly
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        resolved_agent = await sync_to_async(resolve_agent_from_token_claims)(
            claims, str(org_id), str(env_id)
        )

        if not resolved_agent:
            raise raise_mcp_http_exception(
                ErrorCodes.AGENT_NOT_FOUND,
                "Agent not found or access denied. No ServiceAccount matches (subject, issuer) or Agent is disabled.",
                status.HTTP_403_FORBIDDEN,
            )

        # P0: Session-Lock - Validate agent consistency
        # Query parameter agent_id (if provided) must match resolved agent
        query_agent_id = request.query_params.get("agent_id")
        if query_agent_id and query_agent_id != str(resolved_agent.id):
            raise raise_mcp_http_exception(
                ErrorCodes.AGENT_SESSION_MISMATCH,
                f"Agent ID mismatch: query specifies '{query_agent_id}' but token maps to '{resolved_agent.id}'. "
                "Agent cannot be changed during session. Use a new token to switch agents.",
                status.HTTP_403_FORBIDDEN,
            )

        # Extract client IP for audit
        client_ip = request.client.host if request.client else None
        # Try to get real IP from X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        # Generate request ID for tracing
        import uuid
        request_id = str(uuid.uuid4())
        
        # Add resolved agent_id and audit metadata to claims (for downstream use)
        claims["_resolved_agent_id"] = str(resolved_agent.id)
        claims["agent_id"] = str(resolved_agent.id)  # For backward compatibility
        claims["_client_ip"] = client_ip
        claims["_request_id"] = request_id
        claims["_jti"] = claims.get("jti")  # Pass jti through for audit
        
        return claims

    return validate_token_dependency


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> User:
    """
    Authenticate user via Bearer token (Django Token fallback).

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        Authenticated user instance

    Raises:
        HTTPException: 401 if token is invalid or missing
    """
    token_key = credentials.credentials

    try:
        token = await sync_to_async(Token.objects.select_related("user").get)(
            key=token_key
        )
        # Access user attribute (already loaded via select_related)
        user = token.user

        # Check if user is active
        if not user.is_active:
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_TOKEN,
                "User account is disabled",
                status.HTTP_401_UNAUTHORIZED,
                headers=get_www_authenticate_header(),
            )

        return user
    except Token.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            "Invalid authentication token",
            status.HTTP_401_UNAUTHORIZED,
            headers=get_www_authenticate_header(),
        )


async def get_organization(org_id: str) -> Organization:
    """
    Get organization by ID.

    Args:
        org_id: Organization UUID

    Returns:
        Organization instance

    Raises:
        HTTPException: 404 if organization not found
    """
    try:
        return await sync_to_async(Organization.objects.get)(id=org_id)
    except Organization.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.ORGANIZATION_NOT_FOUND,
            f"Organization {org_id} not found",
            status.HTTP_404_NOT_FOUND,
        )


async def get_environment(env_id: str, organization: Organization) -> Environment:
    """
    Get environment by ID, ensuring it belongs to organization.

    Args:
        env_id: Environment UUID
        organization: Organization instance

    Returns:
        Environment instance

    Raises:
        HTTPException: 404 if environment not found or doesn't belong to org
    """
    try:
        env = await sync_to_async(Environment.objects.get)(
            id=env_id, organization=organization
        )
        return env
    except Environment.DoesNotExist:
        raise raise_mcp_http_exception(
            ErrorCodes.ENVIRONMENT_NOT_FOUND,
            f"Environment {env_id} not found or doesn't belong to organization",
            status.HTTP_404_NOT_FOUND,
        )


async def get_or_create_mcp_agent(
    organization: Organization,
    environment: Environment,
) -> Agent:
    """
    Get or create a default MCP agent for the organization/environment.

    Args:
        organization: Organization instance
        environment: Environment instance

    Returns:
        Agent instance
    """
    from apps.connections.models import Connection

    # Try to find existing agent first
    agent = await sync_to_async(
        lambda: Agent.objects.filter(
            organization=organization,
            environment=environment,
            name="mcp-fabric-agent",
        ).first()
    )()

    if agent:
        return agent

    # Find or create a connection for this org/env
    connection = await sync_to_async(
        lambda: Connection.objects.filter(
            organization=organization,
            environment=environment,
        ).first()
    )()

    if not connection:
        # Create a minimal connection if none exists
        connection = await sync_to_async(Connection.objects.create)(
            organization=organization,
            environment=environment,
            name="mcp-fabric-connection",
            endpoint="http://localhost:8000",  # Placeholder
            auth_method="none",
            status="ok",
        )

    # Create agent
    agent = await sync_to_async(Agent.objects.create)(
        organization=organization,
        environment=environment,
        connection=connection,
        name="mcp-fabric-agent",
        version="1.0.0",
        enabled=True,
    )

    return agent
