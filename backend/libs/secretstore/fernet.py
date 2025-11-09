"""
Fernet-based SecretStore implementation.
"""
from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.fernet import Fernet
from django.conf import settings

from .base import SecretStore


class FernetSecretStore(SecretStore):
    """Fernet-based secret storage implementation."""

    def __init__(self) -> None:
        """Initialize Fernet secret store."""
        key = getattr(settings, "SECRETSTORE_FERNET_KEY", None)
        if key is None:
            # Generate a new key (for development only)
            key = Fernet.generate_key()
        elif isinstance(key, str):
            key = key.encode()
        elif not isinstance(key, bytes):
            raise ValueError("SECRETSTORE_FERNET_KEY must be bytes or str")

        # Ensure key is 32 bytes base64-encoded
        if len(key) != 44:  # Fernet keys are 32 bytes base64-encoded (44 chars)
            # If it's not the right length, generate a key from it
            key_bytes = key[:32] if len(key) >= 32 else key.ljust(32, b"0")
            key = base64.urlsafe_b64encode(key_bytes)

        self.cipher = Fernet(key)
        self._storage: dict[str, str] = {}  # In-memory storage

    def put_secret(self, scope: dict[str, str], key: str, value: str) -> str:
        """
        Store a secret and return a reference.

        Args:
            scope: Dictionary with scope information
            key: Key identifier for the secret
            value: Secret value to store

        Returns:
            Secret reference string
        """
        # Create a reference that includes scope and key
        ref_data = {
            "scope": scope,
            "key": key,
        }
        ref_json = json.dumps(ref_data, sort_keys=True)
        ref_encoded = base64.urlsafe_b64encode(ref_json.encode()).decode()

        # Encrypt the value
        encrypted_value = self.cipher.encrypt(value.encode()).decode()

        # Store in memory
        self._storage[ref_encoded] = encrypted_value

        return ref_encoded

    def get_secret(self, ref: str) -> str:
        """
        Retrieve a secret by reference.

        Args:
            ref: Secret reference returned by put_secret

        Returns:
            Secret value as string
        """
        if ref not in self._storage:
            raise ValueError(f"Secret reference not found: {ref}")

        encrypted_value = self._storage[ref]
        decrypted_bytes = self.cipher.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()

