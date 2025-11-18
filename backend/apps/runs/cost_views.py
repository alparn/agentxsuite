"""
Cost reporting API views.

Provides endpoints for cost analytics and reporting.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.runs.cost_services import (
    get_cost_summary_by_agent,
    get_cost_summary_by_environment,
    get_cost_summary_by_model,
    get_cost_summary_by_tool,
    get_organization_total_cost,
)
from apps.tenants.models import Organization

logger = logging.getLogger(__name__)


class CostReportViewSet(ViewSet):
    """
    ViewSet for cost reporting and analytics.
    
    Provides aggregated cost data by various dimensions:
    - Organization total
    - By agent
    - By environment
    - By model
    - By tool
    """
    
    def list(self, request, org_id=None):
        """
        Get organization-level cost summary.
        
        Query parameters:
        - environment: UUID (optional)
        - days: int (default: 30)
        
        Response:
        {
            "organization_id": "...",
            "total_cost": 84.25,
            "total_runs": 1250,
            "period_days": 30,
            ...
        }
        """
        if not org_id:
            return Response(
                {"error": "Organization ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Verify organization exists
        try:
            Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response(
                {"error": "Organization not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        environment_id = request.query_params.get("environment")
        days = int(request.query_params.get("days", 30))
        
        summary = get_organization_total_cost(
            organization_id=org_id,
            environment_id=environment_id,
            days=days,
        )
        
        return Response(summary)
    
    @action(detail=False, methods=["get"])
    def by_agent(self, request, org_id=None):
        """
        Get cost summary grouped by agent.
        
        Query parameters:
        - environment: UUID (optional)
        - days: int (default: 30)
        
        Response:
        [
            {
                "agent_id": "...",
                "agent__name": "SupportAgent",
                "total_cost": 41.50,
                "total_runs": 520,
                "total_tokens": 150000,
                ...
            },
            ...
        ]
        """
        if not org_id:
            return Response(
                {"error": "Organization ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        environment_id = request.query_params.get("environment")
        days = int(request.query_params.get("days", 30))
        
        results = get_cost_summary_by_agent(
            organization_id=org_id,
            environment_id=environment_id,
            days=days,
        )
        
        # Convert QuerySet to list and format Decimal fields
        data = []
        for item in results:
            data.append({
                "agent_id": str(item["agent_id"]),
                "agent_name": item["agent__name"],
                "total_cost": float(item["total_cost"] or 0),
                "total_runs": item["total_runs"] or 0,
                "total_tokens": item["total_tokens"] or 0,
                "total_input_tokens": item["total_input_tokens"] or 0,
                "total_output_tokens": item["total_output_tokens"] or 0,
            })
        
        return Response(data)
    
    @action(detail=False, methods=["get"])
    def by_environment(self, request, org_id=None):
        """
        Get cost summary grouped by environment.
        
        Query parameters:
        - days: int (default: 30)
        
        Response:
        [
            {
                "environment_id": "...",
                "environment__name": "production",
                "total_cost": 62.00,
                "total_runs": 850,
                ...
            },
            ...
        ]
        """
        if not org_id:
            return Response(
                {"error": "Organization ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        days = int(request.query_params.get("days", 30))
        
        results = get_cost_summary_by_environment(
            organization_id=org_id,
            days=days,
        )
        
        data = []
        for item in results:
            data.append({
                "environment_id": str(item["environment_id"]),
                "environment_name": item["environment__name"],
                "total_cost": float(item["total_cost"] or 0),
                "total_runs": item["total_runs"] or 0,
                "total_tokens": item["total_tokens"] or 0,
                "total_input_tokens": item["total_input_tokens"] or 0,
                "total_output_tokens": item["total_output_tokens"] or 0,
            })
        
        return Response(data)
    
    @action(detail=False, methods=["get"])
    def by_model(self, request, org_id=None):
        """
        Get cost summary grouped by model.
        
        Query parameters:
        - environment: UUID (optional)
        - days: int (default: 30)
        
        Response:
        [
            {
                "model_name": "gpt-4",
                "total_cost": 55.20,
                "total_runs": 320,
                ...
            },
            ...
        ]
        """
        if not org_id:
            return Response(
                {"error": "Organization ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        environment_id = request.query_params.get("environment")
        days = int(request.query_params.get("days", 30))
        
        results = get_cost_summary_by_model(
            organization_id=org_id,
            environment_id=environment_id,
            days=days,
        )
        
        data = []
        for item in results:
            data.append({
                "model_name": item["model_name"],
                "total_cost": float(item["total_cost"] or 0),
                "total_runs": item["total_runs"] or 0,
                "total_tokens": item["total_tokens"] or 0,
                "total_input_tokens": item["total_input_tokens"] or 0,
                "total_output_tokens": item["total_output_tokens"] or 0,
            })
        
        return Response(data)
    
    @action(detail=False, methods=["get"])
    def by_tool(self, request, org_id=None):
        """
        Get cost summary grouped by tool.
        
        Query parameters:
        - environment: UUID (optional)
        - days: int (default: 30)
        
        Response:
        [
            {
                "tool_id": "...",
                "tool__name": "database_query",
                "total_cost": 28.50,
                "total_runs": 450,
                ...
            },
            ...
        ]
        """
        if not org_id:
            return Response(
                {"error": "Organization ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        environment_id = request.query_params.get("environment")
        days = int(request.query_params.get("days", 30))
        
        results = get_cost_summary_by_tool(
            organization_id=org_id,
            environment_id=environment_id,
            days=days,
        )
        
        data = []
        for item in results:
            data.append({
                "tool_id": str(item["tool_id"]),
                "tool_name": item["tool__name"],
                "total_cost": float(item["total_cost"] or 0),
                "total_runs": item["total_runs"] or 0,
                "total_tokens": item["total_tokens"] or 0,
                "total_input_tokens": item["total_input_tokens"] or 0,
                "total_output_tokens": item["total_output_tokens"] or 0,
            })
        
        return Response(data)

