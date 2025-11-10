"""
Base SecretStore interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class SecretStore(ABC):
    """Abstract base class for secret storage."""

    @abstractmethod
    def put_secret(self, scope: dict[str, str], key: str, value: str) -> str:
        """
        Store a secret and return a reference.

        Args:
            scope: Dictionary with scope information (e.g., {"org": "org_id", "env": "env_id"})
            key: Key identifier for the secret
            value: Secret value to store

        Returns:
            Secret reference string that can be used to retrieve the secret
        """
        raise NotImplementedError

    @abstractmethod
    def get_secret(self, ref: str, check_permissions: bool = True) -> str:
        """
        Retrieve a secret by reference.

        Security: Only Superuser or Agent-Service should retrieve secret values.
        Set check_permissions=False only for internal service calls (e.g., runs.services).

        Args:
            ref: Secret reference returned by put_secret
            check_permissions: If True, check if caller is authorized (default: True)

        Returns:
            Secret value as string

        Raises:
            PermissionError: If caller is not authorized to retrieve secrets
        """
        raise NotImplementedError

