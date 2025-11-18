"""
Service functions for system tools.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from django.utils import timezone

from apps.agents.models import Agent, AgentMode
from apps.connections.models import Connection
from apps.runs.models import Run
from apps.tools.models import Tool

logger = logging.getLogger(__name__)


def get_or_create_system_connection(organization, environment) -> Connection:
    """
    Get or create the system connection for an organization/environment.
    
    System connection is a special connection with endpoint="agentxsuite://system"
    that is used for all system tools.
    
    Args:
        organization: Organization instance
        environment: Environment instance
    
    Returns:
        Connection instance for system tools
    """
    connection, created = Connection.objects.get_or_create(
        organization=organization,
        environment=environment,
        name="AgentxSuite System",
        defaults={
            "endpoint": "agentxsuite://system",
            "auth_method": "none",
            "status": "ok",
        },
    )
    if created:
        logger.info(
            f"Created system connection for {organization.name}/{environment.name}",
            extra={
                "org_id": str(organization.id),
                "env_id": str(environment.id),
                "connection_id": str(connection.id),
            },
        )
    return connection


def run_system_tool_with_audit(
    *,
    tool_name: str,
    handler: Callable[..., dict[str, Any]],
    payload: dict[str, Any],
    organization_id: str,
    environment_id: str,
    token_agent_id: str | None = None,
    jti: str | None = None,
    client_ip: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute a system tool with audit logging (creates Run record).
    
    System tools now have Tool models linked to a special system connection
    (endpoint="agentxsuite://system").
    
    Args:
        tool_name: Name of the system tool (e.g., "agentxsuite_list_agents")
        handler: Handler function to execute
        payload: Tool input arguments
        organization_id: Organization ID
        environment_id: Environment ID
        token_agent_id: Agent ID from token (for audit)
        jti: JWT ID (for audit)
        client_ip: Client IP (for audit)
        request_id: Request ID (for audit)
    
    Returns:
        Handler result dictionary
    """
    from apps.tenants.models import Organization, Environment
    from libs.logging.context import set_context_ids
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    # Get agent from token_agent_id (required for audit)
    agent = None
    if token_agent_id:
        try:
            agent = Agent.objects.get(
                id=token_agent_id,
                organization=org,
                environment=env,
                enabled=True,
            )
        except Agent.DoesNotExist:
            logger.warning(
                f"Agent {token_agent_id} not found for system tool {tool_name}",
                extra={
                    "tool_name": tool_name,
                    "agent_id": token_agent_id,
                    "org_id": str(org.id),
                    "env_id": str(env.id),
                },
            )
            # Continue without agent (system tools can run without agent)
    
    # Create Run record for audit (even if no agent)
    started_at = timezone.now()
    run = None
    
    # Get or create system connection
    system_connection = get_or_create_system_connection(org, env)
    
    # Get or create system tool model
    tool, _ = Tool.objects.get_or_create(
        organization=org,
        environment=env,
        name=tool_name,
        version="1.0.0",
        defaults={
            "connection": system_connection,
            "schema_json": {},  # Will be populated from SYSTEM_TOOLS definition
            "enabled": True,
            "sync_status": "synced",
        },
    )
    
    if agent:
        # Create Run with agent and tool
        run = Run.objects.create(
            organization=org,
            environment=env,
            agent=agent,
            tool=tool,  # System tools now have Tool models
            status="running",
            started_at=started_at,
            input_json=payload,
        )
        
        # Set context IDs for logging
        set_context_ids(
            run_id=str(run.id),
            agent_id=str(agent.id),
            org_id=str(org.id),
            env_id=str(env.id),
        )
    
    try:
        # Execute handler
        result = handler(**payload)
        
        # Update Run if created
        if run:
            run.status = "succeeded" if result.get("status") == "success" else "failed"
            run.ended_at = timezone.now()
            run.output_json = result
            if result.get("status") != "success":
                run.error_text = result.get("error_description") or result.get("error", "Unknown error")
            run.save()
        
        return result
    except Exception as e:
        logger.error(
            f"Error executing system tool {tool_name}",
            extra={
                "tool_name": tool_name,
                "org_id": str(org.id),
                "env_id": str(env.id),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        
        # Update Run if created
        if run:
            run.status = "failed"
            run.ended_at = timezone.now()
            run.error_text = str(e)
            run.save()
        
        return {
            "status": "error",
            "error": "execution_failed",
            "error_description": str(e),
        }


def list_agents_handler(
    organization_id: str,
    environment_id: str,
    enabled_only: bool = True,
    mode: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handler for agentxsuite_list_agents."""
    from apps.tenants.models import Organization, Environment
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    queryset = Agent.objects.filter(organization=org, environment=env)
    if enabled_only:
        queryset = queryset.filter(enabled=True)
    if mode:
        queryset = queryset.filter(mode=mode)
    
    agents = queryset.order_by("-created_at")
    
    return {
        "status": "success",
        "agents": [
            {
                "id": str(a.id),
                "name": a.name,
                "slug": a.slug,
                "mode": a.mode,
                "enabled": a.enabled,
            }
            for a in agents
        ],
    }


def get_agent_handler(
    organization_id: str,
    environment_id: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handler for agentxsuite_get_agent."""
    from apps.tenants.models import Organization, Environment
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    if not agent_id and not agent_name:
        return {"status": "error", "error": "missing_parameter"}
    
    try:
        if agent_id:
            agent = Agent.objects.get(id=agent_id, organization=org, environment=env)
        else:
            agent = Agent.objects.get(name=agent_name, organization=org, environment=env)
        
        return {
            "status": "success",
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "slug": agent.slug,
                "mode": agent.mode,
                "enabled": agent.enabled,
            },
        }
    except Agent.DoesNotExist:
        return {"status": "error", "error": "agent_not_found"}


def create_agent_handler(
    organization_id: str,
    environment_id: str,
    name: str,
    mode: str = "caller",
    enabled: bool = True,
    capabilities: list[str] | None = None,
    tags: list[str] | None = None,
    connection_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handler for agentxsuite_create_agent."""
    from apps.tenants.models import Organization, Environment
    from apps.connections.models import Connection
    from apps.agents.models import InboundAuthMethod
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    if Agent.objects.filter(organization=org, environment=env, name=name).exists():
        return {"status": "error", "error": "agent_already_exists"}
    
    # Validate connection for RUNNER mode
    connection = None
    if mode == "runner":
        if not connection_id:
            return {"status": "error", "error": "connection_required", "error_description": "RUNNER mode requires a connection"}
        try:
            connection = Connection.objects.get(id=connection_id, organization=org, environment=env)
        except Connection.DoesNotExist:
            return {"status": "error", "error": "connection_not_found"}
    
    try:
        agent = Agent.objects.create(
            organization=org,
            environment=env,
            name=name,
            mode=AgentMode(mode),
            enabled=enabled,
            capabilities=capabilities or [],
            tags=tags or [],
            connection=connection,
            inbound_auth_method=InboundAuthMethod.NONE,
        )
        return {
            "status": "success",
            "agent_id": str(agent.id),
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "mode": agent.mode,
            },
        }
    except Exception as e:
        logger.error(f"Failed to create agent: {e}", exc_info=True)
        return {"status": "error", "error": "creation_failed", "error_description": str(e)}


def list_connections_handler(
    organization_id: str,
    environment_id: str,
    status: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handler for agentxsuite_list_connections."""
    from apps.tenants.models import Organization, Environment
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    queryset = Connection.objects.filter(organization=org, environment=env)
    if status:
        queryset = queryset.filter(status=status)
    
    connections = queryset.order_by("-created_at")
    
    return {
        "status": "success",
        "connections": [
            {
                "id": str(c.id),
                "name": c.name,
                "endpoint": c.endpoint,
                "status": c.status,
            }
            for c in connections
        ],
    }


def list_tools_handler(
    organization_id: str,
    environment_id: str,
    enabled_only: bool = True,
    connection_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handler for agentxsuite_list_tools."""
    from apps.tenants.models import Organization, Environment
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    queryset = Tool.objects.filter(organization=org, environment=env)
    if enabled_only:
        queryset = queryset.filter(enabled=True)
    if connection_id:
        queryset = queryset.filter(connection_id=connection_id)
    
    tools = queryset.order_by("-created_at")
    
    return {
        "status": "success",
        "tools": [
            {
                "id": str(t.id),
                "name": t.name,
                "version": t.version,
                "enabled": t.enabled,
            }
            for t in tools
        ],
    }


def list_runs_handler(
    organization_id: str,
    environment_id: str,
    limit: int = 10,
    status: str | None = None,
    agent_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Handler for agentxsuite_list_runs."""
    from apps.tenants.models import Organization, Environment
    
    try:
        org = Organization.objects.get(id=organization_id)
        env = Environment.objects.get(id=environment_id, organization=org)
    except (Organization.DoesNotExist, Environment.DoesNotExist) as e:
        return {"status": "error", "error": "not_found", "error_description": str(e)}
    
    queryset = Run.objects.filter(organization=org, environment=env)
    if status:
        queryset = queryset.filter(status=status)
    if agent_id:
        queryset = queryset.filter(agent_id=agent_id)
    
    runs = queryset.select_related("agent", "tool").order_by("-started_at")[:limit]
    
    return {
        "status": "success",
        "runs": [
            {
                "id": str(r.id),
                "status": r.status,
                "agent_name": r.agent.name,
                "tool_name": r.tool.name,
            }
            for r in runs
        ],
    }


# Mapping von Tool-Namen zu Handler-Funktionen
TOOL_HANDLERS = {
    "agentxsuite_list_agents": list_agents_handler,
    "agentxsuite_get_agent": get_agent_handler,
    "agentxsuite_create_agent": create_agent_handler,
    "agentxsuite_list_connections": list_connections_handler,
    "agentxsuite_list_tools": list_tools_handler,
    "agentxsuite_list_runs": list_runs_handler,
}

