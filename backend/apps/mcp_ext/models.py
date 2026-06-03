"""
MCP Extensions models: Resources and Prompts.
"""
from __future__ import annotations

from django.db import models

from libs.common.models import TimeStamped


class Resource(TimeStamped):
    """Resource model for MCP resources."""

    TYPE_CHOICES = [
        ("static", "Static"),
        ("http", "HTTP"),
        ("sql", "SQL"),
        ("s3", "S3"),
        ("file", "File"),
    ]

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="resources",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="resources",
    )
    name = models.CharField(max_length=120)
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="static",
    )
    config_json = models.JSONField(
        default=dict,
        help_text="Configuration for resource type (e.g., URL for HTTP, value for static)",
    )
    mime_type = models.CharField(
        max_length=80,
        default="application/json",
        help_text="MIME type of the resource content",
    )
    schema_json = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON Schema describing the resource structure",
    )
    secret_ref = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Secret reference for authentication (e.g., API keys)",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mcp_ext_resource"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"


class Prompt(TimeStamped):
    """Prompt model for MCP prompts."""

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="prompts",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="prompts",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    input_schema = models.JSONField(
        default=dict,
        help_text="JSON Schema for prompt input variables",
    )
    template_system = models.TextField(
        blank=True,
        help_text="System message template (Jinja2)",
    )
    template_user = models.TextField(
        blank=True,
        help_text="User message template (Jinja2)",
    )
    uses_resources = models.JSONField(
        default=list,
        help_text="List of resource names used by this prompt",
    )
    output_hints = models.JSONField(
        default=dict,
        blank=True,
        help_text="Hints for expected output format",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "mcp_ext_prompt"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "name"]]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.name}"


class MCPServerRegistration(TimeStamped):
    """
    Registry of external MCP servers that can be exposed via AgentxSuite.
    
    This allows centralized management of all MCP servers (internal + external)
    with unified credential handling and policy enforcement.
    """

    class ServerType(models.TextChoices):
        STDIO = "stdio", "stdio (native)"
        HTTP = "http", "HTTP-based"
        WEBSOCKET = "ws", "WebSocket"

    class AuthMethod(models.TextChoices):
        NONE = "none", "No Authentication"
        BEARER = "bearer", "Bearer Token"
        BASIC = "basic", "Basic Auth"
        API_KEY = "api_key", "API Key"
        OAUTH2 = "oauth2", "OAuth2"

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="mcp_servers",
        help_text="Organization that owns this MCP server",
    )
    environment = models.ForeignKey(
        "tenants.Environment",
        on_delete=models.CASCADE,
        related_name="mcp_servers",
        help_text="Environment this server is available in",
    )
    connection = models.OneToOneField(
        "connections.Connection",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mcp_server_registration",
        help_text="Canonical AgentxSuite connection backing this legacy registration.",
    )

    # Server metadata
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name (e.g., 'GitHub MCP Server')",
    )
    slug = models.SlugField(
        max_length=64,
        help_text="Unique identifier for Claude Desktop config (e.g., 'github')",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of what this server provides",
    )
    server_type = models.CharField(
        max_length=10,
        choices=ServerType.choices,
        default=ServerType.HTTP,
        help_text="Transport protocol for MCP communication",
    )

    # Connection details for different server types
    endpoint = models.URLField(
        blank=True,
        max_length=500,
        help_text="For HTTP/WS servers: full URL (e.g., 'https://api.github.com/mcp')",
    )
    command = models.CharField(
        max_length=500,
        blank=True,
        help_text="For stdio servers: executable command (e.g., 'npx', 'python')",
    )
    args = models.JSONField(
        default=list,
        help_text="Command arguments as array (e.g., ['-y', '@modelcontextprotocol/server-github'])",
    )
    env_vars = models.JSONField(
        default=dict,
        help_text="Environment variables for stdio servers (e.g., {'GITHUB_TOKEN': 'secret://github-token'})",
    )

    # Authentication
    auth_method = models.CharField(
        max_length=20,
        choices=AuthMethod.choices,
        default=AuthMethod.NONE,
        help_text="Authentication method for HTTP/WS servers",
    )
    secret_ref = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reference to secret in SecretStore (e.g., 'github-pat')",
    )

    # Status & Health
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this server is active and available for use",
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time a health check was performed",
    )
    health_status = models.CharField(
        max_length=20,
        default="unknown",
        help_text="Current health status (unknown/healthy/unhealthy)",
    )
    health_message = models.TextField(
        blank=True,
        help_text="Details from last health check",
    )

    # Metadata
    tags = models.JSONField(
        default=list,
        help_text="Tags for categorization (e.g., ['development', 'external'])",
    )
    metadata = models.JSONField(
        default=dict,
        help_text="Additional metadata (e.g., version, capabilities)",
    )

    class Meta:
        db_table = "mcp_ext_server_registration"
        ordering = ["-created_at"]
        unique_together = [["organization", "environment", "slug"]]
        indexes = [
            models.Index(fields=["organization", "environment", "enabled"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["server_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name}/{self.environment.name}/{self.slug}"

    def clean(self):
        """Validate model constraints."""
        from django.core.exceptions import ValidationError

        errors = {}

        # Validate server type specific fields
        if self.server_type == self.ServerType.STDIO:
            if not self.command:
                errors["command"] = "Command is required for stdio servers"
        elif self.server_type in [self.ServerType.HTTP, self.ServerType.WEBSOCKET]:
            if not self.endpoint:
                errors["endpoint"] = "Endpoint is required for HTTP/WebSocket servers"

        # Validate environment belongs to organization
        if self.environment and self.organization:
            if self.environment.organization_id != self.organization_id:
                errors["environment"] = "Environment must belong to the selected organization"

        egress_allowlist = self.metadata.get("egress_allowlist") if isinstance(self.metadata, dict) else None
        if egress_allowlist is not None and (
            not isinstance(egress_allowlist, list)
            or not all(isinstance(entry, str) for entry in egress_allowlist)
        ):
            errors["metadata"] = "metadata.egress_allowlist must be a list of strings"

        if errors:
            raise ValidationError(errors)

    def save(self, *args, sync_connection: bool = True, **kwargs):
        """Persist the legacy registration and keep its canonical Connection in sync."""
        super().save(*args, **kwargs)
        if not sync_connection:
            return

        connection = self.sync_to_connection()
        if self.connection_id != connection.id:
            type(self).objects.filter(pk=self.pk).update(connection=connection)
            self.connection = connection

    def sync_to_connection(self):
        """Create or update the canonical Connection backing this registration."""
        from apps.connections.models import Connection

        defaults = {
            "transport": self._connection_transport(),
            "endpoint": self.endpoint or None,
            "command": self.command,
            "args": self.args or [],
            "env_ref": self.metadata.get("env_ref") if isinstance(self.metadata, dict) else None,
            "auth_method": self._connection_auth_method(),
            "secret_ref": self.secret_ref or None,
            "egress_allowlist": self._connection_egress_allowlist(),
            "status": self._connection_status(),
        }

        if self.connection_id:
            Connection.objects.filter(pk=self.connection_id).update(**defaults)
            return Connection.objects.get(pk=self.connection_id)

        connection, _created = Connection.objects.update_or_create(
            organization=self.organization,
            environment=self.environment,
            name=self.slug,
            defaults=defaults,
        )
        return connection

    def _connection_transport(self):
        """Map legacy registration server types to Connection transports."""
        from apps.connections.models import Connection

        if self.server_type == self.ServerType.STDIO:
            return Connection.Transport.STDIO
        if self.server_type == self.ServerType.WEBSOCKET:
            return Connection.Transport.SSE
        return Connection.Transport.STREAMABLE_HTTP

    def _connection_auth_method(self) -> str:
        """Map registration auth methods to Connection auth methods."""
        if self.auth_method in {"none", "bearer", "basic"}:
            return self.auth_method
        return "bearer" if self.secret_ref else "none"

    def _connection_egress_allowlist(self) -> list[str]:
        """Read HTTP egress allowlist from metadata for the canonical Connection."""
        if not isinstance(self.metadata, dict):
            return []
        allowlist = self.metadata.get("egress_allowlist") or []
        return [str(entry) for entry in allowlist]

    def _connection_status(self) -> str:
        """Translate registration health status to Connection status."""
        if self.health_status == "healthy":
            return "ok"
        if self.health_status == "unhealthy":
            return "fail"
        return "unknown"


class MCPHubServer(TimeStamped):
    """
    Registry of MCP servers discovered from GitHub.
    
    This is a global registry (not org/env-specific) that stores
    publicly available MCP servers found via GitHub API searches.
    """

    # GitHub repository identifiers
    github_id = models.BigIntegerField(
        unique=True,
        help_text="GitHub repository ID",
    )
    full_name = models.CharField(
        max_length=255,
        unique=True,
        help_text="GitHub repository full name (e.g., 'modelcontextprotocol/server-github')",
    )
    name = models.CharField(
        max_length=255,
        help_text="Repository name",
    )
    description = models.TextField(
        blank=True,
        help_text="Repository description",
    )
    html_url = models.URLField(
        max_length=500,
        help_text="GitHub repository URL",
    )

    # GitHub stats
    stargazers_count = models.IntegerField(
        default=0,
        help_text="Number of stars",
    )
    forks_count = models.IntegerField(
        default=0,
        help_text="Number of forks",
    )
    language = models.CharField(
        max_length=100,
        blank=True,
        help_text="Primary programming language",
    )
    topics = models.JSONField(
        default=list,
        help_text="GitHub topics/tags",
    )

    # Owner info
    owner_login = models.CharField(
        max_length=255,
        help_text="GitHub owner username",
    )
    owner_avatar_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Owner avatar URL",
    )

    # Metadata
    updated_at_github = models.DateTimeField(
        help_text="Last update time from GitHub",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time we synced data from GitHub",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this server is still active/available",
    )

    class Meta:
        db_table = "mcp_ext_hub_server"
        ordering = ["-stargazers_count", "-updated_at_github"]
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["language"]),
            models.Index(fields=["stargazers_count"]),
            models.Index(fields=["is_active", "-stargazers_count"]),
        ]

    def __str__(self) -> str:
        return self.full_name










