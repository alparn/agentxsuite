"""
Settings for MCP Fabric FastAPI service.
"""
from __future__ import annotations

import os
from pathlib import Path

# Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# FastAPI settings
API_V1_PREFIX = "/mcp"
DEFAULT_TIMEOUT_SECONDS = 30

