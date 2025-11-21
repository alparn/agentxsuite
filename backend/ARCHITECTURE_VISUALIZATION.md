# 🏗️ AgentxSuite - Architecture Visualization

## 📊 Entity-Relationship Diagram (Models)

```mermaid
erDiagram
    %% Core Tenant Models
    Organization ||--o{ Environment : "has"
    Organization ||--o{ OrganizationMembership : "has"
    User ||--o{ OrganizationMembership : "belongs_to"
    
    %% Connection & Tool Chain
    Organization ||--o{ Connection : "has"
    Environment ||--o{ Connection : "has"
    Connection ||--o{ Tool : "provides"
    Connection ||--o{ Agent : "used_by"
    
    %% Agent & Service Account
    Organization ||--o{ Agent : "has"
    Environment ||--o{ Agent : "has"
    Agent ||--o| ServiceAccount : "authenticates_with"
    Agent ||--o{ IssuedToken : "issues"
    User ||--o{ IssuedToken : "revokes"
    
    %% Tool Execution
    Organization ||--o{ Tool : "has"
    Environment ||--o{ Tool : "has"
    Agent ||--o{ Run : "executes"
    Tool ||--o{ Run : "executed_in"
    Run ||--o{ RunStep : "has"
    
    %% Policy System
    Organization ||--o{ Policy : "has"
    Environment ||--o{ Policy : "has"
    Policy ||--o{ PolicyRule : "contains"
    Policy ||--o{ PolicyBinding : "bound_to"
    
    %% Audit
    Organization ||--o{ AuditEvent : "logs"
    
    %% Model Definitions
    Organization {
        uuid id PK
        string name UK
        datetime created_at
        datetime updated_at
    }
    
    Environment {
        uuid id PK
        uuid organization_id FK
        string name
        string type
        datetime created_at
        datetime updated_at
    }
    
    User {
        uuid id PK
        string email UK
        string password
        string first_name
        string last_name
        boolean is_active
        datetime created_at
    }
    
    OrganizationMembership {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        string role
        boolean is_active
        datetime created_at
    }
    
    Connection {
        uuid id PK
        uuid organization_id FK
        uuid environment_id FK
        string name
        string endpoint
        string auth_method
        string secret_ref
        string status
        datetime last_seen_at
        datetime created_at
    }
    
    Tool {
        uuid id PK
        uuid organization_id FK
        uuid environment_id FK
        uuid connection_id FK
        string name
        string version
        json schema_json
        boolean enabled
        string sync_status
        datetime synced_at
        datetime created_at
    }
    
    Agent {
        uuid id PK
        uuid organization_id FK
        uuid environment_id FK
        uuid connection_id FK "nullable"
        uuid service_account_id FK "nullable"
        string name
        string slug
        string mode "RUNNER|CALLER"
        string inbound_auth_method "BEARER|MTLS|NONE"
        boolean enabled
        json capabilities
        json tags
        datetime created_at
    }
    
    ServiceAccount {
        uuid id PK
        uuid organization_id FK
        uuid environment_id FK "nullable"
        string name
        string subject
        string credential_ref
        string audience
        string issuer
        json scope_allowlist
        boolean enabled
        datetime created_at
    }
    
    IssuedToken {
        uuid id PK
        uuid agent_id FK
        uuid revoked_by_id FK "nullable"
        string jti UK
        datetime expires_at
        datetime revoked_at
        json scopes
        json metadata
        datetime created_at
    }
    
    Run {
        uuid id PK
        uuid organization_id FK
        uuid environment_id FK
        uuid agent_id FK
        uuid tool_id FK
        string status "pending|running|succeeded|failed"
        datetime started_at
        datetime ended_at
        json input_json
        json output_json
        text error_text
        datetime created_at
    }
    
    RunStep {
        uuid id PK
        uuid run_id FK
        string step_type
        text message
        json details
        datetime timestamp
    }
    
    Policy {
        uuid id PK
        uuid organization_id FK
        uuid environment_id FK "nullable"
        string name
        integer version
        boolean is_active
        json rules_json
        datetime created_at
    }
    
    PolicyRule {
        uuid id PK
        uuid policy_id FK
        string action
        string target
        string effect "allow|deny"
        json conditions
        datetime created_at
    }
    
    PolicyBinding {
        uuid id PK
        uuid policy_id FK
        string scope_type "org|env|agent|tool|role|user|resource_ns"
        string scope_id
        integer priority
        datetime created_at
    }
    
    AuditEvent {
        uuid id PK
        uuid organization_id FK "nullable"
        string event_type
        json event_data
        datetime ts
        string subject
        string action
        string target
        string decision "allow|deny"
        integer rule_id
        json context
        datetime created_at
    }
```

## 🔌 API Endpoints Overview

### 🔐 Authentication (`/api/v1/auth/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/auth/register/` | Register user | ❌ |
| `POST` | `/api/v1/auth/login/` | User login & get token | ❌ |
| `POST` | `/api/v1/auth/logout/` | User logout & delete token | ✅ |
| `GET` | `/api/v1/auth/me/` | Current user & organization | ✅ |
| `PUT/PATCH` | `/api/v1/auth/me/` | Update user profile | ✅ |
| `GET` | `/api/v1/auth/me/orgs/` | List user organizations | ✅ |
| `POST` | `/api/v1/auth/me/orgs/` | Add user to organization | ✅ |

### 🏢 Organizations & Environments (`/api/v1/orgs/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/` | List organizations | ✅ |
| `POST` | `/api/v1/orgs/` | Create organization | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/` | Organization details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/` | Update organization | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/` | Delete organization | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/environments/` | List environments | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/environments/` | Create environment | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/environments/{env_id}/` | Environment details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/environments/{env_id}/` | Update environment | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/environments/{env_id}/` | Delete environment | ✅ |

### 🔗 Connections (`/api/v1/orgs/{org_id}/connections/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/connections/` | List connections | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/connections/` | Create connection | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/connections/{id}/` | Connection details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/connections/{id}/` | Update connection | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/connections/{id}/` | Delete connection | ✅ |
| `POST` | `/api/v1/connections/{id}/test/` | Test connection | ✅ |
| `POST` | `/api/v1/connections/{id}/sync/` | Sync tools from connection | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/connections/store-secret/` | Store secret in SecretStore | ✅ |

### 🤖 Agents (`/api/v1/orgs/{org_id}/agents/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/agents/` | List agents | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/agents/` | Create agent | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/agents/{id}/` | Agent details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/agents/{id}/` | Update agent | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/agents/{id}/` | Delete agent | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/agents/{id}/ping/` | Test agent status & connection | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/agents/{id}/tokens/` | List tokens | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/agents/{id}/tokens/` | Generate token | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/agents/{id}/tokens/{jti}/revoke/` | Revoke token | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/agents/{id}/tokens/{jti}/` | Delete token (only if revoked/expired) | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/agents/create-axcore/` | Create AxCore agent completely | ✅ |

### 🛠️ Tools (`/api/v1/orgs/{org_id}/tools/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/tools/` | List tools | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/tools/` | Create tool | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/tools/{id}/` | Tool details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/tools/{id}/` | Update tool | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/tools/{id}/` | Delete tool | ✅ |

### ▶️ Runs (`/api/v1/orgs/{org_id}/runs/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/runs/` | List runs | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/runs/{id}/` | Run details | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/runs/{id}/steps/` | List run steps | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/runs/execute/` | **Unified Tool Execution** (recommended) | ✅ |

### 🔒 Policies (`/api/v1/orgs/{org_id}/policies/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/policies/` | List policies | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/policies/` | Create policy | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/policies/{id}/` | Policy details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/policies/{id}/` | Update policy | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/policies/{id}/` | Delete policy | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/policies/{id}/rules/` | Add rule to policy | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/policies/evaluate/` | Evaluate policy | ✅ |
| `POST` | `/api/v1/policies/evaluate/` | Evaluate policy (global) | ✅ |

#### Policy Rules (`/api/v1/policies/rules/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/policies/rules/` | List rules | ✅ |
| `POST` | `/api/v1/policies/rules/` | Create rule | ✅ |
| `GET` | `/api/v1/policies/rules/{id}/` | Rule details | ✅ |
| `PUT/PATCH` | `/api/v1/policies/rules/{id}/` | Update rule | ✅ |
| `DELETE` | `/api/v1/policies/rules/{id}/` | Delete rule | ✅ |

#### Policy Bindings (`/api/v1/policies/bindings/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/policies/bindings/` | List bindings | ✅ |
| `POST` | `/api/v1/policies/bindings/` | Create binding | ✅ |
| `GET` | `/api/v1/policies/bindings/{id}/` | Binding details | ✅ |
| `PUT/PATCH` | `/api/v1/policies/bindings/{id}/` | Update binding | ✅ |
| `DELETE` | `/api/v1/policies/bindings/{id}/` | Delete binding | ✅ |

### 🔍 Audit (`/api/v1/orgs/{org_id}/audit/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/audit/` | List audit events (with filters) | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/audit/{id}/` | Audit event details | ✅ |
| `GET` | `/api/v1/audit/` | Global audit events (last 24h) | ✅ |

**Filter Parameters:**
- `subject` - Filter by subject (Agent/User/Client)
- `action` - Filter by action (e.g., `tool.invoke`)
- `target` - Filter by target (e.g., `tool:pdf/read`)
- `decision` - Filter by decision (`allow`/`deny`)
- `ts_from` - Time window start
- `ts_to` - Time window end

### 👤 Service Accounts (`/api/v1/orgs/{org_id}/service-accounts/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/service-accounts/` | List service accounts | ✅ |
| `POST` | `/api/v1/orgs/{org_id}/service-accounts/` | Create service account | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/service-accounts/{id}/` | Service account details | ✅ |
| `PUT/PATCH` | `/api/v1/orgs/{org_id}/service-accounts/{id}/` | Update service account | ✅ |
| `DELETE` | `/api/v1/orgs/{org_id}/service-accounts/{id}/` | Delete service account | ✅ |

### 🌐 MCP Extensions (`/api/v1/orgs/{org_id}/mcp/`)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/orgs/{org_id}/mcp/{env_id}/resources/` | List MCP resources | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/mcp/{env_id}/resources/{uri}/` | MCP resource details | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/mcp/{env_id}/prompts/` | List MCP prompts | ✅ |
| `GET` | `/api/v1/orgs/{org_id}/mcp/{env_id}/prompts/{name}/` | MCP prompt details | ✅ |

## 🔄 Data Flow Diagram

```mermaid
sequenceDiagram
    participant Client
    participant API as Django REST API
    participant Service as Service Layer
    participant Policy as Policy Engine (PDP)
    participant MCP as MCP Server
    participant Audit as Audit Log
    
    Client->>API: POST /runs/execute/
    API->>Service: execute_tool_run()
    
    Service->>Policy: evaluate(action, target)
    Policy-->>Service: decision: allow/deny
    
    alt Policy Decision: DENY
        Service->>Audit: log(run_denied)
        Service-->>API: ValueError("Access denied")
        API-->>Client: 400 Bad Request
    else Policy Decision: ALLOW
        Service->>Service: validate_input_json()
        Service->>Service: check_rate_limit()
        Service->>Service: check_timeout()
        
        Service->>Audit: log(run_started)
        Service->>MCP: execute_tool(tool, input)
        MCP-->>Service: result
        
        Service->>Audit: log(run_finished)
        Service-->>API: result
        API-->>Client: 201 Created
    end
```

## 🏛️ Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                          │
│  (Frontend, CLI, MCP Clients, External Services)        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    API Layer (DRF)                       │
│  - ViewSets (CRUD)                                       │
│  - Serializers (Validation)                             │
│  - Authentication (Token/JWT)                           │
│  - Audit Logging Mixin                                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Service Layer                           │
│  - Business Logic                                        │
│  - Policy Checks (PDP)                                   │
│  - Rate Limiting                                         │
│  - Timeout Management                                    │
│  - MCP Integration                                       │
│  - Secret Management                                     │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                        ▼
┌──────────────────┐    ┌──────────────────┐
│   Model Layer    │    │  External APIs    │
│  - Django ORM    │    │  - MCP Servers    │
│  - Validations   │    │  - SecretStore    │
│  - Relationships │    │  - Redis (Rate)   │
└──────────────────┘    └──────────────────┘
```

## 🔐 Security Flow

```mermaid
graph TD
    A[Client Request] --> B{Authentication}
    B -->|Token/JWT| C[User/Agent Identity]
    B -->|Invalid| D[401 Unauthorized]
    
    C --> E[Authorization Check]
    E --> F{Policy Engine}
    
    F -->|Allow| G[Rate Limit Check]
    F -->|Deny| H[403 Forbidden + Audit]
    
    G -->|OK| I[Input Validation]
    G -->|Exceeded| J[429 Too Many Requests]
    
    I -->|Valid| K[Tool Execution]
    I -->|Invalid| L[400 Bad Request]
    
    K --> M[Audit Log]
    M --> N[Response]
```

## 📝 Important Constraints & Validations

### Model Constraints

1. **Organization**
   - `name` is unique

2. **Environment**
   - `(organization, name)` is unique

3. **Connection**
   - `(organization, environment, name)` is unique

4. **Tool**
   - `(organization, environment, name, version)` is unique

5. **Agent**
   - `(organization, environment, name)` is unique
   - `(organization, environment, slug)` is unique (case-insensitive)
   - `RUNNER` mode requires `connection`
   - `BEARER` auth requires `bearer_secret_ref` or `inbound_secret_ref`
   - `MTLS` auth requires `mtls_cert_ref` and `mtls_key_ref`

6. **Policy**
   - `(organization, name)` is unique

7. **ServiceAccount**
   - `(organization, name)` is unique
   - `(subject, issuer)` is unique

8. **IssuedToken**
   - `jti` is unique

### API Validations

- **Cross-Field Validation**: `environment.organization == organization` (in Serializers)
- **Policy Evaluation**: Before every tool run
- **JSON Schema Validation**: Tool inputs are validated against `schema_json`
- **Rate Limiting**: Per `agent_id + tool_id` (Redis Token Bucket)
- **Timeout**: Configurable per run (default: 30s)

## 🎯 Multi-Tenancy

All resources are **organization-scoped**:
- URLs: `/api/v1/orgs/{org_id}/...`
- Models: `organization` + `environment` ForeignKeys
- Filtering: Automatically by `org_id` from URL

**Exceptions:**
- `/api/v1/auth/` - User-specific
- `/api/v1/policies/evaluate/` - Can be called without `org_id`
- `/api/v1/audit/` - Globally available (last 24h)

---

**Created:** 2025-01-27  
**Version:** 1.0  
**Status:** Current for AgentxSuite MVP
