"""
Protected Resource Metadata (PRM) endpoint for OAuth2/OIDC.
"""
from __future__ import annotations

from decouple import config
from fastapi import APIRouter

from mcp_fabric.settings import AUTHORIZATION_SERVERS, MCP_CANONICAL_URI, SCOPES_SUPPORTED

router = APIRouter(tags=["prm"])

# OIDC configuration (fallback)
OIDC_ISSUER = config("OIDC_ISSUER", default=None)
MCP_FABRIC_BASE_URL = config("MCP_FABRIC_BASE_URL", default="http://localhost:8090")


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource() -> dict:
    """
    Protected Resource Metadata (PRM) endpoint.

    Returns OAuth2/OIDC metadata for protected resources according to
    RFC 8414 (OAuth 2.0 Authorization Server Metadata) and RFC 8693 (OAuth 2.0 Token Exchange).

    Includes resource_metadata with detailed information about the protected resource.

    Returns:
        PRM metadata dictionary with:
        - resource: Resource identifier (MCP_CANONICAL_URI)
        - authorization_servers: List of authorization server issuer URIs
        - scopes_supported: List of supported scopes
        - resource_metadata: Additional metadata about the resource
    """
    # Use configured authorization servers or fallback to OIDC_ISSUER
    authorization_servers = AUTHORIZATION_SERVERS.copy() if AUTHORIZATION_SERVERS else []
    if OIDC_ISSUER and OIDC_ISSUER not in authorization_servers:
        authorization_servers.append(OIDC_ISSUER)

    # Resource identifier (canonical URI)
    resource = MCP_CANONICAL_URI or f"{MCP_FABRIC_BASE_URL.rstrip('/')}/mcp"

    # Resource metadata with additional information
    resource_metadata = {
        "resource": resource,
        "resource_type": "mcp_fabric",
        "version": "1.0.0",
        "endpoints": {
            "manifest": "/mcp/{org_id}/{env_id}/.well-known/mcp/manifest.json",
            "tools": "/mcp/{org_id}/{env_id}/.well-known/mcp/tools",
            "run": "/mcp/{org_id}/{env_id}/.well-known/mcp/run",
            "resources": "/mcp/{org_id}/{env_id}/.well-known/mcp/resources",
            "prompts": "/mcp/{org_id}/{env_id}/.well-known/mcp/prompts",
        },
        "authentication": {
            "schemes": ["Bearer"],
            "token_format": "JWT",
            "audience_validation": "strict",  # No token passthrough
            "resource_parameter_supported": True,
        },
    }

    return {
        "resource": resource,
        "authorization_servers": authorization_servers,
        "scopes_supported": SCOPES_SUPPORTED,
        "resource_metadata": resource_metadata,
    }




