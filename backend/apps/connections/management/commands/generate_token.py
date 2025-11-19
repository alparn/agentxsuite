"""
Management command to generate a token for a connection.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.agents.models import Agent
from apps.agents.services import generate_token_for_agent
from apps.connections.models import Connection
from apps.tenants.models import Environment, Organization
from libs.secretstore import get_secretstore


class Command(BaseCommand):
    """Generate a token for a connection and store it in SecretStore."""

    help = (
        "Generate a JWT token for a connection's agent and store it in SecretStore. "
        "Updates the connection with auth_method='bearer' and secret_ref."
    )

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "connection_id",
            type=str,
            help="Connection UUID",
        )
        parser.add_argument(
            "--ttl",
            type=int,
            default=30,
            help="Token TTL in minutes (default: 30)",
        )
        parser.add_argument(
            "--scopes",
            type=str,
            nargs="+",
            default=["mcp:tools", "mcp:manifest"],
            help="Token scopes (default: mcp:tools mcp:manifest)",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        connection_id = options["connection_id"]
        ttl_minutes = options["ttl"]
        scopes = options["scopes"]

        try:
            connection = Connection.objects.select_related(
                "organization", "environment"
            ).get(id=connection_id)
        except Connection.DoesNotExist:
            raise CommandError(f"Connection {connection_id} not found")

        self.stdout.write(
            f"Connection: {connection.name} ({connection.organization.name}/{connection.environment.name})"
        )

        # Find or create an agent for this connection
        agent = Agent.objects.filter(
            organization=connection.organization,
            environment=connection.environment,
            connection=connection,
        ).first()

        if not agent:
            # Try to find any agent for this org/env
            agent = Agent.objects.filter(
                organization=connection.organization,
                environment=connection.environment,
            ).first()

        if not agent:
            raise CommandError(
                f"No agent found for organization {connection.organization.name} "
                f"and environment {connection.environment.name}. "
                "Please create an agent first or use --create-agent flag."
            )

        if not agent.service_account:
            raise CommandError(
                f"Agent {agent.id} does not have a ServiceAccount. "
                "Please create a ServiceAccount for this agent first."
            )

        self.stdout.write(f"Using agent: {agent.name} (ID: {agent.id})")

        # Get system user (first superuser)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        system_user = User.objects.filter(is_superuser=True).first()
        if not system_user:
            raise CommandError("No superuser found. Please create a superuser first.")
        
        # Generate token
        try:
            token_string, issued_token = generate_token_for_agent(
                agent,
                user=system_user,
                name=f"Token for {connection.name}",
                purpose="api",
                ttl_minutes=ttl_minutes,
                scopes=scopes,
            )
            self.stdout.write(
                self.style.SUCCESS(f"Token generated successfully!")
            )
            self.stdout.write(f"Token JTI: {issued_token.jti}")
            self.stdout.write(f"Expires at: {issued_token.expires_at}")
            self.stdout.write(f"Scopes: {', '.join(scopes)}")
        except Exception as e:
            raise CommandError(f"Failed to generate token: {e}")

        # Store token in SecretStore
        try:
            secret_store = get_secretstore()
            scope = {
                "org": str(connection.organization.id),
                "env": str(connection.environment.id),
            }
            secret_ref = secret_store.put_secret(
                scope, "mcp_fabric_token", token_string
            )
            self.stdout.write(
                self.style.SUCCESS(f"Token stored in SecretStore!")
            )
            self.stdout.write(f"Secret Reference: {secret_ref}")
        except Exception as e:
            raise CommandError(f"Failed to store token: {e}")

        # Update connection
        try:
            connection.auth_method = "bearer"
            connection.secret_ref = secret_ref
            connection.save(update_fields=["auth_method", "secret_ref"])
            self.stdout.write(
                self.style.SUCCESS(f"Connection updated successfully!")
            )
            self.stdout.write(f"  auth_method: bearer")
            self.stdout.write(f"  secret_ref: {secret_ref}")
        except Exception as e:
            raise CommandError(f"Failed to update connection: {e}")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Token setup complete!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nYou can now test the connection:")
        self.stdout.write(
            f"  curl -X POST 'http://localhost:8000/api/v1/connections/{connection_id}/sync/' \\"
        )
        self.stdout.write(f"    -H 'Authorization: Token YOUR_API_TOKEN'")

