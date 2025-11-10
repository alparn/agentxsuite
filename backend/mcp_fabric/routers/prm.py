"""
Protected Resource Metadata (PRM) endpoint for OAuth2/OIDC.
"""
from __future__ import annotations

from decouple import config
from fastapi import APIRouter

router = APIRouter(tags=["prm"])

# OIDC configuration
OIDC_ISSUER = config("OIDC_ISSUER", default=None)
MCP_FABRIC_BASE_URL = config("MCP_FABRIC_BASE_URL", default="http://localhost:8090")


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource() -> dict:
    """
    Protected Resource Metadata (PRM) endpoint.

    Returns OAuth2/OIDC metadata for protected resources according to
    RFC 8414 (OAuth 2.0 Authorization Server Metadata) and RFC 8693 (OAuth 2.0 Token Exchange).

    Returns:
        PRM metadata dictionary with authorization_servers, scopes_supported, resource
    """
    authorization_servers = []
    if OIDC_ISSUER:
        authorization_servers.append(OIDC_ISSUER)

    # MCP-specific scopes
    scopes_supported = [
        "mcp:manifest",  # Access to manifest endpoint
        "mcp:tools",  # Access to tools listing
        "mcp:run",  # Access to tool execution
        "mcp:resources",  # Access to resources listing
        "mcp:resource:read",  # Access to read resource content
        "mcp:prompts",  # Access to prompts listing
        "mcp:prompt:invoke",  # Access to invoke prompts
    ]

    # Resource identifier (this MCP Fabric instance)
    resource = f"{MCP_FABRIC_BASE_URL.rstrip('/')}/mcp"

    return {
        "resource": resource,
        "authorization_servers": authorization_servers,
        "scopes_supported": scopes_supported,
    }




