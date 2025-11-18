"""
Tests for cost tracking and calculation.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone
from model_bakery import baker

from apps.agents.models import InboundAuthMethod
from apps.runs.cost_services import (
    calculate_run_cost,
    get_cost_summary_by_agent,
    get_cost_summary_by_environment,
    get_cost_summary_by_model,
    get_cost_summary_by_tool,
    get_model_pricing,
    get_organization_total_cost,
    update_run_with_usage,
)
from apps.runs.models import ModelPricing, Run


@pytest.fixture
def org_and_env(db):
    """Create test organization and environment."""
    org = baker.make("tenants.Organization", name="TestOrg")
    env = baker.make(
        "tenants.Environment",
        organization=org,
        name="production",
    )
    return org, env


@pytest.fixture
def connection(org_and_env, db):
    """Create shared test connection."""
    org, env = org_and_env
    return baker.make(
        "connections.Connection",
        organization=org,
        environment=env,
        name="test-connection",
        endpoint="https://example.com",
        auth_method="none",
    )


@pytest.fixture
def agent(org_and_env, connection, db):
    """Create test agent."""
    org, env = org_and_env
    return baker.make(
        "agents.Agent",
        organization=org,
        environment=env,
        connection=connection,
        name="TestAgent",
        slug="test-agent",
        enabled=True,
        inbound_auth_method=InboundAuthMethod.NONE,
        capabilities=[],
        tags=[],
    )


@pytest.fixture
def tool(org_and_env, connection, db):
    """Create test tool."""
    org, env = org_and_env
    return baker.make(
        "tools.Tool",
        organization=org,
        environment=env,
        connection=connection,
        name="test_tool",
        schema_json={"type": "object"},
        sync_status="synced",
        enabled=True,
    )


@pytest.fixture
def gpt4_pricing(db):
    """Create GPT-4 pricing."""
    return baker.make(
        ModelPricing,
        model_name="gpt-4",
        provider="openai",
        input_cost_per_1k=Decimal("0.030000"),
        output_cost_per_1k=Decimal("0.060000"),
        currency="USD",
        is_active=True,
    )


@pytest.fixture
def claude_pricing(db):
    """Create Claude pricing."""
    return baker.make(
        ModelPricing,
        model_name="claude-3-opus",
        provider="anthropic",
        input_cost_per_1k=Decimal("0.015000"),
        output_cost_per_1k=Decimal("0.075000"),
        currency="USD",
        is_active=True,
    )


@pytest.mark.django_db
class TestModelPricing:
    """Tests for ModelPricing model and retrieval."""
    
    def test_get_model_pricing(self, gpt4_pricing):
        """Test retrieving pricing for a model."""
        pricing = get_model_pricing("gpt-4")
        assert pricing is not None
        assert pricing.model_name == "gpt-4"
        assert pricing.provider == "openai"
        assert pricing.input_cost_per_1k == Decimal("0.030000")
        assert pricing.output_cost_per_1k == Decimal("0.060000")
    
    def test_get_model_pricing_not_found(self):
        """Test retrieving pricing for non-existent model."""
        pricing = get_model_pricing("nonexistent-model")
        assert pricing is None
    
    def test_get_model_pricing_inactive(self, gpt4_pricing):
        """Test that inactive pricing is not returned."""
        gpt4_pricing.is_active = False
        gpt4_pricing.save()
        
        pricing = get_model_pricing("gpt-4")
        assert pricing is None
    
    def test_get_model_pricing_versioning(self, db):
        """Test that most recent pricing is returned."""
        # Create two pricing entries for same model
        old_pricing = baker.make(
            ModelPricing,
            model_name="gpt-4",
            provider="openai",
            input_cost_per_1k=Decimal("0.020000"),
            output_cost_per_1k=Decimal("0.040000"),
            is_active=True,
        )
        # Make old pricing older
        old_pricing.effective_from = timezone.now() - timezone.timedelta(days=30)
        old_pricing.save()
        
        new_pricing = baker.make(
            ModelPricing,
            model_name="gpt-4",
            provider="openai",
            input_cost_per_1k=Decimal("0.030000"),
            output_cost_per_1k=Decimal("0.060000"),
            is_active=True,
        )
        
        pricing = get_model_pricing("gpt-4")
        assert pricing.id == new_pricing.id
        assert pricing.input_cost_per_1k == Decimal("0.030000")


@pytest.mark.django_db
class TestCostCalculation:
    """Tests for cost calculation logic."""
    
    def test_calculate_run_cost_gpt4(self, agent, tool, gpt4_pricing):
        """Test cost calculation for GPT-4."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        costs = calculate_run_cost(
            run=run,
            input_tokens=1000,
            output_tokens=500,
            model_name="gpt-4",
        )
        
        # 1000 tokens * 0.03 / 1000 = 0.03
        assert costs["cost_input"] == Decimal("0.030000")
        # 500 tokens * 0.06 / 1000 = 0.03
        assert costs["cost_output"] == Decimal("0.030000")
        # Total = 0.06
        assert costs["cost_total"] == Decimal("0.060000")
        assert costs["currency"] == "USD"
    
    def test_calculate_run_cost_claude(self, agent, tool, claude_pricing):
        """Test cost calculation for Claude."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        costs = calculate_run_cost(
            run=run,
            input_tokens=2000,
            output_tokens=1000,
            model_name="claude-3-opus",
        )
        
        # 2000 tokens * 0.015 / 1000 = 0.03
        assert costs["cost_input"] == Decimal("0.030000")
        # 1000 tokens * 0.075 / 1000 = 0.075
        assert costs["cost_output"] == Decimal("0.075000")
        # Total = 0.105
        assert costs["cost_total"] == Decimal("0.105000")
    
    def test_calculate_run_cost_no_pricing(self, agent, tool):
        """Test cost calculation when pricing not found."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        costs = calculate_run_cost(
            run=run,
            input_tokens=1000,
            output_tokens=500,
            model_name="unknown-model",
        )
        
        # Should return zero costs
        assert costs["cost_input"] == Decimal("0.000000")
        assert costs["cost_output"] == Decimal("0.000000")
        assert costs["cost_total"] == Decimal("0.000000")
    
    def test_calculate_run_cost_zero_tokens(self, agent, tool, gpt4_pricing):
        """Test cost calculation with zero tokens."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        costs = calculate_run_cost(
            run=run,
            input_tokens=0,
            output_tokens=0,
            model_name="gpt-4",
        )
        
        assert costs["cost_input"] == Decimal("0.000000")
        assert costs["cost_output"] == Decimal("0.000000")
        assert costs["cost_total"] == Decimal("0.000000")


@pytest.mark.django_db
class TestUpdateRunWithUsage:
    """Tests for updating runs with usage data."""
    
    def test_update_run_with_usage(self, agent, tool, gpt4_pricing):
        """Test updating run with usage data."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "model": "gpt-4",
        }
        
        updated_run = update_run_with_usage(run, usage, save=True)
        
        assert updated_run.input_tokens == 1000
        assert updated_run.output_tokens == 500
        assert updated_run.total_tokens == 1500
        assert updated_run.model_name == "gpt-4"
        assert updated_run.cost_total == Decimal("0.060000")
    
    def test_update_run_with_usage_alternative_fields(self, agent, tool, gpt4_pricing):
        """Test updating run with alternative field names."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "model_name": "gpt-4",
        }
        
        updated_run = update_run_with_usage(run, usage, save=True)
        
        assert updated_run.input_tokens == 1000
        assert updated_run.output_tokens == 500
        assert updated_run.total_tokens == 1500
        assert updated_run.model_name == "gpt-4"
    
    def test_update_run_without_save(self, agent, tool, gpt4_pricing):
        """Test updating run without saving."""
        run = baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
        )
        
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "model": "gpt-4",
        }
        
        updated_run = update_run_with_usage(run, usage, save=False)
        
        # Fields should be updated
        assert updated_run.input_tokens == 1000
        
        # But not in database
        run.refresh_from_db()
        assert run.input_tokens == 0


@pytest.mark.django_db
class TestCostSummaries:
    """Tests for cost summary functions."""
    
    def test_get_cost_summary_by_agent(self, agent, tool, gpt4_pricing):
        """Test getting cost summary by agent."""
        # Create multiple runs with costs
        for _ in range(3):
            run = baker.make(
                Run,
                organization=agent.organization,
                environment=agent.environment,
                agent=agent,
                tool=tool,
                status="succeeded",
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                model_name="gpt-4",
                cost_total=Decimal("0.060000"),
            )
        
        results = get_cost_summary_by_agent(
            organization_id=str(agent.organization.id),
            days=30,
        )
        
        assert len(results) == 1
        summary = results[0]
        assert str(summary["agent_id"]) == str(agent.id)
        assert summary["agent__name"] == agent.name
        assert summary["total_cost"] == Decimal("0.180000")  # 3 * 0.06
        assert summary["total_runs"] == 3
        assert summary["total_tokens"] == 4500  # 3 * 1500
    
    def test_get_cost_summary_by_environment(self, org_and_env, agent, tool, gpt4_pricing):
        """Test getting cost summary by environment."""
        org, env = org_and_env
        
        # Create runs
        for _ in range(2):
            run = baker.make(
                Run,
                organization=org,
                environment=env,
                agent=agent,
                tool=tool,
                status="succeeded",
                cost_total=Decimal("0.060000"),
            )
        
        results = get_cost_summary_by_environment(
            organization_id=str(org.id),
            days=30,
        )
        
        assert len(results) == 1
        summary = results[0]
        assert str(summary["environment_id"]) == str(env.id)
        assert summary["total_cost"] == Decimal("0.120000")
    
    def test_get_cost_summary_by_model(self, agent, tool, gpt4_pricing, claude_pricing):
        """Test getting cost summary by model."""
        # Create runs with different models
        baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
            model_name="gpt-4",
            cost_total=Decimal("0.060000"),
        )
        baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
            model_name="claude-3-opus",
            cost_total=Decimal("0.105000"),
        )
        
        results = get_cost_summary_by_model(
            organization_id=str(agent.organization.id),
            days=30,
        )
        
        assert len(results) == 2
        # Results should be ordered by cost (highest first)
        assert results[0]["model_name"] == "claude-3-opus"
        assert results[0]["total_cost"] == Decimal("0.105000")
        assert results[1]["model_name"] == "gpt-4"
        assert results[1]["total_cost"] == Decimal("0.060000")
    
    def test_get_cost_summary_by_tool(self, agent, gpt4_pricing):
        """Test getting cost summary by tool."""
        tool1 = baker.make(
            "tools.Tool",
            organization=agent.organization,
            environment=agent.environment,
            name="tool1",
        )
        tool2 = baker.make(
            "tools.Tool",
            organization=agent.organization,
            environment=agent.environment,
            name="tool2",
        )
        
        # Create runs for different tools
        baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool1,
            cost_total=Decimal("0.060000"),
        )
        baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool2,
            cost_total=Decimal("0.030000"),
        )
        
        results = get_cost_summary_by_tool(
            organization_id=str(agent.organization.id),
            days=30,
        )
        
        assert len(results) == 2
        assert results[0]["total_cost"] == Decimal("0.060000")
        assert results[1]["total_cost"] == Decimal("0.030000")
    
    def test_get_organization_total_cost(self, agent, tool, gpt4_pricing):
        """Test getting organization total cost."""
        # Create successful and failed runs
        baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="succeeded",
            cost_total=Decimal("0.060000"),
            total_tokens=1500,
        )
        baker.make(
            Run,
            organization=agent.organization,
            environment=agent.environment,
            agent=agent,
            tool=tool,
            status="failed",
            cost_total=Decimal("0.000000"),
        )
        
        summary = get_organization_total_cost(
            organization_id=str(agent.organization.id),
            days=30,
        )
        
        assert summary["total_cost"] == 0.060000
        assert summary["total_runs"] == 2
        assert summary["successful_runs"] == 1
        assert summary["failed_runs"] == 1
        assert summary["total_tokens"] == 1500
        assert summary["currency"] == "USD"

