"""API views for Claude Agent SDK integration."""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .agent_registry import AgentxSuiteToolRegistry
from .oauth import OAuthManager
from .sdk_agent import AgentxSuiteClaudeAgent

logger = logging.getLogger(__name__)

oauth_manager = OAuthManager()


@api_view(["GET"])
@permission_classes([AllowAny])
def agent_manifest(request: Request) -> Response:
    """
    Complete agent manifest for Claude's hosted platform.
    
    This endpoint provides comprehensive metadata about the AgentxSuite agent
    for Claude's hosted agent platform, including authentication, capabilities,
    tools, and API endpoints.
    """
    base_url = request.build_absolute_uri('/')[:-1]
    registry = AgentxSuiteToolRegistry()
    
    manifest = {
        # Basic Information
        "schema_version": "1.0",
        "name": "AgentxSuite",
        "display_name": "AgentxSuite - Enterprise MCP Orchestration",
        "description": "Enterprise-grade MCP agent orchestration platform with policy enforcement, audit logging, and multi-agent support",
        "version": "0.1.0",
        "homepage": "https://agentxsuite.com",
        "documentation_url": "https://agentxsuite.com/docs",
        "support_email": "support@agentxsuite.com",
        
        # Provider Information
        "provider": {
            "name": "AgentxSuite",
            "url": "https://agentxsuite.com",
            "support_url": "https://agentxsuite.com/support"
        },
        
        # Authentication Configuration
        "authentication": {
            "type": "oauth2",
            "oauth2": {
                "authorization_url": f"{base_url}/api/v1/claude-agent/authorize",
                "token_url": f"{base_url}/api/v1/claude-agent/token",
                "scopes": {
                    "agent:execute": "Execute agents and tools",
                    "tools:read": "Read available tools",
                    "runs:read": "Read execution history",
                    "agent:read": "Read agent information"
                },
                "default_scopes": ["agent:execute", "tools:read"]
            }
        },
        
        # API Endpoints
        "api": {
            "base_url": f"{base_url}/api/v1/claude-agent",
            "version": "v1",
            "endpoints": {
                "manifest": "/manifest",
                "tools": "/tools",
                "execute": "/execute",
                "health": "/health",
                "openapi": "/openapi.json"
            }
        },
        
        # Capabilities
        "capabilities": {
            "tool_execution": True,
            "streaming": False,
            "multi_agent": True,
            "conversation_history": True,
            "context_preservation": True,
            "audit_logging": True,
            "policy_enforcement": True,
            "rate_limiting": True,
            "cost_tracking": True,
            "async_execution": True
        },
        
        # Available Tools with Full Schemas
        "tools": registry.get_tools(),
        
        # Rate Limits
        "rate_limits": {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "concurrent_requests": 10,
            "burst_allowance": 100
        },
        
        # Security
        "security": {
            "tls_required": True,
            "supported_auth_methods": ["oauth2", "api_key"],
            "token_expiration_seconds": 31536000,  # 1 year
            "signature_algorithm": "HMAC-SHA256"
        },
        
        # Metadata
        "metadata": {
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": timezone.now().isoformat(),
            "status": "active",
            "environment": "production" if not settings.DEBUG else "development"
        }
    }
    
    response = Response(manifest)
    
    # Add cache and security headers
    response["Cache-Control"] = "public, max-age=900"  # 15 minutes
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    
    # Log manifest access for monitoring
    logger.info(
        "Agent manifest accessed",
        extra={
            "user_agent": request.META.get("HTTP_USER_AGENT"),
            "ip": request.META.get("REMOTE_ADDR")
        }
    )
    
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def wellknown_agent_manifest(request: Request) -> Response:
    """
    Well-known endpoint for agent discovery.
    
    This follows the standard for service discovery and allows
    Claude's platform to automatically discover the agent.
    
    Accessible at: /.well-known/agent-manifest
    """
    base_url = request.build_absolute_uri('/')[:-1]
    
    return Response({
        "manifest_url": f"{base_url}/api/v1/claude-agent/manifest",
        "name": "AgentxSuite",
        "type": "agent_platform",
        "version": "1.0",
        "status": "active"
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def openapi_spec(request: Request) -> Response:
    """
    OpenAPI 3.0 specification for Claude Agent SDK endpoints.
    
    This helps Claude and developers understand the API structure
    and enables automatic client generation.
    """
    base_url = request.build_absolute_uri('/')[:-1]
    registry = AgentxSuiteToolRegistry()
    
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "AgentxSuite Claude Agent API",
            "version": "1.0.0",
            "description": "API for Claude hosted agents to interact with AgentxSuite platform",
            "contact": {
                "name": "AgentxSuite Support",
                "email": "support@agentxsuite.com",
                "url": "https://agentxsuite.com/support"
            },
            "license": {
                "name": "AGPL-3.0",
                "url": "https://github.com/alparn/agentxsuite/blob/main/LICENSE"
            }
        },
        "servers": [
            {
                "url": f"{base_url}/api/v1/claude-agent",
                "description": "Production" if not settings.DEBUG else "Development"
            }
        ],
        "paths": {
            "/manifest": {
                "get": {
                    "summary": "Get agent manifest",
                    "description": "Returns comprehensive agent metadata and capabilities",
                    "operationId": "getManifest",
                    "tags": ["Discovery"],
                    "responses": {
                        "200": {
                            "description": "Agent manifest",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Manifest"}
                                }
                            }
                        }
                    }
                }
            },
            "/tools": {
                "get": {
                    "summary": "List available tools",
                    "description": "Get all tools that Claude agents can use",
                    "operationId": "listTools",
                    "tags": ["Tools"],
                    "security": [{"oauth2": ["tools:read"]}],
                    "responses": {
                        "200": {
                            "description": "List of tools",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ToolsList"}
                                }
                            }
                        }
                    }
                }
            },
            "/execute": {
                "post": {
                    "summary": "Execute agent",
                    "description": "Execute a Claude agent with the provided message",
                    "operationId": "executeAgent",
                    "tags": ["Execution"],
                    "security": [{"oauth2": ["agent:execute"]}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ExecuteRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Execution result",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ExecuteResponse"}
                                }
                            }
                        },
                        "400": {"description": "Bad request"},
                        "401": {"description": "Unauthorized"},
                        "429": {"description": "Rate limit exceeded"}
                    }
                }
            },
            "/health": {
                "get": {
                    "summary": "Health check",
                    "description": "Check if the service is healthy",
                    "operationId": "healthCheck",
                    "tags": ["System"],
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/HealthResponse"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "securitySchemes": {
                "oauth2": {
                    "type": "oauth2",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": f"{base_url}/api/v1/claude-agent/authorize",
                            "tokenUrl": f"{base_url}/api/v1/claude-agent/token",
                            "scopes": {
                                "agent:execute": "Execute agents and tools",
                                "tools:read": "Read available tools",
                                "runs:read": "Read execution history",
                                "agent:read": "Read agent information"
                            }
                        }
                    }
                }
            },
            "schemas": {
                "Manifest": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "description": {"type": "string"},
                        "capabilities": {"type": "object"},
                        "tools": {"type": "array"}
                    }
                },
                "ToolsList": {
                    "type": "object",
                    "properties": {
                        "tools": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Tool"}
                        },
                        "count": {"type": "integer"}
                    }
                },
                "Tool": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "input_schema": {"type": "object"}
                    },
                    "required": ["name", "description", "input_schema"]
                },
                "ExecuteRequest": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "organization_id": {"type": "string", "format": "uuid"},
                        "environment_id": {"type": "string", "format": "uuid"},
                        "system_prompt": {"type": "string"}
                    },
                    "required": ["message", "organization_id", "environment_id"]
                },
                "ExecuteResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "response": {"type": "string"},
                        "usage": {"type": "object"},
                        "cost": {"type": "object"},
                        "tool_calls": {"type": "array"}
                    }
                },
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
                        "version": {"type": "string"},
                        "timestamp": {"type": "string", "format": "date-time"}
                    }
                }
            }
        },
        "tags": [
            {"name": "Discovery", "description": "Service discovery endpoints"},
            {"name": "Tools", "description": "Tool management"},
            {"name": "Execution", "description": "Agent execution"},
            {"name": "System", "description": "System status"}
        ]
    }
    
    return Response(spec)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_tools(request: Request) -> Response:
    """
    List all available tools with full schemas.
    
    Requires authentication with tools:read scope.
    """
    registry = AgentxSuiteToolRegistry()
    tools = registry.get_tools()
    
    return Response({
        "tools": tools,
        "count": len(tools),
        "timestamp": timezone.now().isoformat()
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def execute_agent(request: Request) -> Response:
    """
    Execute Claude agent with the provided message.
    
    Requires authentication with agent:execute scope.
    """
    try:
        # Extract parameters
        message = request.data.get("message")
        organization_id = request.data.get("organization_id")
        environment_id = request.data.get("environment_id")
        system_prompt = request.data.get("system_prompt")
        
        if not all([message, organization_id, environment_id]):
            return Response(
                {"error": "message, organization_id, and environment_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get auth token from request
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                {"error": "Invalid authorization header"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        token = auth_header.split(" ")[1]
        
        # Initialize agent
        agent = AgentxSuiteClaudeAgent(
            api_key=getattr(settings, "ANTHROPIC_API_KEY", ""),
            organization_id=organization_id,
            environment_id=environment_id,
            auth_token=token,
            model=request.data.get("model", "claude-sonnet-4-20250514"),
            mcp_servers=request.data.get("mcp_servers")
        )
        
        # Execute conversation
        import asyncio
        result = asyncio.run(agent.execute_conversation(
            messages=[{"role": "user", "content": message}],
            system_prompt=system_prompt
        ))
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def oauth_login(request: Request):
    """
    Custom login page for OAuth flow.
    
    GET: Displays login form
    POST: Processes login and redirects to authorization page
    """
    from django.shortcuts import render, redirect
    from django.contrib.auth import authenticate, login
    from urllib.parse import unquote
    
    next_url = request.GET.get("next", "/api/v1/claude-agent/authorize")
    
    if request.method == "GET":
        # User is already authenticated
        if request.user.is_authenticated:
            return redirect(next_url)
        
        # Display login form
        return render(request, "oauth_login.html", {
            "next_url": next_url,
            "login_url": request.path,
        })
    
    else:  # POST - Process login
        username = request.POST.get("username")
        password = request.POST.get("password")
        next_url = request.POST.get("next", "/api/v1/claude-agent/authorize")
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Login successful
            login(request, user)
            logger.info(f"OAuth login successful for user: {username}")
            
            # Redirect to the authorization page
            return redirect(next_url)
        else:
            # Login failed
            logger.warning(f"OAuth login failed for user: {username}")
            return render(request, "oauth_login.html", {
                "error": "Invalid username or password",
                "next_url": next_url,
                "login_url": request.path,
            })


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    """
    Health check endpoint.
    
    Returns service status and version information.
    """
    from django.db import connection
    
    # Check database connectivity
    db_healthy = True
    try:
        connection.ensure_connection()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_healthy = False
    
    # Check Anthropic API key
    anthropic_configured = bool(getattr(settings, "ANTHROPIC_API_KEY", None))
    
    # Determine overall status
    if db_healthy and anthropic_configured:
        status_str = "healthy"
        http_status = status.HTTP_200_OK
    elif db_healthy:
        status_str = "degraded"
        http_status = status.HTTP_200_OK
    else:
        status_str = "unhealthy"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response({
        "status": status_str,
        "version": "0.1.0",
        "timestamp": timezone.now().isoformat(),
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
            "anthropic_api": "configured" if anthropic_configured else "not_configured"
        }
    }, status=http_status)


# OAuth Endpoints

@api_view(["POST"])
@permission_classes([AllowAny])
def oauth_initiate(request: Request) -> Response:
    """
    Initiate OAuth flow by generating state and authorization URL.
    
    This endpoint should be called before redirecting to the authorization page.
    It generates a secure state token and stores it in the cache.
    """
    try:
        organization_id = request.data.get("organization_id")
        environment_id = request.data.get("environment_id")
        scopes = request.data.get("scopes", oauth_manager.DEFAULT_SCOPES)
        redirect_uri = request.data.get("redirect_uri")
        
        if not organization_id or not environment_id:
            return Response(
                {"error": "organization_id and environment_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate state and authorization URL
        base_url = request.build_absolute_uri('/')[:-1]
        result = oauth_manager.initiate_flow(
            organization_id=organization_id,
            environment_id=environment_id,
            base_url=base_url
        )
        
        # Add redirect_uri and scopes to the URL if provided
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        parsed_url = urlparse(result["authorization_url"])
        params = parse_qs(parsed_url.query)
        
        # Add/override redirect_uri if provided
        if redirect_uri:
            params["redirect_uri"] = [redirect_uri]
        
        # Add scopes if provided
        if scopes:
            scope_str = " ".join(scopes) if isinstance(scopes, list) else scopes
            params["scope"] = [scope_str]
        
        # Rebuild URL with updated params (no duplicates)
        new_query = urlencode(params, doseq=True)
        auth_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        
        return Response({
            "authorization_url": auth_url,
            "state": result["state"],
            "expires_at": (datetime.now() + timedelta(seconds=oauth_manager.STATE_TOKEN_TIMEOUT)).isoformat()
        })
    except Exception as e:
        logger.error(f"OAuth initiation failed: {e}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def oauth_authorize(request: Request):
    """
    OAuth 2.0 authorization endpoint.
    
    GET: Displays authorization page where users approve access.
    POST: Processes the authorization and redirects with code.
    """
    from django.shortcuts import render, redirect
    from django.urls import reverse
    from urllib.parse import urlencode, quote
    
    try:
        if request.method == "GET":
            # Extract parameters
            client_id = request.GET.get("client_id")
            redirect_uri = request.GET.get("redirect_uri")
            response_type = request.GET.get("response_type", "code")
            state = request.GET.get("state")
            scope = request.GET.get("scope", "")
            organization_id = request.GET.get("organization_id")
            environment_id = request.GET.get("environment_id")
            
            # Check if user is authenticated FIRST
            if not request.user.is_authenticated:
                # Store OAuth parameters in session before redirecting to login
                if all([client_id, state, organization_id, environment_id]):
                    request.session["oauth_params"] = {
                        "client_id": client_id,
                        "redirect_uri": redirect_uri,
                        "response_type": response_type,
                        "state": state,
                        "scope": scope,
                        "organization_id": organization_id,
                        "environment_id": environment_id,
                    }
                    request.session.modified = True  # Force session save
                
                # Check if request has valid token in Authorization header or cookies
                # This allows users who are already logged in via frontend to proceed
                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                if auth_header.startswith('Token '):
                    # User has token from frontend - try to authenticate
                    from rest_framework.authtoken.models import Token
                    token_key = auth_header.split(' ')[1]
                    try:
                        token = Token.objects.get(key=token_key)
                        # Manually set the user (DRF authentication)
                        request.user = token.user
                        # Continue with authorization (don't redirect to login)
                    except Token.DoesNotExist:
                        pass
                
                # Still not authenticated - redirect to login
                if not request.user.is_authenticated:
                    login_url = f"/api/v1/claude-agent/login?next={quote(request.get_full_path())}"
                    return redirect(login_url)
            
            # User is authenticated - check if parameters are missing (after login redirect)
            if not all([client_id, redirect_uri, state, organization_id, environment_id]):
                # Try to restore from session
                if "oauth_params" in request.session:
                    oauth_params = request.session.pop("oauth_params", {})
                    client_id = oauth_params.get("client_id")
                    redirect_uri = oauth_params.get("redirect_uri")
                    response_type = oauth_params.get("response_type", "code")
                    state = oauth_params.get("state")
                    scope = oauth_params.get("scope", "")
                    organization_id = oauth_params.get("organization_id")
                    environment_id = oauth_params.get("environment_id")
                    
                    # Verify we got all required params from session
                    if not all([client_id, redirect_uri, state, organization_id, environment_id]):
                        return render(request, "oauth_authorize.html", {
                            "error": "Session expired. Please start the authorization flow again from the frontend."
                        })
                else:
                    return render(request, "oauth_authorize.html", {
                        "error": "Missing required parameters. Please start the authorization flow again from the frontend."
                    })
            
            # Get organization and environment info
            from apps.tenants.models import Organization, Environment
            try:
                org = Organization.objects.get(id=organization_id)
                env = Environment.objects.get(id=environment_id, organization=org)
                
                # Check if user has access
                if not org.members.filter(id=request.user.id).exists():
                    return render(request, "oauth_authorize.html", {
                        "error": "You do not have access to this organization"
                    })
            except (Organization.DoesNotExist, Environment.DoesNotExist):
                return render(request, "oauth_authorize.html", {
                    "error": "Organization or Environment not found"
                })
            
            # Parse scopes
            scopes = scope.split() if scope else oauth_manager.DEFAULT_SCOPES
            scope_descriptions = [oauth_manager.VALID_SCOPES.get(s, s) for s in scopes]
            
            # Render authorization page
            return render(request, "oauth_authorize.html", {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": response_type,
                "state": state,
                "scope": scope,
                "organization_id": organization_id,
                "environment_id": environment_id,
                "organization_name": org.name,
                "environment_name": env.name,
                "scopes": scope_descriptions,
                "authorize_url": request.get_full_path(),
            })
        
        else:  # POST - User approved
            # Extract parameters from form
            client_id = request.POST.get("client_id")
            redirect_uri = request.POST.get("redirect_uri")
            state = request.POST.get("state")
            organization_id = request.POST.get("organization_id")
            environment_id = request.POST.get("environment_id")
            approve = request.POST.get("approve")
            
            if not approve:
                # User denied authorization
                error_params = urlencode({
                    "error": "access_denied",
                    "error_description": "User denied authorization",
                    "state": state
                })
                return redirect(f"{redirect_uri}?{error_params}")
            
            # Generate authorization code
            auth_code = oauth_manager.generate_authorization_code(
                user=request.user,
                organization_id=organization_id,
                environment_id=environment_id
            )
            
            # Redirect to callback with code
            callback_params = urlencode({
                "code": auth_code,
                "state": state
            })
            return redirect(f"{redirect_uri}?{callback_params}")
            
    except Exception as e:
        logger.error(f"OAuth authorization failed: {e}", exc_info=True)
        return render(request, "oauth_authorize.html", {
            "error": str(e)
        })


@api_view(["POST"])
@permission_classes([AllowAny])
def oauth_token(request: Request) -> Response:
    """
    OAuth 2.0 token endpoint.
    
    Exchanges authorization code for access token.
    """
    try:
        result = oauth_manager.token(request)
        return Response(result)
    except Exception as e:
        logger.error(f"OAuth token exchange failed: {e}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def oauth_revoke(request: Request) -> Response:
    """
    OAuth 2.0 token revocation endpoint.
    
    Revokes an access token.
    """
    try:
        result = oauth_manager.revoke(request)
        return Response(result)
    except Exception as e:
        logger.error(f"OAuth token revocation failed: {e}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )




