# 🧠 AgentxSuite

AgentxSuite is an open-source platform to connect, manage, and monitor AI Agents and Tools across multiple MCP servers — all in one unified interface.

![AgentxSuite Dashboard](docs/agentxsuite.png)

## 🚀 Overview

AgentxSuite provides a consistent control layer for distributed AI agents.

It connects Agents, Tools, and Policies under a single orchestration system, built for secure, multi-tenant, and MCP-compatible environments.

## 🧩 Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.2+, Django REST Framework 3.15+ |
| MCP Service | FastAPI 0.104+ (MCP Fabric Layer) |
| Database | PostgreSQL (production) / SQLite (development) |
| Language | Python 3.11+ |

### backend/

```
  config/              # Django project configuration
  apps/
    accounts/          # User model & auth
    tenants/           # Organizations & Environments
    connections/       # MCP server connections
    agents/            # Agent definitions
    tools/             # Tool registry
    runs/              # Run orchestration
    policies/          # Access policies
    audit/             # Audit events (stub)
  libs/
    secretstore/       # Secret storage abstraction
    permissions/       # RBAC utilities
  mcp_fabric/          # FastAPI MCP-compatible service
    routers/           # Manifest, tools, and run endpoints
    tests/             # Unit & integration tests
  requirements/        # Dependencies (base, dev, test)
```

## ⚙️ Setup

### 1. Create a virtual environment

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

### 3. Apply migrations

```bash
python manage.py migrate
```

### 4. (Optional) Create a superuser

```bash
python manage.py createsuperuser
```

### 5. Start the servers

**Django API**
```bash
python manage.py runserver
```

**MCP Fabric (FastAPI)**
```bash
uvicorn mcp_fabric.main:app --reload --port 8090
```

## 🔑 Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register/` | POST | Register new user |
| `/api/v1/auth/login/` | POST | Login and get token |
| `/api/v1/auth/logout/` | POST | Logout current user |
| `/api/v1/auth/me/` | GET | Get current user info |

**Header:**
```
Authorization: Token <your-token>
```

## 🧱 Core Endpoints

### Organizations & Environments

- `GET  /api/v1/orgs/`
- `POST /api/v1/orgs/`
- `GET  /api/v1/orgs/:org_id/environments/`
- `POST /api/v1/orgs/:org_id/environments/`

### Connections

- `GET  /api/v1/orgs/:org_id/connections/`
- `POST /api/v1/orgs/:org_id/connections/`
- `POST /api/v1/connections/:id/test/`
- `POST /api/v1/connections/:id/sync/`

### Agents, Tools & Runs

- `GET  /api/v1/orgs/:org_id/agents/`
- `POST /api/v1/orgs/:org_id/agents/`
- `GET  /api/v1/orgs/:org_id/tools/`
- `POST /api/v1/orgs/:org_id/tools/`
- `POST /api/v1/orgs/:org_id/runs/execute/` - **Unified tool execution endpoint** (recommended)
- `POST /api/v1/tools/:id/run/` - Legacy endpoint (deprecated, use `/runs/execute/` instead)
- `GET  /api/v1/orgs/:org_id/runs/`

#### Unified Run API

The unified run endpoint (`POST /api/v1/orgs/:org_id/runs/execute/`) provides a consistent way to execute tools:

**Request:**
```json
{
  "tool": "uuid-or-name",      // Tool UUID or name
  "agent": "uuid",              // Optional if Agent-Token is used
  "input": {...},               // Input data
  "environment": "uuid",        // Optional, derived from tool if not provided
  "timeout_seconds": 30         // Optional timeout
}
```

**Response (MCP-compatible format):**
```json
{
  "run_id": "uuid",
  "status": "succeeded",
  "content": [{"type": "text", "text": "..."}],
  "isError": false,
  "agent": {"id": "...", "name": "..."},
  "tool": {"id": "...", "name": "..."},
  "execution": {
    "started_at": "2025-01-01T12:00:00Z",
    "ended_at": "2025-01-01T12:00:02Z",
    "duration_ms": 2000
  }
}
```

**Agent Selection:**
- If using an Agent Token: Agent is automatically extracted from token (highest priority)
- If no Agent Token: `agent` field in request is required (no automatic fallback)
- For security reasons, automatic agent selection is not allowed

## 🧬 MCP Fabric (FastAPI Service)

MCP Fabric exposes standardized MCP endpoints to access tools from connected environments.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp/{org_id}/{env_id}/.well-known/mcp/manifest.json` | GET | Get MCP manifest |
| `/mcp/{org_id}/{env_id}/.well-known/mcp/tools` | GET | List registered tools |
| `/mcp/{org_id}/{env_id}/.well-known/mcp/run` | POST | Execute a tool |

**Authentication:**
```
Authorization: Bearer <token>
```

### Architecture Highlights

- **fastmcp** — Embedded MCP server for manifest, tools, and run endpoints
- **registry.py** — Dynamically registers Django tools with fastmcp
- **adapters.py** — Bridges FastAPI tool handlers to Django services
- **Security Layer** — Policy checks, JSON schema validation, rate limiting, timeouts, and audit logging

## 🧪 Testing

**Run all tests:**
```bash
pytest
```

**With coverage:**
```bash
pytest --cov=apps --cov=libs --cov-report=term-missing
```

**Run specific test:**
```bash
pytest apps/policies/tests/unit/test_policies_allow_deny.py
```

**Local test setup (with mock MCP server):**
```bash
python manage.py seed_local_agentsuite
bash dev/run_servers.sh
```

## 🧹 Code Quality

```bash
ruff check .
ruff format .
mypy apps libs
```

**Or via Makefile:**
```bash
make install
make lint
make typecheck
make test
```

## 🌟 Features

- Multi-tenant architecture (Organizations & Environments)
- Policy-based access control
- MCP-compatible FastAPI gateway
- SecretStore with Fernet encryption
- Clean service-layer architecture
- High test coverage and strict type checking

## 📄 License

Licensed under AGPL-3.0.

See [LICENSE](LICENSE) for details.
