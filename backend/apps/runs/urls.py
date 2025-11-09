"""
URLs for runs app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.runs.views import RunViewSet

router = DefaultRouter()
router.register(r"runs", RunViewSet, basename="run")

urlpatterns = [
    path("", include(router.urls)),
]

