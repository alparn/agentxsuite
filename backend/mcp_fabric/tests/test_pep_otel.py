"""
Tests for OpenTelemetry integration in PEP (Policy Enforcement Point).
"""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from model_bakery import baker

from apps.agents.models import Agent
from apps.audit.models import AuditEvent
from apps.policies.models import Policy
from apps.tenants.models import Environment, Organization
from apps.tools.models import Tool
from mcp_fabric.pep import check_policy_before_agent_call, check_policy_before_tool_call


@pytest.fixture
def org_env():
    """Create organization and environment for testing."""
    org = baker.make(Organization, name="test-org")
    env = baker.make(Environment, name="test-env", organization=org, type="dev")
    return org, env


@pytest.fixture
def agent_tool(org_env):
    """Create agent and tool for testing."""
    org, env = org_env
    from apps.connections.models import Connection

    conn = baker.make(Connection, organization=org, environment=env, name="test-conn")
    agent = Agent(
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
        enabled=True,
        mode="runner",
        inbound_auth_method="none",
    )
    agent.save(skip_validation=True)
    tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="test-tool",
        enabled=True,
    )
    return agent, tool


@pytest.mark.django_db
class TestPEPOpenTelemetryToolCall:
    """Test OpenTelemetry integration in check_policy_before_tool_call."""

    def test_pep_creates_otel_span_when_available(self, agent_tool, mocker):
        """Test that PEP creates OpenTelemetry span when OTel is available."""
        agent, tool = agent_tool

        # Mock OpenTelemetry tracer
        mock_span = mocker.Mock()
        mock_tracer = mocker.Mock()
        mock_tracer.start_span.return_value = mock_span
        mocker.patch("mcp_fabric.pep.tracer", mock_tracer)
        mocker.patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True)
        mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

        # Create allow policy with rule and binding
        from apps.policies.models import PolicyRule, PolicyBinding

        policy = baker.make(
            Policy,
            organization=agent.organization,
            environment=agent.environment,
            name="allow-policy",
            is_active=True,
        )
        rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target=f"tool:{tool.name}",
            effect="allow",
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="tool",
            scope_id=tool.id,
            priority=1,
        )

        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
            jti="test-jti-123",
            client_ip="192.168.1.1",
            request_id="req-456",
        )

        # Verify span was created
        mock_tracer.start_span.assert_called_once()
        assert "pep.tool.invoke" in str(mock_tracer.start_span.call_args)

        # Verify span attributes were set
        assert mock_span.set_attribute.call_count >= 5  # At least agent_id, tool_id, etc.
        attribute_calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert attribute_calls.get("pep.agent_id") == str(agent.id)
        assert attribute_calls.get("pep.tool_id") == str(tool.id)
        assert attribute_calls.get("pep.tool_name") == tool.name
        assert attribute_calls.get("pep.jti") == "test-jti-123"
        assert attribute_calls.get("pep.client_ip") == "192.168.1.1"
        assert attribute_calls.get("pep.request_id") == "req-456"

        # Verify span status and end
        mock_span.set_status.assert_called_once()
        mock_span.end.assert_called_once()

        assert allowed is True

    def test_pep_span_includes_decision_and_audit_event_id(self, agent_tool, mocker):
        """Test that PEP span includes decision and audit event ID."""
        agent, tool = agent_tool

        mock_span = mocker.Mock()
        mock_tracer = mocker.Mock()
        mock_tracer.start_span.return_value = mock_span
        mocker.patch("mcp_fabric.pep.tracer", mock_tracer)
        mocker.patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True)
        mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

        # Create allow policy with rule and binding
        from apps.policies.models import PolicyRule, PolicyBinding

        policy = baker.make(
            Policy,
            organization=agent.organization,
            environment=agent.environment,
            name="allow-policy",
            is_active=True,
        )
        rule = PolicyRule.objects.create(
            policy=policy,
            action="tool.invoke",
            target=f"tool:{tool.name}",
            effect="allow",
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="tool",
            scope_id=tool.id,
            priority=1,
        )

        allowed, reason = check_policy_before_tool_call(
            agent_id=str(agent.id),
            tool=tool,
            payload={},
        )

        # Verify decision and audit_event_id were set
        attribute_calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert attribute_calls.get("pep.decision") == "allow"
        assert "pep.audit_event_id" in attribute_calls

        # Verify audit event was created
        audit_event = AuditEvent.objects.filter(event_type="pep_decision").latest("created_at")
        assert audit_event.decision == "allow"
        assert str(audit_event.id) == attribute_calls.get("pep.audit_event_id")

        assert allowed is True

    def test_pep_handles_errors_with_otel_span(self, agent_tool, mocker):
        """Test that PEP records errors in OpenTelemetry span."""
        agent, tool = agent_tool

        mock_span = mocker.Mock()
        mock_tracer = mocker.Mock()
        mock_tracer.start_span.return_value = mock_span
        mocker.patch("mcp_fabric.pep.tracer", mock_tracer)
        mocker.patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True)
        mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

        # Mock PDP to raise exception
        mocker.patch("mcp_fabric.pep.get_pdp", side_effect=Exception("PDP error"))

        with pytest.raises(Exception):
            check_policy_before_tool_call(
                agent_id=str(agent.id),
                tool=tool,
                payload={},
            )

        # Verify error was recorded in span
        mock_span.set_status.assert_called()
        mock_span.record_exception.assert_called()
        mock_span.end.assert_called_once()

    def test_pep_works_without_otel(self, agent_tool):
        """Test that PEP works correctly when OpenTelemetry is not available."""
        agent, tool = agent_tool

        with patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", False):
            # Create allow policy with rule and binding
            from apps.policies.models import PolicyRule, PolicyBinding

            policy = baker.make(
                Policy,
                organization=agent.organization,
                environment=agent.environment,
                name="allow-policy",
                is_active=True,
            )
            rule = PolicyRule.objects.create(
                policy=policy,
                action="tool.invoke",
                target=f"tool:{tool.name}",
                effect="allow",
            )
            PolicyBinding.objects.create(
                policy=policy,
                scope_type="tool",
                scope_id=tool.id,
                priority=1,
            )

            allowed, reason = check_policy_before_tool_call(
                agent_id=str(agent.id),
                tool=tool,
                payload={},
            )

            assert allowed is True
            # Verify audit event was still created
            audit_event = AuditEvent.objects.filter(event_type="pep_decision").latest("created_at")
            assert audit_event is not None


@pytest.mark.django_db
class TestPEPOpenTelemetryAgentCall:
    """Test OpenTelemetry integration in check_policy_before_agent_call."""

    def test_pep_agent_call_creates_otel_span(self, org_env, mocker):
        """Test that PEP creates OpenTelemetry span for agent-to-agent calls."""
        org, env = org_env

        from apps.connections.models import Connection

        conn = baker.make(Connection, organization=org, environment=env, name="test-conn")
        caller_agent = Agent(
            organization=org,
            environment=env,
            connection=conn,
            name="caller-agent",
            enabled=True,
            mode="runner",
            inbound_auth_method="none",
            default_max_depth=5,
        )
        caller_agent.save(skip_validation=True)
        target_agent = Agent(
            organization=org,
            environment=env,
            connection=conn,
            name="target-agent",
            enabled=True,
            mode="runner",
            inbound_auth_method="none",
            default_max_depth=5,
        )
        target_agent.save(skip_validation=True)

        mock_span = mocker.Mock()
        mock_tracer = mocker.Mock()
        mock_tracer.start_span.return_value = mock_span
        mocker.patch("mcp_fabric.pep.tracer", mock_tracer)
        mocker.patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True)
        mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

        # Create allow policy with rule and binding
        from apps.policies.models import PolicyRule, PolicyBinding

        policy = baker.make(
            Policy,
            organization=org,
            environment=env,
            name="allow-policy",
            is_active=True,
        )
        rule = PolicyRule.objects.create(
            policy=policy,
            action="agent.invoke",
            target=f"agent:{target_agent.slug}",
            effect="allow",
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="agent",
            scope_id=target_agent.id,
            priority=1,
        )

        allowed, reason = check_policy_before_agent_call(
            caller_agent_id=str(caller_agent.id),
            target_agent_id=str(target_agent.id),
            context={"depth": 1, "budget_left_cents": 1000, "ttl_valid": True},
        )

        # Verify span was created
        mock_tracer.start_span.assert_called_once()
        assert "pep.agent.invoke" in str(mock_tracer.start_span.call_args)

        # Verify span attributes
        attribute_calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert attribute_calls.get("pep.caller_agent_id") == str(caller_agent.id)
        assert attribute_calls.get("pep.target_agent_id") == str(target_agent.id)
        assert attribute_calls.get("pep.depth") == 1
        assert attribute_calls.get("pep.budget_left_cents") == 1000
        assert attribute_calls.get("pep.ttl_valid") is True

        mock_span.set_status.assert_called_once()
        mock_span.end.assert_called_once()

        assert allowed is True

    def test_pep_agent_call_span_includes_decision(self, org_env, mocker):
        """Test that PEP agent call span includes decision."""
        org, env = org_env

        from apps.connections.models import Connection

        conn = baker.make(Connection, organization=org, environment=env, name="test-conn")
        caller_agent = Agent(
            organization=org,
            environment=env,
            connection=conn,
            name="caller-agent",
            enabled=True,
            mode="runner",
            inbound_auth_method="none",
            default_max_depth=5,
        )
        caller_agent.save(skip_validation=True)
        target_agent = Agent(
            organization=org,
            environment=env,
            connection=conn,
            name="target-agent",
            enabled=True,
            mode="runner",
            inbound_auth_method="none",
            default_max_depth=5,
        )
        target_agent.save(skip_validation=True)

        mock_span = mocker.Mock()
        mock_tracer = mocker.Mock()
        mock_tracer.start_span.return_value = mock_span
        mocker.patch("mcp_fabric.pep.tracer", mock_tracer)
        mocker.patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True)
        mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

        # Create allow policy with rule and binding
        from apps.policies.models import PolicyRule, PolicyBinding

        policy = baker.make(
            Policy,
            organization=org,
            environment=env,
            name="allow-policy",
            is_active=True,
        )
        rule = PolicyRule.objects.create(
            policy=policy,
            action="agent.invoke",
            target=f"agent:{target_agent.slug}",
            effect="allow",
        )
        PolicyBinding.objects.create(
            policy=policy,
            scope_type="agent",
            scope_id=target_agent.id,
            priority=1,
        )

        allowed, reason = check_policy_before_agent_call(
            caller_agent_id=str(caller_agent.id),
            target_agent_id=str(target_agent.id),
            context={"depth": 1, "budget_left_cents": 1000, "ttl_valid": True},
        )

        # Verify decision was set
        attribute_calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert attribute_calls.get("pep.decision") == "allow"
        assert "pep.audit_event_id" in attribute_calls

        assert allowed is True


@pytest.mark.django_db
class TestPEPOpenTelemetryRealSDK:
    """Test PEP with real OpenTelemetry SDK (integration tests)."""

    def test_pep_tool_call_with_real_otel_sdk(self, agent_tool):
        """Test PEP tool call with real OTel SDK (InMemorySpanExporter)."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            agent, tool = agent_tool

            # Setup real OTel SDK with in-memory exporter
            # Reset tracer provider if already set (to avoid "Overriding not allowed" warning)
            import warnings
            try:
                # Try to get existing provider and clear it
                existing_provider = trace.get_tracer_provider()
                if hasattr(existing_provider, 'shutdown'):
                    existing_provider.shutdown()
            except Exception:
                pass
            
            tracer_provider = TracerProvider()
            memory_exporter = InMemorySpanExporter()
            span_processor = SimpleSpanProcessor(memory_exporter)
            tracer_provider.add_span_processor(span_processor)
            # Reset internal state and suppress warning
            trace._TRACER_PROVIDER = None
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                trace.set_tracer_provider(tracer_provider)

            # Patch the tracer in PEP
            with patch("mcp_fabric.pep.tracer", trace.get_tracer(__name__)):
                with patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True):
                    # Create allow policy with rule and binding
                    from apps.policies.models import PolicyRule, PolicyBinding

                    policy = baker.make(
                        Policy,
                        organization=agent.organization,
                        environment=agent.environment,
                        name="allow-policy",
                        is_active=True,
                    )
                    rule = PolicyRule.objects.create(
                        policy=policy,
                        action="tool.invoke",
                        target=f"tool:{tool.name}",
                        effect="allow",
                    )
                    PolicyBinding.objects.create(
                        policy=policy,
                        scope_type="tool",
                        scope_id=tool.id,
                        priority=1,
                    )

                    allowed, reason = check_policy_before_tool_call(
                        agent_id=str(agent.id),
                        tool=tool,
                        payload={},
                        jti="test-jti-real",
                        client_ip="10.0.0.1",
                        request_id="req-real-123",
                    )

            spans = memory_exporter.get_finished_spans()
            assert len(spans) == 1

            span = spans[0]
            assert span.name == "pep.tool.invoke"
            assert span.attributes["pep.agent_id"] == str(agent.id)
            assert span.attributes["pep.tool_id"] == str(tool.id)
            assert span.attributes["pep.tool_name"] == tool.name
            assert span.attributes["pep.jti"] == "test-jti-real"
            assert span.attributes["pep.client_ip"] == "10.0.0.1"
            assert span.attributes["pep.request_id"] == "req-real-123"
            assert span.attributes["pep.decision"] == "allow"
            assert "pep.audit_event_id" in span.attributes

            # Verify span status
            assert span.status.status_code.value == 1  # OK

            assert allowed is True
        except ImportError:
            pytest.skip("OpenTelemetry SDK not available")

    def test_pep_agent_call_with_real_otel_sdk(self, org_env):
        """Test PEP agent call with real OTel SDK."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            org, env = org_env

            caller_agent = Agent(
                organization=org,
                environment=env,
                name="caller-agent",
                enabled=True,
                default_max_depth=5,
                capabilities=[],
                tags=[],
            )
            caller_agent.save(skip_validation=True)
            
            target_agent = Agent(
                organization=org,
                environment=env,
                name="target-agent",
                enabled=True,
                default_max_depth=5,
                capabilities=[],
                tags=[],
            )
            target_agent.save(skip_validation=True)

            # Setup tracer provider with in-memory exporter
            # Note: If a provider is already set, we can't override it, so we use the existing one
            # and add our span processor to it
            from opentelemetry.sdk.trace import TracerProvider
            import warnings
            
            memory_exporter = InMemorySpanExporter()
            span_processor = SimpleSpanProcessor(memory_exporter)
            
            try:
                # Try to get existing provider
                existing_provider = trace.get_tracer_provider()
                # If it's an SDK provider, add our processor to it
                if isinstance(existing_provider, TracerProvider):
                    existing_provider.add_span_processor(span_processor)
                    tracer_provider = existing_provider
                else:
                    # Create new provider if not SDK provider
                    tracer_provider = TracerProvider()
                    tracer_provider.add_span_processor(span_processor)
                    # Reset internal state and suppress warning
                    trace._TRACER_PROVIDER = None
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        trace.set_tracer_provider(tracer_provider)
            except Exception:
                # Fallback: create new provider
                tracer_provider = TracerProvider()
                tracer_provider.add_span_processor(span_processor)
                trace._TRACER_PROVIDER = None
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    trace.set_tracer_provider(tracer_provider)

            with patch("mcp_fabric.pep.tracer", trace.get_tracer(__name__)):
                with patch("mcp_fabric.pep.OTELEMETRY_AVAILABLE", True):
                    # Create allow policy with rule and binding
                    from apps.policies.models import PolicyRule, PolicyBinding

                    policy = baker.make(
                        Policy,
                        organization=org,
                        environment=env,
                        name="allow-policy",
                        is_active=True,
                    )
                    rule = PolicyRule.objects.create(
                        policy=policy,
                        action="agent.invoke",
                        target=f"agent:{target_agent.slug}",
                        effect="allow",
                    )
                    PolicyBinding.objects.create(
                        policy=policy,
                        scope_type="agent",
                        scope_id=target_agent.id,
                        priority=1,
                    )

                    allowed, reason = check_policy_before_agent_call(
                        caller_agent_id=str(caller_agent.id),
                        target_agent_id=str(target_agent.id),
                        context={"depth": 2, "budget_left_cents": 500, "ttl_valid": True},
                    )

            spans = memory_exporter.get_finished_spans()
            assert len(spans) == 1

            span = spans[0]
            assert span.name == "pep.agent.invoke"
            assert span.attributes["pep.caller_agent_id"] == str(caller_agent.id)
            assert span.attributes["pep.target_agent_id"] == str(target_agent.id)
            assert span.attributes["pep.depth"] == 2
            assert span.attributes["pep.budget_left_cents"] == 500
            assert span.attributes["pep.ttl_valid"] is True
            assert span.attributes["pep.decision"] == "allow"

            assert allowed is True
        except ImportError:
            pytest.skip("OpenTelemetry SDK not available")

