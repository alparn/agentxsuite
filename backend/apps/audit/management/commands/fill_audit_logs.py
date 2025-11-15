"""
Management command to fill missing fields in existing audit logs.

Extracts information from event_data and updates subject, action, target, decision fields.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.agents.models import Agent
from apps.audit.models import AuditEvent
from apps.tools.models import Tool


class Command(BaseCommand):
    """Fill missing fields in existing audit logs."""

    help = "Fill missing subject, action, target, decision fields in existing audit logs"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of records to process",
        )

    def handle(self, *args, **options) -> None:
        """Execute the command."""
        dry_run = options["dry_run"]
        limit = options.get("limit")

        # Find audit events with missing fields
        query = Q(subject__isnull=True) | Q(action__isnull=True) | Q(target__isnull=True)
        events = AuditEvent.objects.filter(query).order_by("-created_at")

        if limit:
            events = events[:limit]

        total = events.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No audit events with missing fields found."))
            return

        self.stdout.write(f"Found {total} audit events with missing fields.")

        updated = 0
        skipped = 0
        errors = 0

        for event in events:
            try:
                updated_fields = self._update_event(event)
                if updated_fields:
                    if not dry_run:
                        event.save(update_fields=updated_fields)
                    updated += 1
                    self.stdout.write(
                        f"{'[DRY RUN] Would update' if dry_run else 'Updated'} "
                        f"event {event.id} ({event.event_type}): "
                        f"{', '.join(updated_fields)}"
                    )
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"Error updating event {event.id}: {e}")
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Summary:"))
        self.stdout.write(f"  Total: {total}")
        self.stdout.write(f"  {'Would update' if dry_run else 'Updated'}: {updated}")
        self.stdout.write(f"  Skipped: {skipped}")
        if errors > 0:
            self.stdout.write(self.style.ERROR(f"  Errors: {errors}"))

    def _update_event(self, event: AuditEvent) -> list[str]:
        """Update an audit event with missing fields."""
        updated_fields = []
        event_data = event.event_data or {}

        # Update subject (agent identity)
        if not event.subject:
            subject = self._get_subject(event, event_data)
            if subject:
                event.subject = subject
                updated_fields.append("subject")

        # Update action (map event_type to action)
        if not event.action:
            action = self._get_action(event.event_type)
            if action:
                event.action = action
                updated_fields.append("action")

        # Update target (tool identity)
        if not event.target:
            target = self._get_target(event, event_data)
            if target:
                event.target = target
                updated_fields.append("target")

        # Update decision (infer from event_type)
        if not event.decision:
            decision = self._get_decision(event.event_type)
            if decision:
                event.decision = decision
                updated_fields.append("decision")

        # Update rule_id (extract from event_data if available)
        if not event.rule_id and "rule_id" in event_data:
            try:
                event.rule_id = int(event_data["rule_id"])
                updated_fields.append("rule_id")
            except (ValueError, TypeError):
                pass

        return updated_fields

    def _get_subject(self, event: AuditEvent, event_data: dict) -> str | None:
        """Get subject from event_data or by loading related objects."""
        # Try to get from event_data first
        if "subject" in event_data:
            return event_data["subject"]

        # Try to load agent from event_data
        agent_id = event_data.get("agent_id")
        if agent_id:
            try:
                agent = Agent.objects.get(id=agent_id)
                org = agent.organization
                env = agent.environment
                return f"agent:{agent.name}@{org.name}/{env.name}"
            except Agent.DoesNotExist:
                pass

        return None

    def _get_action(self, event_type: str) -> str | None:
        """Map event_type to action."""
        if event_type.startswith("mcp."):
            if event_type == "mcp.tool.invoked":
                return "tool.invoke"
            return event_type.replace("mcp.", "").replace("_", ".")
        elif event_type == "run_started":
            return "tool.run"
        elif event_type == "run_succeeded":
            return "tool.run.success"
        elif event_type.startswith("run_failed"):
            return "tool.run.failed"
        elif event_type == "run_denied":
            return "tool.run.denied"
        else:
            return event_type.replace("_", ".")

    def _get_target(self, event: AuditEvent, event_data: dict) -> str | None:
        """Get target from event_data or by loading related objects."""
        # Try to get from event_data first
        if "target" in event_data:
            return event_data["target"]

        # Try to load tool from event_data
        tool_id = event_data.get("tool_id")
        if tool_id:
            try:
                tool = Tool.objects.get(id=tool_id)
                return f"tool:{tool.name}"
            except Tool.DoesNotExist:
                pass

        return None

    def _get_decision(self, event_type: str) -> str | None:
        """Infer decision from event_type."""
        if event_type == "run_denied":
            return "deny"
        elif event_type in ("run_started", "run_succeeded"):
            return "allow"
        elif event_type.startswith("run_failed"):
            # Failed runs were allowed but failed during execution
            return "allow"
        return None

