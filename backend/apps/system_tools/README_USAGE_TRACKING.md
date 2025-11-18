# Token Usage Tracking für System Tools

## Übersicht

AgentxSuite kann automatisch Token-Usage und Kosten für Tool-Ausführungen tracken. Dies ist besonders wichtig für:
- **Budget-Management**: Überwachung der LLM-Ausgaben pro Agent/Tool/Org
- **Cost Analytics**: Detaillierte Kostenaufstellung nach Model, Environment, etc.
- **Usage Insights**: Verstehen, welche Tools die meisten Tokens verbrauchen

## Wie funktioniert es?

Nach jeder erfolgreichen Tool-Ausführung prüft `apps.runs.services.start_run()`:
1. Ob die Tool-Response ein `usage` oder `token_usage` Feld enthält
2. Falls ja, wird `apps.runs.cost_services.update_run_with_usage()` aufgerufen
3. Token-Counts und Kosten werden im `Run`-Objekt gespeichert

## System Tool Handler: Usage liefern

Wenn dein System-Tool intern einen LLM aufruft (z.B. OpenAI, Anthropic, etc.), solltest du die Usage-Daten im Response mitliefern:

### Format

```python
{
    "status": "success",
    # ... andere Response-Felder ...
    "usage": {
        "input_tokens": 183,        # oder "prompt_tokens"
        "output_tokens": 42,        # oder "completion_tokens"
        "total_tokens": 225,        # optional, wird berechnet falls fehlt
        "model": "gpt-4-turbo"      # oder "model_name"
    }
}
```

**Unterstützte Feld-Namen:**
- `input_tokens` oder `prompt_tokens`
- `output_tokens` oder `completion_tokens`
- `model` oder `model_name`

### Beispiel: System Tool mit OpenAI

```python
def analyze_text_with_llm_handler(
    organization_id: str,
    environment_id: str,
    text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Analysiert Text mit einem LLM."""
    import openai
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "Du bist ein Text-Analyst."},
                {"role": "user", "content": text}
            ]
        )
        
        analysis_result = response.choices[0].message.content
        
        # Usage-Daten aus OpenAI Response extrahieren
        usage_data = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "model": response.model
        }
        
        return {
            "status": "success",
            "analysis": analysis_result,
            "usage": usage_data  # ← Wichtig: Usage mitliefern!
        }
    except Exception as e:
        return {
            "status": "error",
            "error": "llm_error",
            "error_description": str(e)
        }
```

### Beispiel: System Tool mit Anthropic Claude

```python
def summarize_with_claude_handler(
    organization_id: str,
    environment_id: str,
    document: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Erstellt Zusammenfassung mit Claude."""
    import anthropic
    
    client = anthropic.Anthropic()
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": document}]
        )
        
        summary = response.content[0].text
        
        # Usage-Daten aus Anthropic Response extrahieren
        usage_data = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": "claude-3-5-sonnet-20241022"
        }
        
        return {
            "status": "success",
            "summary": summary,
            "usage": usage_data  # ← Wichtig: Usage mitliefern!
        }
    except Exception as e:
        return {
            "status": "error",
            "error": "llm_error",
            "error_description": str(e)
        }
```

## Externe MCP-Server: Usage liefern

Wenn du einen **externen MCP-Server** entwickelst, der von AgentxSuite aufgerufen wird:

### HTTP-Response Format

```json
{
    "status": "success",
    "output": "...",
    "usage": {
        "input_tokens": 183,
        "output_tokens": 42,
        "model": "gpt-4-turbo"
    }
}
```

AgentxSuite extrahiert automatisch das `usage`-Feld aus der Response.

## Cost Calculation

Sobald Usage-Daten vorhanden sind:
1. AgentxSuite sucht in der `ModelPricing`-Tabelle nach dem Model
2. Berechnet: `cost_input = (input_tokens / 1000) * input_cost_per_1k`
3. Berechnet: `cost_output = (output_tokens / 1000) * output_cost_per_1k`
4. Speichert alle Werte im `Run`-Objekt

### Model Pricing verwalten

Preise können verwaltet werden über:
- **Management Command**: `python manage.py load_model_pricing --update`
- **Django Admin**: `/admin/runs/modelpricing/`
- **API**: `POST /api/v1/runs/model-pricing/`

## Best Practices

1. **Immer Usage liefern, wenn LLM verwendet**: Auch wenn es "nur" eine kleine Anfrage ist
2. **Model-Name exakt angeben**: Verwende den offiziellen Model-Namen (z.B. `gpt-4-turbo`, nicht `gpt4`)
3. **Fehler nicht verschlucken**: Wenn LLM-Call fehlschlägt, gib trotzdem partielles Usage zurück (falls verfügbar)
4. **Performance**: Usage-Extraktion ist optional und wirft keine Fehler bei Problemen

## Debugging

Falls Usage nicht erfasst wird:
1. Prüfe `Run.output_json` in der DB – enthält es `usage` oder `token_usage`?
2. Prüfe `Run` Steps: Es sollte einen Step "Extracting token usage..." geben
3. Falls Cost = 0: Prüfe ob Model in `ModelPricing` vorhanden ist
4. Logs: `logger.warning` falls Cost-Berechnung fehlschlägt

## Frontend: Cost anzeigen

Kosten werden automatisch in der UI angezeigt:
- **Run Detail View**: Zeigt `cost_total`, `input_tokens`, `output_tokens`
- **Cost Analytics Dashboard**: `/cost-analytics` (geplant)
- **Agent Budget**: In Agent-Detail, Budget vs. tatsächliche Kosten

## Zusammenfassung

**Für System-Tool-Entwickler:**
```python
return {
    "status": "success",
    "result": "...",
    "usage": {
        "input_tokens": ...,
        "output_tokens": ...,
        "model": "..."
    }
}
```

**Für externe MCP-Server:**
- Gleiches Format im HTTP-Response
- AgentxSuite extrahiert automatisch

**Ergebnis:**
- Automatische Token-Tracking
- Automatische Cost-Berechnung
- Budget-Management
- Analytics & Insights

