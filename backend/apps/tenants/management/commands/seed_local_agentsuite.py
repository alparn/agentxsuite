"""
Management command to seed local test data for AgentxSuite runner/caller tests.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.agents.models import Agent, AgentMode
from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool


class Command(BaseCommand):
    """Seed local data for AgentxSuite runner/caller tests."""

    help = "Seed local data for AgentxSuite runner/caller tests"

    def handle(self, *args, **options) -> None:
        """Execute the command."""
        # Create organization
        org, created = Organization.objects.get_or_create(name="Acme")
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created organization: {org.name}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Found existing organization: {org.name}"))

        # Create environment
        env, created = Environment.objects.get_or_create(
            organization=org,
            name="prod",
            defaults={"type": "prod"},
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created environment: {org.name}/{env.name}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Found existing environment: {org.name}/{env.name}")
            )

        # Verbindung zum Mock-MCP
        conn, created = Connection.objects.get_or_create(
            organization=org,
            environment=env,
            name="mock-mcp",
            defaults={
                "endpoint": "http://127.0.0.1:8091/.well-known/mcp/",
                "auth_method": "bearer",
                "status": "ok",
                "last_seen_at": timezone.now(),
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created connection: {org.name}/{env.name}/{conn.name}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found existing connection: {org.name}/{env.name}/{conn.name}"
                )
            )

        # Tool, das vom Mock-MCP „gesynct" wäre
        tool, created = Tool.objects.get_or_create(
            organization=org,
            environment=env,
            name="create_customer_note",
            defaults={
                "version": "1.0.0",
                "enabled": True,
                "connection": conn,
                "sync_status": "synced",
                "synced_at": timezone.now(),
                "schema_json": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["customer_id", "note"],
                },
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created tool: {org.name}/{env.name}/{tool.name}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found existing tool: {org.name}/{env.name}/{tool.name}"
                )
            )

        # Runner-Agent (outbound, braucht connection)
        runner, created = Agent.objects.get_or_create(
            organization=org,
            environment=env,
            name="CRM-Runner",
            defaults={
                "enabled": True,
                "version": "1.0.0",
                "mode": AgentMode.RUNNER,
                "connection": conn,
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created runner agent: {org.name}/{env.name}/{runner.name}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found existing runner agent: {org.name}/{env.name}/{runner.name}"
                )
            )

        # Caller-Agent (inbound, keine connection)
        caller, created = Agent.objects.get_or_create(
            organization=org,
            environment=env,
            name="ChatGPT-Caller",
            defaults={
                "enabled": True,
                "version": "1.0.0",
                "mode": AgentMode.CALLER,
                "inbound_auth_method": "bearer",
                "inbound_secret_ref": "secret_dummy",
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created caller agent: {org.name}/{env.name}/{caller.name}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found existing caller agent: {org.name}/{env.name}/{caller.name}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\nSeed complete:\n"
                f"  - Organization: {org.name}\n"
                f"  - Environment: {env.name}\n"
                f"  - Connection: {conn.name} -> {conn.endpoint}\n"
                f"  - Tool: {tool.name}\n"
                f"  - Runner Agent: {runner.name}\n"
                f"  - Caller Agent: {caller.name}\n"
            )
        )

