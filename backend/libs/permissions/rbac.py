"""
Simple RBAC stub for permissions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import User


def has_scope(user: User, scope: str) -> bool:  # noqa: ARG001
    """
    Check if user has a specific scope (stub).

    Args:
        user: User instance
        scope: Scope string (e.g., "org:read", "org:write")

    Returns:
        True if user has scope (stub always returns True)
    """
    # Stub implementation - always returns True
    return True

