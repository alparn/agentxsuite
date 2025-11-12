"""
URLs for policies app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.policies.views import (
    PolicyBindingViewSet,
    PolicyRuleViewSet,
    PolicyViewSet,
)

router = DefaultRouter()
router.register(r"policies", PolicyViewSet, basename="policy")
router.register(r"policy-rules", PolicyRuleViewSet, basename="policy-rule")
router.register(r"policy-bindings", PolicyBindingViewSet, basename="policy-binding")

urlpatterns = [
    path("", include(router.urls)),
]
