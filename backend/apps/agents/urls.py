"""
URLs for agents app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.agents.views import AgentViewSet

router = DefaultRouter()
router.register(r"agents", AgentViewSet, basename="agent")
# Token operations are handled via @action in AgentViewSet:
# - List tokens: GET /agents/{id}/tokens/ (via list_tokens action)
# - Generate token: POST /agents/{id}/tokens/ (via generate_token action)
# - Revoke/Delete: Will be added as actions in AgentViewSet

urlpatterns = [
    path("", include(router.urls)),
]

