# Token Usage Tracking for System Tools

## Overview

AgentxSuite can automatically track token usage and costs for tool executions. This is particularly important for:
- **Budget Management**: Monitor LLM spending per Agent/Tool/Organization
- **Cost Analytics**: Detailed cost breakdown by Model, Environment, etc.
- **Usage Insights**: Understand which tools consume the most tokens

## How It Works

After each successful tool execution, `apps.runs.services.start_run()`:
1. Checks if the tool response contains a `usage` or `token_usage` field
2. If yes, calls `apps.runs.cost_services.update_run_with_usage()`
3. Saves token counts and costs in the `Run` object

## System Tool Handlers: Returning Usage Data

If your system tool internally calls an LLM (e.g., OpenAI, Anthropic, etc.), you should include usage data in the response:

### Format

```python
{
    "status": "success",
    # ... other response fields ...
    "usage": {
        "input_tokens": 183,        # or "prompt_tokens"
        "output_tokens": 42,        # or "completion_tokens"
        "total_tokens": 225,        # optional, calculated if missing
        "model": "gpt-4-turbo"      # or "model_name"
    }
}
```

**Supported Field Names:**
- `input_tokens` or `prompt_tokens`
- `output_tokens` or `completion_tokens`
- `model` or `model_name`

### Example: System Tool with OpenAI

```python
def analyze_text_with_llm_handler(
    organization_id: str,
    environment_id: str,
    text: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Analyzes text using an LLM."""
    import openai
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a text analyst."},
                {"role": "user", "content": text}
            ]
        )
        
        analysis_result = response.choices[0].message.content
        
        # Extract usage data from OpenAI response
        usage_data = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "model": response.model
        }
        
        return {
            "status": "success",
            "analysis": analysis_result,
            "usage": usage_data  # ← Important: Include usage!
        }
    except Exception as e:
        return {
            "status": "error",
            "error": "llm_error",
            "error_description": str(e)
        }
```

### Example: System Tool with Anthropic Claude

```python
def summarize_with_claude_handler(
    organization_id: str,
    environment_id: str,
    document: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Creates summary using Claude."""
    import anthropic
    
    client = anthropic.Anthropic()
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": document}]
        )
        
        summary = response.content[0].text
        
        # Extract usage data from Anthropic response
        usage_data = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": "claude-3-5-sonnet-20241022"
        }
        
        return {
            "status": "success",
            "summary": summary,
            "usage": usage_data  # ← Important: Include usage!
        }
    except Exception as e:
        return {
            "status": "error",
            "error": "llm_error",
            "error_description": str(e)
        }
```

## External MCP Servers: Returning Usage Data

If you develop an **external MCP server** that is called by AgentxSuite:

### HTTP Response Format

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

AgentxSuite automatically extracts the `usage` field from the response.

## Cost Calculation

Once usage data is available:
1. AgentxSuite looks up the model in the `ModelPricing` table
2. Calculates: `cost_input = (input_tokens / 1000) * input_cost_per_1k`
3. Calculates: `cost_output = (output_tokens / 1000) * output_cost_per_1k`
4. Saves all values in the `Run` object

### Managing Model Pricing

Prices can be managed via:
- **Management Command**: `python manage.py load_model_pricing --update`
- **Django Admin**: `/admin/runs/modelpricing/`
- **API**: `POST /api/v1/runs/model-pricing/`

## Best Practices

1. **Always return usage when using LLMs**: Even for small requests
2. **Provide exact model names**: Use official model names (e.g., `gpt-4-turbo`, not `gpt4`)
3. **Don't swallow errors**: If LLM call fails, still return partial usage if available
4. **Performance**: Usage extraction is optional and won't throw errors on failure

## Debugging

If usage is not being captured:
1. Check `Run.output_json` in DB – does it contain `usage` or `token_usage`?
2. Check `Run` steps: There should be a "Extracting token usage..." step
3. If cost = 0: Check if model exists in `ModelPricing`
4. Logs: `logger.warning` if cost calculation fails

## Frontend: Displaying Costs

Costs are automatically displayed in the UI:
- **Run Detail View**: Shows `cost_total`, `input_tokens`, `output_tokens`
- **Cost Analytics Dashboard**: `/cost-analytics` (planned)
- **Agent Budget**: In agent detail, budget vs. actual costs

## Summary

**For System Tool Developers:**
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

**For External MCP Servers:**
- Same format in HTTP response
- AgentxSuite extracts automatically

**Result:**
- Automatic token tracking
- Automatic cost calculation
- Budget management
- Analytics & insights
