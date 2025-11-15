"""
Django middleware for logging context propagation.
"""
from __future__ import annotations

import uuid

from libs.logging.context import clear_context_ids, set_context_ids

try:
    from opentelemetry import trace
    from opentelemetry.trace import format_trace_id

    OTELEMETRY_AVAILABLE = True
except ImportError:
    OTELEMETRY_AVAILABLE = False


class LoggingContextMiddleware:
    """
    Middleware that sets context IDs for logging.

    Extracts trace_id, request_id, and other IDs from request
    and sets them in context variables for automatic log injection.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate or extract request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Extract trace_id from OpenTelemetry if available
        trace_id = None
        if OTELEMETRY_AVAILABLE:
            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                trace_id = format_trace_id(span.get_span_context().trace_id)

        # Extract org_id and env_id from URL if present
        org_id = None
        env_id = None
        if hasattr(request, "resolver_match") and request.resolver_match:
            org_id = request.resolver_match.kwargs.get("org_id")
            env_id = request.resolver_match.kwargs.get("env_id")

        # Set context IDs
        set_context_ids(
            trace_id=trace_id,
            request_id=request_id,
            org_id=str(org_id) if org_id else None,
            env_id=str(env_id) if env_id else None,
        )

        # Add request_id to request for response headers
        request._request_id = request_id
        request._trace_id = trace_id

        try:
            response = self.get_response(request)

            # Add trace_id and request_id to response headers
            if trace_id:
                response["X-Trace-ID"] = trace_id
            response["X-Request-ID"] = request_id

            return response
        finally:
            # Clear context IDs after request (important for async/threading)
            clear_context_ids()

