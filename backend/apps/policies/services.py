"""
Policy services for access control checks.
"""
from __future__ import annotations

from typing import Tuple


def is_allowed(rules_json: dict, tool_name: str) -> Tuple[bool, str]:
    """
    Check if a tool is allowed by policy rules (stub implementation).

    Denies if tool_name is in rules_json["deny"] list.

    Args:
        rules_json: Policy rules dictionary
        tool_name: Name of the tool to check

    Returns:
        Tuple of (is_allowed: bool, reason: str)
    """
    deny = set(rules_json.get("deny", []))

    if tool_name in deny:
        return False, f"tool '{tool_name}' is denied"

    return True, "ok"

