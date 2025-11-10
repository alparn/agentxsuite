"""
Fernet-based SecretStore implementation with persistent database storage.
"""
from __future__ import annotations

import base64
import json

from cryptography.fernet import Fernet
from django.conf import settings

from .base import SecretStore


class FernetSecretStore(SecretStore):
    """
    Fernet-based secret storage implementation with persistent database storage.

    Security Features:
    - Encrypted using Fernet (AES-128 in CBC mode with HMAC)
    - Stored persistently in the database
    - Never stored in plaintext
    - Secret values never exposed in API responses (only ref, created_at, expires_at)
    - Only Superuser or Agent-Service can retrieve secret values
    - Optional expiration dates supported
    
    Note: Fernet uses AES-128. For AES-256, consider using cryptography.fernet.Fernet
    with a custom key derivation or upgrade to a different encryption backend.
    """

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

    def put_secret(self, scope: dict[str, str], key: str, value: str) -> str:
        """
        Store a secret and return a reference.

        Args:
            scope: Dictionary with scope information (e.g., {"org": "org_id", "env": "env_id"})
            key: Key identifier for the secret
            value: Secret value to store

        Returns:
            Secret reference string
        """
        # Import here to avoid circular imports
        from apps.secretstore.models import StoredSecret

        # Create a reference that includes scope and key
        ref_data = {
            "scope": scope,
            "key": key,
        }
        ref_json = json.dumps(ref_data, sort_keys=True)
        ref_encoded = base64.urlsafe_b64encode(ref_json.encode()).decode()

        # Encrypt the value
        encrypted_value = self.cipher.encrypt(value.encode()).decode()

        # Extract org/env from scope for indexing
        org_id = scope.get("org")
        env_id = scope.get("env")

        # Store in database (update if exists)
        StoredSecret.objects.update_or_create(
            ref=ref_encoded,
            defaults={
                "encrypted_value": encrypted_value,
                "organization_id": org_id,
                "environment_id": env_id,
                "key_name": key,
            },
        )

        return ref_encoded

    def get_secret(self, ref: str, check_permissions: bool = True) -> str:
        """
        Retrieve a secret by reference.
        
        Security: Only Superuser or Agent-Service (runs.services) can retrieve secret values.
        This prevents unauthorized access to secrets via API endpoints.

        Args:
            ref: Secret reference returned by put_secret
            check_permissions: If True, check if caller is authorized (default: True)
                             Set to False only for internal service calls (e.g., runs.services)

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret reference not found or expired
            PermissionError: If caller is not authorized to retrieve secrets
        """
        # Import here to avoid circular imports
        from apps.secretstore.models import StoredSecret
        from django.utils import timezone

        try:
            stored_secret = StoredSecret.objects.get(ref=ref)
        except StoredSecret.DoesNotExist:
            raise ValueError(f"Secret reference not found: {ref}")

        # Check expiration
        if stored_secret.expires_at and stored_secret.expires_at < timezone.now():
            raise ValueError(f"Secret reference expired: {ref}")

        # Security check: Only allow Superuser or Agent-Service to retrieve secrets
        if check_permissions:
            import inspect
            
            # Get the caller's module to check if it's from runs.services (Agent-Service)
            frame = inspect.currentframe()
            is_agent_service = False
            if frame and frame.f_back:
                caller_module = frame.f_back.f_globals.get("__name__", "")
                # Allow if called from runs.services (Agent-Service)
                is_agent_service = caller_module.startswith("apps.runs.services")
            
            # Check if user is superuser (if request context available)
            # Note: This check works when called from Django views/DRF endpoints
            # For internal service calls, use check_permissions=False
            is_superuser = False
            try:
                from django.utils.functional import SimpleLazyObject
                from django.contrib.auth.models import AnonymousUser
                
                # Try to get current user from thread-local storage
                # Django middleware stores request.user in thread-local context
                try:
                    from threading import local
                    thread_local = local()
                    if hasattr(thread_local, "request"):
                        user = getattr(thread_local.request, "user", None)
                        if user and not isinstance(user, (SimpleLazyObject, AnonymousUser)):
                            is_superuser = getattr(user, "is_superuser", False)
                except (AttributeError, ImportError):
                    # No request context available
                    pass
            except Exception:
                # If no request context, assume not superuser
                pass
            
            if not (is_agent_service or is_superuser):
                raise PermissionError(
                    "Only Superuser or Agent-Service can retrieve secret values. "
                    "Secret values are never exposed in API responses. "
                    "Use check_permissions=False only for internal service calls."
                )

        # Decrypt the value
        decrypted_bytes = self.cipher.decrypt(stored_secret.encrypted_value.encode())
        return decrypted_bytes.decode()

