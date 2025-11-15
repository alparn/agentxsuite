"""
JSON formatter for structured logging.

Outputs all logs as JSON for easy parsing and aggregation.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON with consistent fields:
    - timestamp, level, logger, message
    - trace_id, run_id, request_id, org_id, env_id, agent_id, tool_id (from context)
    - exception info (if present)
    - extra fields from LogRecord
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: LogRecord instance

        Returns:
            JSON string representation of the log record
        """
        # Base log data
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context IDs (set by ContextFilter)
        if hasattr(record, "trace_id") and record.trace_id:
            log_data["trace_id"] = record.trace_id
        if hasattr(record, "run_id") and record.run_id:
            log_data["run_id"] = record.run_id
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if hasattr(record, "org_id") and record.org_id:
            log_data["org_id"] = record.org_id
        if hasattr(record, "env_id") and record.env_id:
            log_data["env_id"] = record.env_id
        if hasattr(record, "agent_id") and record.agent_id:
            log_data["agent_id"] = record.agent_id
        if hasattr(record, "tool_id") and record.tool_id:
            log_data["tool_id"] = record.tool_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }

        # Add extra fields from LogRecord (but exclude internal fields)
        excluded_fields = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
            "trace_id",
            "run_id",
            "request_id",
            "org_id",
            "env_id",
            "agent_id",
            "tool_id",
        }

        for key, value in record.__dict__.items():
            if key not in excluded_fields and not key.startswith("_"):
                # Only include serializable values
                try:
                    json.dumps(value)  # Test if serializable
                    log_data[key] = value
                except (TypeError, ValueError):
                    # Skip non-serializable values
                    log_data[key] = str(value)

        return json.dumps(log_data, ensure_ascii=False)

