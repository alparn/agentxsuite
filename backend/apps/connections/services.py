"""
Connection services for testing and syncing connections.
"""
from __future__ import annotations

from django.utils import timezone

from apps.connections.models import Connection
from apps.tools.models import Tool


def test_connection(conn: Connection) -> Connection:
    """
    Test a connection (stub implementation).

    Sets status deterministically based on endpoint.

    Args:
        conn: Connection instance to test

    Returns:
        Updated Connection instance
    """
    # Stub: set status based on endpoint pattern
    if "fail" in conn.endpoint.lower():
        conn.status = "fail"
    else:
        conn.status = "ok"

    conn.last_seen_at = timezone.now()
    conn.save(update_fields=["status", "last_seen_at"])
    return conn


def sync_connection(conn: Connection) -> list[Tool]:
    """
    Sync tools from a connection (stub implementation).

    Creates 1-2 dummy tools for the connection's org/env.

    Args:
        conn: Connection instance to sync

    Returns:
        List of created Tool instances
    """
    tools = []

    # Create dummy tool 1
    tool1, created1 = Tool.objects.get_or_create(
        organization=conn.organization,
        environment=conn.environment,
        name=f"{conn.name}_tool_1",
        defaults={
            "version": "1.0.0",
            "schema_json": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                },
            },
            "enabled": True,
        },
    )
    if created1:
        tools.append(tool1)

    # Create dummy tool 2
    tool2, created2 = Tool.objects.get_or_create(
        organization=conn.organization,
        environment=conn.environment,
        name=f"{conn.name}_tool_2",
        defaults={
            "version": "1.0.0",
            "schema_json": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
            },
            "enabled": True,
        },
    )
    if created2:
        tools.append(tool2)

    return tools

