"""
URLs for policies app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.policies.views import PolicyViewSet

router = DefaultRouter()
router.register(r"policies", PolicyViewSet, basename="policy")

urlpatterns = [
    path("", include(router.urls)),
]

