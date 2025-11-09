"""
Validators for connections app.
"""
from __future__ import annotations

from rest_framework import serializers


def validate_secret_ref_required(auth_method: str, secret_ref: str | None) -> None:
    """
    Validate that secret_ref is provided when auth_method requires it.

    Args:
        auth_method: Authentication method
        secret_ref: Secret reference (may be None)

    Raises:
        serializers.ValidationError: If secret_ref is required but missing
    """
    if auth_method in ("bearer", "basic") and not secret_ref:
        raise serializers.ValidationError(
            {"secret_ref": "secret_ref is required for bearer and basic auth methods"},
        )

