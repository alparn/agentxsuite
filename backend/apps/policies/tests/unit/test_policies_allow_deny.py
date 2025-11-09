"""
Unit tests for policy allow/deny logic.
"""
from __future__ import annotations

import pytest

from apps.policies.services import is_allowed


def test_deny_beats_all():
    """Test that deny list takes precedence."""
    allowed, reason = is_allowed({"deny": ["db.drop"]}, "db.drop")
    assert allowed is False
    assert "denied" in reason


def test_allow_when_not_in_deny():
    """Test that tools not in deny list are allowed."""
    allowed, reason = is_allowed({"deny": ["db.drop"]}, "db.select")
    assert allowed is True
    assert reason == "ok"


def test_empty_rules_allows_all():
    """Test that empty rules allow all tools."""
    allowed, reason = is_allowed({}, "any.tool")
    assert allowed is True
    assert reason == "ok"


def test_empty_deny_list_allows_all():
    """Test that empty deny list allows all tools."""
    allowed, reason = is_allowed({"deny": []}, "any.tool")
    assert allowed is True
    assert reason == "ok"


def test_multiple_deny_items():
    """Test that multiple deny items work correctly."""
    rules = {"deny": ["db.drop", "fs.delete", "system.shutdown"]}
    allowed1, _ = is_allowed(rules, "db.drop")
    allowed2, _ = is_allowed(rules, "fs.delete")
    allowed3, _ = is_allowed(rules, "system.shutdown")
    allowed4, _ = is_allowed(rules, "db.select")

    assert allowed1 is False
    assert allowed2 is False
    assert allowed3 is False
    assert allowed4 is True

