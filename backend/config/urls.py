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
    path("api/v1/orgs/<int:org_id>/", include("apps.connections.urls")),
    path("api/v1/orgs/<int:org_id>/", include("apps.agents.urls")),
    path("api/v1/orgs/<int:org_id>/", include("apps.tools.urls")),
    path("api/v1/orgs/<int:org_id>/", include("apps.runs.urls")),
    path("api/v1/", include("apps.connections.urls")),  # For /connections/:id/test and /sync
    path("api/v1/", include("apps.tools.urls")),  # For /tools/:id/run
]
