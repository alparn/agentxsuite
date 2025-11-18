"""
ModelPricing API views.

Provides CRUD operations for model pricing configuration.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.runs.cost_serializers import ModelPricingSerializer
from apps.runs.models import ModelPricing

logger = logging.getLogger(__name__)


class ModelPricingViewSet(ModelViewSet):
    """
    ViewSet for ModelPricing management.
    
    Allows admins to configure and update model pricing.
    """
    
    queryset = ModelPricing.objects.all()
    serializer_class = ModelPricingSerializer
    
    def get_queryset(self):
        """Filter by active status and ordering."""
        queryset = super().get_queryset()
        
        # Filter by active status if requested
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            is_active_bool = is_active.lower() in ["true", "1", "yes"]
            queryset = queryset.filter(is_active=is_active_bool)
        
        # Filter by provider if requested
        provider = self.request.query_params.get("provider")
        if provider:
            queryset = queryset.filter(provider=provider)
        
        # Filter by model name if requested
        model_name = self.request.query_params.get("model_name")
        if model_name:
            queryset = queryset.filter(model_name__icontains=model_name)
        
        return queryset.order_by("-effective_from")

