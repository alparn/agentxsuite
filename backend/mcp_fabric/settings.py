"""
Settings for MCP Fabric FastAPI service.
"""
from __future__ import annotations

import os
from pathlib import Path

from decouple import config

# Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# FastAPI settings
API_V1_PREFIX = "/mcp"
DEFAULT_TIMEOUT_SECONDS = 30

# CORS Configuration
MCP_FABRIC_CORS_ORIGINS = config(
    "MCP_FABRIC_CORS_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:8090,http://127.0.0.1:8090",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

# MCP Canonical URI (resource identifier)
MCP_CANONICAL_URI = config(
    "MCP_CANONICAL_URI",
    default=config("MCP_FABRIC_BASE_URL", default="http://localhost:8090").rstrip("/") + "/mcp",
)

# Authorization servers (comma-separated list of issuer URIs)
AUTHORIZATION_SERVERS = config(
    "AUTHORIZATION_SERVERS",
    default=config("OIDC_ISSUER", default=""),
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# Supported scopes for MCP Fabric
SCOPES_SUPPORTED = [
    "mcp:manifest",  # Access to manifest endpoint
    "mcp:tools",  # Access to tools listing
    "mcp:run",  # Access to tool execution
    "mcp:resources",  # Access to resources listing
    "mcp:resource:read",  # Access to read resource content
    "mcp:prompts",  # Access to prompts listing
    "mcp:prompt:invoke",  # Access to invoke prompts
]

# Token TTL settings (P0 security)
# Maximum token TTL in minutes (default: 30 minutes)
MCP_TOKEN_MAX_TTL_MINUTES = config(
    "MCP_TOKEN_MAX_TTL_MINUTES",
    default=30,
    cast=int,
)
# Maximum age of iat claim in minutes (default: 60 minutes)
MCP_TOKEN_MAX_IAT_AGE_MINUTES = config(
    "MCP_TOKEN_MAX_IAT_AGE_MINUTES",
    default=60,
    cast=int,
)

