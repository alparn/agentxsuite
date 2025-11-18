"""
URLs for runs app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.runs.cost_views import CostReportViewSet
from apps.runs.pricing_views import ModelPricingViewSet
from apps.runs.views import RunViewSet

router = DefaultRouter()
router.register(r"runs", RunViewSet, basename="run")
router.register(r"costs", CostReportViewSet, basename="cost")
router.register(r"pricing", ModelPricingViewSet, basename="pricing")

urlpatterns = [
    path("", include(router.urls)),
]

