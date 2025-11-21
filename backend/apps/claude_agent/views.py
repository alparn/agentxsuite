"""API views for Claude Agent SDK integration."""

import logging

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
            organization_id=organization_id,
            environment_id=environment_id,
            auth_token=token,
            model=request.data.get("model", "claude-sonnet-4-20250514")
        )
        
        # Execute conversation
        import asyncio
        result = asyncio.run(agent.execute_conversation(
            messages=[{"role": "user", "content": message}],
            system_prompt=system_prompt,
            track_costs=True
        ))
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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

@api_view(["GET"])
@permission_classes([AllowAny])
def oauth_authorize(request: Request) -> Response:
    """
    OAuth 2.0 authorization endpoint.
    
    Initiates the OAuth flow for Claude hosted agents.
    """
    try:
        result = oauth_manager.authorize(request)
        return Response(result)
    except Exception as e:
        logger.error(f"OAuth authorization failed: {e}", exc_info=True)
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


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


@api_view(["GET"])
@permission_classes([AllowAny])
def authorize(request: Request) -> Response:
    """
    OAuth authorization endpoint.

    Initiates the OAuth flow for Claude agents to authenticate
    with AgentxSuite.
    """
    # Extract parameters
    client_id = request.query_params.get("client_id")
    redirect_uri = request.query_params.get("redirect_uri")
    response_type = request.query_params.get("response_type")
    state = request.query_params.get("state")
    scope = request.query_params.get("scope", "")

    # Validate parameters
    if not all([client_id, redirect_uri, response_type, state]):
        return Response(
            {"error": "invalid_request", "error_description": "Missing required parameters"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if response_type != "code":
        return Response(
            {"error": "unsupported_response_type"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # In production, this would redirect to a consent screen
    # For now, return authorization URL for manual flow
    return Response(
        {
            "message": "Authorization required",
            "next_step": "User must authenticate and grant access",
            "authorization_url": f"/auth/claude-agent/consent?state={state}",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_access(request: Request) -> Response:
    """
    Grant access after user authentication.

    This endpoint is called after the user authenticates and
    consents to granting access to the Claude agent.
    """
    state = request.data.get("state")
    organization_id = request.data.get("organization_id")
    environment_id = request.data.get("environment_id")

    # Validate state
    state_data = oauth_manager.validate_state(state)
    if not state_data:
        return Response(
            {"error": "invalid_state"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Generate authorization code
    code = oauth_manager.generate_authorization_code(
        user=request.user,
        organization_id=organization_id or state_data["organization_id"],
        environment_id=environment_id or state_data["environment_id"],
    )

    return Response(
        {
            "authorization_code": code,
            "redirect_uri": oauth_manager.redirect_uri,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def token_exchange(request: Request) -> Response:
    """
    OAuth token exchange endpoint.

    Exchanges authorization code for access token.
    """
    grant_type = request.data.get("grant_type")
    code = request.data.get("code")
    client_id = request.data.get("client_id")
    client_secret = request.data.get("client_secret")

    # Validate grant type
    if grant_type != "authorization_code":
        return Response(
            {"error": "unsupported_grant_type"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate required parameters
    if not all([code, client_id]):
        return Response(
            {"error": "invalid_request", "error_description": "Missing required parameters"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Exchange code for token
    token_data = oauth_manager.exchange_code_for_token(code, client_secret)

    if not token_data:
        return Response(
            {"error": "invalid_grant"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(token_data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def execute_agent(request: Request) -> Response:
    """
    Execute Claude agent with provided message.

    This endpoint allows direct agent execution for testing
    and development purposes.
    """
    message = request.data.get("message")
    organization_id = request.data.get("organization_id")
    environment_id = request.data.get("environment_id")
    system_prompt = request.data.get("system_prompt")

    if not all([message, organization_id, environment_id]):
        return Response(
            {"error": "Missing required parameters: message, organization_id, environment_id"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get API key from settings
    api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        return Response(
            {"error": "Anthropic API key not configured"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Get or create auth token for user
    from rest_framework.authtoken.models import Token

    token, _ = Token.objects.get_or_create(user=request.user)

    # Initialize and execute agent
    try:
        agent = AgentxSuiteClaudeAgent(
            api_key=api_key,
            organization_id=organization_id,
            environment_id=environment_id,
            auth_token=token.key,
        )

        # Execute message (async call in sync view - should be refactored for production)
        import asyncio

        result = asyncio.run(agent.execute_single_message(message, system_prompt))

        return Response(result)

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return Response(
            {"error": f"Agent execution failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_tools(request: Request) -> Response:
    """
    List available tools for Claude agents.

    Returns the tool registry that defines what tools
    Claude agents can use.
    """
    from .agent_registry import AgentxSuiteToolRegistry

    registry = AgentxSuiteToolRegistry()
    tools = registry.get_tools()

    return Response({"tools": tools, "count": len(tools)})

