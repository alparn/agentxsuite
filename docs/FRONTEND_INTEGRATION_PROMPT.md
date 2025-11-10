# Frontend-Integration: MCP Resources & Prompts

## Kontext

Das Backend hat kürzlich neue Features für **MCP Resources** und **MCP Prompts** implementiert. Diese müssen nun im Frontend integriert werden, ähnlich wie bereits für Tools, Agents, Connections, etc. implementiert.

## Backend-Übersicht

### Models & Datenstruktur

#### Resource Model (`apps.mcp_ext.models.Resource`)
```typescript
interface Resource {
  id: string; // UUID
  organization: Organization; // read-only
  environment: Environment; // read-only
  environment_id: string; // UUID, write-only
  name: string; // max 120 chars, unique per (org, env, name)
  type: "static" | "http" | "sql" | "s3" | "file";
  config_json: Record<string, any>; // Konfiguration je nach Typ
  mime_type: string; // default: "application/json"
  schema_json?: Record<string, any> | null; // JSON Schema für Struktur
  secret_ref?: string | null; // Secret-Referenz für Auth
  enabled: boolean; // default: true
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}
```

#### Prompt Model (`apps.mcp_ext.models.Prompt`)
```typescript
interface Prompt {
  id: string; // UUID
  organization: Organization; // read-only
  environment: Environment; // read-only
  environment_id: string; // UUID, write-only
  name: string; // max 120 chars, unique per (org, env, name)
  description: string; // Text
  input_schema: Record<string, any>; // JSON Schema für Input-Variablen
  template_system: string; // Jinja2-Template für System-Message
  template_user: string; // Jinja2-Template für User-Message
  uses_resources: string[]; // Liste von Resource-Namen
  output_hints?: Record<string, any> | null; // Hinweise für Output-Format
  enabled: boolean; // default: true
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}
```

### API-Endpoints

#### DRF API (Django REST Framework) - **NOCH NICHT IMPLEMENTIERT**

Die folgenden Endpoints müssen noch im Backend erstellt werden (analog zu `ToolViewSet`):

```
GET    /api/v1/orgs/{org_id}/resources/          # Liste aller Resources
POST   /api/v1/orgs/{org_id}/resources/          # Neue Resource erstellen
GET    /api/v1/orgs/{org_id}/resources/{id}/     # Resource-Details
PUT    /api/v1/orgs/{org_id}/resources/{id}/     # Resource aktualisieren
PATCH  /api/v1/orgs/{org_id}/resources/{id}/     # Resource teilweise aktualisieren
DELETE /api/v1/orgs/{org_id}/resources/{id}/     # Resource löschen

GET    /api/v1/orgs/{org_id}/prompts/            # Liste aller Prompts
POST   /api/v1/orgs/{org_id}/prompts/            # Neuen Prompt erstellen
GET    /api/v1/orgs/{org_id}/prompts/{id}/       # Prompt-Details
PUT    /api/v1/orgs/{org_id}/prompts/{id}/       # Prompt aktualisieren
PATCH  /api/v1/orgs/{org_id}/prompts/{id}/       # Prompt teilweise aktualisieren
DELETE /api/v1/orgs/{org_id}/prompts/{id}/       # Prompt löschen
```

**Hinweis:** Diese Endpoints müssen zuerst im Backend implementiert werden (ViewSets in `apps.mcp_ext.views`).

#### MCP Fabric API (FastAPI) - **BEREITS IMPLEMENTIERT**

Diese Endpoints sind bereits verfügbar und dienen der MCP-Protokoll-Integration:

**Resources:**
```
GET /api/v1/mcp/{org_id}/{env_id}/.well-known/mcp/resources
GET /api/v1/mcp/{org_id}/{env_id}/.well-known/mcp/resources/{resource_name}
```

**Prompts:**
```
GET /api/v1/mcp/{org_id}/{env_id}/.well-known/mcp/prompts
POST /api/v1/mcp/{org_id}/{env_id}/.well-known/mcp/prompts/{prompt_name}/invoke
```

**Authentifizierung:** Bearer Token mit Scopes:
- `mcp:resources` - Liste von Resources
- `mcp:resource:read` - Resource-Inhalt lesen
- `mcp:prompts` - Liste von Prompts
- `mcp:prompt:invoke` - Prompt ausführen

### Serializers

Die Serializers sind bereits im Backend vorhanden (`apps.mcp_ext.serializers`):
- `ResourceSerializer`
- `PromptSerializer`

## Frontend-Aufgaben

### 1. API-Client erweitern (`frontend/lib/api.ts`)

Erweitere den API-Client um Funktionen für Resources und Prompts:

```typescript
// Resources
export const resourcesApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/resources/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/resources/${id}/`),
  create: (orgId: string, data: Partial<Resource>) => 
    api.post(`/orgs/${orgId}/resources/`, data),
  update: (orgId: string, id: string, data: Partial<Resource>) => 
    api.put(`/orgs/${orgId}/resources/${id}/`, data),
  delete: (orgId: string, id: string) => 
    api.delete(`/orgs/${orgId}/resources/${id}/`),
};

// Prompts
export const promptsApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/prompts/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/prompts/${id}/`),
  create: (orgId: string, data: Partial<Prompt>) => 
    api.post(`/orgs/${orgId}/prompts/`, data),
  update: (orgId: string, id: string, data: Partial<Prompt>) => 
    api.put(`/orgs/${orgId}/prompts/${id}/`, data),
  delete: (orgId: string, id: string) => 
    api.delete(`/orgs/${orgId}/prompts/${id}/`),
};
```

### 2. MCP Fabric Client erweitern (`frontend/lib/mcpFabric.ts`)

Erweitere den MCP Fabric Client um Resources und Prompts:

```typescript
// Resources
async getResources(orgId: string, envId: string): Promise<MCPResource[]>
async getResource(orgId: string, envId: string, resourceName: string): Promise<MCPResourceContent>

// Prompts
async getPrompts(orgId: string, envId: string): Promise<MCPPrompt[]>
async invokePrompt(orgId: string, envId: string, promptName: string, input: Record<string, any>): Promise<MCPPromptResponse>
```

### 3. Views erstellen

Erstelle neue View-Komponenten analog zu `MCPToolsView.tsx`:

#### `frontend/components/ResourcesView.tsx`
- Liste aller Resources mit Filterung nach Environment
- CRUD-Operationen (Create, Read, Update, Delete)
- Anzeige von Resource-Typ, Status (enabled/disabled), MIME-Type
- Dialog für Resource-Erstellung/Bearbeitung
- Resource-Inhalt anzeigen (via MCP Fabric API)

#### `frontend/components/PromptsView.tsx`
- Liste aller Prompts mit Filterung nach Environment
- CRUD-Operationen (Create, Read, Update, Delete)
- Anzeige von Prompt-Name, Description, verwendete Resources
- Dialog für Prompt-Erstellung/Bearbeitung
- Prompt-Invoke-Funktionalität (via MCP Fabric API)

### 4. Dialog-Komponenten erstellen

#### `frontend/components/ResourceDialog.tsx`
- Formular für Resource-Erstellung/Bearbeitung
- Felder:
  - Name (required, max 120 chars)
  - Environment (Dropdown)
  - Type (Dropdown: static, http, sql, s3, file)
  - Config JSON (JSON-Editor, dynamisch je nach Type)
  - MIME Type (Text-Input, default: "application/json")
  - Schema JSON (optional, JSON-Editor)
  - Secret Ref (optional, Text-Input)
  - Enabled (Checkbox)
- Validierung:
  - Name muss unique sein pro (org, env)
  - Config JSON muss valides JSON sein
  - Schema JSON muss valides JSON Schema sein (falls angegeben)

#### `frontend/components/PromptDialog.tsx`
- Formular für Prompt-Erstellung/Bearbeitung
- Felder:
  - Name (required, max 120 chars)
  - Environment (Dropdown)
  - Description (Textarea)
  - Input Schema (JSON-Editor für JSON Schema)
  - Template System (Textarea, Jinja2-Template)
  - Template User (Textarea, Jinja2-Template)
  - Uses Resources (Multi-Select, Liste verfügbarer Resources)
  - Output Hints (optional, JSON-Editor)
  - Enabled (Checkbox)
- Validierung:
  - Name muss unique sein pro (org, env)
  - Input Schema muss valides JSON Schema sein
  - Templates sollten Jinja2-Syntax unterstützen (Syntax-Highlighting)

#### `frontend/components/PromptInvokeDialog.tsx`
- Dialog für Prompt-Ausführung
- Dynamisches Formular basierend auf `input_schema`
- Anzeige des gerenderten Prompts (System + User Message)
- Anzeige des Outputs nach Ausführung
- Fehlerbehandlung

### 5. Navigation erweitern

Erweitere `frontend/components/Sidebar.tsx` um:
- "Resources" Menüpunkt (Icon: Database/FileText)
- "Prompts" Menüpunkt (Icon: MessageSquare)

### 6. Routing erweitern

Erweitere die Routing-Konfiguration (vermutlich in `app/[locale]/...`) um:
- `/resources` → `ResourcesView`
- `/prompts` → `PromptsView`

### 7. TypeScript-Typen definieren

Erweitere oder erstelle `frontend/lib/types.ts`:

```typescript
export interface Resource {
  id: string;
  organization: Organization;
  environment: Environment;
  environment_id: string;
  name: string;
  type: "static" | "http" | "sql" | "s3" | "file";
  config_json: Record<string, any>;
  mime_type: string;
  schema_json?: Record<string, any> | null;
  secret_ref?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface Prompt {
  id: string;
  organization: Organization;
  environment: Environment;
  environment_id: string;
  name: string;
  description: string;
  input_schema: Record<string, any>;
  template_system: string;
  template_user: string;
  uses_resources: string[];
  output_hints?: Record<string, any> | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

// MCP Fabric Types
export interface MCPResource {
  uri: string;
  name: string;
  description?: string;
  mimeType: string;
}

export interface MCPResourceContent {
  uri: string;
  mimeType: string;
  text?: string;
  blob?: string;
}

export interface MCPPrompt {
  name: string;
  description?: string;
  arguments?: Array<{
    name: string;
    description?: string;
    required?: boolean;
  }>;
}

export interface MCPPromptResponse {
  messages: Array<{
    role: "user" | "assistant" | "system";
    content: string | Array<{ type: string; text: string }>;
  }>;
}
```

## Design-Richtlinien

### UI/UX
- Konsistent mit bestehenden Views (ToolsView, AgentsView, etc.)
- Verwendung von shadcn/ui Komponenten
- Responsive Design
- Loading States und Error Handling
- Toast-Notifications für Erfolg/Fehler

### Formular-Validierung
- Client-seitige Validierung mit react-hook-form + zod
- Server-seitige Fehler anzeigen
- JSON-Editoren für komplexe Felder (z.B. mit `react-json-view` oder `monaco-editor`)

### Fehlerbehandlung
- Netzwerk-Fehler abfangen
- 401/403/404/500 Fehler behandeln
- Benutzerfreundliche Fehlermeldungen
- Retry-Mechanismus für fehlgeschlagene Requests

## Implementierungsreihenfolge

1. **Backend:** DRF ViewSets für Resources und Prompts erstellen
2. **Frontend:** TypeScript-Typen definieren
3. **Frontend:** API-Client-Funktionen hinzufügen
4. **Frontend:** MCP Fabric Client erweitern
5. **Frontend:** Views erstellen (ResourcesView, PromptsView)
6. **Frontend:** Dialog-Komponenten erstellen
7. **Frontend:** Navigation und Routing erweitern
8. **Frontend:** Testing und Fehlerbehandlung

## Referenzen

- `frontend/components/MCPToolsView.tsx` - Beispiel für ähnliche Implementierung
- `frontend/components/ToolsView.tsx` - Beispiel für CRUD-View
- `frontend/components/ToolDialog.tsx` - Beispiel für Dialog-Komponente
- `backend/apps/mcp_ext/models.py` - Backend-Models
- `backend/apps/mcp_ext/serializers.py` - Backend-Serializers
- `backend/mcp_fabric/routes_resources.py` - MCP Fabric Resources API
- `backend/mcp_fabric/routes_prompts.py` - MCP Fabric Prompts API

## Wichtige Hinweise

1. **Environment-Filterung:** Alle Resources und Prompts sind an ein Environment gebunden. Die Views müssen nach dem aktuell ausgewählten Environment filtern.

2. **Policy-Integration:** Resources und Prompts unterliegen Policy-Checks. Die MCP Fabric API prüft automatisch, aber für CRUD-Operationen müssen die Policies im Frontend berücksichtigt werden.

3. **Secret-Referenzen:** `secret_ref` Felder sollten nicht im Klartext angezeigt werden. Nur die Referenz-ID anzeigen, nicht den tatsächlichen Secret-Wert.

4. **Jinja2-Templates:** Für Prompt-Templates sollte ein Editor mit Jinja2-Syntax-Highlighting verwendet werden (z.B. `monaco-editor` mit Jinja2-Sprachunterstützung).

5. **JSON Schema:** Input Schema und Output Hints sollten mit einem JSON Schema Editor validiert werden.

6. **Resource-Typen:** Je nach Resource-Typ (`static`, `http`, `sql`, `s3`, `file`) müssen unterschiedliche Config-Felder angezeigt werden. Implementiere eine dynamische Formular-Logik.

7. **Uses Resources:** Im Prompt-Dialog sollte eine Multi-Select-Dropdown mit verfügbaren Resources angezeigt werden (gefiltert nach Environment).

