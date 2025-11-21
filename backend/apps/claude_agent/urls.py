"""URL configuration for Claude Agent SDK integration."""

from django.urls import path

from . import views

app_name = "claude_agent"

urlpatterns = [
    # Discovery endpoints
    path("manifest", views.agent_manifest, name="manifest"),
    path("openapi.json", views.openapi_spec, name="openapi"),
    
    # OAuth flow
    path("authorize", views.oauth_authorize, name="authorize"),
    path("token", views.oauth_token, name="token"),
    path("revoke", views.oauth_revoke, name="revoke"),
    
    # Tools
    path("tools", views.list_tools, name="tools"),
    
    # Agent execution
    path("execute", views.execute_agent, name="execute"),
    
    # System
    path("health", views.health_check, name="health"),
]

