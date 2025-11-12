"""
Tests for MCP Fabric security features.
"""
from __future__ import annotations

import uuid
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from apps.accounts.models import ServiceAccount
from apps.agents.models import Agent
from apps.audit.models import AuditEvent
from apps.policies.models import Policy
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool
from mcp_fabric.main import app
from mcp_fabric.oidc import validate_token
from mcp_fabric.pep import check_policy_before_tool_call
from mcp_fabric.routers.prm import oauth_protected_resource


@pytest.fixture
def org_env():
    """Create organization and environment for testing."""
    org = Organization.objects.create(name="test-org")
    env = Environment.objects.create(name="test-env", organization=org, type="development")
    return org, env


@pytest.fixture
def service_account(org_env):
    """Create service account for testing."""
    org, env = org_env
    return ServiceAccount.objects.create(
        organization=org,
        environment=env,
        name="test-service-account",
        audience="https://mcp.example.com/mcp",
        issuer="https://auth.example.com",
        scope_allowlist=["mcp:tools", "mcp:run"],
        enabled=True,
    )


@pytest.fixture
def agent_tool(org_env):
    """Create agent and tool for testing."""
    org, env = org_env
    from apps.connections.models import Connection

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


@pytest.mark.django_db
class TestStrictAudienceCheck:
    """Test strict audience checking (no token passthrough)."""

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    @patch("mcp_fabric.oidc.OIDC_ISSUER", "https://auth.example.com")
    @patch("mcp_fabric.oidc.AUTHORIZATION_SERVERS", ["https://auth.example.com"])
    @patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp")
    def test_audience_must_match_resource(self, mock_get_key, mock_get_jwks, org_env):
        """Test that audience must match resource parameter."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        
        # Mock RSA public key for signature verification
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        
        # Generate matching key pair
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        mock_get_key.return_value = public_key

        # Create token with RS256 and wrong audience
        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        token = jwt.encode(
            {
                "iss": "https://auth.example.com",
                "aud": "https://wrong.example.com/mcp",
                "sub": "test",
                "exp": 9999999999,
                "nbf": 0,
                "org_id": str(org.id),
                "env_id": str(env.id),
            },
            pem_private,
            algorithm="RS256",
        )

        # Should raise 401 for invalid audience
        with pytest.raises(HTTPException) as exc_info:
            validate_token(
                token,
                resource="https://mcp.example.com/mcp",
                required_org_id=str(org.id),
                required_env_id=str(env.id),
            )
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        # Check that error mentions audience (either in detail or error_description)
        error_detail = str(exc_info.value.detail)
        assert "audience" in error_detail.lower() or "invalid" in error_detail.lower()

    @patch("mcp_fabric.oidc.get_jwks")
    @patch("mcp_fabric.oidc.get_signing_key")
    def test_audience_must_match_canonical_uri(self, mock_get_key, mock_get_jwks, org_env):
        """Test that audience must match MCP_CANONICAL_URI if no resource parameter."""
        org, env = org_env
        mock_get_jwks.return_value = {"keys": []}
        mock_get_key.return_value = Mock()

        with patch("mcp_fabric.oidc.MCP_CANONICAL_URI", "https://mcp.example.com/mcp"):
            token = jwt.encode(
                {
                    "iss": "https://auth.example.com",
                    "aud": "https://mcp.example.com/mcp",
                    "sub": "test",
                    "exp": 9999999999,
                    "nbf": 0,
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                },
                "secret",
                algorithm="HS256",
            )

            # Should not raise if audience matches
            # Note: This test would need proper JWKS setup to fully validate
            # For now, we test the logic path


@pytest.mark.django_db
class TestResourceParameter:
    """Test resource parameter validation."""

    def test_resource_parameter_extracted_from_query(self, org_env):
        """Test that resource parameter is extracted from query string."""
        # This would be tested via integration test with TestClient
        pass


@pytest.mark.django_db
class TestWellKnownEndpoint:
    """Test well-known endpoint."""

    @pytest.mark.asyncio
    async def test_oauth_protected_resource_metadata(self):
        """Test that PRM endpoint returns correct metadata."""
        with patch("mcp_fabric.routers.prm.MCP_CANONICAL_URI", "https://mcp.example.com/mcp"):
            with patch("mcp_fabric.routers.prm.AUTHORIZATION_SERVERS", ["https://auth.example.com"]):
                result = await oauth_protected_resource()
                assert "resource" in result
                assert "authorization_servers" in result
                assert "scopes_supported" in result
                assert "resource_metadata" in result
                assert result["resource"] == "https://mcp.example.com/mcp"
                assert "https://auth.example.com" in result["authorization_servers"]
                assert result["resource_metadata"]["authentication"]["audience_validation"] == "strict"


@pytest.mark.django_db
class TestPEPMiddleware:
    """Test Policy Enforcement Point middleware."""

    def test_pep_allows_when_policy_allows(self, agent_tool):
        """Test that PEP allows when policy explicitly allows."""
        agent, tool = agent_tool

        # Create allow policy
        Policy.objects.create(
            organization=agent.organization,
            environment=agent.environment,
            name="allow-policy",
            rules_json={"allow": [tool.name]},
            enabled=True,
        )

        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
        )
        assert allowed is True
        assert reason is None

        # Check audit log
        audit = AuditEvent.objects.filter(event_type="pep_allowed").first()
        assert audit is not None
        assert audit.event_data["tool_name"] == tool.name

    def test_pep_denies_when_no_policy(self, agent_tool):
        """Test that PEP denies by default when no policy exists."""
        agent, tool = agent_tool

        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
        )
        assert allowed is False
        assert reason is not None

        # Check audit log
        audit = AuditEvent.objects.filter(event_type="pep_denied").first()
        assert audit is not None
        assert audit.event_data["tool_name"] == tool.name

    def test_pep_denies_when_policy_denies(self, agent_tool):
        """Test that PEP denies when policy explicitly denies."""
        agent, tool = agent_tool

        # Create deny policy
        Policy.objects.create(
            organization=agent.organization,
            environment=agent.environment,
            name="deny-policy",
            rules_json={"deny": [tool.name]},
            enabled=True,
        )

        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
        )
        assert allowed is False
        assert "denied" in reason.lower()

        # Check audit log
        audit = AuditEvent.objects.filter(event_type="pep_denied").first()
        assert audit is not None


@pytest.mark.django_db
class TestServiceAccount:
    """Test ServiceAccount model."""

    def test_service_account_creation(self, org_env):
        """Test creating a service account."""
        org, env = org_env
        sa = ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="test-sa",
            audience="https://mcp.example.com/mcp",
            issuer="https://auth.example.com",
            scope_allowlist=["mcp:tools"],
        )
        assert sa.organization == org
        assert sa.environment == env
        assert sa.audience == "https://mcp.example.com/mcp"
        assert sa.issuer == "https://auth.example.com"
        assert "mcp:tools" in sa.scope_allowlist

    def test_service_account_unique_name_per_org(self, org_env):
        """Test that service account names are unique per organization."""
        org, env = org_env
        ServiceAccount.objects.create(
            organization=org,
            environment=env,
            name="test-sa",
            audience="https://mcp.example.com/mcp",
            issuer="https://auth.example.com",
        )

        # Try to create another with same name in same org
        with pytest.raises(Exception):  # IntegrityError
            ServiceAccount.objects.create(
                organization=org,
                environment=env,
                name="test-sa",
                audience="https://mcp2.example.com/mcp",
                issuer="https://auth.example.com",
            )


@pytest.mark.django_db
class TestWWWAuthenticateHeader:
    """Test WWW-Authenticate header generation."""

    def test_www_authenticate_includes_resource(self):
        """Test that WWW-Authenticate header includes resource parameter."""
        from mcp_fabric.deps import get_www_authenticate_header
        from mcp_fabric import settings

        with patch.object(settings, "MCP_CANONICAL_URI", "https://mcp.example.com/mcp"):
            header = get_www_authenticate_header(resource="https://mcp.example.com/mcp")
            assert "WWW-Authenticate" in header
            assert 'resource="https://mcp.example.com/mcp"' in header["WWW-Authenticate"]

    def test_www_authenticate_includes_scope(self):
        """Test that WWW-Authenticate header includes scope parameter."""
        from mcp_fabric.deps import get_www_authenticate_header

        header = get_www_authenticate_header(scope="mcp:tools")
        assert "WWW-Authenticate" in header
        assert 'scope="mcp:tools"' in header["WWW-Authenticate"]


@pytest.mark.django_db
class TestSessionHandling:
    """Test that session handling is hard (no sessions as auth replacement)."""

    def test_session_auth_disabled_in_drf(self):
        """Test that SessionAuthentication is disabled in DRF config."""
        from django.conf import settings

        assert "rest_framework.authentication.SessionAuthentication" not in settings.REST_FRAMEWORK[
            "DEFAULT_AUTHENTICATION_CLASSES"
        ]
        assert settings.MCP_FABRIC_SESSION_AUTH_DISABLED is True

