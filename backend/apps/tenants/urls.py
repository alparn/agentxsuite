"""
URLs for tenants app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.tenants.views import EnvironmentViewSet, OrganizationViewSet

router = DefaultRouter()
router.register(r"orgs", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("", include(router.urls)),
]

