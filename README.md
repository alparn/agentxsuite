# AgentxSuite

AgentxSuite is an open-source platform to connect, manage, and monitor AI Agents and Tools across multiple MCP servers — in one unified interface.

![AgentxSuite Dashboard](docs/agentxsuite.png)

## Stack

- Django 5.2+
- Django REST Framework 3.15+
- FastAPI 0.104+ (MCP Fabric Service)
- PostgreSQL (production) / SQLite (development)
- Python 3.11+

## Project Structure

```
backend/
  config/              # Django project configuration
    settings/          # Split settings (base, dev, test)
  apps/                # Django applications
    accounts/          # User model
    tenants/           # Organization, Environment
    connections/       # MCP server connections
    agents/            # Agents
    tools/             # Tool registry
    runs/              # Run execution
    policies/           # Access policies
    audit/             # Audit events (stub)
  libs/                # Shared libraries
    secretstore/       # Secret storage abstraction
    permissions/       # RBAC (stub)
  mcp_fabric/          # FastAPI MCP-compatible service
    routers/           # MCP endpoints (manifest, tools, run)
    tests/             # MCP Fabric tests
  requirements/        # Python dependencies
```

## Setup

### 1. Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements/base.txt
pip install -r requirements/dev.txt
pip install -r requirements/test.txt
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Create superuser (optional)

```bash
python manage.py createsuperuser
```

### 5. Run development server

**Django REST API:**
```bash
python manage.py runserver
```

**MCP Fabric Service (FastAPI):**
```bash
cd backend
uvicorn mcp_fabric.main:app --reload --port 8090
```

The MCP Fabric service provides MCP-compatible endpoints for accessing tools via the existing security layer (policies, rate limits, validation, audit).

## API Endpoints

### Authentication

- `POST /api/v1/auth/register/` - Register a new user (email + password)
- `POST /api/v1/auth/login/` - Login user (email + password, returns token)
- `POST /api/v1/auth/logout/` - Logout user (requires token)
- `GET /api/v1/auth/me/` - Get current user details (requires token)

**Example Registration:**
```json
POST /api/v1/auth/register/
{
  "email": "user@example.com",
  "password": "securepass123",
  "password_confirm": "securepass123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Example Login:**
```json
POST /api/v1/auth/login/
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

**Using Token:**
Add header to authenticated requests:
```
Authorization: Token <your-token-here>
```

### Organizations & Environments

- `GET /api/v1/orgs/` - List organizations
- `POST /api/v1/orgs/` - Create organization
- `GET /api/v1/orgs/:org_id/environments/` - List environments
- `POST /api/v1/orgs/:org_id/environments/` - Create environment

### Connections

- `GET /api/v1/orgs/:org_id/connections/` - List connections
- `POST /api/v1/orgs/:org_id/connections/` - Create connection
- `POST /api/v1/connections/:id/test/` - Test connection
- `POST /api/v1/connections/:id/sync/` - Sync tools from connection

### Agents

- `GET /api/v1/orgs/:org_id/agents/` - List agents
- `POST /api/v1/orgs/:org_id/agents/` - Create agent

### Tools

- `GET /api/v1/orgs/:org_id/tools/` - List tools
- `POST /api/v1/orgs/:org_id/tools/` - Create tool
- `POST /api/v1/tools/:id/run/` - Execute tool

### Runs

- `GET /api/v1/orgs/:org_id/runs/` - List runs

### MCP Fabric (FastAPI Service)

The MCP Fabric service provides MCP-compatible endpoints for accessing tools through the existing security infrastructure. It uses **fastmcp** as an embedded MCP server, dynamically registering tools from the Django database.

**Start the Service:**
```bash
cd backend
uvicorn mcp_fabric.main:app --reload --port 8090
```

**Endpoints:**

- `GET /mcp/{org_id}/{env_id}/.well-known/mcp/manifest.json` - Get MCP manifest
- `GET /mcp/{org_id}/{env_id}/.well-known/mcp/tools` - List available tools
- `POST /mcp/{org_id}/{env_id}/.well-known/mcp/run` - Execute a tool

**Authentication:**
All endpoints require Bearer token authentication:
```
Authorization: Bearer <your-token-here>
```

**Current Auth Status:** Bearer token header is required. OIDC/JWKS validation will be integrated in the future (issuer, aud, scope).

**Example: Get Manifest**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8090/mcp/{org_id}/{env_id}/.well-known/mcp/manifest.json
```

**Example: Get Tools**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8090/mcp/{org_id}/{env_id}/.well-known/mcp/tools
```

**Example: Run Tool**
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"tool": "my-tool", "input": {"x": 1}}' \
  http://localhost:8090/mcp/{org_id}/{env_id}/.well-known/mcp/run
```

**Architecture:**
- **fastmcp**: Embedded MCP server providing manifest/tools/run endpoints
- **registry.py**: Dynamically registers Django tools with fastmcp MCPServer
- **adapters.py**: Bridges fastmcp tool handlers to Django `start_run` service
- **routers/mcp.py**: FastAPI routes that create MCPServer instances per request

**Security:**
All tool executions go through the existing Django security checks:
- Policy validation (allow/deny rules)
- JSON Schema validation
- Rate limiting
- Timeout protection
- Audit logging

No secrets are logged or exposed in responses. Business logic remains in Django services, not in FastAPI routes.

**Frontend Integration:**
See [MCP Fabric Frontend Workflow](docs/MCP_FABRIC_FRONTEND_WORKFLOW.md) for detailed implementation guide.

## Testing

### Run all tests

```bash
pytest
```

### Run with coverage

```bash
pytest --cov=apps --cov=libs --cov-report=term-missing
```

### Run specific test file

```bash
pytest apps/policies/tests/unit/test_policies_allow_deny.py
```

### Lokales Test-Setup

Für lokale Tests von Runner- und Caller-Agents steht ein Mock-MCP-Server und Testdaten-Setup zur Verfügung.

#### 1. Testdaten erstellen

```bash
cd backend
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py migrate
python manage.py seed_local_agentsuite
```

Dies erstellt:
- Organization: "Acme"
- Environment: "prod"
- Connection: "mock-mcp" → `http://127.0.0.1:8091/.well-known/mcp/`
- Tool: "create_customer_note"
- Runner-Agent: "CRM-Runner" (outbound, nutzt Connection)
- Caller-Agent: "ChatGPT-Caller" (inbound, keine Connection)

#### 2. Server starten

**Option A: Beide Server zusammen starten**
```bash
cd backend
export DJANGO_SETTINGS_MODULE=config.settings.dev
bash dev/run_servers.sh
```

**Option B: Server einzeln starten**

Terminal 1 (Mock MCP Server):
```bash
cd backend
export DJANGO_SETTINGS_MODULE=config.settings.dev
uvicorn dev.mock_mcp_server:app --reload --port 8091
```

Terminal 2 (MCP Fabric):
```bash
cd backend
export DJANGO_SETTINGS_MODULE=config.settings.dev
uvicorn mcp_fabric.main:app --reload --port 8090
```

#### 3. Manuelle Tests

**Runner-Test (Django Backend ruft Mock-MCP):**

Via Django Shell:
```bash
python manage.py shell
```

```python
from apps.tenants.models import Organization, Environment
from apps.tools.models import Tool
from apps.agents.models import Agent
from apps.runs.services import start_run

org = Organization.objects.get(name="Acme")
env = Environment.objects.get(organization=org, name="prod")
tool = Tool.objects.get(organization=org, environment=env, name="create_customer_note")
agent = Agent.objects.get(organization=org, environment=env, name="CRM-Runner")

run = start_run(
    agent=agent,
    tool=tool,
    input_json={"customer_id": "CUST-42", "note": "Follow-up Friday"},
    timeout_seconds=10
)
print(f"Run status: {run.status}")
print(f"Output: {run.output_json}")
```

**Caller-Test (Externer Client ruft MCP-Fabric):**

Tools auflisten:
```bash
curl -s -H "Authorization: Bearer x" \
  http://127.0.0.1:8090/mcp/{org_id}/{env_id}/.well-known/mcp/tools | jq .
```

Tool ausführen:
```bash
curl -s -H "Authorization: Bearer x" \
  -H "Content-Type: application/json" \
  -d '{"tool":"create_customer_note","input":{"customer_id":"CUST-42","note":"hello from caller"}}' \
  http://127.0.0.1:8090/mcp/{org_id}/{env_id}/.well-known/mcp/run | jq .
```

**Hinweis:** Ersetze `{org_id}` und `{env_id}` mit den tatsächlichen UUIDs aus der Datenbank:
```bash
python manage.py shell -c "from apps.tenants.models import Organization, Environment; org = Organization.objects.get(name='Acme'); env = Environment.objects.get(organization=org, name='prod'); print(f'org_id={org.id}, env_id={env.id}')"
```

#### 4. Automatisierte Tests

```bash
# Alle lokalen MCP-Flow-Tests
pytest backend/tests/test_local_mcp_flow.py

# Mit Mock-HTTP (empfohlen für CI/CD)
pytest backend/tests/test_local_mcp_flow.py::test_runner_start_run_with_mock_httpx -v
```

**Ports:**
- Mock MCP Server: `http://127.0.0.1:8091`
- MCP Fabric: `http://127.0.0.1:8090`

## Code Quality

### Linting

```bash
ruff check .
ruff format .
```

### Type Checking

```bash
mypy apps libs
```

## Development

### Make Targets

```bash
make install   # Install all dependencies
make lint      # Run ruff check and format check
make format    # Format code with ruff
make typecheck # Run mypy
make test      # Run pytest
make test-cov  # Run pytest with coverage
make migrate   # Create and apply migrations
make run       # Run development server
```

## Features

- CRUD operations for Organizations, Environments, Connections, Agents, Tools, and Runs
- Connection testing and synchronization
- Tool execution orchestration
- Policy-based access control
- SecretStore abstraction with Fernet encryption
- Comprehensive unit test coverage
- Strict type checking and documentation
- Clean architecture with service layer separation
- Email-based authentication

## Roadmap

- ✅ FastAPI Gateway (MCP Fabric)
- WebSocket streaming for MCP Fabric
- Real MCP connection testing
- Real tool synchronization
- Advanced policy checks (input validation, rate limits)
- Audit event signals
- Production secret vault integration

## License

See [LICENSE](LICENSE) file for details.
