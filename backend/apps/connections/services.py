"""
Connection services for testing and syncing connections.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.connections.models import Connection
from apps.tools.models import Tool

logger = logging.getLogger(__name__)


def test_connection(conn: Connection) -> Connection:
    """
    Test a connection with comprehensive MCP validation.

    This performs a full MCP server verification including:
    - Health endpoint check
    - Tools endpoint validation
    - MCP format verification
    - Authentication check (if configured)

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
    Sync tools from a connection with strict MCP validation.

    Performs MCP server verification before syncing tools.
    No fallback tools are created - sync must succeed or fail.

    Args:
        conn: Connection instance to sync

    Returns:
        Tuple of (created_tools, updated_tools) lists

    Raises:
        ValidationError: If endpoint is not a valid MCP server or sync fails
    """
    # 1. Verify MCP server before syncing
    if not verify_mcp_server(conn):
        raise ValidationError(
            f"Endpoint {conn.endpoint} is not a valid MCP server. "
            "Health check or tools endpoint validation failed."
        )

    # 2. Fetch tools with strict validation
    tools_data = _fetch_tools_with_validation(conn)
    if not tools_data:
        raise ValidationError(
            f"Could not fetch tools from {conn.endpoint}. "
            "No valid tools endpoint found or response format invalid."
        )

    # 3. Parse and validate tools list
    tools_list = tools_data.get("tools", [])
    if not tools_list or not isinstance(tools_list, list):
        raise ValidationError(
            f"No valid tools found in response from {conn.endpoint}. "
            "Response must contain a 'tools' array."
        )

    created_tools = []
    updated_tools = []
    sync_timestamp = timezone.now()

    # 4. Create or update tools with connection reference
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

    logger.info(
        f"Sync completed for {conn.name}: "
        f"{len(created_tools)} created, {len(updated_tools)} updated"
    )

    return (created_tools, updated_tools)


def _fetch_mcp_manifest(conn: Connection) -> dict | None:
    """
    Fetch MCP manifest from server.

    Tries multiple common manifest endpoint variants:
    - /.well-known/mcp/manifest.json (RFC 5785 standard)
    - /manifest.json
    - /mcp/manifest.json
    - /mcp.json

    Args:
        conn: Connection instance

    Returns:
        Manifest dictionary if found, None otherwise
    """
    manifest_urls = [
        urljoin(conn.endpoint.rstrip("/") + "/", ".well-known/mcp/manifest.json"),
        urljoin(conn.endpoint.rstrip("/") + "/", "manifest.json"),
        urljoin(conn.endpoint.rstrip("/") + "/", "mcp/manifest.json"),
        urljoin(conn.endpoint.rstrip("/") + "/", "mcp.json"),
    ]

    for manifest_url in manifest_urls:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(manifest_url)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Validate manifest structure
                        if isinstance(data, dict):
                            logger.info(f"Found MCP manifest at {manifest_url}")
                            return data
                    except ValueError:
                        logger.debug(f"Invalid JSON from {manifest_url}")
                        continue
        except httpx.TimeoutException:
            logger.debug(f"Timeout checking manifest at {manifest_url}")
            continue
        except httpx.RequestError as e:
            logger.debug(f"Request error checking manifest at {manifest_url}: {e}")
            continue
        except Exception as e:
            logger.debug(f"Unexpected error checking manifest at {manifest_url}: {e}")
            continue

    return None


def _get_endpoints_from_manifest(manifest: dict, base_endpoint: str) -> dict[str, str]:
    """
    Extract endpoint URLs from manifest.

    Manifest may contain:
    - tools_endpoint: URL for tools list
    - health_endpoint: URL for health check
    - Other custom endpoints

    Args:
        manifest: Manifest dictionary
        base_endpoint: Base endpoint URL

    Returns:
        Dictionary with endpoint_type -> endpoint_url mappings
    """
    endpoints = {}

    # Common manifest field names
    if "tools_endpoint" in manifest:
        endpoints["tools"] = manifest["tools_endpoint"]
    if "health_endpoint" in manifest:
        endpoints["health"] = manifest["health_endpoint"]

    # Also check for nested endpoints object
    if "endpoints" in manifest and isinstance(manifest["endpoints"], dict):
        endpoints.update(manifest["endpoints"])

    # Resolve relative URLs to absolute
    for key, value in endpoints.items():
        if isinstance(value, str) and not value.startswith(("http://", "https://")):
            endpoints[key] = urljoin(base_endpoint.rstrip("/") + "/", value.lstrip("/"))

    return endpoints


def verify_mcp_server(conn: Connection) -> bool:
    """
    Verify that endpoint is a valid MCP server.

    Checks:
    1. Try to fetch manifest (optional but preferred)
    2. Health endpoint responds with 200 (from manifest or default)
    3. Tools endpoint exists and returns valid MCP format (from manifest or default)

    Args:
        conn: Connection instance to verify

    Returns:
        True if valid MCP server, False otherwise
    """
    # Normalize endpoint: remove trailing /mcp if present (MCP Fabric uses /.well-known/mcp prefix)
    base_endpoint = conn.endpoint.rstrip("/")
    if base_endpoint.endswith("/mcp"):
        base_endpoint = base_endpoint[:-4]  # Remove /mcp suffix
        logger.debug(f"Normalized endpoint from {conn.endpoint} to {base_endpoint}")
    
    # 1. Try to fetch manifest (optional - improves verification)
    # Temporarily use normalized endpoint for manifest fetch
    original_endpoint = conn.endpoint
    conn.endpoint = base_endpoint
    try:
        manifest = _fetch_mcp_manifest(conn)
        endpoints = {}
        if manifest:
            endpoints = _get_endpoints_from_manifest(manifest, base_endpoint)
            logger.info(f"Using endpoints from manifest: {list(endpoints.keys())}")
    finally:
        conn.endpoint = original_endpoint  # Restore original

    # 2. Health check (use manifest endpoint or default)
    health_urls = []
    if "health" in endpoints:
        health_urls.append(endpoints["health"])
    health_urls.append(urljoin(base_endpoint.rstrip("/") + "/", "health"))

    health_ok = False
    for health_url in health_urls:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(health_url)
                if response.status_code == 200:
                    health_ok = True
                    logger.debug(f"Health check successful: {health_url}")
                    break
        except Exception:
            continue

    if not health_ok:
        logger.warning(f"Health check failed for {conn.endpoint}")
        return False

    # 3. Tools endpoint validation (use manifest endpoint or defaults)
    tools_urls = []
    if "tools" in endpoints:
        tools_urls.append(endpoints["tools"])
    
    # Add standard MCP tool endpoint variants (use normalized base_endpoint)
    tools_urls.extend([
        urljoin(base_endpoint.rstrip("/") + "/", ".well-known/mcp/tools"),
        urljoin(base_endpoint.rstrip("/") + "/", "mcp/tools"),
        urljoin(base_endpoint.rstrip("/") + "/", "tools"),
    ])

    # Prepare headers from connection auth_method
    headers = {}
    if conn.auth_method == "bearer" and conn.secret_ref:
        try:
            from libs.secretstore import get_secretstore
            secret_store = get_secretstore()
            token = secret_store.get_secret(conn.secret_ref, check_permissions=False)
            headers["Authorization"] = f"Bearer {token}"
        except Exception as e:
            logger.warning(f"Could not retrieve auth token for connection: {e}")

    # Track if we got 401 responses (server exists but needs auth)
    got_auth_required = False

    for tools_url in tools_urls:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(tools_url, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # MCP Fabric returns a list directly, validate it
                        if isinstance(data, list):
                            # Validate tool structure
                            for tool in data:
                                if not isinstance(tool, dict) or "name" not in tool:
                                    logger.warning(
                                        f"Invalid tool structure in {tools_url}"
                                    )
                                    return False
                            logger.info(f"MCP Fabric server verified: {tools_url}")
                            return True
                        # Validate MCP format: must be dict with "tools" key
                        if isinstance(data, dict) and "tools" in data:
                            if isinstance(data["tools"], list):
                                # Validate tool structure
                                for tool in data["tools"]:
                                    if not isinstance(tool, dict) or "name" not in tool:
                                        logger.warning(
                                            f"Invalid tool structure in {tools_url}"
                                        )
                                        return False
                                logger.info(f"MCP server verified: {tools_url}")
                                return True
                    except ValueError:
                        logger.debug(f"Invalid JSON response from {tools_url}")
                        continue
                elif response.status_code == 401:
                    # 401 means server exists and responds, but needs authentication
                    got_auth_required = True
                    logger.debug(f"Authentication required for {tools_url}")
                    continue
                elif response.status_code == 404:
                    logger.debug(f"Endpoint not found: {tools_url}")
                    continue
        except httpx.TimeoutException:
            logger.debug(f"Timeout checking {tools_url}")
            continue
        except httpx.RequestError as e:
            logger.debug(f"Request error checking {tools_url}: {e}")
            continue
        except Exception as e:
            logger.debug(f"Unexpected error checking {tools_url}: {e}")
            continue

    # If health passed AND we got 401 responses, the server likely exists but needs auth
    # This is acceptable for MCP servers with authentication requirements
    if got_auth_required:
        logger.info(f"MCP server detected at {conn.endpoint} (authentication required)")
        return True

    logger.warning(f"No valid tools endpoint found for {conn.endpoint}")
    return False


def _fetch_tools_with_validation(conn: Connection) -> dict | None:
    """
    Fetch tools from MCP server with strict validation.

    Uses manifest endpoints if available, otherwise falls back to standard MCP endpoints.

    Args:
        conn: Connection instance

    Returns:
        Tools data dictionary if valid, None otherwise
    """
    # Normalize endpoint: remove trailing /mcp if present (MCP Fabric uses /.well-known/mcp prefix)
    base_endpoint = conn.endpoint.rstrip("/")
    if base_endpoint.endswith("/mcp"):
        base_endpoint = base_endpoint[:-4]  # Remove /mcp suffix
        logger.debug(f"Normalized endpoint from {conn.endpoint} to {base_endpoint}")
    
    # Try to get endpoints from manifest first
    original_endpoint = conn.endpoint
    conn.endpoint = base_endpoint
    try:
        manifest = _fetch_mcp_manifest(conn)
        tools_urls = []
        
        if manifest:
            endpoints = _get_endpoints_from_manifest(manifest, base_endpoint)
            if "tools" in endpoints:
                tools_urls.append(endpoints["tools"])
                logger.info(f"Using tools endpoint from manifest: {endpoints['tools']}")
    finally:
        conn.endpoint = original_endpoint  # Restore original
    
    # Add standard MCP tool endpoint variants (use normalized base_endpoint)
    tools_urls.extend([
        urljoin(base_endpoint.rstrip("/") + "/", ".well-known/mcp/tools"),
        urljoin(base_endpoint.rstrip("/") + "/", "mcp/tools"),
        urljoin(base_endpoint.rstrip("/") + "/", "tools"),
    ])

    # Prepare headers from connection auth_method
    headers = {}
    if conn.auth_method == "bearer" and conn.secret_ref:
        try:
            from libs.secretstore import get_secretstore
            secret_store = get_secretstore()
            token = secret_store.get_secret(conn.secret_ref, check_permissions=False)
            headers["Authorization"] = f"Bearer {token}"
        except Exception as e:
            logger.warning(f"Could not retrieve auth token for connection: {e}")

    for tools_url in tools_urls:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(tools_url, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # MCP Fabric returns a list directly, wrap it in dict format
                        if isinstance(data, list):
                            logger.info(f"Fetched tools list from {tools_url} (MCP Fabric format)")
                            return {"tools": data}
                        # Validate structure for standard MCP format
                        if (
                            isinstance(data, dict)
                            and "tools" in data
                            and isinstance(data["tools"], list)
                            and len(data["tools"]) > 0
                        ):
                            logger.info(f"Fetched tools from {tools_url}")
                            return data
                    except ValueError as e:
                        logger.debug(f"Invalid JSON from {tools_url}: {e}")
                        continue
                elif response.status_code == 401:
                    logger.warning(f"Authentication required for {tools_url}")
                    continue
                elif response.status_code == 404:
                    logger.debug(f"Endpoint not found: {tools_url}")
                    continue
        except httpx.TimeoutException:
            logger.debug(f"Timeout fetching from {tools_url}")
            continue
        except httpx.RequestError as e:
            logger.debug(f"Request error fetching from {tools_url}: {e}")
            continue
        except Exception as e:
            logger.debug(f"Unexpected error fetching from {tools_url}: {e}")
            continue

    return None

