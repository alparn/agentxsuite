# MCP Agents Platform MVP

A Django 5 + DRF platform for centrally managing MCP (Model Context Protocol) agents.

## Stack

- Django 5.2+
- Django REST Framework 3.15+
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

```bash
python manage.py runserver
```

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
- `POST /api/v1/connections/:id/test/` - Test connection (stub)
- `POST /api/v1/connections/:id/sync/` - Sync tools from connection (stub)

### Agents

- `GET /api/v1/orgs/:org_id/agents/` - List agents
- `POST /api/v1/orgs/:org_id/agents/` - Create agent

### Tools

- `GET /api/v1/orgs/:org_id/tools/` - List tools
- `POST /api/v1/orgs/:org_id/tools/` - Create tool
- `POST /api/v1/tools/:id/run/` - Run tool (orchestrator stub)

### Runs

- `GET /api/v1/orgs/:org_id/runs/` - List runs

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

## MVP Features

- ✅ CRUD for Environment, Connection, Agent, Tool, Run
- ✅ Connection test/sync stubs
- ✅ Tool run orchestrator stub
- ✅ Policy check stub
- ✅ SecretStore abstraction (Fernet implementation)
- ✅ Unit tests for core functionality
- ✅ Strict typing and docstrings
- ✅ Clean architecture with services layer
- ✅ Email-based authentication (no username)

## Next Steps (Not in MVP)

- FastAPI Gateway with WebSockets
- Real MCP connection testing
- Real tool synchronization
- Advanced policy checks (input validation, rate limits)
- Audit event signals
- Production secret vault integration

## License

See [LICENSE](LICENSE) file for details.
