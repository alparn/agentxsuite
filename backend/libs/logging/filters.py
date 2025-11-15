"""
Logging filters for context injection and secret redaction.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from libs.logging.context import get_context_ids


class ContextFilter(logging.Filter):
    """
    Filter that injects context IDs into LogRecords.

    Reads context variables (trace_id, run_id, request_id, etc.)
    and adds them as attributes to the LogRecord.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Inject context IDs into log record.

        Args:
            record: LogRecord instance

        Returns:
            True (always passes, just adds attributes)
        """
        context_ids = get_context_ids()

        # Add context IDs as attributes to LogRecord
        record.trace_id = context_ids.get("trace_id")
        record.run_id = context_ids.get("run_id")
        record.request_id = context_ids.get("request_id")
        record.org_id = context_ids.get("org_id")
        record.env_id = context_ids.get("env_id")
        record.agent_id = context_ids.get("agent_id")
        record.tool_id = context_ids.get("tool_id")

        return True


class SecretRedactionFilter(logging.Filter):
    """
    Filter that redacts secrets from log messages.

    Redacts:
    - Bearer tokens (Authorization: Bearer ...)
    - Passwords (password=..., pwd=..., passwd=...)
    - API keys (api_key=..., apikey=..., key=...)
    - Secrets (secret=..., secret_key=...)
    - Tokens (token=..., access_token=..., refresh_token=...)
    - Credentials (credential=..., credentials=...)
    """

    # Patterns for secret redaction
    REDACTION_PATTERNS = [
        # Bearer tokens
        (r'(?i)(authorization\s*:\s*bearer\s+)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(bearer\s+)([^\s,;"]+)', r'\1[REDACTED]'),
        # Passwords
        (r'(?i)(password\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(pwd\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(passwd\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        # API keys
        (r'(?i)(api[_-]?key\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(apikey\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(key\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        # Secrets
        (r'(?i)(secret[_-]?key\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(secret\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        # Tokens
        (r'(?i)(access[_-]?token\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(refresh[_-]?token\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(token\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        # Credentials
        (r'(?i)(credential\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        (r'(?i)(credentials\s*[=:]\s*)([^\s,;"]+)', r'\1[REDACTED]'),
        # JWT tokens (standalone)
        (r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b', '[REDACTED_JWT]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Redact secrets from log message and extra fields.

        Args:
            record: LogRecord instance

        Returns:
            True (always passes, just redacts content)
        """
        # Redact message
        if record.getMessage():
            message = record.getMessage()
            for pattern, replacement in self.REDACTION_PATTERNS:
                message = re.sub(pattern, replacement, message)
            # Update record message (hacky but works)
            record.msg = message
            record.args = ()  # Clear args since we've formatted the message

        # Redact extra fields (in record.__dict__)
        for key, value in list(record.__dict__.items()):
            if isinstance(value, str):
                redacted_value = value
                for pattern, replacement in self.REDACTION_PATTERNS:
                    redacted_value = re.sub(pattern, replacement, redacted_value)
                if redacted_value != value:
                    setattr(record, key, redacted_value)
            elif isinstance(value, dict):
                # Recursively redact dict values
                redacted_dict = self._redact_dict(value)
                setattr(record, key, redacted_dict)

        return True

    def _redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively redact secrets from dictionary.

        Args:
            data: Dictionary to redact

        Returns:
            Redacted dictionary
        """
        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted_value = value
                for pattern, replacement in self.REDACTION_PATTERNS:
                    redacted_value = re.sub(pattern, replacement, redacted_value)
                redacted[key] = redacted_value
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted

