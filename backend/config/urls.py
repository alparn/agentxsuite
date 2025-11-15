"""
URL configuration for config project.
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.tenants.urls")),
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
    path("api/v1/", include("apps.connections.urls")),  # For /connections/:id/test and /sync
    path("api/v1/", include("apps.tools.urls")),  # For /tools/:id/run
    path("api/v1/", include("apps.canvas.urls")),  # For /orgs/:org_id/canvas/
]
