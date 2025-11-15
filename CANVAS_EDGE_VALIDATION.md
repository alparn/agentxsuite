# Canvas Edge Validation - Logische Verknüpfungen

Diese Dokumentation beschreibt, welche Modelle logisch miteinander verknüpft werden können basierend auf den Datenbankbeziehungen und Geschäftslogik.

## Übersicht der Modelle

1. **Organization** - Organisationseinheit
2. **Environment** - Umgebung (gehört zu Organization)
3. **Agent** - Agent (gehört zu Organization + Environment, optional Connection)
4. **Tool** - Tool (gehört zu Organization + Environment + Connection)
5. **Resource** - Resource (gehört zu Organization + Environment)
6. **Policy** - Policy (gehört zu Organization, optional Environment)
7. **Server/Connection** - MCP Server Verbindung (gehört zu Organization + Environment)

## Logische Verknüpfungen

### Agent → Tool (`agent-tool`)
**✅ Logisch**: Agent führt Tools aus
- **Backend-Beziehung**: `Run` Modell verbindet Agent und Tool
- **Verwendung**: Agent kann Tools über `start_run()` ausführen
- **Policy**: Policy prüft `is_allowed(agent, tool, payload)`

### Agent → Resource (`agent-resource`)
**✅ Logisch**: Agent greift auf Resources zu
- **Backend-Beziehung**: `is_allowed_resource(agent, resource_name, action)`
- **Verwendung**: Agent kann Resources lesen/schreiben

### Agent → Server (`agent-server`)
**✅ Logisch**: Agent läuft auf Server/Connection
- **Backend-Beziehung**: `Agent.connection` ForeignKey (optional)
- **Verwendung**: Agent kann mit einem MCP Server verbunden sein

### Agent → Environment (`agent-environment`)
**✅ Logisch**: Agent gehört zu Environment
- **Backend-Beziehung**: `Agent.environment` ForeignKey (required)
- **Verwendung**: Agent ist einer Umgebung zugeordnet

### Tool → Server (`tool-server`)
**✅ Logisch**: Tool kommt von Server/Connection
- **Backend-Beziehung**: `Tool.connection` ForeignKey (required)
- **Verwendung**: Tool gehört zu einem MCP Server

### Resource → Server (`resource-server`)
**⚠️ Teilweise logisch**: Resource kann von Server kommen
- **Backend-Beziehung**: Keine direkte FK, aber Resource kann über MCP Server bereitgestellt werden
- **Verwendung**: Resource kann von einem MCP Server stammen

### Policy → Agent (`policy-agent`)
**✅ Logisch**: Policy gilt für Agent
- **Backend-Beziehung**: `PolicyBinding` mit `scope_type="agent"`
- **Verwendung**: Policy kann auf spezifische Agents angewendet werden

### Policy → Tool (`policy-tool`)
**✅ Logisch**: Policy gilt für Tool
- **Backend-Beziehung**: `PolicyBinding` mit `scope_type="tool"`
- **Verwendung**: Policy kann auf spezifische Tools angewendet werden

### Policy → Server (`policy-server`)
**⚠️ Teilweise logisch**: Policy kann für Server gelten
- **Backend-Beziehung**: Keine direkte FK, aber Policy kann über Scope angewendet werden
- **Verwendung**: Policy kann auf Server/Connections angewendet werden

### Policy → Resource (`policy-resource`)
**✅ Logisch**: Policy gilt für Resource
- **Backend-Beziehung**: `PolicyBinding` mit `scope_type="resource_ns"`
- **Verwendung**: Policy kann auf Resource-Namespaces angewendet werden

### Environment → Server (`environment-server`)
**⚠️ Teilweise logisch**: Environment kann auf Server laufen
- **Backend-Beziehung**: Keine direkte FK
- **Verwendung**: Environment kann mit einem Server verbunden sein

### Organization → Environment (`organization-environment`)
**✅ Logisch**: Organization enthält Environment
- **Backend-Beziehung**: `Environment.organization` ForeignKey (required)
- **Verwendung**: Environment gehört zu einer Organization

## Nicht unterstützte Verknüpfungen

Folgende Verknüpfungen sind **nicht logisch** und werden nicht unterstützt:

- Tool → Agent (Richtung falsch, sollte Agent → Tool sein)
- Resource → Agent (Richtung falsch, sollte Agent → Resource sein)
- Server → Agent (Richtung falsch, sollte Agent → Server sein)
- Environment → Agent (Richtung falsch, sollte Agent → Environment sein)
- Server → Tool (Richtung falsch, sollte Tool → Server sein)
- Server → Resource (Richtung falsch, sollte Resource → Server sein)
- Agent → Policy (Richtung falsch, sollte Policy → Agent sein)
- Tool → Policy (Richtung falsch, sollte Policy → Tool sein)
- Resource → Policy (Richtung falsch, sollte Policy → Resource sein)
- Server → Policy (Richtung falsch, sollte Policy → Server sein)
- Environment → Organization (Richtung falsch, sollte Organization → Environment sein)
- Server → Environment (Richtung falsch, sollte Environment → Server sein)

## Implementierung

Die Validierung wird in `frontend/lib/canvasEdgeValidation.ts` implementiert:

- `isValidEdgeConnection()` - Prüft, ob eine Verknüpfung logisch ist
- `getValidEdgeTypes()` - Gibt gültige Edge-Typen für eine Verbindung zurück
- `getDefaultEdgeType()` - Gibt den Standard-Edge-Typ zurück
- `getValidTargetTypes()` - Gibt gültige Ziel-Typen für einen Quell-Typ zurück
- `getValidSourceTypes()` - Gibt gültige Quell-Typen für einen Ziel-Typ zurück

## Verwendung

Die Validierung wird automatisch angewendet bei:
- Manueller Edge-Erstellung (onConnect)
- Automatischer Edge-Erstellung beim Erstellen neuer Nodes
- Edge-Bearbeitung in der Edge-Sidebar

