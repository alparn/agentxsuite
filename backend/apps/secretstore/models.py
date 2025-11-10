"""
Models for secret storage.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class StoredSecret(TimeStamped):
    """Model for storing encrypted secrets persistently.
    
    Security:
    - Secret values are never exposed in API responses
    - Only ref, created_at, updated_at, expires_at are returned
    - Secret values can only be retrieved by authorized services (Superuser or Agent-Service)
    - Values are encrypted using Fernet (AES-128) before storage
    """

    # Secret reference (base64-encoded scope+key)
    ref = models.CharField(max_length=500, unique=True, db_index=True)
    # Encrypted secret value (Fernet-encrypted, AES-128)
    # NEVER expose this in API responses
    encrypted_value = models.TextField()
    # Scope information (for reference/debugging, not used for lookup)
    organization_id = models.UUIDField(null=True, blank=True)
    environment_id = models.UUIDField(null=True, blank=True)
    key_name = models.CharField(max_length=255)
    # Optional expiration date for secrets
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiration date for the secret")

    class Meta:
        db_table = "secretstore_storedsecret"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ref"]),
            models.Index(fields=["organization_id", "environment_id", "key_name"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"Secret: {self.key_name} ({self.ref[:20]}...)"

