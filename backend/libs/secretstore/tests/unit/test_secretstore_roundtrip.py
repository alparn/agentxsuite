"""
Unit tests for secretstore round-trip operations.
"""
from __future__ import annotations

import pytest

from libs.secretstore import get_secretstore


@pytest.mark.django_db
def test_secretstore_roundtrip():
    """Test that put_secret and get_secret work correctly."""
    store = get_secretstore()

    scope = {"org": "org-1", "env": "env-1"}
    key = "test-key"
    value = "test-secret-value"

    # Store secret
    ref = store.put_secret(scope, key, value)

    # Retrieve secret
    retrieved = store.get_secret(ref)

    assert retrieved == value
    assert ref is not None
    assert isinstance(ref, str)


@pytest.mark.django_db
def test_secretstore_scoping():
    """Test that secrets are scoped correctly."""
    store = get_secretstore()

    scope1 = {"org": "org-1", "env": "env-1"}
    scope2 = {"org": "org-2", "env": "env-1"}

    ref1 = store.put_secret(scope1, "key", "value1")
    ref2 = store.put_secret(scope2, "key", "value2")

    # Different scopes should produce different refs
    assert ref1 != ref2

    # But both should retrieve correctly
    assert store.get_secret(ref1) == "value1"
    assert store.get_secret(ref2) == "value2"


@pytest.mark.django_db
def test_secretstore_get_nonexistent():
    """Test that getting non-existent secret raises error."""
    store = get_secretstore()

    with pytest.raises(ValueError, match="Secret reference not found"):
        store.get_secret("nonexistent-ref")


@pytest.mark.django_db
def test_secretstore_different_keys_same_scope():
    """Test that different keys in same scope work."""
    store = get_secretstore()

    scope = {"org": "org-1", "env": "env-1"}

    ref1 = store.put_secret(scope, "key1", "value1")
    ref2 = store.put_secret(scope, "key2", "value2")

    assert ref1 != ref2
    assert store.get_secret(ref1) == "value1"
    assert store.get_secret(ref2) == "value2"

