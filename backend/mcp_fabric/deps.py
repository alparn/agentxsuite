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
from fastapi import Depends, HTTPException, Path, Security, status
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


def get_www_authenticate_header() -> dict[str, str]:
    """
    Get WWW-Authenticate header with PRM URL.

    Returns:
        Dictionary with WWW-Authenticate header
    """
    prm_url = get_prm_url()
    if OIDC_ISSUER:
        return {
            "WWW-Authenticate": f'Bearer realm="{prm_url}", as_uri="{OIDC_ISSUER}"'
        }
    return {"WWW-Authenticate": f'Bearer realm="{prm_url}"'}


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
) -> dict:
    """
    Validate token with OIDC/JWKS and check scopes/claims.

    Args:
        token: Bearer token string
        required_scopes: Required scopes (e.g., ["mcp:tools"])
        required_org_id: Required org_id in token claims
        required_env_id: Required env_id in token claims

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
        org_id: UUID = Path(...),
        env_id: UUID = Path(...),
        credentials: HTTPAuthorizationCredentials | None = Security(security),
    ) -> dict:
        """
        Get and validate Bearer token with scope and org/env checks.

        This dependency:
        1. Extracts Bearer token from Authorization header
        2. Validates token with OIDC/JWKS (if configured)
        3. Checks required scopes
        4. Validates org_id/env_id claims match URL parameters (cross-tenant protection)

        Args:
            org_id: Organization ID from URL path
            env_id: Environment ID from URL path
            credentials: HTTP Bearer credentials

        Returns:
            Decoded token claims

        Raises:
            HTTPException: 401 if token missing/invalid, 403 if scopes/claims mismatch
        """
        token = get_bearer_token(credentials)
        claims = get_validated_token(
            token,
            required_scopes=required_scopes,
            required_org_id=str(org_id),
            required_env_id=str(env_id),
        )
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
