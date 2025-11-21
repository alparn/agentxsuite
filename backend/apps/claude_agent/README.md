# Claude Agent SDK Integration

This module provides integration with Claude's hosted Agent SDK, allowing Claude agents running in Anthropic's cloud to access AgentxSuite tools and capabilities.

## Architecture

The integration works as follows:

```
Claude (Hosted Agent)
        ↓
Claude Agent SDK
        ↓
AgentxSuite Cloud API Layer (this module)
        ↓
MCP / Tool Execution / Policy Engine
```

This complements the existing HTTP-Bridge approach:
- **Bridge**: `Claude Desktop → Bridge → AgentxSuite` (for local/desktop use)
- **SDK**: `Claude Cloud → SDK → AgentxSuite` (for cloud/production use)

## Components

### `agent_registry.py`
Defines tools that Claude agents can use. Each tool maps to AgentxSuite's internal MCP endpoints.

### `tool_handlers.py`
Implements the execution logic for each tool by calling AgentxSuite's internal APIs.

### `sdk_agent.py`
Main Claude agent implementation that handles conversations and tool execution.

### `oauth.py`
Manages OAuth authentication flow for Claude agents to access AgentxSuite.

### `views.py`
REST API endpoints for agent manifest, OAuth flow, and agent execution.

## Setup

### 1. Install Dependencies
```bash
pip install anthropic>=0.40.0 httpx
```

### 2. Configure Settings

Add to your Django settings (e.g., `config/settings/base.py`):

```python
# Anthropic API Configuration
ANTHROPIC_API_KEY = "sk-ant-..."  # Required for Claude SDK

# OAuth Configuration
CLAUDE_AGENT_CLIENT_ID = "agentxsuite-claude-agent"  # Default, can customize
CLAUDE_AGENT_CLIENT_SECRET = "your-secure-random-secret"  # Optional but recommended for production
CLAUDE_AGENT_REDIRECT_URI = "https://yourdomain.com/auth/callback"  # Where to redirect after auth

# OAuth Authorize URL (auto-detected if not set)
OAUTH_AUTHORIZE_URL = "https://yourdomain.com"  # Base URL for authorization endpoint

# AgentxSuite API Base URL (for tool handlers)
AGENTXSUITE_API_BASE_URL = "http://localhost:8000"  # Internal API endpoint

# Cache Configuration (required for OAuth)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/0",
    }
}
```

### 3. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ...
    "apps.claude_agent",
    # ...
]
```

### 4. Generate Client Secret (Production)

For production deployments, generate a secure client secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then add it to your environment variables:

```bash
export CLAUDE_AGENT_CLIENT_SECRET="generated_secret_here"
```

### 5. Configure CORS (if needed)

If your frontend is on a different domain, configure CORS:

```python
CORS_ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://claude.ai",  # For Claude hosted agents
]

CORS_ALLOW_CREDENTIALS = True
```

## API Endpoints

### Agent Discovery
- `GET /.well-known/agent-manifest` - Well-known endpoint for automatic agent discovery
- `GET /api/v1/claude-agent/manifest` - Complete agent manifest with schemas
- `GET /api/v1/claude-agent/openapi.json` - OpenAPI 3.0 specification
- `GET /api/v1/claude-agent/tools` - List available tools with full schemas

### OAuth Flow
- `GET /api/v1/claude-agent/authorize` - Start OAuth authorization
- `POST /api/v1/claude-agent/token` - Exchange code for access token
- `POST /api/v1/claude-agent/revoke` - Revoke access token

### Agent Execution
- `POST /api/v1/claude-agent/execute` - Execute agent with message

### System
- `GET /api/v1/claude-agent/health` - Health check and service status

## Usage Examples

### OAuth Flow (Python)

```python
from apps.claude_agent.oauth import OAuthManager

# Initialize OAuth manager
oauth = OAuthManager()

# Step 1: Initiate OAuth flow
flow_data = oauth.initiate_flow(
    organization_id="org-123",
    environment_id="env-456"
)

print(f"Visit this URL: {flow_data['authorization_url']}")
print(f"State token: {flow_data['state']}")

# Step 2: After user authorizes, you receive a callback with code
# Exchange code for access token
from django.http import HttpRequest

# Simulate token request
request = HttpRequest()
request.method = "POST"
request.POST = {
    "grant_type": "authorization_code",
    "code": "received_auth_code",
    "redirect_uri": "http://localhost:3000/auth/callback",
    "client_id": "agentxsuite-claude-agent",
    "client_secret": "your-secret"  # if configured
}

token_data = oauth.token(request)
print(f"Access Token: {token_data['access_token']}")

# Step 3: Use the token to access AgentxSuite APIs
# (token can be used with SDK agent or direct API calls)
```

### Agent Execution (Python)

```python
from apps.claude_agent.sdk_agent import AgentxSuiteClaudeAgent

# Initialize agent with OAuth token
agent = AgentxSuiteClaudeAgent(
    api_key="sk-ant-...",
    organization_id="org-uuid",
    environment_id="env-uuid",
    auth_token="oauth_access_token_from_above"
)

# Execute a message
result = await agent.execute_single_message(
    "List all available tools and then execute a database query"
)

print(result["response"])
print(f"Cost: ${result['cost']['total_cost']}")
```

### OAuth Flow (cURL)

```bash
# Step 1: Get agent manifest (discover OAuth endpoints)
curl http://localhost:8000/.well-known/agent-manifest

# Step 2: Initiate OAuth flow (visit in browser)
# This would typically be done by redirecting user in web app
open "http://localhost:8000/api/v1/claude-agent/authorize?client_id=agentxsuite-claude-agent&redirect_uri=http://localhost:3000/auth/callback&response_type=code&state=random_state_123&organization_id=org-uuid&environment_id=env-uuid&scope=agent:execute+tools:read"

# Step 3: After user authorizes, exchange code for token
curl -X POST http://localhost:8000/api/v1/claude-agent/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "code": "AUTH_CODE_FROM_CALLBACK",
    "redirect_uri": "http://localhost:3000/auth/callback",
    "client_id": "agentxsuite-claude-agent",
    "client_secret": "your-secret"
  }'

# Response:
# {
#   "access_token": "abc123...",
#   "token_type": "Bearer",
#   "expires_in": 31536000,
#   "scope": "agent:execute tools:read",
#   "organization_id": "org-uuid",
#   "environment_id": "env-uuid"
# }

# Step 4: Use access token to call APIs
curl -X GET http://localhost:8000/api/v1/claude-agent/tools \
  -H "Authorization: Bearer abc123..."

# Execute agent with token
curl -X POST http://localhost:8000/api/v1/claude-agent/execute \
  -H "Authorization: Bearer abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What tools are available?",
    "organization_id": "org-uuid",
    "environment_id": "env-uuid"
  }'

# Step 5: Revoke token when done
curl -X POST http://localhost:8000/api/v1/claude-agent/revoke \
  -H "Authorization: Bearer abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123..."
  }'
```

## OAuth 2.0 Implementation

The OAuth implementation follows RFC 6749 (OAuth 2.0 Authorization Framework) with the Authorization Code flow:

### Flow Overview
1. **Authorization Request**: Client requests authorization with organization/environment scope
2. **User Authentication**: User authenticates and grants access
3. **Authorization Code**: Server issues short-lived authorization code
4. **Token Exchange**: Client exchanges code for long-lived access token
5. **API Access**: Client uses token to access AgentxSuite APIs
6. **Token Revocation**: Tokens can be revoked following RFC 7009

### Security Features
- **State Parameter**: CSRF protection using cryptographically random state tokens
- **Code Expiration**: Authorization codes expire after 10 minutes
- **One-Time Use**: Codes and states are invalidated after first use
- **Client Authentication**: Optional client_secret for additional security
- **Scope Validation**: Only valid scopes (agent:execute, tools:read, etc.) are allowed
- **Organization Scoping**: Tokens are bound to specific organizations and environments
- **Cache-Based Storage**: Temporary data stored in Django cache, not database

### Available Scopes
- `agent:execute` - Execute agents and tools
- `tools:read` - Read available tools
- `runs:read` - Read execution history
- `agent:read` - Read agent information

### Token Storage
- Access tokens stored in Django's `Token` model (DRF)
- Metadata (org_id, env_id, scopes) stored in Redis cache
- Tokens are long-lived (1 year) by default
- Can be revoked at any time

## Security

- All tool executions go through AgentxSuite's policy engine
- OAuth 2.0 flow ensures proper authentication and authorization
- Tokens are scoped to specific organizations and environments
- Audit logging tracks all agent actions
- CSRF protection via state parameter
- Client secret validation (optional but recommended)

## Available Tools

Claude agents can use these tools out of the box:

1. **list_available_tools** - List all tools in the environment
2. **execute_tool** - Execute any registered tool
3. **get_agent_info** - Get agent details and capabilities
4. **list_runs** - View recent tool executions and their results

## Extending

To add new tools:

1. Add tool definition to `agent_registry.py`:
   ```python
   {
       "name": "my_custom_tool",
       "description": "Tool description",
       "input_schema": {...}
   }
   ```

2. Add handler to `tool_handlers.py`:
   ```python
   async def my_custom_tool(self, param1, param2):
       # Call internal API
       response = self.client.post(...)
       return {"success": True, "result": response.json()}
   ```

3. Register handler in `handle_tool_call()` method.

## Testing

Run the test suite:
```bash
pytest apps/claude_agent/tests/
```

## Notes

- This module requires `anthropic` SDK version 0.40.0+
- Agent execution is asynchronous (uses async/await)
- OAuth tokens are stored in Django's cache for security
- Tool execution goes through the same validation as MCP HTTP requests

