"""
Cost calculation services for runs.

Handles token tracking and cost calculation based on model pricing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone

from apps.runs.models import ModelPricing, Run

logger = logging.getLogger(__name__)


def get_model_pricing(model_name: str, at_time: datetime | None = None) -> ModelPricing | None:
    """
    Get pricing for a model at a specific time.
    
    Args:
        model_name: Model identifier (e.g., 'gpt-4', 'claude-3-opus')
        at_time: Time to get pricing for (defaults to now)
    
    Returns:
        ModelPricing instance or None if not found
    """
    if at_time is None:
        at_time = timezone.now()
    
    try:
        # Get the most recent pricing that was effective at the given time
        return ModelPricing.objects.filter(
            model_name=model_name,
            effective_from__lte=at_time,
            is_active=True,
        ).order_by("-effective_from").first()
    except ModelPricing.DoesNotExist:
        logger.warning(f"No pricing found for model '{model_name}'")
        return None


def calculate_run_cost(
    run: Run,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model_name: str = "",
) -> dict[str, Decimal]:
    """
    Calculate cost for a run based on token usage and model pricing.
    
    Args:
        run: Run instance
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed
        model_name: Model identifier (e.g., 'gpt-4')
    
    Returns:
        Dictionary with cost breakdown:
        {
            "cost_input": Decimal,
            "cost_output": Decimal,
            "cost_total": Decimal,
            "currency": str,
        }
    """
    # Get pricing for the model
    pricing = get_model_pricing(model_name, at_time=run.started_at or timezone.now())
    
    if not pricing:
        logger.warning(
            f"No pricing found for model '{model_name}' - "
            f"run {run.id} will have zero cost"
        )
        return {
            "cost_input": Decimal("0.000000"),
            "cost_output": Decimal("0.000000"),
            "cost_total": Decimal("0.000000"),
            "currency": "USD",
        }
    
    # Calculate costs (per 1000 tokens)
    cost_input = (Decimal(input_tokens) / Decimal(1000)) * pricing.input_cost_per_1k
    cost_output = (Decimal(output_tokens) / Decimal(1000)) * pricing.output_cost_per_1k
    cost_total = cost_input + cost_output
    
    # Round to 6 decimal places
    cost_input = cost_input.quantize(Decimal("0.000001"))
    cost_output = cost_output.quantize(Decimal("0.000001"))
    cost_total = cost_total.quantize(Decimal("0.000001"))
    
    logger.info(
        f"Cost calculated for run {run.id}: "
        f"{input_tokens} input + {output_tokens} output tokens = "
        f"${cost_total} ({model_name})"
    )
    
    return {
        "cost_input": cost_input,
        "cost_output": cost_output,
        "cost_total": cost_total,
        "currency": pricing.currency,
    }


def update_run_with_usage(
    run: Run,
    usage: dict[str, Any],
    save: bool = True,
) -> Run:
    """
    Update a run with token usage and calculate costs.
    
    Expected usage format (from MCP/LLM response):
    {
        "prompt_tokens": int,      # or "input_tokens"
        "completion_tokens": int,  # or "output_tokens"
        "total_tokens": int,
        "model": str,              # or "model_name"
    }
    
    Args:
        run: Run instance to update
        usage: Usage dictionary from LLM response
        save: Whether to save the run after updating
    
    Returns:
        Updated Run instance
    """
    # Extract token counts (support multiple field names)
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
    total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
    model_name = usage.get("model", usage.get("model_name", ""))
    
    # Update token fields
    run.input_tokens = input_tokens
    run.output_tokens = output_tokens
    run.total_tokens = total_tokens
    run.model_name = model_name
    
    # Calculate and update costs
    if model_name:
        costs = calculate_run_cost(
            run=run,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model_name,
        )
        run.cost_input = costs["cost_input"]
        run.cost_output = costs["cost_output"]
        run.cost_total = costs["cost_total"]
        run.cost_currency = costs["currency"]
    
    if save:
        run.save(update_fields=[
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "model_name",
            "cost_input",
            "cost_output",
            "cost_total",
            "cost_currency",
        ])
    
    return run


def get_cost_summary_by_agent(
    organization_id: str,
    environment_id: str | None = None,
    days: int = 30,
) -> QuerySet:
    """
    Get cost summary grouped by agent.
    
    Args:
        organization_id: Organization UUID
        environment_id: Optional environment UUID to filter by
        days: Number of days to look back (default: 30)
    
    Returns:
        QuerySet with aggregated costs per agent
    """
    start_date = timezone.now() - timedelta(days=days)
    
    queryset = Run.objects.filter(
        organization_id=organization_id,
        created_at__gte=start_date,
    ).values(
        "agent_id",
        "agent__name",
    ).annotate(
        total_cost=Sum("cost_total"),
        total_runs=Count("id"),
        total_tokens=Sum("total_tokens"),
        total_input_tokens=Sum("input_tokens"),
        total_output_tokens=Sum("output_tokens"),
    ).order_by("-total_cost")
    
    if environment_id:
        queryset = queryset.filter(environment_id=environment_id)
    
    return queryset


def get_cost_summary_by_environment(
    organization_id: str,
    days: int = 30,
) -> QuerySet:
    """
    Get cost summary grouped by environment.
    
    Args:
        organization_id: Organization UUID
        days: Number of days to look back (default: 30)
    
    Returns:
        QuerySet with aggregated costs per environment
    """
    start_date = timezone.now() - timedelta(days=days)
    
    return Run.objects.filter(
        organization_id=organization_id,
        created_at__gte=start_date,
    ).values(
        "environment_id",
        "environment__name",
    ).annotate(
        total_cost=Sum("cost_total"),
        total_runs=Count("id"),
        total_tokens=Sum("total_tokens"),
        total_input_tokens=Sum("input_tokens"),
        total_output_tokens=Sum("output_tokens"),
    ).order_by("-total_cost")


def get_cost_summary_by_model(
    organization_id: str,
    environment_id: str | None = None,
    days: int = 30,
) -> QuerySet:
    """
    Get cost summary grouped by model.
    
    Args:
        organization_id: Organization UUID
        environment_id: Optional environment UUID to filter by
        days: Number of days to look back (default: 30)
    
    Returns:
        QuerySet with aggregated costs per model
    """
    start_date = timezone.now() - timedelta(days=days)
    
    queryset = Run.objects.filter(
        organization_id=organization_id,
        created_at__gte=start_date,
        model_name__isnull=False,
    ).exclude(
        model_name="",
    ).values(
        "model_name",
    ).annotate(
        total_cost=Sum("cost_total"),
        total_runs=Count("id"),
        total_tokens=Sum("total_tokens"),
        total_input_tokens=Sum("input_tokens"),
        total_output_tokens=Sum("output_tokens"),
    ).order_by("-total_cost")
    
    if environment_id:
        queryset = queryset.filter(environment_id=environment_id)
    
    return queryset


def get_cost_summary_by_tool(
    organization_id: str,
    environment_id: str | None = None,
    days: int = 30,
) -> QuerySet:
    """
    Get cost summary grouped by tool.
    
    Args:
        organization_id: Organization UUID
        environment_id: Optional environment UUID to filter by
        days: Number of days to look back (default: 30)
    
    Returns:
        QuerySet with aggregated costs per tool
    """
    start_date = timezone.now() - timedelta(days=days)
    
    queryset = Run.objects.filter(
        organization_id=organization_id,
        created_at__gte=start_date,
    ).values(
        "tool_id",
        "tool__name",
    ).annotate(
        total_cost=Sum("cost_total"),
        total_runs=Count("id"),
        total_tokens=Sum("total_tokens"),
        total_input_tokens=Sum("input_tokens"),
        total_output_tokens=Sum("output_tokens"),
    ).order_by("-total_cost")
    
    if environment_id:
        queryset = queryset.filter(environment_id=environment_id)
    
    return queryset


def get_organization_total_cost(
    organization_id: str,
    environment_id: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """
    Get total cost for an organization.
    
    Args:
        organization_id: Organization UUID
        environment_id: Optional environment UUID to filter by
        days: Number of days to look back (default: 30)
    
    Returns:
        Dictionary with total cost and breakdown
    """
    start_date = timezone.now() - timedelta(days=days)
    
    queryset = Run.objects.filter(
        organization_id=organization_id,
        created_at__gte=start_date,
    )
    
    if environment_id:
        queryset = queryset.filter(environment_id=environment_id)
    
    aggregates = queryset.aggregate(
        total_cost=Sum("cost_total"),
        total_cost_input=Sum("cost_input"),
        total_cost_output=Sum("cost_output"),
        total_runs=Count("id"),
        total_tokens=Sum("total_tokens"),
        total_input_tokens=Sum("input_tokens"),
        total_output_tokens=Sum("output_tokens"),
        successful_runs=Count("id", filter=Q(status="succeeded")),
        failed_runs=Count("id", filter=Q(status="failed")),
    )
    
    return {
        "organization_id": organization_id,
        "environment_id": environment_id,
        "period_days": days,
        "start_date": start_date.isoformat(),
        "end_date": timezone.now().isoformat(),
        "total_cost": float(aggregates["total_cost"] or 0),
        "total_cost_input": float(aggregates["total_cost_input"] or 0),
        "total_cost_output": float(aggregates["total_cost_output"] or 0),
        "total_runs": aggregates["total_runs"] or 0,
        "successful_runs": aggregates["successful_runs"] or 0,
        "failed_runs": aggregates["failed_runs"] or 0,
        "total_tokens": aggregates["total_tokens"] or 0,
        "total_input_tokens": aggregates["total_input_tokens"] or 0,
        "total_output_tokens": aggregates["total_output_tokens"] or 0,
        "currency": "USD",
    }

