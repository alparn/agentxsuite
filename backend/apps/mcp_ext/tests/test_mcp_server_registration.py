"""
Tests for MCP Server Registration model and API endpoints.
"""
from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.mcp_ext.models import MCPServerRegistration
from apps.tenants.models import Environment, Organization


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def org():
    """Create test organization."""
    return Organization.objects.create(name="Test Org")


@pytest.fixture
def environment(org):
    """Create test environment."""
    return Environment.objects.create(
        name="Test Environment",
        type="development",
        organization=org,
    )


@pytest.fixture
def http_server(org, environment):
    """Create test HTTP MCP server."""
    return MCPServerRegistration.objects.create(
        organization=org,
        environment=environment,
        name="GitHub MCP Server",
        slug="github",
        description="GitHub integration via MCP",
        server_type=MCPServerRegistration.ServerType.HTTP,
        endpoint="https://api.github.com/.well-known/mcp",
        auth_method=MCPServerRegistration.AuthMethod.BEARER,
        secret_ref="github-pat",
        enabled=True,
        health_status="unknown",
    )


@pytest.fixture
def stdio_server(org, environment):
    """Create test stdio MCP server."""
    return MCPServerRegistration.objects.create(
        organization=org,
        environment=environment,
        name="Local MCP Server",
        slug="local",
        server_type=MCPServerRegistration.ServerType.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/Users/test/documents"],
        env_vars={"DEBUG": "true"},
        enabled=True,
    )


class TestMCPServerRegistrationModel:
    """Tests for MCPServerRegistration model."""

    @pytest.mark.django_db
    def test_create_http_server(self, org, environment):
        """Test creating an HTTP MCP server."""
        server = MCPServerRegistration.objects.create(
            organization=org,
            environment=environment,
            name="Test HTTP Server",
            slug="test-http",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://example.com/.well-known/mcp",
            enabled=True,
        )
        
        assert server.id is not None
        assert server.name == "Test HTTP Server"
        assert server.slug == "test-http"
        assert server.server_type == MCPServerRegistration.ServerType.HTTP
        assert server.endpoint == "https://example.com/.well-known/mcp"
        assert server.enabled is True
        assert str(server) == f"{org.name}/{environment.name}/test-http"

    @pytest.mark.django_db
    def test_create_stdio_server(self, org, environment):
        """Test creating a stdio MCP server."""
        server = MCPServerRegistration.objects.create(
            organization=org,
            environment=environment,
            name="Test stdio Server",
            slug="test-stdio",
            server_type=MCPServerRegistration.ServerType.STDIO,
            command="python",
            args=["-m", "my_mcp_server"],
            env_vars={"API_KEY": "secret://my-api-key"},
            enabled=True,
        )
        
        assert server.server_type == MCPServerRegistration.ServerType.STDIO
        assert server.command == "python"
        assert server.args == ["-m", "my_mcp_server"]
        assert server.env_vars == {"API_KEY": "secret://my-api-key"}

    @pytest.mark.django_db
    def test_unique_slug_per_org_env(self, org, environment):
        """Test that slug must be unique per org/env combination."""
        MCPServerRegistration.objects.create(
            organization=org,
            environment=environment,
            name="Server 1",
            slug="unique-slug",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://example.com",
        )
        
        # Creating another server with same slug in same org/env should fail
        with pytest.raises(Exception):  # IntegrityError
            MCPServerRegistration.objects.create(
                organization=org,
                environment=environment,
                name="Server 2",
                slug="unique-slug",
                server_type=MCPServerRegistration.ServerType.HTTP,
                endpoint="https://example2.com",
            )

    @pytest.mark.django_db
    def test_http_server_requires_endpoint(self, org, environment):
        """Test that HTTP servers require endpoint field."""
        server = MCPServerRegistration(
            organization=org,
            environment=environment,
            name="Test Server",
            slug="test",
            server_type=MCPServerRegistration.ServerType.HTTP,
            # endpoint intentionally missing
        )
        
        with pytest.raises(ValidationError) as exc_info:
            server.full_clean()
        
        assert "endpoint" in exc_info.value.message_dict

    @pytest.mark.django_db
    def test_stdio_server_requires_command(self, org, environment):
        """Test that stdio servers require command field."""
        server = MCPServerRegistration(
            organization=org,
            environment=environment,
            name="Test Server",
            slug="test",
            server_type=MCPServerRegistration.ServerType.STDIO,
            # command intentionally missing
        )
        
        with pytest.raises(ValidationError) as exc_info:
            server.full_clean()
        
        assert "command" in exc_info.value.message_dict

    @pytest.mark.django_db
    def test_environment_must_belong_to_organization(self, org):
        """Test that environment must belong to the organization."""
        other_org = Organization.objects.create(name="Other Org")
        other_env = Environment.objects.create(
            name="Other Environment",
            type="production",
            organization=other_org,
        )
        
        server = MCPServerRegistration(
            organization=org,  # Different org!
            environment=other_env,
            name="Test Server",
            slug="test",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://example.com",
        )
        
        with pytest.raises(ValidationError) as exc_info:
            server.full_clean()
        
        assert "environment" in exc_info.value.message_dict


class TestMCPServerRegistrationAPI:
    """Tests for MCP Server Registration API endpoints."""

    @pytest.mark.django_db
    def test_list_servers(self, api_client, org, environment, http_server, stdio_server):
        """Test listing MCP servers."""
        # Note: In real scenario, you'd need authentication
        # For now, we assume the endpoint is accessible or mocked
        
        # This is a placeholder - actual API tests would need proper auth setup
        servers = MCPServerRegistration.objects.filter(organization=org)
        assert servers.count() == 2
        
        # Verify both servers are present
        slugs = [s.slug for s in servers]
        assert "github" in slugs
        assert "local" in slugs

    @pytest.mark.django_db
    def test_filter_servers_by_environment(self, org):
        """Test filtering servers by environment."""
        env1 = Environment.objects.create(name="Dev", type="development", organization=org)
        env2 = Environment.objects.create(name="Prod", type="production", organization=org)
        
        MCPServerRegistration.objects.create(
            organization=org,
            environment=env1,
            name="Dev Server",
            slug="dev-server",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://dev.example.com",
        )
        
        MCPServerRegistration.objects.create(
            organization=org,
            environment=env2,
            name="Prod Server",
            slug="prod-server",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://prod.example.com",
        )
        
        dev_servers = MCPServerRegistration.objects.filter(organization=org, environment=env1)
        assert dev_servers.count() == 1
        assert dev_servers.first().slug == "dev-server"
        
        prod_servers = MCPServerRegistration.objects.filter(organization=org, environment=env2)
        assert prod_servers.count() == 1
        assert prod_servers.first().slug == "prod-server"

    @pytest.mark.django_db
    def test_server_defaults(self, org, environment):
        """Test default values for server fields."""
        server = MCPServerRegistration.objects.create(
            organization=org,
            environment=environment,
            name="Minimal Server",
            slug="minimal",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://example.com",
        )
        
        # Check defaults
        assert server.enabled is True
        assert server.health_status == "unknown"
        assert server.auth_method == MCPServerRegistration.AuthMethod.NONE
        assert server.args == []
        assert server.env_vars == {}
        assert server.tags == []
        assert server.metadata == {}
        assert server.description == ""
        assert server.command == ""
        assert server.secret_ref == ""

    @pytest.mark.django_db
    def test_server_with_tags_and_metadata(self, org, environment):
        """Test server with tags and metadata."""
        server = MCPServerRegistration.objects.create(
            organization=org,
            environment=environment,
            name="Tagged Server",
            slug="tagged",
            server_type=MCPServerRegistration.ServerType.HTTP,
            endpoint="https://example.com",
            tags=["external", "beta"],
            metadata={"version": "1.0.0", "maintainer": "team@example.com"},
        )
        
        assert "external" in server.tags
        assert "beta" in server.tags
        assert server.metadata["version"] == "1.0.0"
        assert server.metadata["maintainer"] == "team@example.com"

