"""
Connection services for testing and syncing connections.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.connections import mcp_client
from apps.connections.models import Connection
from apps.tools.models import Tool

logger = logging.getLogger(__name__)


class EndpointType:
    """Enum-like class for connection endpoint types."""
    
    SYSTEM = "system"  # agentxsuite://system
    OWN_MCP_FABRIC = "own_mcp_fabric"  # http://localhost:8090
    EXTERNAL_MCP = "external_mcp"  # Any other HTTP endpoint


def _detect_endpoint_type(conn: Connection) -> str:
    """
    Detect the type of connection endpoint.
    
    Args:
        conn: Connection instance
    
    Returns:
        EndpointType constant (SYSTEM, OWN_MCP_FABRIC, or EXTERNAL_MCP)
    """
    endpoint = (conn.endpoint or "").rstrip("/")
    
    # Special case: agentxsuite://system
    if endpoint == "agentxsuite://system":
        return EndpointType.SYSTEM
    
    # Check if it's our own MCP Fabric service
    mcp_fabric_endpoints = _get_mcp_fabric_endpoints()
    if any(endpoint.startswith(e) for e in mcp_fabric_endpoints):
        return EndpointType.OWN_MCP_FABRIC
    
    # Default: external MCP server
    return EndpointType.EXTERNAL_MCP


def test_connection(conn: Connection) -> Connection:
    """
    Test a connection with MCP tools/list validation.

    Args:
        conn: Connection instance to test

    Returns:
        Updated Connection instance
    """
    try:
        # Use comprehensive MCP verification instead of simple health check
        is_valid = verify_mcp_server(conn)
        
        if is_valid:
            conn.status = "ok"
            logger.info(f"Connection {conn.name} MCP validation successful")
        else:
            conn.status = "fail"
            logger.warning(f"Connection {conn.name} MCP validation failed")
                
    except Exception as e:
        conn.status = "fail"
        logger.error(f"Connection {conn.name} test unexpected error: {e}")

    conn.last_seen_at = timezone.now()
    conn.save(update_fields=["status", "last_seen_at"])
    return conn


def sync_connection(conn: Connection) -> tuple[list[Tool], list[Tool]]:
    """
    Sync tools from a connection using MCP tools/list.

    No fallback tools are created - sync must succeed or fail.

    Args:
        conn: Connection instance to sync

    Returns:
        Tuple of (created_tools, updated_tools) lists

    Raises:
        ValidationError: If MCP tools/list fails or returns no usable tools.
    """
    tools_data = _fetch_tools_with_validation(conn)
    if not tools_data:
        raise ValidationError(
            f"Could not fetch tools from connection {conn.name}. "
            "MCP tools/list failed or returned an invalid response."
        )

    tools_list = tools_data.get("tools", [])
    if not tools_list or not isinstance(tools_list, list):
        raise ValidationError(
            f"No valid tools found for connection {conn.name}. "
            "MCP tools/list must return at least one tool."
        )

    created_tools = []
    updated_tools = []
    sync_timestamp = timezone.now()

    for tool_def in tools_list:
        if not isinstance(tool_def, dict):
            logger.warning(f"Skipping invalid tool definition: {tool_def}")
            continue

        tool_name = tool_def.get("name")
        if not tool_name or not isinstance(tool_name, str):
            logger.warning(f"Skipping tool without valid name: {tool_def}")
            continue

        # Get schema according to MCP protocol standard
        # MCP standard: inputSchema (CamelCase) - JSON Schema format
        # Also support common alternatives for compatibility
        schema = (
            tool_def.get("inputSchema")  # MCP protocol standard (CamelCase)
            or tool_def.get("input_schema")  # Alternative format (snake_case) - for compatibility
            or tool_def.get("schema")  # Generic fallback
            or {}
        )
        if not isinstance(schema, dict):
            logger.warning(f"Tool '{tool_name}' has invalid schema type ({type(schema)}), using empty dict")
            schema = {}
        
        # Ensure schema has at least type: object structure
        if not schema.get("type"):
            schema["type"] = "object"
        if "properties" not in schema:
            schema["properties"] = {}

        # Use version in lookup to match unique_together constraint
        version = "1.0.0"
        tool, created = Tool.objects.get_or_create(
            organization=conn.organization,
            environment=conn.environment,
            name=tool_name,
            version=version,
            defaults={
                "connection": conn,  # MANDATORY: Link tool to connection
                "schema_json": schema,
                "enabled": True,
                "sync_status": "synced",
                "synced_at": sync_timestamp,
            },
        )

        # Update existing tool (even if connection changed)
        if not created:
            tool.connection = conn  # Update connection if changed
            tool.schema_json = schema
            tool.sync_status = "synced"
            tool.synced_at = sync_timestamp
            tool.save(update_fields=["connection", "schema_json", "sync_status", "synced_at"])
            updated_tools.append(tool)
            logger.info(f"Updated tool: {tool_name}")
        else:
            created_tools.append(tool)
            logger.info(f"Created tool: {tool_name}")

    # Update connection status and last_seen_at after successful sync
    conn.status = "ok"
    conn.last_seen_at = timezone.now()
    conn.save(update_fields=["status", "last_seen_at"])

    curated_count = 0
    if getattr(settings, "TOOL_CURATION_ENABLED", False) and getattr(
        settings,
        "TOOL_CURATION_AUTO_SYNC",
        False,
    ):
        from apps.tools.curation_service import CurationService
        from apps.tools.curators.registry import CuratorsRegistry

        raw_tools = list(
            Tool.objects.filter(
                organization=conn.organization,
                environment=conn.environment,
                connection=conn,
                enabled=True,
            )
        )
        curator = CuratorsRegistry.get_curator(conn, raw_tools)
        curated_tools = CurationService.generate_curated_tools(
            connection=conn,
            raw_tools=raw_tools,
            curator=curator,
        )
        curated_count = len(curated_tools)

    logger.info(
        f"Sync completed for {conn.name}: "
        f"{len(created_tools)} created, {len(updated_tools)} updated, "
        f"{curated_count} curated"
    )

    return (created_tools, updated_tools)


def _verify_system_connection(conn: Connection) -> bool:
    """
    Verify system connection (agentxsuite://system).
    
    Args:
        conn: Connection instance
    
    Returns:
        True if valid, False otherwise
    """
    if not conn.organization or not conn.environment:
        logger.warning("System connection missing organization or environment")
        return False
    
    try:
        from mcp_fabric.registry import get_tools_list_for_org_env
        
        tools_list = get_tools_list_for_org_env(
            org=conn.organization,
            env=conn.environment,
        )
        
        # Filter for system tools only (agentxsuite_*)
        system_tools = [t for t in tools_list if t.get("name", "").startswith("agentxsuite_")]
        
        if system_tools and len(system_tools) > 0:
            logger.info(f"System connection verified: found {len(system_tools)} system tools")
            return True
        else:
            logger.warning("System connection has no system tools registered")
            return False
    except Exception as e:
        logger.warning(f"Error validating system connection: {e}")
        return False


def _verify_own_mcp_fabric(conn: Connection) -> bool:
    """
    Verify own MCP Fabric service by checking database directly.
    
    Args:
        conn: Connection instance
    
    Returns:
        True if valid, False otherwise
    """
    if not conn.organization or not conn.environment:
        logger.warning("MCP Fabric connection missing organization or environment")
        return False
    
    try:
        from mcp_fabric.registry import get_tools_list_for_org_env
        
        tools_list = get_tools_list_for_org_env(
            org=conn.organization,
            env=conn.environment,
        )
        
        if tools_list and len(tools_list) > 0:
            logger.info(f"MCP Fabric server verified: found {len(tools_list)} tools in database")
            return True
        else:
            logger.warning("MCP Fabric server has no tools registered")
            return False
    except Exception as e:
        logger.warning(f"Error validating own MCP Fabric service: {e}")
        return False


def verify_mcp_server(conn: Connection) -> bool:
    """
    Verify that endpoint is a valid MCP server.

    Uses strategy pattern based on connection type:
    - SYSTEM: Validate via database (system tools)
    - OWN_MCP_FABRIC: Validate via database (all tools)
    - EXTERNAL_MCP: Validate via real MCP tools/list through mcp_client

    Args:
        conn: Connection instance to verify

    Returns:
        True if valid MCP server, False otherwise
    """
    endpoint_type = _detect_endpoint_type(conn)
    
    if endpoint_type == EndpointType.SYSTEM:
        return _verify_system_connection(conn)
    elif endpoint_type == EndpointType.OWN_MCP_FABRIC:
        return _verify_own_mcp_fabric(conn)

    try:
        tools = mcp_client.list_tools(conn)
    except mcp_client.MCPClientError as exc:
        logger.warning(f"MCP verification failed for connection {conn.name}: {exc}")
        return False

    if not tools:
        logger.warning(f"MCP verification found no tools for connection {conn.name}")
        return False

    logger.info(f"MCP server verified for connection {conn.name}: found {len(tools)} tools")
    return True


def _get_mcp_fabric_endpoints() -> list[str]:
    """
    Get list of MCP Fabric endpoints for own service detection.
    
    Returns both localhost and 127.0.0.1 variants of the configured MCP Fabric URL.
    """
    try:
        from mcp_fabric.deps import MCP_FABRIC_BASE_URL
        
        endpoints = [MCP_FABRIC_BASE_URL.rstrip("/")]
        
        # Also add 127.0.0.1 variant if URL contains localhost
        if "localhost" in MCP_FABRIC_BASE_URL:
            endpoints.append(MCP_FABRIC_BASE_URL.replace("localhost", "127.0.0.1").rstrip("/"))
        
        return endpoints
    except ImportError:
        # Fallback if mcp_fabric is not available
        logger.warning("Could not import MCP_FABRIC_BASE_URL, using defaults")
        return ["http://localhost:8090", "http://127.0.0.1:8090"]


def _fetch_tools_from_database(conn: Connection, system_tools_only: bool = False) -> dict | None:
    """
    Fetch tools directly from database (for system or own MCP Fabric connections).
    
    Args:
        conn: Connection instance
        system_tools_only: If True, filter for system tools (agentxsuite_*) only
    
    Returns:
        Tools data dictionary if valid, None otherwise
    """
    if not conn.organization or not conn.environment:
        logger.warning("Connection missing organization or environment")
        return None
    
    try:
        from mcp_fabric.registry import get_tools_list_for_org_env
        
        tools_list = get_tools_list_for_org_env(
            org=conn.organization,
            env=conn.environment,
        )
        
        if system_tools_only:
            # Filter for system tools only (agentxsuite_*)
            tools_list = [t for t in tools_list if t.get("name", "").startswith("agentxsuite_")]
            logger.info(f"Fetched {len(tools_list)} system tools from database")
        else:
            logger.info(f"Fetched {len(tools_list)} tools from database")
        
        return {"tools": tools_list}
    except Exception as e:
        logger.warning(f"Error fetching tools from database: {e}")
        return None


def _fetch_tools_with_validation(conn: Connection) -> dict | None:
    """
    Fetch tools from MCP server with strict validation.

    Uses strategy pattern based on connection type:
    - SYSTEM: Fetch system tools from database
    - OWN_MCP_FABRIC: Fetch all tools from database
    - EXTERNAL_MCP: Fetch via real MCP tools/list through mcp_client

    Args:
        conn: Connection instance

    Returns:
        Tools data dictionary if valid, None otherwise
    """
    endpoint_type = _detect_endpoint_type(conn)
    
    # System or own MCP Fabric: fetch from database
    if endpoint_type == EndpointType.SYSTEM:
        return _fetch_tools_from_database(conn, system_tools_only=True)
    elif endpoint_type == EndpointType.OWN_MCP_FABRIC:
        return _fetch_tools_from_database(conn, system_tools_only=False)

    try:
        tools = mcp_client.list_tools(conn)
    except mcp_client.MCPClientError as exc:
        logger.warning(f"Could not fetch MCP tools for connection {conn.name}: {exc}")
        return None

    return {"tools": tools}

