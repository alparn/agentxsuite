# MCP Fabric Frontend Workflow

Dieses Dokument beschreibt den Workflow für die Frontend-Implementierung des MCP Fabric Services.

## Übersicht

MCP Fabric ist ein FastAPI-Service, der MCP-kompatible Endpoints bereitstellt. Das Frontend muss:

1. **MCP Tools auflisten** - Verfügbare Tools für eine Org/Env anzeigen
2. **Tools ausführen** - Tools über MCP-kompatible API aufrufen
3. **Ergebnisse anzeigen** - Run-Ergebnisse in MCP-Format darstellen
4. **Fehlerbehandlung** - Policy-Denials, Validierungsfehler, etc. behandeln

## Architektur

```
Frontend (Next.js)
    ↓
MCP Fabric API Client (lib/mcpFabric.ts)
    ↓
MCP Fabric Service (FastAPI auf Port 8090)
    ↓
Django Services (Policy, Validation, Rate Limit, Audit)
```

## 1. API Client Setup

### 1.1 Environment Variable

Ergänze `.env.local` oder `env.development.example`:

```env
NEXT_PUBLIC_MCP_FABRIC_URL=http://localhost:8090
```

### 1.2 MCP Fabric API Client

Erstelle `frontend/lib/mcpFabric.ts`:

```typescript
import axios from "axios";
import { useAuthStore } from "./store";

const MCP_FABRIC_URL = process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090";

// MCP Types
export interface MCPManifest {
  protocol_version: string;
  name: string;
  version: string;
  capabilities: Record<string, any>;
}

export interface MCPTool {
  name: string;
  description?: string;
  inputSchema: Record<string, any>;
}

export interface MCPToolsResponse {
  tools: MCPTool[];
}

export interface MCPRunRequest {
  name: string;
  arguments: Record<string, any>;
}

export interface MCPRunContent {
  type: string;
  text: string;
}

export interface MCPRunResponse {
  content: MCPRunContent[];
  isError: boolean;
}

// API Client
class MCPFabricClient {
  private getAuthToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("auth_token");
  }

  private getHeaders(): Record<string, string> {
    const token = this.getAuthToken();
    return {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    };
  }

  async getManifest(orgId: string, envId: string): Promise<MCPManifest> {
    const response = await axios.get<MCPManifest>(
      `${MCP_FABRIC_URL}/mcp/${orgId}/${envId}/.well-known/mcp/manifest.json`,
      { headers: this.getHeaders() }
    );
    return response.data;
  }

  async getTools(orgId: string, envId: string): Promise<MCPToolsResponse> {
    const response = await axios.get<MCPToolsResponse>(
      `${MCP_FABRIC_URL}/mcp/${orgId}/${envId}/.well-known/mcp/tools`,
      { headers: this.getHeaders() }
    );
    return response.data;
  }

  async runTool(
    orgId: string,
    envId: string,
    toolName: string,
    arguments: Record<string, any>
  ): Promise<MCPRunResponse> {
    const response = await axios.post<MCPRunResponse>(
      `${MCP_FABRIC_URL}/mcp/${orgId}/${envId}/.well-known/mcp/run`,
      { name: toolName, arguments },
      { headers: this.getHeaders() }
    );
    return response.data;
  }
}

export const mcpFabric = new MCPFabricClient();
```

## 2. Komponenten-Implementierung

### 2.1 MCP Tools View Komponente

Erstelle `frontend/components/MCPToolsView.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import { mcpFabric, MCPTool } from "@/lib/mcpFabric";
import { useAppStore } from "@/lib/store";

export function MCPToolsView() {
  const { currentOrgId, currentEnvId } = useAppStore();
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (currentOrgId && currentEnvId) {
      loadTools();
    }
  }, [currentOrgId, currentEnvId]);

  const loadTools = async () => {
    if (!currentOrgId || !currentEnvId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await mcpFabric.getTools(currentOrgId, currentEnvId);
      setTools(response.tools);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load tools");
    } finally {
      setLoading(false);
    }
  };

  if (!currentOrgId || !currentEnvId) {
    return (
      <div className="p-4 text-gray-500">
        Please select an organization and environment
      </div>
    );
  }

  if (loading) {
    return <div className="p-4">Loading tools...</div>;
  }

  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error: {error}
        <button onClick={loadTools} className="ml-2 underline">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">MCP Tools</h2>
      <div className="grid gap-4">
        {tools.map((tool) => (
          <MCPToolCard key={tool.name} tool={tool} />
        ))}
        {tools.length === 0 && (
          <div className="text-gray-500">No tools available</div>
        )}
      </div>
    </div>
  );
}

function MCPToolCard({ tool }: { tool: MCPTool }) {
  const { currentOrgId, currentEnvId } = useAppStore();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDialog, setShowDialog] = useState(false);

  const handleRun = async (args: Record<string, any>) => {
    if (!currentOrgId || !currentEnvId) return;

    setRunning(true);
    setError(null);
    setResult(null);

    try {
      const response = await mcpFabric.runTool(
        currentOrgId,
        currentEnvId,
        tool.name,
        args
      );

      if (response.isError) {
        setError(response.content[0]?.text || "Unknown error");
      } else {
        setResult(response.content[0]?.text || "Success");
      }
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Failed to execute tool"
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="border rounded-lg p-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-semibold text-lg">{tool.name}</h3>
          {tool.description && (
            <p className="text-gray-500 text-sm mt-1">{tool.description}</p>
          )}
        </div>
        <button
          onClick={() => setShowDialog(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          disabled={running}
        >
          {running ? "Running..." : "Run"}
        </button>
      </div>

      {showDialog && (
        <MCPToolRunDialog
          tool={tool}
          onRun={handleRun}
          onClose={() => {
            setShowDialog(false);
            setResult(null);
            setError(null);
          }}
          running={running}
          result={result}
          error={error}
        />
      )}
    </div>
  );
}
```

### 2.2 Tool Run Dialog

Erstelle `frontend/components/MCPToolRunDialog.tsx`:

```typescript
"use client";

import { useState } from "react";
import { MCPTool } from "@/lib/mcpFabric";

interface MCPToolRunDialogProps {
  tool: MCPTool;
  onRun: (args: Record<string, any>) => void;
  onClose: () => void;
  running: boolean;
  result: string | null;
  error: string | null;
}

export function MCPToolRunDialog({
  tool,
  onRun,
  onClose,
  running,
  result,
  error,
}: MCPToolRunDialogProps) {
  const [args, setArgs] = useState<Record<string, any>>({});

  // Parse JSON Schema to generate form fields
  const schema = tool.inputSchema || {};
  const properties = schema.properties || {};
  const required = schema.required || [];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun(args);
  };

  const updateArg = (key: string, value: any) => {
    setArgs((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4">Run Tool: {tool.name}</h2>

        {tool.description && (
          <p className="text-gray-500 mb-4">{tool.description}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {Object.entries(properties).map(([key, prop]: [string, any]) => (
            <div key={key}>
              <label className="block text-sm font-medium mb-1">
                {key}
                {required.includes(key) && (
                  <span className="text-red-500 ml-1">*</span>
                )}
              </label>
              <input
                type={getInputType(prop.type)}
                value={args[key] || ""}
                onChange={(e) => {
                  const value =
                    prop.type === "number"
                      ? parseFloat(e.target.value) || 0
                      : prop.type === "boolean"
                      ? e.target.checked
                      : e.target.value;
                  updateArg(key, value);
                }}
                className="w-full px-3 py-2 border rounded"
                required={required.includes(key)}
                placeholder={prop.description || key}
              />
              {prop.description && (
                <p className="text-xs text-gray-500 mt-1">{prop.description}</p>
              )}
            </div>
          ))}

          {Object.keys(properties).length === 0 && (
            <p className="text-gray-500">No parameters required</p>
          )}

          <div className="flex gap-2 justify-end mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border rounded"
              disabled={running}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              disabled={running}
            >
              {running ? "Running..." : "Run Tool"}
            </button>
          </div>
        </form>

        {result && (
          <div className="mt-4 p-4 bg-green-50 dark:bg-green-900 rounded">
            <h3 className="font-semibold mb-2">Result:</h3>
            <pre className="whitespace-pre-wrap text-sm">{result}</pre>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900 rounded">
            <h3 className="font-semibold mb-2">Error:</h3>
            <pre className="whitespace-pre-wrap text-sm">{error}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

function getInputType(schemaType: string): string {
  switch (schemaType) {
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "checkbox";
    case "string":
    default:
      return "text";
  }
}
```

## 3. Integration in bestehende Views

### 3.1 Tools View erweitern

Ergänze `frontend/components/ToolsView.tsx` um MCP Fabric Tab:

```typescript
// In ToolsView.tsx
import { MCPToolsView } from "./MCPToolsView";

// Füge Tab hinzu:
<Tabs>
  <TabsList>
    <TabsTrigger value="registry">Tool Registry</TabsTrigger>
    <TabsTrigger value="mcp">MCP Fabric</TabsTrigger>
  </TabsList>
  <TabsContent value="registry">
    {/* Existing tool registry view */}
  </TabsContent>
  <TabsContent value="mcp">
    <MCPToolsView />
  </TabsContent>
</Tabs>
```

### 3.2 Neue Route erstellen (Optional)

Erstelle `frontend/app/[locale]/mcp-fabric/page.tsx`:

```typescript
import { MCPToolsView } from "@/components/MCPToolsView";
import { AppLayout } from "@/components/layout-app";

export default function MCPFabricPage() {
  return (
    <AppLayout>
      <MCPToolsView />
    </AppLayout>
  );
}
```

## 4. Workflow-Diagramm

```
┌─────────────────┐
│  User wählt     │
│  Org/Env        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MCPToolsView   │
│  lädt Tools     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GET /mcp/.../  │
│  tools          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Tools werden   │
│  angezeigt      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User klickt    │
│  "Run"          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Dialog öffnet  │
│  (Formular)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User füllt     │
│  Parameter aus  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  POST /mcp/.../ │
│  run            │
└────────┬────────┘
         │
         ├──► Policy Denied → Error anzeigen
         ├──► Validation Error → Error anzeigen
         ├──► Rate Limit → Error anzeigen
         └──► Success → Ergebnis anzeigen
```

## 5. Fehlerbehandlung

### 5.1 Error Types

```typescript
// In mcpFabric.ts
export class MCPFabricError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code?: string
  ) {
    super(message);
    this.name = "MCPFabricError";
  }
}

// Error Handler
export function handleMCPError(error: any): string {
  if (error.response) {
    const status = error.response.status;
    const detail = error.response.data?.detail || "Unknown error";

    switch (status) {
      case 401:
        return "Authentication required. Please login again.";
      case 403:
        return `Access denied: ${detail}`;
      case 404:
        return `Not found: ${detail}`;
      case 408:
        return `Timeout: ${detail}`;
      case 429:
        return "Rate limit exceeded. Please try again later.";
      default:
        return `Error ${status}: ${detail}`;
    }
  }
  return "Network error. Please check your connection.";
}
```

### 5.2 Error Display Component

```typescript
export function MCPErrorDisplay({ error }: { error: string }) {
  return (
    <div className="p-4 bg-red-50 dark:bg-red-900 rounded-lg border border-red-200 dark:border-red-800">
      <div className="flex items-center gap-2">
        <AlertCircle className="w-5 h-5 text-red-600" />
        <span className="font-semibold text-red-800 dark:text-red-200">
          Error
        </span>
      </div>
      <p className="mt-2 text-red-700 dark:text-red-300">{error}</p>
    </div>
  );
}
```

## 6. Testing Workflow

### 6.1 Unit Tests

```typescript
// __tests__/mcpFabric.test.ts
import { mcpFabric } from "@/lib/mcpFabric";

describe("MCP Fabric Client", () => {
  it("should get manifest", async () => {
    const manifest = await mcpFabric.getManifest("org-id", "env-id");
    expect(manifest.protocol_version).toBe("2024-11-05");
  });

  it("should get tools", async () => {
    const response = await mcpFabric.getTools("org-id", "env-id");
    expect(response.tools).toBeInstanceOf(Array);
  });
});
```

### 6.2 Integration Tests

```typescript
// __tests__/MCPToolsView.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MCPToolsView } from "@/components/MCPToolsView";

describe("MCPToolsView", () => {
  it("should load and display tools", async () => {
    render(<MCPToolsView />);
    await waitFor(() => {
      expect(screen.getByText("MCP Tools")).toBeInTheDocument();
    });
  });
});
```

## 7. UI/UX Überlegungen

### 7.1 Loading States

- Skeleton Loader während Tool-Liste lädt
- Spinner während Tool-Ausführung
- Disabled Buttons während Operationen

### 7.2 Success Feedback

- Toast-Notification bei erfolgreicher Ausführung
- Ergebnis-Highlighting
- Copy-to-Clipboard für Ergebnisse

### 7.3 Error Feedback

- Inline-Errors bei Validierungsfehlern
- Toast-Notifications bei API-Fehlern
- Retry-Buttons bei temporären Fehlern

## 8. Implementierungsreihenfolge

1. ✅ **API Client** (`lib/mcpFabric.ts`)
   - Basis-Client mit Auth
   - Error Handling

2. ✅ **MCP Tools View** (`components/MCPToolsView.tsx`)
   - Tool-Liste anzeigen
   - Loading/Error States

3. ✅ **Tool Run Dialog** (`components/MCPToolRunDialog.tsx`)
   - JSON Schema → Formular
   - Parameter-Eingabe
   - Ergebnis-Anzeige

4. ✅ **Integration**
   - In ToolsView integrieren
   - Routing (optional)

5. ✅ **Error Handling**
   - Error-Komponenten
   - User-freundliche Meldungen

6. ✅ **Testing**
   - Unit Tests
   - Integration Tests

7. ✅ **Polish**
   - Loading States
   - Success Feedback
   - Error Recovery

## 9. Beispiel-Nutzung

```typescript
// In einer Komponente
import { mcpFabric } from "@/lib/mcpFabric";
import { useAppStore } from "@/lib/store";

function MyComponent() {
  const { currentOrgId, currentEnvId } = useAppStore();

  const handleRunTool = async () => {
    try {
      const result = await mcpFabric.runTool(
        currentOrgId!,
        currentEnvId!,
        "my-tool",
        { param1: "value1" }
      );
      console.log("Result:", result);
    } catch (error) {
      console.error("Error:", error);
    }
  };

  return <button onClick={handleRunTool}>Run Tool</button>;
}
```

## 10. Checkliste

- [ ] Environment Variable `NEXT_PUBLIC_MCP_FABRIC_URL` gesetzt
- [ ] `lib/mcpFabric.ts` erstellt
- [ ] `components/MCPToolsView.tsx` erstellt
- [ ] `components/MCPToolRunDialog.tsx` erstellt
- [ ] Error Handling implementiert
- [ ] Integration in ToolsView
- [ ] Tests geschrieben
- [ ] Loading States implementiert
- [ ] Error Messages user-freundlich
- [ ] Dokumentation aktualisiert

## 11. Nächste Schritte

Nach der Basis-Implementierung:

1. **WebSocket Support** - Live-Updates für Run-Status
2. **Tool History** - Letzte Ausführungen anzeigen
3. **Tool Favoriten** - Häufig genutzte Tools markieren
4. **Batch Execution** - Mehrere Tools gleichzeitig ausführen
5. **Result Export** - Ergebnisse als JSON/CSV exportieren

