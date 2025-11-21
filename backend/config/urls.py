"""
URL configuration for config project.
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.claude_agent import views as claude_views

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Well-known endpoints for service discovery
    path(".well-known/agent-manifest", claude_views.wellknown_agent_manifest, name="wellknown_agent_manifest"),
    
    # API endpoints
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.tenants.urls")),
    # Environments unter orgs (like agents, connections, etc.)
    path("api/v1/orgs/<uuid:org_id>/", include("apps.tenants.environments_urls")),
    path("api/v1/orgs/<uuid:org_id>/", include("apps.connections.urls")),
    path("api/v1/orgs/<uuid:org_id>/", include("apps.agents.urls")),
    path("api/v1/orgs/<uuid:org_id>/", include("apps.accounts.urls")),  # ServiceAccounts unter org
    path("api/v1/orgs/<uuid:org_id>/", include("apps.tools.urls")),
    path("api/v1/orgs/<uuid:org_id>/", include("apps.runs.urls")),
    path("api/v1/orgs/<uuid:org_id>/", include("apps.policies.urls")),
    path("api/v1/orgs/<uuid:org_id>/", include("apps.audit.urls")),
    path("api/v1/", include("apps.policies.urls")),  # For /policies/evaluate (no org_id required)
    path("api/v1/", include("apps.audit.urls")),  # For global audit list
    path("api/v1/orgs/<uuid:org_id>/", include("apps.mcp_ext.urls")),
    path("api/v1/mcp-hub/", include("apps.mcp_ext.urls")),  # Global MCP Hub (not org-specific)
    path("api/v1/", include("apps.connections.urls")),  # For /connections/:id/test and /sync
    path("api/v1/", include("apps.tools.urls")),  # For /tools/:id/run
    path("api/v1/", include("apps.canvas.urls")),  # For /orgs/:org_id/canvas/
    path("api/v1/claude-agent/", include("apps.claude_agent.urls")),  # Claude Agent SDK integration
]
