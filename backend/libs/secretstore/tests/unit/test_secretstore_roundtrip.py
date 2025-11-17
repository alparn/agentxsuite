"""
Unit tests for secretstore round-trip operations.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from libs.secretstore import get_secretstore
from apps.tenants.models import Organization, Environment


@pytest.fixture
def org_env(db):
    """Create test organization and environment."""
    org = baker.make(Organization, name="TestOrg")
    env = baker.make(Environment, organization=org, name="dev", type="dev")
    return org, env


@pytest.mark.django_db
def test_secretstore_roundtrip(org_env):
    """Test that put_secret and get_secret work correctly."""
    org, env = org_env
    store = get_secretstore()

    scope = {"org": str(org.id), "env": str(env.id)}
    key = "test-key"
    value = "test-secret-value"

    # Store secret
    ref = store.put_secret(scope, key, value)

    # Retrieve secret
    retrieved = store.get_secret(ref, check_permissions=False)

    assert retrieved == value
    assert ref is not None
    assert isinstance(ref, str)


@pytest.mark.django_db
def test_secretstore_scoping(org_env):
    """Test that secrets are scoped correctly."""
    org1, env1 = org_env
    org2 = baker.make(Organization, name="OtherOrg")
    env2 = baker.make(Environment, organization=org2, name="dev", type="dev")
    
    store = get_secretstore()

    scope1 = {"org": str(org1.id), "env": str(env1.id)}
    scope2 = {"org": str(org2.id), "env": str(env2.id)}

    ref1 = store.put_secret(scope1, "key", "value1")
    ref2 = store.put_secret(scope2, "key", "value2")

    # Different scopes should produce different refs
    assert ref1 != ref2

    # But both should retrieve correctly
    assert store.get_secret(ref1, check_permissions=False) == "value1"
    assert store.get_secret(ref2, check_permissions=False) == "value2"


@pytest.mark.django_db
def test_secretstore_get_nonexistent():
    """Test that getting non-existent secret raises error."""
    store = get_secretstore()

    with pytest.raises(ValueError, match="Secret reference not found"):
        store.get_secret("nonexistent-ref", check_permissions=False)


@pytest.mark.django_db
def test_secretstore_different_keys_same_scope(org_env):
    """Test that different keys in same scope work."""
    org, env = org_env
    store = get_secretstore()

    scope = {"org": str(org.id), "env": str(env.id)}

    ref1 = store.put_secret(scope, "key1", "value1")
    ref2 = store.put_secret(scope, "key2", "value2")

    assert ref1 != ref2
    assert store.get_secret(ref1, check_permissions=False) == "value1"
    assert store.get_secret(ref2, check_permissions=False) == "value2"

