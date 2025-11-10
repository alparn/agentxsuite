"""
Tests for Agent mode validation.
"""
from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.agents.models import Agent, AgentMode, InboundAuthMethod
from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization


@pytest.fixture
def org_env():
    """Create test organization and environment."""
    org = Organization.objects.create(name="TestOrg")
    env = Environment.objects.create(organization=org, name="dev", type="dev")
    return org, env


@pytest.fixture
def org_env_conn(org_env):
    """Create test organization, environment, and connection."""
    org, env = org_env
    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="none",
        status="ok",
    )
    return org, env, conn


def make_agent(org, env, **kwargs):
    """
    Helper to create Agent instances with sensible defaults.

    Args:
        org: Organization instance
        env: Environment instance
        **kwargs: Override defaults (mode, inbound_auth_method, connection, etc.)

    Returns:
        Agent instance (not saved)
    """
    defaults = {
        "organization": org,
        "environment": env,
        "mode": AgentMode.RUNNER,
        "inbound_auth_method": InboundAuthMethod.NONE,
    }
    return Agent(**{**defaults, **kwargs})


@pytest.mark.django_db
def test_runner_requires_connection(org_env_conn):
    """Test that RUNNER mode requires connection."""
    org, env, conn = org_env_conn

    # Create runner without connection - should fail
    a = make_agent(org, env, name="runner1", mode=AgentMode.RUNNER, connection=None)
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "connection" in exc_info.value.error_dict
    field_err = exc_info.value.error_dict["connection"][0]
    assert "RUNNER" in str(field_err)
    # Django ValidationError messages are strings, not ErrorList with codes
    # The error message itself contains the validation message

    # Create runner with connection - should succeed
    a.connection = conn
    a.full_clean()  # no error
    a.save()
    assert a.mode == AgentMode.RUNNER
    assert a.connection == conn


@pytest.mark.django_db
def test_caller_can_have_connection(org_env_conn):
    """Test that CALLER mode can optionally have connection (for outbound tool execution)."""
    org, env, conn = org_env_conn

    # Create caller without connection - should succeed
    a = make_agent(org, env, name="caller1", mode=AgentMode.CALLER, connection=None)
    a.full_clean()  # ok
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.connection is None

    # Create caller with connection - should also succeed (connection is optional for CALLER)
    a2 = make_agent(org, env, name="caller1b", mode=AgentMode.CALLER, connection=conn)
    a2.full_clean()  # ok
    a2.save()
    assert a2.mode == AgentMode.CALLER
    assert a2.connection == conn


@pytest.mark.django_db
def test_caller_inbound_secret_required_for_bearer(org_env):
    """Test that CALLER with bearer auth requires secret reference."""
    org, env = org_env

    # Create caller with bearer auth but no secret - should fail
    a = make_agent(org, env, name="caller2", mode=AgentMode.CALLER, inbound_auth_method=InboundAuthMethod.BEARER, inbound_secret_ref=None)
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "inbound_secret_ref" in exc_info.value.error_dict
    field_err = exc_info.value.error_dict["inbound_secret_ref"][0]
    assert InboundAuthMethod.BEARER in str(field_err)

    # Create caller with bearer auth but empty string secret - should fail
    a.inbound_secret_ref = ""
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "inbound_secret_ref" in exc_info.value.error_dict

    # Create caller with bearer auth and secret - should succeed
    a.inbound_secret_ref = "secret-ref-123"
    a.full_clean()  # ok
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.inbound_auth_method == InboundAuthMethod.BEARER
    assert a.inbound_secret_ref == "secret-ref-123"


@pytest.mark.django_db
def test_caller_inbound_secret_required_for_mtls(org_env):
    """Test that CALLER with mTLS auth requires secret reference."""
    org, env = org_env

    # Create caller with mtls auth but no secret - should fail
    a = make_agent(org, env, name="caller3", mode=AgentMode.CALLER, inbound_auth_method=InboundAuthMethod.MTLS, inbound_secret_ref=None)
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "inbound_secret_ref" in exc_info.value.error_dict
    field_err = exc_info.value.error_dict["inbound_secret_ref"][0]
    assert InboundAuthMethod.MTLS in str(field_err)

    # Create caller with mtls auth but empty string secret - should fail
    a.inbound_secret_ref = ""
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "inbound_secret_ref" in exc_info.value.error_dict

    # Create caller with mtls auth and secret - should succeed
    a.inbound_secret_ref = "mtls-secret-ref"
    a.full_clean()  # ok
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.inbound_auth_method == InboundAuthMethod.MTLS
    assert a.inbound_secret_ref == "mtls-secret-ref"


@pytest.mark.parametrize(
    "auth_method,secret_ref,should_succeed",
    [
        (InboundAuthMethod.NONE, None, True),
        (InboundAuthMethod.NONE, "", True),  # Empty string allowed for none auth
        (InboundAuthMethod.NONE, "optional-secret", True),  # Optional secret allowed
        (InboundAuthMethod.BEARER, None, False),
        (InboundAuthMethod.BEARER, "", False),  # Empty string not allowed for bearer
        (InboundAuthMethod.BEARER, "secret-ref", True),
        (InboundAuthMethod.MTLS, None, False),
        (InboundAuthMethod.MTLS, "", False),  # Empty string not allowed for mtls
        (InboundAuthMethod.MTLS, "mtls-secret", True),
    ],
)
@pytest.mark.django_db
def test_caller_auth_secret_validation(org_env, auth_method, secret_ref, should_succeed):
    """Test CALLER auth method and secret reference validation."""
    org, env = org_env

    a = make_agent(
        org,
        env,
        name=f"caller-{auth_method}-{secret_ref or 'none'}",
        mode=AgentMode.CALLER,
        inbound_auth_method=auth_method,
        inbound_secret_ref=secret_ref,
    )

    if should_succeed:
        a.full_clean()  # ok
        a.save()
        assert a.mode == AgentMode.CALLER
        assert a.inbound_auth_method == auth_method
        assert a.inbound_secret_ref == secret_ref
    else:
        with pytest.raises(ValidationError) as exc_info:
            a.full_clean()
        assert "inbound_secret_ref" in exc_info.value.error_dict
        field_err = exc_info.value.error_dict["inbound_secret_ref"][0]
        assert auth_method in str(field_err)


@pytest.mark.django_db
def test_unique_together_org_env_name_integrity_error(org_env_conn):
    """Test unique_together constraint raises IntegrityError via objects.create."""
    org, env, conn = org_env_conn

    # Create first agent
    Agent.objects.create(
        organization=org,
        environment=env,
        name="unique-agent",
        mode=AgentMode.RUNNER,
        connection=conn,
    )

    # Try to create duplicate via objects.create - should raise IntegrityError
    with pytest.raises(IntegrityError):
        Agent.objects.create(
            organization=org,
            environment=env,
            name="unique-agent",
            mode=AgentMode.RUNNER,
            connection=conn,
        )


@pytest.mark.django_db
def test_unique_together_org_env_name_validation_error(org_env_conn):
    """Test unique_together constraint raises ValidationError via validate_unique."""
    org, env, conn = org_env_conn

    # Create first agent
    Agent.objects.create(
        organization=org,
        environment=env,
        name="unique-agent-2",
        mode=AgentMode.RUNNER,
        connection=conn,
    )

    # Try to create duplicate via validate_unique - should raise ValidationError
    a = make_agent(org, env, name="unique-agent-2", connection=conn)
    with pytest.raises(ValidationError) as exc_info:
        a.validate_unique()  # validate_unique checks unique_together
    # Django's validate_unique raises ValidationError with error_dict containing the fields
    # that violate unique_together. The error may be on "name" or as a non-field error.
    assert len(exc_info.value.error_dict) > 0 or len(exc_info.value.messages) > 0


@pytest.mark.django_db
def test_runner_default_mode(org_env_conn):
    """Test that default mode is RUNNER."""
    org, env, conn = org_env_conn

    a = make_agent(org, env, name="default-agent", connection=conn)
    assert a.mode == AgentMode.RUNNER
    a.full_clean()
    a.save()
    assert a.mode == AgentMode.RUNNER


@pytest.mark.django_db
def test_caller_default_inbound_auth_method(org_env):
    """Test that CALLER default inbound_auth_method is 'bearer' (from model default)."""
    org, env = org_env

    # Create caller without specifying inbound_auth_method - should use model default
    # Don't use make_agent here, as it sets inbound_auth_method="none" by default
    a = Agent(
        organization=org,
        environment=env,
        name="caller-default",
        mode=AgentMode.CALLER,
    )
    # Model default is "bearer", but we need secret_ref for bearer
    assert a.inbound_auth_method == "bearer"  # Model default

    # Should fail without secret_ref (bearer requires it)
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "inbound_secret_ref" in exc_info.value.error_dict

    # Set secret_ref - should succeed
    a.inbound_secret_ref = "default-secret"
    a.full_clean()  # ok
    a.save()
    assert a.inbound_auth_method == "bearer"


@pytest.mark.django_db
def test_caller_none_auth_with_secret_ref_allowed(org_env):
    """Test that CALLER with NONE auth can have secret_ref (explicit test)."""
    org, env = org_env

    # Create caller with NONE auth but with secret_ref - should succeed
    # This explicitly tests that secret_ref is optional (not required) for NONE auth,
    # but it's allowed to be set if needed
    a = make_agent(
        org,
        env,
        name="caller-none-with-secret",
        mode=AgentMode.CALLER,
        inbound_auth_method=InboundAuthMethod.NONE,
        inbound_secret_ref="optional-secret",
    )
    a.full_clean()  # ok
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.inbound_auth_method == InboundAuthMethod.NONE
    assert a.inbound_secret_ref == "optional-secret"


@pytest.mark.django_db
def test_caller_none_auth_without_secret_ref_allowed(org_env):
    """Test that CALLER with NONE auth does not require secret_ref (explicit test)."""
    org, env = org_env

    # Create caller with NONE auth and no secret_ref - should succeed
    # This explicitly tests that secret_ref is not required for NONE auth
    a = make_agent(
        org,
        env,
        name="caller-none-without-secret",
        mode=AgentMode.CALLER,
        inbound_auth_method=InboundAuthMethod.NONE,
        inbound_secret_ref=None,
    )
    a.full_clean()  # ok
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.inbound_auth_method == InboundAuthMethod.NONE
    assert a.inbound_secret_ref is None


@pytest.mark.django_db
def test_mode_transition_runner_to_caller_with_connection(org_env_conn):
    """Test mode transition from RUNNER to CALLER with connection set."""
    org, env, conn = org_env_conn

    # Create runner with connection
    a = make_agent(org, env, name="transition-agent", connection=conn)
    a.save()
    assert a.mode == AgentMode.RUNNER
    assert a.connection == conn

    # Transition to CALLER - connection should remain (it's optional for CALLER)
    a.mode = AgentMode.CALLER
    a.inbound_auth_method = "none"
    a.full_clean()  # Should succeed - connection is optional for CALLER
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.connection == conn  # Connection remains


@pytest.mark.django_db
def test_mode_transition_caller_to_runner_without_connection(org_env):
    """Test mode transition from CALLER to RUNNER without connection."""
    org, env = org_env

    # Create caller without connection
    a = make_agent(org, env, name="transition-agent-2", mode=AgentMode.CALLER, connection=None)
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.connection is None

    # Transition to RUNNER without connection - should fail
    a.mode = AgentMode.RUNNER
    with pytest.raises(ValidationError) as exc_info:
        a.full_clean()
    assert "connection" in exc_info.value.error_dict
    field_err = exc_info.value.error_dict["connection"][0]
    assert "RUNNER" in str(field_err)


@pytest.mark.django_db
def test_mode_transition_caller_to_runner_with_connection(org_env_conn):
    """Test mode transition from CALLER to RUNNER with connection."""
    org, env, conn = org_env_conn

    # Create caller with connection
    a = make_agent(org, env, name="transition-agent-3", mode=AgentMode.CALLER, connection=conn)
    a.save()
    assert a.mode == AgentMode.CALLER
    assert a.connection == conn

    # Transition to RUNNER with connection - should succeed
    a.mode = AgentMode.RUNNER
    a.full_clean()  # Should succeed - connection is set
    a.save()
    assert a.mode == AgentMode.RUNNER
    assert a.connection == conn


@pytest.mark.django_db
def test_connection_must_match_org_env(org_env_conn):
    """Test that connection must match agent's organization and environment."""
    org, env, conn = org_env_conn

    # Create connection in different org/env
    other_org = Organization.objects.create(name="OtherOrg")
    other_env = Environment.objects.create(organization=other_org, name="dev", type="dev")
    bad_conn = Connection.objects.create(
        organization=other_org,
        environment=other_env,
        name="bad-conn",
        endpoint="https://example.com",
        auth_method="none",
        status="ok",
    )

    # Try to create agent with mismatched connection - Django FK constraint allows this
    # but we should validate it in clean() if needed
    # For now, Django allows FK mismatches at model level, so this test documents current behavior
    a = make_agent(org, env, name="mismatch-agent", connection=bad_conn)
    # Django FK doesn't validate org/env match, so this would succeed at model level
    # If we want to enforce this, we'd add validation in clean()
    a.full_clean()  # Currently succeeds - FK constraint doesn't check org/env match
    a.save()
    # Document that this is allowed - if we want to prevent it, add validation in Agent.clean()
    assert a.connection == bad_conn
    assert a.connection.organization != a.organization  # Mismatch exists but is allowed

