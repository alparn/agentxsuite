"""
URLs for tools app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tools.views import ToolViewSet

router = DefaultRouter()
router.register(r"tools", ToolViewSet, basename="tool")

urlpatterns = [
    path("", include(router.urls)),
]

