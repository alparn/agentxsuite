"""
Management command to create dummy data for all models.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.agents.models import Agent
from apps.audit.models import AuditEvent
from apps.connections.models import Connection
from apps.policies.models import Policy
from apps.runs.models import Run
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


class Command(BaseCommand):
    """Create dummy data for all models."""

    help = "Create dummy data for all models and assign organization to admin user"

    def handle(self, *args, **options) -> None:
        """Execute the command."""
        self.stdout.write(self.style.SUCCESS("Creating dummy data..."))

        # Get or create admin user
        admin_user, created = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "first_name": "Admin",
                "last_name": "User",
                "is_superuser": True,
                "is_staff": True,
            },
        )
        if created:
            admin_user.set_password("admin")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin user: {admin_user.email}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Found existing admin user: {admin_user.email}"))

        # Create Organizations
        orgs = []
        org_names = ["Acme Corp", "TechStart Inc", "Global Solutions"]
        for name in org_names:
            org, created = Organization.objects.get_or_create(name=name)
            orgs.append(org)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created organization: {org.name}"))

        # Create membership for admin user with first organization
        from apps.tenants.models import OrganizationMembership
        
        admin_org = orgs[0]
        membership, created = OrganizationMembership.objects.get_or_create(
            user=admin_user,
            organization=admin_org,
            defaults={
                "role": "owner",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created membership: {admin_user.email} -> {admin_org.name} (owner)")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Admin user already member of: {admin_org.name}")
            )

        # Create Environments for each organization
        environments = []
        env_configs = [
            ("Development", "dev"),
            ("Staging", "stage"),
            ("Production", "prod"),
        ]
        for org in orgs:
            for env_name, env_type in env_configs:
                env, created = Environment.objects.get_or_create(
                    organization=org,
                    name=env_name,
                    defaults={"type": env_type},
                )
                environments.append(env)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created environment: {org.name}/{env.name}")
                    )

        # Create Connections for each environment
        connections = []
        connection_names = ["MCP Server Alpha", "MCP Server Beta", "MCP Server Gamma"]
        auth_methods = ["none", "bearer", "basic"]
        for env in environments:
            for idx, conn_name in enumerate(connection_names[:2]):  # 2 connections per env
                conn, created = Connection.objects.get_or_create(
                    organization=env.organization,
                    environment=env,
                    name=conn_name,
                    defaults={
                        "endpoint": f"https://mcp-{env.organization.name.lower().replace(' ', '-')}-{env.name.lower()}.example.com",
                        "auth_method": auth_methods[idx % len(auth_methods)],
                        "status": "ok" if idx == 0 else "unknown",
                        "last_seen_at": timezone.now() if idx == 0 else None,
                    },
                )
                connections.append(conn)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created connection: {conn.organization.name}/{conn.environment.name}/{conn.name}")
                    )

        # Create Agents for each connection
        agents = []
        agent_names = ["Data Processor", "Task Runner"]
        for conn in connections:
            for idx, agent_name in enumerate(agent_names):
                # Make agent name unique by including connection name
                unique_agent_name = f"{agent_name} ({conn.name})"
                agent, created = Agent.objects.get_or_create(
                    organization=conn.organization,
                    environment=conn.environment,
                    name=unique_agent_name,
                    defaults={
                        "connection": conn,
                        "version": "1.0.0",
                        "enabled": True,
                    },
                )
                agents.append(agent)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created agent: {agent.organization.name}/{agent.environment.name}/{agent.name}")
                    )

        # Create Tools for each connection
        tools = []
        tool_configs = [
            {
                "name": "database_query",
                "version": "1.0.0",
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "database": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "file_operations",
                "version": "1.0.0",
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["read", "write", "delete"]},
                        "path": {"type": "string"},
                    },
                    "required": ["action", "path"],
                },
            },
            {
                "name": "api_call",
                "version": "1.0.0",
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "endpoint": {"type": "string"},
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                        "payload": {"type": "object"},
                    },
                    "required": ["endpoint", "method"],
                },
            },
            {
                "name": "data_transform",
                "version": "1.0.0",
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "array"},
                        "transformation": {"type": "string"},
                    },
                    "required": ["data", "transformation"],
                },
            },
        ]
        for conn in connections:
            for tool_config in tool_configs:
                tool, created = Tool.objects.get_or_create(
                    organization=conn.organization,
                    environment=conn.environment,
                    connection=conn,
                    name=tool_config["name"],
                    version=tool_config["version"],
                    defaults={
                        "schema_json": tool_config["schema_json"],
                        "enabled": True,
                        "sync_status": "synced",
                        "synced_at": timezone.now(),
                    },
                )
                tools.append(tool)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created tool: {tool.organization.name}/{tool.environment.name}/{tool.name}")
                    )

        # Create Policies for each organization
        policies = []
        policy_configs = [
            {
                "name": "Default Allow Policy",
                "rules_json": {"allow": ["database_query", "file_operations", "api_call", "data_transform"]},
                "environment": None,  # Organization-wide
            },
            {
                "name": "Production Restrictions",
                "rules_json": {"deny": ["file_operations"], "allow": ["database_query", "api_call"]},
                "environment": "Production",
            },
        ]
        for org in orgs:
            for policy_config in policy_configs:
                env = None
                if policy_config["environment"]:
                    env = Environment.objects.filter(
                        organization=org, name=policy_config["environment"]
                    ).first()
                policy, created = Policy.objects.get_or_create(
                    organization=org,
                    name=policy_config["name"],
                    defaults={
                        "environment": env,
                        "rules_json": policy_config["rules_json"],
                        "enabled": True,
                    },
                )
                policies.append(policy)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created policy: {policy.organization.name}/{policy.name}")
                    )

        # Create Runs for some agent/tool combinations
        run_statuses = ["succeeded", "succeeded", "failed", "running"]
        for idx, agent in enumerate(agents[:10]):  # Create runs for first 10 agents
            # Find tools in same environment
            env_tools = [t for t in tools if t.environment == agent.environment]
            if env_tools:
                tool = env_tools[idx % len(env_tools)]
                status = run_statuses[idx % len(run_statuses)]
                started = timezone.now()
                ended = timezone.now() if status in ["succeeded", "failed"] else None

                run, created = Run.objects.get_or_create(
                    organization=agent.organization,
                    environment=agent.environment,
                    agent=agent,
                    tool=tool,
                    defaults={
                        "status": status,
                        "started_at": started,
                        "ended_at": ended,
                        "input_json": {"test": "data", "value": idx},
                        "output_json": {"ok": True, "result": "success"} if status == "succeeded" else None,
                        "error_text": "Test error" if status == "failed" else "",
                    },
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created run: {run.id} - {run.tool.name} ({run.status})")
                    )

        # Create Audit Events
        audit_configs = [
            ("run_started", {"test": "data"}),
            ("run_succeeded", {"result": "ok"}),
            ("run_failed", {"error": "test"}),
            ("policy_check", {"tool": "database_query"}),
        ]
        for org in orgs[:2]:  # Create audit events for first 2 orgs
            for event_type, event_data in audit_configs:
                AuditEvent.objects.create(
                    organization=org,
                    event_type=event_type,
                    event_data=event_data,
                )
        self.stdout.write(self.style.SUCCESS(f"Created {len(audit_configs) * 2} audit events"))

        # Summary
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("Dummy data creation completed!"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary:\n"
                f"- Organizations: {Organization.objects.count()}\n"
                f"- Environments: {Environment.objects.count()}\n"
                f"- Connections: {Connection.objects.count()}\n"
                f"- Agents: {Agent.objects.count()}\n"
                f"- Tools: {Tool.objects.count()}\n"
                f"- Policies: {Policy.objects.count()}\n"
                f"- Runs: {Run.objects.count()}\n"
                f"- Audit Events: {AuditEvent.objects.count()}\n"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nAdmin user: {admin_user.email}\n"
                f"Admin organization: {admin_org.name}\n"
            )
        )

