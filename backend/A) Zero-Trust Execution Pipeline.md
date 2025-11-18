A) Zero-Trust Execution Pipeline

(Ersetzt das alte Flowchart — deutlich präziser für AgentxSuite)

flowchart TD

A[Agent Request <br/> (JWT + Context)] --> B{Token/Identity Validation}
B -->|Invalid| Z1[401 Unauthorized]

B --> C{Capability Layer Check}
C -->|Not Allowed| Z2[403 Forbidden]

C --> D{Policy PDP Evaluation}
D -->|Deny| Z3[403 Forbidden + Audit]

D --> E{Rate Limit <br/> agent+tool}
E -->|Exceeded| Z4[429 Too Many Requests]

E --> F{Input Validation <br/> JSON Schema}
F -->|Invalid| Z5[400 Bad Input]

F --> G{Execution Trace Init <br/> (root_agent, jti)}
G --> H[Execute Tool via MCP Fabric]

H --> I{Output Sanitization}
I -->|Dangerous Content| Z6[Blocked + Audit]

I --> J[Audit Log (success/fail)]
J --> K[Return Response]


Neue Schichten:

Capability Check

Output Sanitization

Execution Trace

B) Multi-Agent Orchestration – Security Graph
graph LR
A[Orchestrator Agent] -->|delegates| B[Worker Agent]
A -->|defines context| C[Execution Context]
C -->|propagates| D[Run]
D -->|bounded by root_agent| E[Tool Execution]
E -->|audited as root_agent| F[Audit Log]
B -->|cannot elevate| C


Wichtig:

Worker-Agent kann keine stärkeren Rechte haben als der Orchestrator.

Root-Agent wird über die gesamte Pipeline mitgeführt.

C) Shadow-Agent Prevention
flowchart LR
S[Token Presented] --> T{Fingerprint Match?}
T -->|No| F1[Reject + Shadow-Agent Alert]
T -->|Yes| U{Audience Scope Match?}
U -->|No| F2[Reject]
U -->|Yes| V[Continue]


Fingerprint =

mTLS client cert hash

device ID

agent signature

2) Konkrete Backend-Änderungsvorschläge

Ich liste dir Änderungen auf, die du in AgentxSuite sofort umsetzen kannst, ohne dein MVP zu zerstören.

✅ A) ServiceAccount erweitern um "capabilities"

Neues Feld:

capabilities = JSONField(default=dict)


Beispiele:

{
  "tools_allow": ["pdf.read", "storage.list"],
  "prompts_allow": ["*"],
  "resources_allow": ["projectA/*"],
  "max_input_bytes": 20000,
  "deny_http_urls": ["169.254.169.254"]
}

✅ B) ExecutionContext erweitern

Neues Attribut:

ExecutionContext(
    root_agent_id,
    caller_agent_id,
    token_jti,
    capabilities,
    trace_id
)


Damit kannst du multi-agent workflows absichern.

✅ C) Output-Sanitizer im Backend

In deiner execute_tool_run Pipeline:

def sanitize_output(output_json):
    if contains_secrets(output_json):
        raise SecurityError("Output contains forbidden patterns")
    return output_json


Patterns:

JWTs

AWS Keys

DB Connection Strings

IP der Runtime

URLs außerhalb Allowed Domains

✅ D) PDP auf Resource-, Prompt- und Metadata-Level

Du hast Policies heute vor Tool-Execution.

Erweitere folgende Endpoints:

/mcp/**/resources/

/mcp/**/prompts/

/connections/**/sync/

Alle bekommen:

pdp.evaluate("resource.read", resource_uri)

✅ E) Forbidden Input Patterns

Im Service Layer:

if input_json.matches(forbidden_patterns):
    deny


Beispiele:

<script>

base64 payloads über N KB

URLs außerhalb allowlist

✅ F) Token + mTLS Binding (Optional für Enterprise)

Im ServiceAccount:

allowed_client_cert_fingerprints


Validiere:

incoming_cert_hash in allowed_client_cert_fingerprints

3) Verbesserungen im ERD für granularere Policies

Unten eine saubere Erweiterung deines ERD für Policies.

A) Neue Tabelle: AgentCapability
erDiagram
    Agent ||--o{ AgentCapability : "has"
    AgentCapability {
        uuid id PK
        uuid agent_id FK
        string type "tool|prompt|resource"
        string name
        boolean allow
        datetime created_at
    }


Das erlaubt z. B.:

Agent darf nur pdf.read

Agent darf keine storage.write

Agent darf nur resources unter projectX/**

B) PolicyRule granularer

Heute:

action, target, effect


Erweitert um:

limit_per_minute
max_payload_size
time_restricted (08:00-20:00)
allow_params (regex)
deny_params (regex)


ERD-Erweiterung:

erDiagram
PolicyRule {
    uuid id
    uuid policy_id
    string action
    string target
    string effect
    json conditions         // bleibt
    json limits             // neu
}

C) Neue Tabelle: ExecutionTrace
erDiagram
Run ||--o{ ExecutionTrace : "has"
ExecutionTrace {
    uuid id
    uuid run_id
    uuid root_agent_id
    uuid caller_agent_id
    string token_jti
    string trace_id
    json chainsour
}


Das brauchst du für echte Orchestration.

D) Resource Access Control separat speichern
erDiagram
Policy ||--o{ ResourceRule : "contains"
ResourceRule {
    uuid id
    uuid policy_id
    string resource_pattern
    string effect
}


So musst du nicht Tool-Rules missbrauchen