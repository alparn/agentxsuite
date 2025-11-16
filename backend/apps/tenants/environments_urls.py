"""
URLs for environments (under orgs).
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tenants.views import EnvironmentViewSet

# Router for environments under orgs
router = DefaultRouter()
router.register(r"environments", EnvironmentViewSet, basename="environment")

urlpatterns = [
    path("", include(router.urls)),
]

