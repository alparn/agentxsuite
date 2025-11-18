"""
Serializers for ModelPricing.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.runs.models import ModelPricing


class ModelPricingSerializer(serializers.ModelSerializer):
    """Serializer for ModelPricing."""
    
    class Meta:
        model = ModelPricing
        fields = [
            "id",
            "model_name",
            "provider",
            "input_cost_per_1k",
            "output_cost_per_1k",
            "currency",
            "effective_from",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]
    
    def validate(self, data):
        """Validate that costs are non-negative."""
        if data.get("input_cost_per_1k") and data["input_cost_per_1k"] < 0:
            raise serializers.ValidationError(
                {"input_cost_per_1k": "Cost cannot be negative"}
            )
        if data.get("output_cost_per_1k") and data["output_cost_per_1k"] < 0:
            raise serializers.ValidationError(
                {"output_cost_per_1k": "Cost cannot be negative"}
            )
        return data

