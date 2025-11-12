"""
Tests for P0 security features: iat, TTL, Session-Lock.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from apps.agents.models import Agent
from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool
from mcp_fabric.errors import ErrorCodes
from mcp_fabric.main import app
from mcp_fabric.oidc import validate_token
from mcp_fabric.settings import MCP_TOKEN_MAX_IAT_AGE_MINUTES, MCP_TOKEN_MAX_TTL_MINUTES


@pytest.fixture
def org_env():
    """Create organization and environment for testing."""
    org = Organization.objects.create(name="test-org")
    env = Environment.objects.create(name="test-env", organization=org, type="development")
    return org, env


@pytest.fixture
def agent_tool(org_env):
    """Create agent and tool for testing."""
    org, env = org_env

    conn = Connection.objects.create(
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="http://localhost",
        auth_method="none",
        status="ok",
    )
    agent = Agent.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
        enabled=True,
    )
    tool = Tool.objects.create(
        organization=org,
        environment=env,
        connection=conn,
        name="test-tool",
        enabled=True,
    )
    return agent, tool


@pytest.fixture
def private_key():
    """Generate RSA private key for testing."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def public_key(private_key):
    """Get public key from private key."""
    return private_key.public_key()


@pytest.mark.django_db
class TestIATValidation:
    """Test iat (issued at) claim validation."""

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_missing_iat_rejected(self, mock_get_key, mock_get_jwks, public_key, org_env, private_key):
        """Test that token without iat claim is rejected."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)

        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "scope": "mcp:run",
                # Missing iat
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        with pytest.raises(HTTPException) as exc_info:
            validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert ErrorCodes.INVALID_TOKEN in str(exc_info.value.detail)

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_iat_too_old_rejected(
        self, mock_get_key, mock_get_jwks, public_key, org_env, private_key
    ):
        """Test that token with iat too old is rejected."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        # iat is older than max age
        iat = now - timedelta(minutes=MCP_TOKEN_MAX_IAT_AGE_MINUTES + 1)
        exp = now + timedelta(minutes=30)

        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        with pytest.raises(HTTPException) as exc_info:
            validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert ErrorCodes.INVALID_TOKEN in str(exc_info.value.detail)
        assert "too old" in str(exc_info.value.detail).lower()

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_valid_iat_accepted(
        self, mock_get_key, mock_get_jwks, public_key, org_env, private_key
    ):
        """Test that token with valid iat is accepted."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        iat = now - timedelta(minutes=10)  # Recent iat
        exp = now + timedelta(minutes=20)

        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        claims = validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))
        assert claims["org_id"] == str(org.id)
        assert claims["env_id"] == str(env.id)


@pytest.mark.django_db
class TestTTLValidation:
    """Test maximum TTL validation."""

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_ttl_exceeds_max_rejected(
        self, mock_get_key, mock_get_jwks, public_key, org_env, private_key
    ):
        """Test that token with TTL exceeding max is rejected."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        iat = now
        # TTL exceeds max (e.g., 60 minutes when max is 30)
        exp = now + timedelta(minutes=MCP_TOKEN_MAX_TTL_MINUTES + 1)

        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        with pytest.raises(HTTPException) as exc_info:
            validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert ErrorCodes.INVALID_TOKEN in str(exc_info.value.detail)
        assert "TTL" in str(exc_info.value.detail) or "ttl" in str(exc_info.value.detail).lower()

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_valid_ttl_accepted(
        self, mock_get_key, mock_get_jwks, public_key, org_env, private_key
    ):
        """Test that token with valid TTL is accepted."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        iat = now
        # TTL within max (e.g., 20 minutes when max is 30)
        exp = now + timedelta(minutes=MCP_TOKEN_MAX_TTL_MINUTES - 10)

        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        claims = validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))
        assert claims["org_id"] == str(org.id)
        assert claims["env_id"] == str(env.id)


@pytest.mark.django_db
class TestSessionLock:
    """Test Session-Lock: Agent-ID binding to token."""

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_agent_id_mismatch_rejected(
        self, mock_get_key, mock_get_jwks, public_key, org_env, agent_tool, private_key
    ):
        """Test that agent_id mismatch between token and query is rejected."""
        org, env = org_env
        agent1, tool = agent_tool
        
        # Create second agent
        agent2 = Agent.objects.create(
            organization=org,
            environment=env,
            connection=agent1.connection,
            name="test-agent-2",
            enabled=True,
        )

        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        iat = now - timedelta(minutes=10)
        exp = now + timedelta(minutes=20)

        # Token has agent1 ID
        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "agent_id": str(agent1.id),  # Token bound to agent1
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        # Validate token first
        claims = validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))
        assert claims["agent_id"] == str(agent1.id)

        # Test adapter with mismatched agent_id
        from mcp_fabric.adapters import run_tool_via_agentxsuite

        result = run_tool_via_agentxsuite(
            tool=tool,
            payload={},
            agent_id=str(agent2.id),  # Request specifies agent2
            token_agent_id=str(agent1.id),  # Token has agent1
        )

        assert result["status"] == "error"
        assert result["error"] == "agent_session_mismatch"

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_agent_id_match_accepted(
        self, mock_get_key, mock_get_jwks, public_key, org_env, agent_tool, private_key
    ):
        """Test that matching agent_id is accepted."""
        org, env = org_env
        agent, tool = agent_tool

        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        iat = now - timedelta(minutes=10)
        exp = now + timedelta(minutes=20)

        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "agent_id": str(agent.id),
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        claims = validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))
        assert claims["agent_id"] == str(agent.id)

        # Test adapter with matching agent_id
        from mcp_fabric.adapters import run_tool_via_agentxsuite

        result = run_tool_via_agentxsuite(
            tool=tool,
            payload={},
            agent_id=str(agent.id),  # Request specifies same agent
            token_agent_id=str(agent.id),  # Token has same agent
        )

        # Should not fail with agent_session_mismatch (may fail for other reasons like policy)
        assert result["status"] != "error" or result.get("error") != "agent_session_mismatch"

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_initial_connect_with_query_agent_id(
        self, mock_get_key, mock_get_jwks, public_key, org_env, agent_tool, private_key
    ):
        """Test that initial Connect with query agent_id works when token has resolved agent_id."""
        org, env = org_env
        agent, tool = agent_tool

        # Create ServiceAccount for agent (required for new mapping)
        from apps.accounts.models import ServiceAccount

        sa = ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="test-sa",
            subject="agent:test@org/env",
            issuer="https://auth.example.com",
            audience="https://mcp.example.com/mcp",
            enabled=True,
        )
        agent.service_account = sa
        agent.save()

        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = public_key

        now = datetime.now(timezone.utc)
        iat = now - timedelta(minutes=10)
        exp = now + timedelta(minutes=20)

        # Token with subject/issuer (will be resolved to agent via mapping)
        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://mcp.example.com/mcp",
                "sub": "agent:test@org/env",  # Required for mapping
                "iat": iat.timestamp(),
                "exp": exp.timestamp(),
                "nbf": (now - timedelta(minutes=1)).timestamp(),
                "org_id": str(org.id),
                "env_id": str(env.id),
                "scope": "mcp:run",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

        claims = validate_token(token, required_org_id=str(org.id), required_env_id=str(env.id))
        assert "sub" in claims

        # Test adapter: resolved agent_id should work
        from mcp_fabric.adapters import run_tool_via_agentxsuite

        result = run_tool_via_agentxsuite(
            tool=tool,
            payload={},
            agent_id=str(agent.id),  # Query specifies agent
            token_agent_id=str(agent.id),  # Resolved agent_id from token
        )

        # Should not fail with agent_session_mismatch (they match)
        assert result["status"] != "error" or result.get("error") != "agent_session_mismatch"


@pytest.mark.django_db
class TestSubjectIssuerAgentMapping:
    """Test (subject, issuer) → Agent mapping (source of truth)."""

    @pytest.fixture
    def service_account_agent(self, org_env):
        """Create ServiceAccount and Agent linked together."""
        org, env = org_env
        from apps.accounts.models import ServiceAccount
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost",
            auth_method="none",
            status="ok",
        )

        sa = ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="test-sa",
            subject="agent:test@org/env",
            issuer="https://auth.example.com",
            audience="https://mcp.example.com/mcp",
            enabled=True,
        )

        agent = Agent.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-agent",
            service_account=sa,
            enabled=True,
        )

        return sa, agent

    def test_resolve_agent_from_valid_subject_issuer(self, service_account_agent, org_env):
        """Test that agent is resolved correctly from (subject, issuer)."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        sa, agent = service_account_agent
        org, env = org_env

        claims = {
            "sub": "agent:test@org/env",
            "iss": "https://auth.example.com",
            "org_id": str(org.id),
            "env_id": str(env.id),
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))

        assert resolved is not None
        assert resolved.id == agent.id
        assert resolved.service_account.id == sa.id

    def test_resolve_agent_fails_without_subject(self, service_account_agent, org_env):
        """Test that agent resolution fails without subject."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        org, env = org_env

        claims = {
            "iss": "https://auth.example.com",
            "org_id": str(org.id),
            "env_id": str(env.id),
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))
        assert resolved is None

    def test_resolve_agent_fails_without_issuer(self, service_account_agent, org_env):
        """Test that agent resolution fails without issuer."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        org, env = org_env

        claims = {
            "sub": "agent:test@org/env",
            "org_id": str(org.id),
            "env_id": str(env.id),
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))
        assert resolved is None

    def test_resolve_agent_fails_when_service_account_not_found(self, org_env):
        """Test that agent resolution fails when ServiceAccount doesn't exist."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        org, env = org_env

        claims = {
            "sub": "agent:nonexistent@org/env",
            "iss": "https://auth.example.com",
            "org_id": str(org.id),
            "env_id": str(env.id),
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))
        assert resolved is None

    def test_resolve_agent_fails_when_org_mismatch(self, service_account_agent):
        """Test that agent resolution fails when org_id doesn't match."""
        from apps.tenants.models import Organization
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        sa, agent = service_account_agent
        other_org = Organization.objects.create(name="other-org")

        claims = {
            "sub": "agent:test@org/env",
            "iss": "https://auth.example.com",
            "org_id": str(other_org.id),  # Wrong org
            "env_id": str(agent.environment.id),
        }

        resolved = resolve_agent_from_token_claims(
            claims, str(other_org.id), str(agent.environment.id)
        )
        assert resolved is None

    def test_resolve_agent_fails_when_agent_disabled(self, service_account_agent, org_env):
        """Test that agent resolution fails when agent is disabled."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        sa, agent = service_account_agent
        org, env = org_env

        # Disable agent
        agent.enabled = False
        agent.save()

        claims = {
            "sub": "agent:test@org/env",
            "iss": "https://auth.example.com",
            "org_id": str(org.id),
            "env_id": str(env.id),
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))
        assert resolved is None

    def test_resolve_agent_validates_token_agent_id(self, service_account_agent, org_env):
        """Test that token agent_id is validated against resolved agent."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        sa, agent = service_account_agent
        org, env = org_env

        # Token claims with mismatched agent_id
        claims = {
            "sub": "agent:test@org/env",
            "iss": "https://auth.example.com",
            "org_id": str(org.id),
            "env_id": str(env.id),
            "agent_id": str(uuid.uuid4()),  # Wrong agent_id
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))
        assert resolved is None  # Should fail because agent_id doesn't match

    def test_resolve_agent_accepts_matching_token_agent_id(self, service_account_agent, org_env):
        """Test that matching token agent_id is accepted."""
        from mcp_fabric.agent_resolver import resolve_agent_from_token_claims

        sa, agent = service_account_agent
        org, env = org_env

        # Token claims with matching agent_id
        claims = {
            "sub": "agent:test@org/env",
            "iss": "https://auth.example.com",
            "org_id": str(org.id),
            "env_id": str(env.id),
            "agent_id": str(agent.id),  # Correct agent_id
        }

        resolved = resolve_agent_from_token_claims(claims, str(org.id), str(env.id))
        assert resolved is not None
        assert resolved.id == agent.id


@pytest.mark.django_db
class TestJTIReplayProtection:
    """Test jti (JWT ID) replay protection."""

    def test_jti_replay_detected(self):
        """Test that duplicate jti is detected as replay."""
        from mcp_fabric.jti_store import check_jti_replay

        jti = "test-jti-12345"
        exp = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())

        # First use - should be OK
        is_replay, reason = check_jti_replay(jti, exp)
        assert is_replay is False
        assert reason is None

        # Second use - should be detected as replay
        is_replay, reason = check_jti_replay(jti, exp)
        assert is_replay is True
        assert "replay" in reason.lower() or "already been used" in reason.lower()

    def test_different_jti_allowed(self):
        """Test that different jti values are allowed."""
        from mcp_fabric.jti_store import check_jti_replay

        jti1 = "test-jti-11111"
        jti2 = "test-jti-22222"
        exp = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())

        # First jti - should be OK
        is_replay, reason = check_jti_replay(jti1, exp)
        assert is_replay is False

        # Second jti - should also be OK
        is_replay, reason = check_jti_replay(jti2, exp)
        assert is_replay is False

    def test_jti_without_exp_uses_default_ttl(self):
        """Test that jti without exp uses default TTL."""
        from mcp_fabric.jti_store import check_jti_replay

        jti = "test-jti-no-exp"

        # Should work without exp
        is_replay, reason = check_jti_replay(jti, None)
        assert is_replay is False

        # Should still be detected as replay
        is_replay, reason = check_jti_replay(jti, None)
        assert is_replay is True

    def test_jti_revocation(self):
        """Test manual jti revocation."""
        from mcp_fabric.jti_store import check_jti_replay, revoke_jti

        jti = "test-jti-revoke"
        exp = int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())

        # First use - should be OK
        is_replay, reason = check_jti_replay(jti, exp)
        assert is_replay is False

        # Revoke
        revoke_jti(jti)

        # Should be detected as replay/revoked
        is_replay, reason = check_jti_replay(jti, exp)
        assert is_replay is True


@pytest.mark.django_db
class TestAuditMetadata:
    """Test audit metadata (jti, ip, request_id) in PEP decisions."""

    @pytest.fixture
    def agent_tool_with_service_account(self, org_env):
        """Create agent with ServiceAccount and tool."""
        org, env = org_env
        from apps.accounts.models import ServiceAccount
        from apps.connections.models import Connection

        conn = Connection.objects.create(
            organization=org,
            environment=env,
            name="test-conn",
            endpoint="http://localhost",
            auth_method="none",
            status="ok",
        )

        sa = ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="test-sa",
            subject="agent:test@org/env",
            issuer="https://auth.example.com",
            audience="https://mcp.example.com/mcp",
            enabled=True,
        )

        agent = Agent.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-agent",
            service_account=sa,
            enabled=True,
        )

        tool = Tool.objects.create(
            organization=org,
            environment=env,
            connection=conn,
            name="test-tool",
            enabled=True,
        )

        return agent, tool

    def test_pep_logs_jti_in_audit(self, agent_tool_with_service_account):
        """Test that PEP logs jti in audit context."""
        from mcp_fabric.pep import check_policy_before_tool_call

        agent, tool = agent_tool_with_service_account
        jti = "test-jti-audit-123"

        # Call PEP with jti
        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
            jti=jti,
        )

        # Check audit event
        from apps.audit.models import AuditEvent

        audit = AuditEvent.objects.filter(
            event_type="pep_decision",
            target=f"tool:{tool.name}",
        ).latest("created_at")

        assert audit.context.get("jti") == jti
        assert audit.context.get("tool_id") == str(tool.id)

    def test_pep_logs_client_ip_in_audit(self, agent_tool_with_service_account):
        """Test that PEP logs client_ip in audit context."""
        from mcp_fabric.pep import check_policy_before_tool_call

        agent, tool = agent_tool_with_service_account
        client_ip = "192.168.1.100"

        # Call PEP with client_ip
        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
            client_ip=client_ip,
        )

        # Check audit event
        from apps.audit.models import AuditEvent

        audit = AuditEvent.objects.filter(
            event_type="pep_decision",
            target=f"tool:{tool.name}",
        ).latest("created_at")

        assert audit.context.get("client_ip") == client_ip
        assert audit.context.get("tool_id") == str(tool.id)

    def test_pep_logs_request_id_in_audit(self, agent_tool_with_service_account):
        """Test that PEP logs request_id in audit context."""
        from mcp_fabric.pep import check_policy_before_tool_call

        agent, tool = agent_tool_with_service_account
        request_id = str(uuid.uuid4())

        # Call PEP with request_id
        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
            request_id=request_id,
        )

        # Check audit event
        from apps.audit.models import AuditEvent

        audit = AuditEvent.objects.filter(
            event_type="pep_decision",
            target=f"tool:{tool.name}",
        ).latest("created_at")

        assert audit.context.get("request_id") == request_id
        assert audit.context.get("tool_id") == str(tool.id)

    def test_pep_logs_all_audit_metadata(self, agent_tool_with_service_account):
        """Test that PEP logs all audit metadata together."""
        from mcp_fabric.pep import check_policy_before_tool_call

        agent, tool = agent_tool_with_service_account
        jti = "test-jti-complete"
        client_ip = "10.0.0.1"
        request_id = str(uuid.uuid4())

        # Call PEP with all metadata
        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
            jti=jti,
            client_ip=client_ip,
            request_id=request_id,
        )

        # Check audit event
        from apps.audit.models import AuditEvent

        audit = AuditEvent.objects.filter(
            event_type="pep_decision",
            target=f"tool:{tool.name}",
        ).latest("created_at")

        assert audit.context.get("jti") == jti
        assert audit.context.get("client_ip") == client_ip
        assert audit.context.get("request_id") == request_id
        assert audit.context.get("tool_id") == str(tool.id)


@pytest.mark.django_db
class TestServiceAccountUniqueConstraint:
    """Test ServiceAccount unique(subject, issuer) constraint."""

    def test_unique_subject_issuer_permitted(self, org_env):
        """Test that same subject with different issuer is permitted."""
        from apps.accounts.models import ServiceAccount

        org, env = org_env

        sa1 = ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="sa1",
            subject="agent:test@org/env",
            issuer="https://auth1.example.com",
            audience="https://mcp.example.com/mcp",
        )

        # Same subject, different issuer - should be OK
        sa2 = ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="sa2",
            subject="agent:test@org/env",
            issuer="https://auth2.example.com",
            audience="https://mcp.example.com/mcp",
        )

        assert sa1.id != sa2.id

    def test_duplicate_subject_issuer_rejected(self, org_env):
        """Test that duplicate (subject, issuer) is rejected."""
        from apps.accounts.models import ServiceAccount

        org, env = org_env

        ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="sa1",
            subject="agent:test@org/env",
            issuer="https://auth.example.com",
            audience="https://mcp.example.com/mcp",
        )

        # Same subject AND issuer - should fail
        with pytest.raises(Exception):  # IntegrityError
            ServiceAccount.objects.create(
                organization=org,
                environment=env,
                name="sa2",
                subject="agent:test@org/env",
                issuer="https://auth.example.com",
                audience="https://mcp2.example.com/mcp",
            )

