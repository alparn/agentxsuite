"""
FastAPI middleware for logging context propagation and JSON logging.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from libs.logging.context import clear_context_ids, set_context_ids

try:
    from opentelemetry import trace
    from opentelemetry.trace import format_trace_id

    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False

logger = logging.getLogger(__name__)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that sets context IDs for logging.

    Extracts trace_id, request_id, and other IDs from request
    and sets them in context variables for automatic log injection.
    Also adds trace_id and request_id to response headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Extract trace_id from OpenTelemetry if available
        trace_id = None
        if OTELEMETRY_AVAILABLE:
            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                trace_id = format_trace_id(span.get_span_context().trace_id)

        # Extract org_id and env_id from path parameters
        org_id = None
        env_id = None
        if "org_id" in request.path_params:
            org_id = str(request.path_params.get("org_id"))
        if "env_id" in request.path_params:
            env_id = str(request.path_params.get("env_id"))

        # Set context IDs
        set_context_ids(
            trace_id=trace_id,
            request_id=request_id,
            org_id=org_id,
            env_id=env_id,
        )

        # Store in request state for later use
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        try:
            response = await call_next(request)

            # Add trace_id and request_id to response headers
            if trace_id:
                response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Clear context IDs after request
            clear_context_ids()

