"""
URL configuration for mcp_ext app.
"""
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.mcp_ext.views import PromptViewSet, ResourceViewSet

router = DefaultRouter()
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"prompts", PromptViewSet, basename="prompt")

urlpatterns = router.urls

