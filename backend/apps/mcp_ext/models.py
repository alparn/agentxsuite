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

        # Validate server type specific fields
        if self.server_type == self.ServerType.STDIO:
            if not self.command:
                raise ValidationError({"command": "Command is required for stdio servers"})
        elif self.server_type in [self.ServerType.HTTP, self.ServerType.WEBSOCKET]:
            if not self.endpoint:
                raise ValidationError({"endpoint": "Endpoint is required for HTTP/WebSocket servers"})

        # Validate environment belongs to organization
        if self.environment and self.organization:
            if self.environment.organization_id != self.organization_id:
                raise ValidationError(
                    {"environment": "Environment must belong to the selected organization"}
                )










