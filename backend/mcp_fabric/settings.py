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

