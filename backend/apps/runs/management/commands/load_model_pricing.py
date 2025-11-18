"""
Management command to load standard model pricing data.

Usage:
    python manage.py load_model_pricing
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.runs.models import ModelPricing


class Command(BaseCommand):
    """Load standard model pricing data."""
    
    help = "Load standard model pricing data for common LLM models"
    
    # Standard pricing as of Nov 2024 (update as needed)
    PRICING_DATA = [
        # OpenAI Models
        {
            "model_name": "gpt-4",
            "provider": "openai",
            "input_cost_per_1k": Decimal("0.030000"),
            "output_cost_per_1k": Decimal("0.060000"),
            "currency": "USD",
        },
        {
            "model_name": "gpt-4-turbo",
            "provider": "openai",
            "input_cost_per_1k": Decimal("0.010000"),
            "output_cost_per_1k": Decimal("0.030000"),
            "currency": "USD",
        },
        {
            "model_name": "gpt-4o",
            "provider": "openai",
            "input_cost_per_1k": Decimal("0.005000"),
            "output_cost_per_1k": Decimal("0.015000"),
            "currency": "USD",
        },
        {
            "model_name": "gpt-3.5-turbo",
            "provider": "openai",
            "input_cost_per_1k": Decimal("0.001500"),
            "output_cost_per_1k": Decimal("0.002000"),
            "currency": "USD",
        },
        # Anthropic Models
        {
            "model_name": "claude-3-opus",
            "provider": "anthropic",
            "input_cost_per_1k": Decimal("0.015000"),
            "output_cost_per_1k": Decimal("0.075000"),
            "currency": "USD",
        },
        {
            "model_name": "claude-3-sonnet",
            "provider": "anthropic",
            "input_cost_per_1k": Decimal("0.003000"),
            "output_cost_per_1k": Decimal("0.015000"),
            "currency": "USD",
        },
        {
            "model_name": "claude-3-haiku",
            "provider": "anthropic",
            "input_cost_per_1k": Decimal("0.000250"),
            "output_cost_per_1k": Decimal("0.001250"),
            "currency": "USD",
        },
        {
            "model_name": "claude-3-5-sonnet",
            "provider": "anthropic",
            "input_cost_per_1k": Decimal("0.003000"),
            "output_cost_per_1k": Decimal("0.015000"),
            "currency": "USD",
        },
        # Google Models
        {
            "model_name": "gemini-pro",
            "provider": "google",
            "input_cost_per_1k": Decimal("0.000500"),
            "output_cost_per_1k": Decimal("0.001500"),
            "currency": "USD",
        },
        {
            "model_name": "gemini-pro-vision",
            "provider": "google",
            "input_cost_per_1k": Decimal("0.000500"),
            "output_cost_per_1k": Decimal("0.001500"),
            "currency": "USD",
        },
        # Groq Models (much cheaper)
        {
            "model_name": "mixtral-8x7b-32768",
            "provider": "groq",
            "input_cost_per_1k": Decimal("0.000270"),
            "output_cost_per_1k": Decimal("0.000270"),
            "currency": "USD",
        },
        {
            "model_name": "llama3-70b-8192",
            "provider": "groq",
            "input_cost_per_1k": Decimal("0.000590"),
            "output_cost_per_1k": Decimal("0.000790"),
            "currency": "USD",
        },
        {
            "model_name": "llama3-8b-8192",
            "provider": "groq",
            "input_cost_per_1k": Decimal("0.000050"),
            "output_cost_per_1k": Decimal("0.000080"),
            "currency": "USD",
        },
    ]
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing pricing (deactivate old, add new)",
        )
    
    def handle(self, *args, **options):
        """Execute command."""
        update_mode = options.get("update", False)
        created_count = 0
        updated_count = 0
        
        for pricing_data in self.PRICING_DATA:
            model_name = pricing_data["model_name"]
            provider = pricing_data["provider"]
            
            # Check if pricing already exists
            existing = ModelPricing.objects.filter(
                model_name=model_name,
                is_active=True,
            ).first()
            
            if existing:
                if update_mode:
                    # Deactivate old pricing
                    existing.is_active = False
                    existing.save()
                    
                    # Create new pricing entry
                    ModelPricing.objects.create(**pricing_data, is_active=True)
                    updated_count += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Updated pricing for {provider}/{model_name}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⊘ Pricing for {provider}/{model_name} already exists (use --update to replace)"
                        )
                    )
            else:
                # Create new pricing
                ModelPricing.objects.create(**pricing_data, is_active=True)
                created_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created pricing for {provider}/{model_name}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Done: {created_count} created, {updated_count} updated"
            )
        )

