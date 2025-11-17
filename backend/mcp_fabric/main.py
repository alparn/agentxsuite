"""
MCP Fabric - FastAPI application for MCP-compatible endpoints.
"""
from __future__ import annotations

import logging
import logging.config
import os
from contextlib import asynccontextmanager

import django
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from mcp_fabric.middleware import LoggingContextMiddleware
from mcp_fabric.routers import mcp, prm
from mcp_fabric.routes_prompts import router as prompts_router
from mcp_fabric.routes_resources import router as resources_router
from mcp_fabric.settings import API_V1_PREFIX, MCP_FABRIC_CORS_ORIGINS

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

# Configure logging - use Django's LOGGING config (JSON format)
# This ensures all logs (including Uvicorn/FastAPI) use JSON format
logging.config.dictConfig(django.conf.settings.LOGGING)  # noqa: F405
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("MCP Fabric service starting up...")
    yield
    # Shutdown
    logger.info("MCP Fabric service shutting down...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="MCP Fabric",
    description="MCP-compatible API for AgentxSuite",
    version="1.0.0",
    lifespan=lifespan,
)

# Logging context middleware - must be first to set context IDs
app.add_middleware(LoggingContextMiddleware)

# CORS middleware - configured exactly like Django corsheaders
# Allow requests from frontend and also direct browser requests (for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=MCP_FABRIC_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=[
        "accept",
        "accept-encoding",
        "authorization",
        "content-type",
        "dnt",
        "origin",
        "user-agent",
        "x-csrftoken",
        "x-requested-with",
        "x-request-id",  # For request ID propagation
    ],
    expose_headers=["X-Trace-ID", "X-Request-ID", "*"],
)


# OPTIONS handler for CORS preflight - must be before routers to avoid auth dependency
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """
    Handle CORS preflight OPTIONS requests.
    
    This is necessary because FastAPI routes with authentication dependencies
    will try to execute those dependencies before CORSMiddleware can respond
    to OPTIONS requests. This handler intercepts OPTIONS requests early.
    """
    origin = request.headers.get("origin")
    allowed_origins = MCP_FABRIC_CORS_ORIGINS
    
    # Check if origin is allowed
    # IMPORTANT: Cannot use "*" when allow_credentials=True
    # Must return the exact origin or None
    if origin and origin in allowed_origins:
        allow_origin = origin
    elif not origin:
        # No origin header (direct browser request) - allow for testing
        # Use the request's own origin if available, otherwise first allowed
        allow_origin = allowed_origins[0] if allowed_origins else None
    else:
        # Origin not in allowed list - use first allowed origin
        allow_origin = allowed_origins[0] if allowed_origins else None
    
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "authorization, content-type, accept, origin",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        },
    )


# Include routers
app.include_router(prm.router)  # PRM endpoint (no prefix)

# MCP routers with org/env scoping
# Tests expect: /mcp/{org_id}/{env_id}/.well-known/mcp/*
# Create parent router with org/env prefix
mcp_scoped_router = APIRouter(prefix="/mcp/{org_id}/{env_id}")
mcp_scoped_router.include_router(mcp.router)  # /.well-known/mcp/*
mcp_scoped_router.include_router(resources_router)  # /.well-known/mcp/resources
mcp_scoped_router.include_router(prompts_router)  # /.well-known/mcp/prompts
app.include_router(mcp_scoped_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

