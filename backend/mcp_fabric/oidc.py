"""
OIDC/JWKS token validation for MCP Fabric.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from decouple import config
from fastapi import HTTPException, status

from mcp_fabric.errors import ErrorCodes, raise_mcp_http_exception
from mcp_fabric.settings import (
    AUTHORIZATION_SERVERS,
    MCP_CANONICAL_URI,
    MCP_TOKEN_MAX_TTL_MINUTES,
    MCP_TOKEN_MAX_IAT_AGE_MINUTES,
)

logger = logging.getLogger(__name__)

# OIDC configuration from environment variables
OIDC_ISSUER = config("OIDC_ISSUER", default=None)
OIDC_AUDIENCE = config("OIDC_AUDIENCE", default=None)
OIDC_JWKS_URI = config("OIDC_JWKS_URI", default=None)
OIDC_ALGORITHMS = config(
    "OIDC_ALGORITHMS", default="RS256,ES256", cast=lambda v: [a.strip() for a in v.split(",")]
)

# Fallback: If JWKS_URI not set but ISSUER is set, construct JWKS_URI
if OIDC_ISSUER and not OIDC_JWKS_URI:
    OIDC_JWKS_URI = f"{OIDC_ISSUER.rstrip('/')}/.well-known/jwks.json"

# Cache for JWKS (in production should use Redis)
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_expiry: datetime | None = None


def get_jwks() -> dict[str, Any]:
    """
    Fetch JWKS from authorization server.

    Caches response for 1 hour.

    Returns:
        JWKS dictionary with "keys"

    Raises:
        HTTPException: 503 if JWKS is not available
    """
    global _jwks_cache, _jwks_cache_expiry

    # Check cache
    if _jwks_cache and _jwks_cache_expiry:
        if datetime.now(timezone.utc) < _jwks_cache_expiry:
            return _jwks_cache

    if not OIDC_JWKS_URI:
        raise raise_mcp_http_exception(
            ErrorCodes.INTERNAL_ERROR,
            "OIDC JWKS URI not configured",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(OIDC_JWKS_URI)
            response.raise_for_status()
            jwks = response.json()

            # Cache for 1 hour
            _jwks_cache = jwks
            _jwks_cache_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

            return jwks
    except httpx.RequestError as e:
        logger.error(f"Failed to fetch JWKS from {OIDC_JWKS_URI}: {e}")
        raise raise_mcp_http_exception(
            ErrorCodes.INTERNAL_ERROR,
            "Failed to fetch JWKS from authorization server",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def jwk_to_rsa_public_key(jwk: dict[str, Any]) -> rsa.RSAPublicKey:
    """
    Convert JWK to RSA public key.

    Args:
        jwk: JWK dictionary with "n" and "e"

    Returns:
        RSA public key object
    """
    # Decode base64url-encoded values
    import base64

    def base64url_decode(value: str) -> int:
        """Decode base64url-encoded value to integer."""
        # Add padding if needed
        padding = 4 - len(value) % 4
        if padding != 4:
            value += "=" * padding
        decoded = base64.urlsafe_b64decode(value)
        return int.from_bytes(decoded, byteorder="big")

    n = base64url_decode(jwk["n"])
    e = base64url_decode(jwk["e"])

    public_numbers = rsa.RSAPublicNumbers(e=e, n=n)
    return public_numbers.public_key()


def get_signing_key(token: str, jwks: dict[str, Any]) -> rsa.RSAPublicKey:
    """
    Find matching signing key from JWKS for the token.

    Args:
        token: JWT token (only header is decoded)
        jwks: JWKS dictionary

    Returns:
        Public key as RSA public key object

    Raises:
        HTTPException: 401 if no matching key found
    """
    try:
        # Decode header without validation
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_TOKEN,
                "Token missing 'kid' in header",
                status.HTTP_401_UNAUTHORIZED,
            )

        # Find key in JWKS
        keys = jwks.get("keys", [])
        for key in keys:
            if key.get("kid") == kid:
                if key.get("kty") == "RSA":
                    return jwk_to_rsa_public_key(key)
                else:
                    raise raise_mcp_http_exception(
                        ErrorCodes.INTERNAL_ERROR,
                        f"Unsupported key type: {key.get('kty')}. Only RSA keys are supported.",
                        status.HTTP_501_NOT_IMPLEMENTED,
                    )

        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_SIGNATURE,
            f"Key with kid '{kid}' not found in JWKS",
            status.HTTP_401_UNAUTHORIZED,
        )
    except jwt.DecodeError as e:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            f"Invalid token format: {e}",
            status.HTTP_401_UNAUTHORIZED,
        )


def validate_token(
    token: str,
    *,
    required_scopes: list[str] | None = None,
    required_org_id: str | None = None,
    required_env_id: str | None = None,
    resource: str | None = None,
) -> dict[str, Any]:
    """
    Validate a JWT token with OIDC/JWKS with strict audience checking.

    Validates:
    - Signature (JWKS)
    - Issuer (iss) - must match one of AUTHORIZATION_SERVERS
    - Audience (aud) - must match resource parameter or MCP_CANONICAL_URI (NO TOKEN-PASSTHROUGH)
    - Expiration (exp)
    - Not Before (nbf)
    - Issued At (iat) - must be present and not too old (max age: MCP_TOKEN_MAX_IAT_AGE_MINUTES)
    - Maximum TTL - exp - iat must not exceed MCP_TOKEN_MAX_TTL_MINUTES
    - Scopes (scope)
    - Org/Env claims (org_id, env_id)

    Args:
        token: JWT token string
        required_scopes: List of required scopes (e.g., ["mcp:tools"])
        required_org_id: Required org_id in token (for cross-tenant protection)
        required_env_id: Required env_id in token (for cross-tenant protection)
        resource: Expected resource/audience identifier (defaults to MCP_CANONICAL_URI)

    Returns:
        Decoded token claims

    Raises:
        HTTPException: 401 for invalid token, 403 for missing scopes/claims
    """
    # If OIDC not configured, skip validation (fallback for development)
    if not OIDC_ISSUER and not AUTHORIZATION_SERVERS:
        logger.warning("OIDC not configured, skipping token validation")
        # Try to decode token anyway (for development)
        try:
            decoded = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
            return decoded
        except jwt.DecodeError:
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_TOKEN,
                "Invalid token format",
                status.HTTP_401_UNAUTHORIZED,
            )

    # Determine expected audience (strict: no passthrough)
    expected_audience = resource or MCP_CANONICAL_URI
    if not expected_audience:
        raise raise_mcp_http_exception(
            ErrorCodes.INTERNAL_ERROR,
            "Resource/audience not configured",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # Fetch JWKS
    jwks = get_jwks()
    public_key = get_signing_key(token, jwks)

    # Decode token WITHOUT audience validation first to check issuer
    try:
        decoded_unverified_aud = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_signature": True, "verify_exp": True, "verify_nbf": True, "verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise raise_mcp_http_exception(
            ErrorCodes.EXPIRED_TOKEN,
            "Token has expired",
            status.HTTP_401_UNAUTHORIZED,
        )
    except jwt.InvalidSignatureError:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_SIGNATURE,
            "Invalid token signature",
            status.HTTP_401_UNAUTHORIZED,
        )
    except jwt.ImmatureSignatureError:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            "Token not yet valid (nbf)",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Validate issuer against AUTHORIZATION_SERVERS (strict)
    token_issuer = decoded_unverified_aud.get("iss")
    if not token_issuer:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_ISSUER,
            "Token missing issuer (iss) claim",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Check if issuer is in allowed list
    if AUTHORIZATION_SERVERS and token_issuer not in AUTHORIZATION_SERVERS:
        # Fallback to OIDC_ISSUER for backward compatibility
        if OIDC_ISSUER and token_issuer != OIDC_ISSUER:
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_ISSUER,
                f"Invalid issuer '{token_issuer}'. Expected one of: {', '.join(AUTHORIZATION_SERVERS)}",
                status.HTTP_401_UNAUTHORIZED,
            )
    elif OIDC_ISSUER and token_issuer != OIDC_ISSUER:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_ISSUER,
            f"Invalid issuer '{token_issuer}'. Expected: {OIDC_ISSUER}",
            status.HTTP_401_UNAUTHORIZED,
        )

    # STRICT AUDIENCE CHECK: Token audience MUST match expected_audience (no passthrough)
    token_audience = decoded_unverified_aud.get("aud")
    if not token_audience:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_AUDIENCE,
            f"Token missing audience (aud) claim. Expected: {expected_audience}",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Handle both string and list audiences
    if isinstance(token_audience, str):
        token_audiences = [token_audience]
    elif isinstance(token_audience, list):
        token_audiences = token_audience
    else:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_AUDIENCE,
            f"Invalid audience format. Expected string or list. Got: {type(token_audience)}",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Audience MUST match exactly (strict check, no passthrough)
    if expected_audience not in token_audiences:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_AUDIENCE,
            f"Token audience '{token_audience}' does not match expected resource '{expected_audience}'",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Use decoded token (audience already validated manually)
    decoded = decoded_unverified_aud

    # P0: Check jti (JWT ID) for replay protection
    jti = decoded.get("jti")
    if jti:
        from mcp_fabric.jti_store import check_jti_replay

        exp = decoded.get("exp")
        is_replay, reason = check_jti_replay(jti, exp)
        if is_replay:
            raise raise_mcp_http_exception(
                ErrorCodes.INVALID_TOKEN,
                reason or "Token jti has already been used (replay attack)",
                status.HTTP_401_UNAUTHORIZED,
            )

    # P0: Check iat (issued at) claim
    iat = decoded.get("iat")
    if iat is None:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            "Token missing issued at (iat) claim",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Convert iat to datetime (JWT iat is Unix timestamp)
    try:
        iat_dt = datetime.fromtimestamp(iat, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            "Invalid issued at (iat) claim format",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Check iat age (token must not be too old)
    now = datetime.now(timezone.utc)
    iat_age = now - iat_dt
    max_iat_age = timedelta(minutes=MCP_TOKEN_MAX_IAT_AGE_MINUTES)
    if iat_age > max_iat_age:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            f"Token issued at (iat) is too old. Maximum age: {MCP_TOKEN_MAX_IAT_AGE_MINUTES} minutes",
            status.HTTP_401_UNAUTHORIZED,
        )

    # P0: Check maximum TTL (exp - iat must not exceed max TTL)
    exp = decoded.get("exp")
    if exp is not None:
        try:
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            token_ttl = exp_dt - iat_dt
            max_ttl = timedelta(minutes=MCP_TOKEN_MAX_TTL_MINUTES)
            if token_ttl > max_ttl:
                raise raise_mcp_http_exception(
                    ErrorCodes.INVALID_TOKEN,
                    f"Token TTL exceeds maximum allowed TTL. Maximum: {MCP_TOKEN_MAX_TTL_MINUTES} minutes",
                    status.HTTP_401_UNAUTHORIZED,
                )
        except (ValueError, TypeError, OSError):
            # exp validation already handled above, but handle edge cases
            pass

    # Check scopes
    if required_scopes:
        token_scopes = (
            decoded.get("scope", "").split()
            if isinstance(decoded.get("scope"), str)
            else decoded.get("scope", [])
        )
        if not isinstance(token_scopes, list):
            token_scopes = [token_scopes] if token_scopes else []

        missing_scopes = [s for s in required_scopes if s not in token_scopes]
        if missing_scopes:
            raise raise_mcp_http_exception(
                ErrorCodes.INSUFFICIENT_SCOPE,
                f"Missing required scopes: {', '.join(missing_scopes)}",
                status.HTTP_403_FORBIDDEN,
            )

    # Check org/env binding (cross-tenant protection)
    if required_org_id:
        token_org_id = decoded.get("org_id") or decoded.get("organization_id")
        if token_org_id != required_org_id:
            raise raise_mcp_http_exception(
                ErrorCodes.CROSS_TENANT_ACCESS,
                f"Token org_id '{token_org_id}' does not match required org_id '{required_org_id}'",
                status.HTTP_403_FORBIDDEN,
            )

    if required_env_id:
        token_env_id = decoded.get("env_id") or decoded.get("environment_id")
        if token_env_id != required_env_id:
            raise raise_mcp_http_exception(
                ErrorCodes.CROSS_TENANT_ACCESS,
                f"Token env_id '{token_env_id}' does not match required env_id '{required_env_id}'",
                status.HTTP_403_FORBIDDEN,
            )

    return decoded
