"""
URLs for agents app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.agents.views import AgentViewSet, IssuedTokenViewSet

router = DefaultRouter()
router.register(r"agents", AgentViewSet, basename="agent")
router.register(r"tokens", IssuedTokenViewSet, basename="token")

# Token API Endpoints:
# - POST   /tokens/              - Create new token
# - GET    /tokens/              - List tokens  
# - GET    /tokens/{id}/         - Get token details
# - DELETE /tokens/{id}/         - Hard delete token
# - POST   /tokens/{id}/revoke/  - Revoke token (soft delete)
# - GET    /tokens/purposes/     - Get purpose metadata
# - GET    /tokens/scopes/       - Get scope metadata

urlpatterns = [
    path("", include(router.urls)),
]

