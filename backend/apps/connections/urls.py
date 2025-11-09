"""
URLs for connections app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.connections.views import ConnectionViewSet

router = DefaultRouter()
router.register(r"connections", ConnectionViewSet, basename="connection")

urlpatterns = [
    path("", include(router.urls)),
]

