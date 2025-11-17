"""
Management command to migrate legacy rules_json policies to PolicyRule system.
"""
from django.core.management.base import BaseCommand

from apps.policies.models import Policy, PolicyRule


class Command(BaseCommand):
    help = "Migrate legacy rules_json policies to PolicyRule system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be migrated without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        
        # Find all policies with rules_json
        policies_with_rules_json = Policy.objects.exclude(
            rules_json={}
        ).exclude(
            rules_json__isnull=True
        )
        
        total = policies_with_rules_json.count()
        self.stdout.write(f"Found {total} policies with rules_json")
        
        migrated = 0
        skipped = 0
        
        for policy in policies_with_rules_json:
            # Check if policy already has PolicyRule objects
            if policy.rules.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping '{policy.name}' - already has PolicyRule objects"
                    )
                )
                skipped += 1
                continue
            
            rules_json = policy.rules_json or {}
            rules_created = 0
            
            # Migrate allow list
            allow_list = rules_json.get("allow", [])
            for pattern in allow_list:
                target = f"tool:{pattern}" if not pattern.startswith("tool:") else pattern
                
                if not dry_run:
                    PolicyRule.objects.create(
                        policy=policy,
                        action="tool.invoke",
                        target=target,
                        effect="allow",
                        conditions={},
                    )
                rules_created += 1
                self.stdout.write(f"  + Allow: {target}")
            
            # Migrate deny list
            deny_list = rules_json.get("deny", [])
            for pattern in deny_list:
                target = f"tool:{pattern}" if not pattern.startswith("tool:") else pattern
                
                if not dry_run:
                    PolicyRule.objects.create(
                        policy=policy,
                        action="tool.invoke",
                        target=target,
                        effect="deny",
                        conditions={},
                    )
                rules_created += 1
                self.stdout.write(f"  + Deny: {target}")
            
            # Migrate resource rules
            allow_resources = rules_json.get("allow_resources", [])
            for resource in allow_resources:
                target = f"resource:{resource}" if not resource.startswith("resource:") else resource
                
                if not dry_run:
                    PolicyRule.objects.create(
                        policy=policy,
                        action="resource.read",
                        target=target,
                        effect="allow",
                        conditions={},
                    )
                rules_created += 1
                self.stdout.write(f"  + Allow Resource: {target}")
            
            deny_resources = rules_json.get("deny_resources", [])
            for resource in deny_resources:
                target = f"resource:{resource}" if not resource.startswith("resource:") else resource
                
                if not dry_run:
                    PolicyRule.objects.create(
                        policy=policy,
                        action="resource.read",
                        target=target,
                        effect="deny",
                        conditions={},
                    )
                rules_created += 1
                self.stdout.write(f"  + Deny Resource: {target}")
            
            # Migrate prompt rules
            allow_prompts = rules_json.get("allow_prompts", [])
            for prompt in allow_prompts:
                target = f"prompt:{prompt}" if not prompt.startswith("prompt:") else prompt
                
                if not dry_run:
                    PolicyRule.objects.create(
                        policy=policy,
                        action="prompt.invoke",
                        target=target,
                        effect="allow",
                        conditions={},
                    )
                rules_created += 1
                self.stdout.write(f"  + Allow Prompt: {target}")
            
            deny_prompts = rules_json.get("deny_prompts", [])
            for prompt in deny_prompts:
                target = f"prompt:{prompt}" if not prompt.startswith("prompt:") else prompt
                
                if not dry_run:
                    PolicyRule.objects.create(
                        policy=policy,
                        action="prompt.invoke",
                        target=target,
                        effect="deny",
                        conditions={},
                    )
                rules_created += 1
                self.stdout.write(f"  + Deny Prompt: {target}")
            
            if rules_created > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{'Would migrate' if dry_run else 'Migrated'} policy '{policy.name}': {rules_created} rules"
                    )
                )
                migrated += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Policy '{policy.name}' has rules_json but no rules to migrate"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'Would migrate' if dry_run else 'Migrated'} {migrated} policies, skipped {skipped}"
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nThis was a dry run. Run without --dry-run to apply changes.")
            )

