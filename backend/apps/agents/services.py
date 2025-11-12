"""
Services for agent token management.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from decouple import config
from django.utils import timezone as django_timezone

from apps.agents.models import Agent, IssuedToken
from mcp_fabric.settings import MCP_CANONICAL_URI, MCP_TOKEN_MAX_TTL_MINUTES

logger = logging.getLogger(__name__)

# JWT signing key (should be loaded from SecretStore in production)
JWT_PRIVATE_KEY = config("JWT_PRIVATE_KEY", default=None)
JWT_PUBLIC_KEY = config("JWT_PUBLIC_KEY", default=None)
JWT_ISSUER = config("JWT_ISSUER", default="https://agentxsuite.local")
JWT_ALGORITHM = "RS256"


def _get_signing_key() -> rsa.RSAPrivateKey:
    """
    Get JWT signing private key.
    
    In production, this should load from SecretStore.
    For development, generates a key if not configured.
    """
    if JWT_PRIVATE_KEY:
        try:
            return serialization.load_pem_private_key(
                JWT_PRIVATE_KEY.encode(),
                password=None,
            )
        except Exception as e:
            logger.error(f"Failed to load JWT private key: {e}")
            raise
    
    # Fallback: generate a key (for development only)
    logger.warning("JWT_PRIVATE_KEY not configured, generating temporary key (development only)")
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _get_public_key() -> rsa.RSAPublicKey:
    """Get JWT public key."""
    if JWT_PUBLIC_KEY:
        try:
            return serialization.load_pem_public_key(JWT_PUBLIC_KEY.encode())
        except Exception:
            pass
    
    # Fallback: derive from private key
    private_key = _get_signing_key()
    return private_key.public_key()


def generate_token_for_agent(
    agent: Agent,
    *,
    ttl_minutes: int | None = None,
    scopes: list[str] | None = None,
    metadata: dict | None = None,
) -> tuple[str, IssuedToken]:
    """
    Generate a JWT token for an agent.
    
    Args:
        agent: Agent instance
        ttl_minutes: Token TTL in minutes (default: MCP_TOKEN_MAX_TTL_MINUTES)
        scopes: List of scopes to grant (default: ["mcp:run", "mcp:tools"])
        metadata: Additional metadata to store with token
    
    Returns:
        Tuple of (token_string, IssuedToken instance)
    """
    if not agent.service_account:
        raise ValueError("Agent must have a ServiceAccount to generate tokens")
    
    sa = agent.service_account
    
    # Default TTL
    if ttl_minutes is None:
        ttl_minutes = MCP_TOKEN_MAX_TTL_MINUTES
    else:
        # Enforce max TTL
        ttl_minutes = min(ttl_minutes, MCP_TOKEN_MAX_TTL_MINUTES)
    
    # Default scopes
    if scopes is None:
        scopes = ["mcp:run", "mcp:tools", "mcp:manifest"]
    
    # Validate scopes against ServiceAccount allowlist
    if sa.scope_allowlist:
        invalid_scopes = [s for s in scopes if s not in sa.scope_allowlist]
        if invalid_scopes:
            raise ValueError(
                f"Scopes {invalid_scopes} are not in ServiceAccount allowlist: {sa.scope_allowlist}"
            )
    
    # Generate jti
    jti = str(uuid.uuid4())
    
    # Calculate timestamps
    now = django_timezone.now()
    iat = int(now.timestamp())
    exp = int((now + timedelta(minutes=ttl_minutes)).timestamp())
    nbf = int((now - timedelta(minutes=1)).timestamp())
    
    # Build token claims
    claims = {
        "iss": JWT_ISSUER,
        "aud": sa.audience or MCP_CANONICAL_URI,
        "sub": sa.subject,
        "jti": jti,
        "iat": iat,
        "exp": exp,
        "nbf": nbf,
        "org_id": str(agent.organization.id),
        "env_id": str(agent.environment.id),
        "agent_id": str(agent.id),
        "scope": " ".join(scopes),
    }
    
    # Sign token
    private_key = _get_signing_key()
    token_string = jwt.encode(claims, private_key, algorithm=JWT_ALGORITHM)
    
    # Store token metadata
    issued_token = IssuedToken.objects.create(
        agent=agent,
        jti=jti,
        expires_at=datetime.fromtimestamp(exp, tz=ZoneInfo("UTC")),
        scopes=scopes,
        metadata=metadata or {},
    )
    
    logger.info(
        f"Generated token for agent {agent.id}",
        extra={
            "agent_id": str(agent.id),
            "jti": jti,
            "ttl_minutes": ttl_minutes,
            "scopes": scopes,
        },
    )
    
    return token_string, issued_token


def revoke_token(jti: str, revoked_by=None) -> IssuedToken:
    """
    Revoke a token by jti.
    
    Args:
        jti: JWT ID
        revoked_by: User who revoked the token (optional)
    
    Returns:
        Updated IssuedToken instance
    """
    try:
        token = IssuedToken.objects.get(jti=jti)
    except IssuedToken.DoesNotExist:
        raise ValueError(f"Token with jti '{jti}' not found")
    
    if token.revoked_at:
        raise ValueError(f"Token with jti '{jti}' is already revoked")
    
    token.revoked_at = django_timezone.now()
    token.revoked_by = revoked_by
    token.save()
    
    # Also revoke in jti_store (for immediate effect)
    from mcp_fabric.jti_store import revoke_jti
    
    revoke_jti(jti)
    
    logger.info(f"Revoked token {jti}", extra={"jti": jti, "revoked_by": str(revoked_by.id) if revoked_by else None})
    
    return token

