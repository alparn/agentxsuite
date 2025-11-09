"""
URLs for audit app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.audit.views import AuditEventViewSet

router = DefaultRouter()
router.register(r"audit", AuditEventViewSet, basename="audit")

urlpatterns = [
    path("", include(router.urls)),
]

