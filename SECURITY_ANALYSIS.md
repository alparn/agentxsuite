# Sicherheitsanalyse: MCP Fabric Token-Management

## Aktuelle Implementierung

### 1. Token-Fallback-Mechanismus
**Problem**: `mcpFabric.ts` verwendet Fallback auf User Token wenn kein Agent Token vorhanden ist.

```typescript
private getHeaders(agentToken?: string | null): Record<string, string> {
  const token = agentToken || this.getAuthToken(); // ⚠️ Fallback auf User Token
  return {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}
```

**Sicherheitsrisiko**: 
- User Tokens sind Django Tokens (keine JWT), haben keine `sub`/`iss` Claims
- MCP Fabric API erwartet JWT mit `sub`/`iss` für Agent-Resolution
- `resolve_agent_from_token_claims()` wird fehlschlagen → `AGENT_NOT_FOUND` Fehler
- **Status**: Nicht kritisch, aber schlechte UX (unklarer Fehler)

### 2. Automatische Agent-Auswahl
**Problem**: Erster enabled Agent wird automatisch ausgewählt ohne Benutzerbestätigung.

```typescript
const defaultAgent = agents.find((a: any) => 
  a.enabled && 
  (a.is_axcore || a.tags?.includes("axcore")) &&
  (a.environment?.id === currentEnvId || a.environment_id === currentEnvId)
) || agents.find((a: any) => 
  a.enabled && 
  (a.environment?.id === currentEnvId || a.environment_id === currentEnvId)
);
```

**Sicherheitsrisiko**:
- Benutzer könnte unerwartet einen Agent mit anderen Berechtigungen verwenden
- Keine explizite Benutzerbestätigung
- **Status**: Mittel - Backend validiert Berechtigungen, aber UX könnte verwirrend sein

### 3. Token-Caching (30 Minuten)
**Problem**: Token wird 30 Minuten gecacht.

**Sicherheitsrisiko**:
- Wenn Agent-Berechtigungen geändert werden, wird alter Token weiter verwendet
- Token könnte ablaufen während Cache noch aktiv ist
- **Status**: Niedrig - Token hat eigene Expiry-Zeit, aber Cache könnte zu lange sein

### 4. Fehlerbehandlung
**Problem**: Wenn Token-Generierung fehlschlägt, wird `null` zurückgegeben ohne klaren Fehler.

```typescript
catch (error: any) {
  console.error("Failed to generate agent token:", error);
  return null; // ⚠️ Kein klarer Fehler für Benutzer
}
```

**Sicherheitsrisiko**:
- Benutzer sieht keine klare Fehlermeldung
- API Calls schlagen fehl mit unklaren Fehlern
- **Status**: Niedrig - UX-Problem, keine direkte Sicherheitslücke

## Empfohlene Verbesserungen

### 1. Fallback entfernen oder explizit machen
```typescript
private getHeaders(agentToken?: string | null): Record<string, string> {
  if (!agentToken) {
    throw new Error("Agent token required for MCP Fabric API calls");
  }
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${agentToken}`,
  };
}
```

### 2. Explizite Fehlerbehandlung
```typescript
const { data: tokenData, error: tokenError } = useQuery({
  // ...
});

useEffect(() => {
  if (tokenError) {
    // Zeige klare Fehlermeldung an
    setError("Failed to generate agent token. Please ensure agent has ServiceAccount configured.");
  }
}, [tokenError]);
```

### 3. Benutzer-Bestätigung für Agent-Auswahl (optional)
- Zeige Liste der verfügbaren Agents
- Benutzer wählt explizit Agent aus
- Oder: Zeige Warnung wenn Agent automatisch ausgewählt wird

### 4. Kürzeres Token-Caching
```typescript
staleTime: 5 * 60 * 1000, // 5 Minuten statt 30
```

### 5. Token-Validierung vor Verwendung
```typescript
// Prüfe ob Token noch gültig ist
const isTokenValid = (token: string): boolean => {
  try {
    const decoded = jwt.decode(token);
    if (!decoded || !decoded.exp) return false;
    return decoded.exp * 1000 > Date.now();
  } catch {
    return false;
  }
};
```

## Backend-Sicherheit (bereits implementiert)

✅ **Agent-Resolution**: Via `(subject, issuer)` Mapping - Source of Truth
✅ **Org/Env-Validierung**: Token `org_id`/`env_id` muss mit URL übereinstimmen
✅ **Scope-Validierung**: Token muss erforderliche Scopes haben
✅ **Session-Lock**: Agent kann nicht während Session geändert werden
✅ **Audit-Logging**: Alle Token-Verwendungen werden geloggt

## Fazit

**Aktuelle Lösung ist grundsätzlich sicher**, aber es gibt UX-Probleme:

1. ⚠️ **Fallback auf User Token**: Sollte entfernt werden - führt zu unklaren Fehlern
2. ⚠️ **Fehlerbehandlung**: Sollte verbessert werden - klare Fehlermeldungen für Benutzer
3. ✅ **Backend-Validierung**: Ist sicher implementiert
4. ⚠️ **Token-Caching**: Könnte kürzer sein (5 statt 30 Minuten)

**Priorität**: 
- **Hoch**: Fallback entfernen, Fehlerbehandlung verbessern
- **Mittel**: Token-Caching verkürzen
- **Niedrig**: Benutzer-Bestätigung für Agent-Auswahl

