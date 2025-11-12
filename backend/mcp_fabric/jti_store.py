"""
JTI (JWT ID) store for replay protection.

Stores jti claims from tokens until expiration to prevent replay attacks.
Uses Redis for distributed storage (fallback to Django cache).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key prefix
JTI_CACHE_PREFIX = "jti:"


def check_jti_replay(jti: str, exp: int | None = None) -> tuple[bool, str | None]:
    """
    Check if jti (JWT ID) has been seen before (replay protection).

    Args:
        jti: JWT ID claim from token
        exp: Expiration timestamp (Unix epoch) - used for TTL

    Returns:
        Tuple of (is_replay: bool, reason: str | None)
        - (True, reason) if jti is a replay
        - (False, None) if jti is new and valid

    Security:
        - Stores jti in cache until token expiration
        - Duplicate jti → replay attack detected
        - TTL based on exp claim (with safety margin)
    """
    if not jti:
        return False, None  # No jti = no replay check (should be validated elsewhere)

    cache_key = f"{JTI_CACHE_PREFIX}{jti}"

    # Check if jti already exists
    existing = cache.get(cache_key)
    if existing is not None:
        logger.warning(
            f"Replay attack detected: jti={jti} already seen",
            extra={
                "jti": jti,
                "cache_key": cache_key,
            },
        )
        return True, f"Token jti '{jti}' has already been used (replay attack)"

    # Calculate TTL from exp claim
    if exp:
        try:
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            ttl_seconds = int((exp_dt - now).total_seconds())

            # Add safety margin (5 minutes) to ensure we keep jti until well after expiration
            ttl_seconds = max(ttl_seconds + 300, 300)  # Minimum 5 minutes
        except (ValueError, TypeError, OSError):
            # Invalid exp, use default TTL
            ttl_seconds = 3600  # 1 hour default
            logger.warning(
                f"Invalid exp claim for jti={jti}, using default TTL",
                extra={"jti": jti, "exp": exp},
            )
    else:
        # No exp claim, use default TTL
        ttl_seconds = 3600  # 1 hour default
        logger.warning(
            f"No exp claim for jti={jti}, using default TTL",
            extra={"jti": jti},
        )

    # Store jti until expiration
    cache.set(cache_key, "seen", timeout=ttl_seconds)

    logger.debug(
        f"Stored jti={jti} with TTL={ttl_seconds}s",
        extra={"jti": jti, "ttl_seconds": ttl_seconds},
    )

    return False, None


def revoke_jti(jti: str) -> None:
    """
    Manually revoke a jti (mark as used).

    Useful for token revocation before expiration.

    Args:
        jti: JWT ID to revoke
    """
    if not jti:
        return

    cache_key = f"{JTI_CACHE_PREFIX}{jti}"
    cache.set(cache_key, "revoked", timeout=86400)  # Keep for 24 hours

    logger.info(f"Revoked jti={jti}", extra={"jti": jti})


