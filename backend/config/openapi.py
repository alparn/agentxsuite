"""OpenAPI schema endpoints for the AgentxSuite control plane."""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def openapi_schema(request):  # noqa: ARG001
    """Return the public OpenAPI schema for API clients and agent tooling."""
    return Response(
        {
            "openapi": "3.0.3",
            "info": {
                "title": "AgentxSuite API",
                "version": "1.0.0",
                "description": "OpenAPI schema for the AgentxSuite control plane.",
            },
            "paths": {
                "/api/v1/orgs/{org_id}/connections/": {
                    "get": {
                        "operationId": "listConnections",
                        "summary": "List connections",
                        "parameters": [{"$ref": "#/components/parameters/OrgId"}],
                        "responses": {
                            "200": {
                                "description": "Connection list",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Connection"},
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "post": {
                        "operationId": "createConnection",
                        "summary": "Create connection",
                        "parameters": [{"$ref": "#/components/parameters/OrgId"}],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ConnectionWrite"}
                                }
                            },
                        },
                        "responses": {
                            "201": {
                                "description": "Created connection",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Connection"}
                                    }
                                },
                            }
                        },
                    },
                },
                "/api/v1/connections/{id}/test/": {
                    "post": {
                        "operationId": "testConnection",
                        "summary": "Validate an MCP connection",
                        "parameters": [{"$ref": "#/components/parameters/ConnectionId"}],
                        "responses": {
                            "200": {
                                "description": "Connection test result",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ConnectionTestResponse"
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
                "/api/v1/connections/{id}/sync/": {
                    "post": {
                        "operationId": "syncConnection",
                        "summary": "Sync tools from an MCP connection",
                        "parameters": [{"$ref": "#/components/parameters/ConnectionId"}],
                        "responses": {
                            "200": {
                                "description": "Connection sync result",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ConnectionSyncResponse"
                                        }
                                    }
                                },
                            }
                        },
                    }
                },
            },
            "components": {
                "parameters": {
                    "OrgId": {
                        "name": "org_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                    "ConnectionId": {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    },
                },
                "schemas": {
                    "Connection": {
                        "type": "object",
                        "required": ["id", "name", "transport", "auth_method", "status"],
                        "properties": {
                            "id": {"type": "string", "format": "uuid", "readOnly": True},
                            "organization": {"type": "object", "readOnly": True},
                            "environment": {"type": "object", "readOnly": True},
                            "name": {"type": "string"},
                            "transport": {"$ref": "#/components/schemas/ConnectionTransport"},
                            "endpoint": {"type": "string", "format": "uri", "nullable": True},
                            "egress_allowlist": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "command": {"type": "string"},
                            "args": {"type": "array", "items": {"type": "string"}},
                            "auth_method": {"$ref": "#/components/schemas/ConnectionAuthMethod"},
                            "status": {"type": "string", "enum": ["unknown", "ok", "fail"]},
                            "last_seen_at": {
                                "type": "string",
                                "format": "date-time",
                                "nullable": True,
                            },
                            "created_at": {"type": "string", "format": "date-time"},
                            "updated_at": {"type": "string", "format": "date-time"},
                        },
                    },
                    "ConnectionWrite": {
                        "allOf": [{"$ref": "#/components/schemas/Connection"}],
                        "properties": {
                            "environment_id": {"type": "string", "format": "uuid"},
                            "env_ref": {"type": "string", "writeOnly": True},
                            "secret_ref": {"type": "string", "writeOnly": True},
                        },
                    },
                    "ConnectionTransport": {
                        "type": "string",
                        "enum": ["stdio", "streamable_http", "sse", "legacy_http"],
                    },
                    "ConnectionAuthMethod": {
                        "type": "string",
                        "enum": ["none", "bearer", "basic"],
                    },
                    "ConnectionTestResponse": {
                        "type": "object",
                        "required": ["status"],
                        "properties": {
                            "status": {"type": "string", "enum": ["ok", "fail", "unknown"]},
                            "last_seen_at": {
                                "type": "string",
                                "format": "date-time",
                                "nullable": True,
                            },
                        },
                    },
                    "ConnectionSyncResponse": {
                        "type": "object",
                        "required": ["tools_created", "tools_updated", "tool_ids"],
                        "properties": {
                            "tools_created": {"type": "integer", "minimum": 0},
                            "tools_updated": {"type": "integer", "minimum": 0},
                            "tool_ids": {
                                "type": "array",
                                "items": {"type": "string", "format": "uuid"},
                            },
                            "message": {"type": "string", "nullable": True},
                        },
                    },
                },
            },
        },
    )
