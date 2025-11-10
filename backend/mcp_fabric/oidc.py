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
) -> dict[str, Any]:
    """
    Validate a JWT token with OIDC/JWKS.

    Validates:
    - Signature (JWKS)
    - Issuer (iss)
    - Audience (aud)
    - Expiration (exp)
    - Not Before (nbf)
    - Scopes (scope)
    - Org/Env claims (org_id, env_id)

    Args:
        token: JWT token string
        required_scopes: List of required scopes (e.g., ["mcp:tools"])
        required_org_id: Required org_id in token (for cross-tenant protection)
        required_env_id: Required env_id in token (for cross-tenant protection)

    Returns:
        Decoded token claims

    Raises:
        HTTPException: 401 for invalid token, 403 for missing scopes/claims
    """
    # If OIDC not configured, skip validation (fallback for development)
    if not OIDC_ISSUER:
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

    # Fetch JWKS
    jwks = get_jwks()
    public_key = get_signing_key(token, jwks)

    # Decode and validate token
    try:
        # Decode token with validation
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],  # Only RSA256 supported for now
            issuer=OIDC_ISSUER,
            audience=OIDC_AUDIENCE,
            options={"verify_exp": True, "verify_nbf": True},
        )

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

    except jwt.ExpiredSignatureError:
        raise raise_mcp_http_exception(
            ErrorCodes.EXPIRED_TOKEN,
            "Token has expired",
            status.HTTP_401_UNAUTHORIZED,
        )
    except jwt.InvalidIssuerError:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_ISSUER,
            f"Invalid issuer. Expected: {OIDC_ISSUER}",
            status.HTTP_401_UNAUTHORIZED,
        )
    except jwt.InvalidAudienceError:
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_AUDIENCE,
            f"Invalid audience. Expected: {OIDC_AUDIENCE}",
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
    except HTTPException:
        # Re-raise HTTPExceptions (e.g., from scope/org/env checks)
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating token: {e}", exc_info=True)
        raise raise_mcp_http_exception(
            ErrorCodes.INVALID_TOKEN,
            "Token validation failed",
            status.HTTP_401_UNAUTHORIZED,
        )
