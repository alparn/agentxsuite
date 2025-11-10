"""
Management command to store secrets in the secret store.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from libs.secretstore import get_secretstore


class Command(BaseCommand):
    """Store a secret in the secret store."""

    help = "Store a secret in the secret store and return the reference"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "org_id",
            type=str,
            help="Organization UUID",
        )
        parser.add_argument(
            "env_id",
            type=str,
            help="Environment UUID",
        )
        parser.add_argument(
            "key",
            type=str,
            help="Secret key identifier (e.g., 'bearer_token')",
        )
        parser.add_argument(
            "value",
            type=str,
            help="Secret value to store",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        org_id = options["org_id"]
        env_id = options["env_id"]
        key = options["key"]
        value = options["value"]

        store = get_secretstore()
        scope = {"org": org_id, "env": env_id}
        ref = store.put_secret(scope, key, value)

        self.stdout.write(
            self.style.SUCCESS(f"Secret stored successfully!")
        )
        self.stdout.write(f"Secret Reference: {ref}")
        self.stdout.write(f"\nUse this reference in the Connection form:")
        self.stdout.write(f"  Secret Reference: {ref}")

