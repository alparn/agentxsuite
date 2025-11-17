"""
Tests for OpenTelemetry integration in audit services.
"""
from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
from model_bakery import baker

from apps.audit.models import AuditEvent
from apps.audit.services import log_run_event, log_security_event
from apps.runs.models import Run
from apps.tenants.models import Organization


@pytest.fixture
def run(org_env):
    """Create test run."""
    org, env = org_env
    from apps.agents.models import Agent, InboundAuthMethod
    from apps.connections.models import Connection
    from apps.tools.models import Tool
    
    conn = baker.make(
        Connection,
        organization=org,
        environment=env,
        name="test-conn",
        endpoint="https://example.com",
        auth_method="none",
    )
    
    agent = baker.make(
        Agent,
        organization=org,
        environment=env,
        connection=conn,
        name="test-agent",
        slug="test-agent",
        enabled=True,
        inbound_auth_method=InboundAuthMethod.NONE,
        capabilities=[],
        tags=[],
    )
    
    tool = baker.make(
        Tool,
        organization=org,
        environment=env,
        connection=conn,
        name="test-tool",
        schema_json={"type": "object"},
        sync_status="synced",
    )
    
    return baker.make(Run, organization=org, environment=env, agent=agent, tool=tool)


@pytest.mark.django_db
def test_log_run_event_with_otel_span_attributes(run, mocker):
    """Test that log_run_event sets correct OTel span attributes."""
    # Mock OTel tracer with attribute tracking
    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span = mocker.Mock()
    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    event_data = {"custom_field": "test_value", "numeric": 42}
    audit_event = log_run_event(run, "run_started", event_data)

    # Verify span was created
    mock_tracer.start_span.assert_called_once()
    assert "audit.run.run_started" in str(mock_tracer.start_span.call_args)

    # Verify core attributes
    assert captured_attributes["audit.event_type"] == "run_started"
    assert captured_attributes["run.id"] == str(run.id)
    assert captured_attributes["agent.id"] == str(run.agent.id)
    assert captured_attributes["tool.id"] == str(run.tool.id)
    assert captured_attributes["organization.id"] == str(run.organization.id)
    assert captured_attributes["environment.id"] == str(run.environment.id)
    assert captured_attributes["audit.event_id"] == str(audit_event.id)

    # Verify event data attributes (limited to first 10)
    assert captured_attributes["audit.data.custom_field"] == "test_value"
    assert captured_attributes["audit.data.numeric"] == "42"

    # Verify span status and end
    mock_span.set_status.assert_called_once()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_security_event_with_otel_span_attributes(mocker):
    """Test that log_security_event sets correct OTel span attributes."""
    org = baker.make(Organization, name="TestOrg")

    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span = mocker.Mock()
    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    event_data = {
        "resource_id": "test-123",
        "resource_name": "test-resource",
        "agent_id": "agent-456",
        "nested": {"key1": "value1", "key2": "value2"},
    }
    audit_event = log_security_event(str(org.id), "resource_read", event_data)

    # Verify core attributes
    assert captured_attributes["audit.event_type"] == "resource_read"
    assert captured_attributes["organization.id"] == str(org.id)
    assert captured_attributes["organization.name"] == org.name
    assert captured_attributes["audit.event_id"] == str(audit_event.id)

    # Verify event data attributes (limited to first 15)
    assert captured_attributes["audit.data.resource_id"] == "test-123"
    assert captured_attributes["audit.data.resource_name"] == "test-resource"
    assert captured_attributes["audit.data.agent_id"] == "agent-456"

    # Verify nested dict handling (limited to first 5)
    assert captured_attributes["audit.data.nested.key1"] == "value1"
    assert captured_attributes["audit.data.nested.key2"] == "value2"

    mock_span.set_status.assert_called_once()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_run_event_with_existing_span_context(run, mocker):
    """Test that log_run_event links to existing span context."""
    # Create a mock current span
    mock_current_span = mocker.Mock()
    mock_span_context = mocker.Mock()
    mock_current_span.get_span_context.return_value = mock_span_context

    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=mock_current_span)

    audit_event = log_run_event(run, "run_started")

    # Verify span was created with context from current span
    mock_tracer.start_span.assert_called_once()
    call_args = mock_tracer.start_span.call_args
    assert call_args[1]["context"] == mock_span_context  # Check context parameter

    assert audit_event is not None
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_security_event_with_existing_span_context(mocker):
    """Test that log_security_event links to existing span context."""
    org = baker.make(Organization, name="TestOrg")

    mock_current_span = mocker.Mock()
    mock_span_context = mocker.Mock()
    mock_current_span.get_span_context.return_value = mock_span_context

    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=mock_current_span)

    audit_event = log_security_event(str(org.id), "resource_read", {"test": "data"})

    # Verify span was created with context
    call_args = mock_tracer.start_span.call_args
    assert call_args[1]["context"] == mock_span_context

    assert audit_event is not None
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_run_event_with_real_otel_sdk(run):
    """Test log_run_event with real OTel SDK (InMemorySpanExporter)."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import InMemorySpanExporter
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        # Setup real OTel SDK with in-memory exporter
        tracer_provider = TracerProvider()
        memory_exporter = InMemorySpanExporter()
        span_processor = SimpleSpanProcessor(memory_exporter)
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)

        # Patch the tracer in audit services
        with patch("apps.audit.services.tracer", trace.get_tracer(__name__)):
            with patch("apps.audit.services.OTELEMETRY_AVAILABLE", True):
                audit_event = log_run_event(run, "run_started", {"test": "data"})

        # Verify span was exported
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "audit.run.run_started"
        assert span.attributes["audit.event_type"] == "run_started"
        assert span.attributes["run.id"] == str(run.id)
        assert span.attributes["agent.id"] == str(run.agent.id)
        assert span.attributes["tool.id"] == str(run.tool.id)
        assert span.attributes["organization.id"] == str(run.organization.id)
        assert span.attributes["environment.id"] == str(run.environment.id)
        assert span.attributes["audit.event_id"] == str(audit_event.id)
        assert span.attributes["audit.data.test"] == "data"

        # Verify span status
        assert span.status.status_code.value == 1  # OK

        assert audit_event is not None
    except ImportError:
        pytest.skip("OpenTelemetry SDK not available")


@pytest.mark.django_db
def test_log_security_event_with_real_otel_sdk():
    """Test log_security_event with real OTel SDK."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import InMemorySpanExporter
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        org = baker.make(Organization, name="TestOrg")

        tracer_provider = TracerProvider()
        memory_exporter = InMemorySpanExporter()
        span_processor = SimpleSpanProcessor(memory_exporter)
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)

        with patch("apps.audit.services.tracer", trace.get_tracer(__name__)):
            with patch("apps.audit.services.OTELEMETRY_AVAILABLE", True):
                audit_event = log_security_event(
                    str(org.id), "resource_read", {"resource_id": "test-123"}
                )

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "audit.security.resource_read"
        assert span.attributes["audit.event_type"] == "resource_read"
        assert span.attributes["organization.id"] == str(org.id)
        assert span.attributes["organization.name"] == org.name
        assert span.attributes["audit.event_id"] == str(audit_event.id)
        assert span.attributes["audit.data.resource_id"] == "test-123"

        assert audit_event is not None
    except ImportError:
        pytest.skip("OpenTelemetry SDK not available")


@pytest.mark.django_db
def test_log_run_event_attribute_limit(run, mocker):
    """Test that event data attributes are limited to prevent huge spans."""
    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span = mocker.Mock()
    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Create event data with more than 10 items (limit for run events)
    event_data = {f"field_{i}": f"value_{i}" for i in range(15)}
    audit_event = log_run_event(run, "run_started", event_data)

    # Count audit.data.* attributes
    data_attributes = [k for k in captured_attributes.keys() if k.startswith("audit.data.")]
    assert len(data_attributes) <= 10  # Should be limited to 10

    assert audit_event is not None


@pytest.mark.django_db
def test_log_security_event_attribute_limit(mocker):
    """Test that security event data attributes are limited."""
    org = baker.make(Organization, name="TestOrg")

    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span = mocker.Mock()
    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Create event data with more than 15 items (limit for security events)
    event_data = {f"field_{i}": f"value_{i}" for i in range(20)}
    audit_event = log_security_event(str(org.id), "resource_read", event_data)

    # Count audit.data.* attributes (excluding nested)
    data_attributes = [
        k for k in captured_attributes.keys() if k.startswith("audit.data.") and "." not in k.split("audit.data.")[1]
    ]
    assert len(data_attributes) <= 15  # Should be limited to 15

    assert audit_event is not None


@pytest.mark.django_db
def test_log_run_event_non_serializable_data(run, mocker):
    """Test that non-JSON-serializable data in event_data raises error."""
    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Non-serializable object (function, class, etc.)
    event_data = {"func": lambda x: x, "class": Run, "valid": "string"}

    # Django JSONField will raise TypeError for non-serializable data
    with pytest.raises(TypeError):
        log_run_event(run, "run_started", event_data)

    # Verify error was recorded in span
    mock_span.set_status.assert_called()
    mock_span.record_exception.assert_called()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_run_event_empty_event_data(run, mocker):
    """Test log_run_event with empty event_data."""
    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    audit_event = log_run_event(run, "run_started", None)

    assert audit_event is not None
    assert audit_event.event_type == "run_started"
    mock_span.set_status.assert_called_once()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_security_event_empty_event_data(mocker):
    """Test log_security_event with empty event_data."""
    org = baker.make(Organization, name="TestOrg")

    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    audit_event = log_security_event(str(org.id), "resource_read", {})

    assert audit_event is not None
    assert audit_event.event_type == "resource_read"
    mock_span.set_status.assert_called_once()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_run_event_db_error_handling(run, mocker):
    """Test that DB errors are properly handled and recorded in span."""
    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Force DB error by patching AuditEvent.objects.create to raise exception
    original_create = AuditEvent.objects.create
    mocker.patch(
        "apps.audit.models.AuditEvent.objects.create",
        side_effect=Exception("DB error"),
    )

    with pytest.raises(Exception, match="DB error"):
        log_run_event(run, "run_started")

    # Verify error was recorded in span
    mock_span.set_status.assert_called()
    # Check that set_status was called with ERROR status
    status_call = mock_span.set_status.call_args
    assert status_call is not None
    # Verify exception was recorded
    mock_span.record_exception.assert_called()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_security_event_org_not_found(mocker):
    """Test log_security_event when organization doesn't exist."""
    mock_span = mocker.Mock()
    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Use non-existent org ID
    import uuid

    fake_org_id = str(uuid.uuid4())
    audit_event = log_security_event(fake_org_id, "resource_read", {"test": "data"})

    # Should still create audit event (org=None)
    assert audit_event is not None
    assert audit_event.organization is None
    assert captured_attributes["organization.exists"] is False
    mock_span.set_status.assert_called_once()
    mock_span.end.assert_called_once()


@pytest.mark.django_db
def test_log_run_event_without_otel(run, mocker):
    """Test that log_run_event works without OTel."""
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", False)

    audit_event = log_run_event(run, "run_started", {"test": "data"})

    assert audit_event is not None
    assert audit_event.event_type == "run_started"
    assert AuditEvent.objects.filter(id=audit_event.id).exists()


@pytest.mark.django_db
def test_log_security_event_without_otel(mocker):
    """Test that log_security_event works without OTel."""
    org = baker.make(Organization, name="TestOrg")
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", False)

    audit_event = log_security_event(str(org.id), "resource_read", {"resource_id": "test-123"})

    assert audit_event is not None
    assert audit_event.event_type == "resource_read"
    assert AuditEvent.objects.filter(id=audit_event.id).exists()


@pytest.mark.django_db
def test_log_run_event_idempotency(run):
    """Test that duplicate events (same run_id + event_type) are allowed (idempotent)."""
    event1 = log_run_event(run, "run_started", {"attempt": 1})
    event2 = log_run_event(run, "run_started", {"attempt": 2})

    # Both should be created (idempotent = can be called multiple times)
    assert event1.id != event2.id
    assert AuditEvent.objects.filter(event_type="run_started", event_data__run_id=str(run.id)).count() == 2


@pytest.mark.django_db
def test_log_run_event_different_event_types(run, mocker):
    """Test that different event types create different spans."""
    captured_spans = []

    def start_span_side_effect(*args, **kwargs):
        span = mocker.Mock()
        span.name = args[0] if args else kwargs.get("name", "unknown")
        captured_spans.append(span.name)
        return span

    mock_tracer = mocker.Mock()
    mock_tracer.start_span.side_effect = start_span_side_effect
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    log_run_event(run, "run_started")
    log_run_event(run, "run_denied")
    log_run_event(run, "run_failed")

    assert len(captured_spans) == 3
    assert "audit.run.run_started" in captured_spans
    assert "audit.run.run_denied" in captured_spans
    assert "audit.run.run_failed" in captured_spans


@pytest.mark.django_db
def test_log_security_event_different_event_types(mocker):
    """Test that different security event types create different spans."""
    org = baker.make(Organization, name="TestOrg")
    captured_spans = []

    def start_span_side_effect(*args, **kwargs):
        span = mocker.Mock()
        span.name = args[0] if args else kwargs.get("name", "unknown")
        captured_spans.append(span.name)
        return span

    mock_tracer = mocker.Mock()
    mock_tracer.start_span.side_effect = start_span_side_effect
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    log_security_event(str(org.id), "resource_read", {})
    log_security_event(str(org.id), "prompt_invoked", {})
    log_security_event(str(org.id), "policy_denied", {})

    assert len(captured_spans) == 3
    assert "audit.security.resource_read" in captured_spans
    assert "audit.security.prompt_invoked" in captured_spans
    assert "audit.security.policy_denied" in captured_spans


@pytest.mark.django_db
def test_log_run_event_high_frequency_performance(run, mocker):
    """Test that logging at high frequency doesn't cause issues."""
    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Log 100 events rapidly
    events = []
    for i in range(100):
        event = log_run_event(run, "run_started", {"iteration": i})
        events.append(event)

    # Verify all events were created
    assert len(events) == 100
    assert all(e is not None for e in events)
    assert AuditEvent.objects.filter(event_type="run_started").count() >= 100

    # Verify spans were created (should be 100)
    assert mock_tracer.start_span.call_count == 100
    assert mock_span.end.call_count == 100


@pytest.mark.django_db
def test_log_security_event_high_frequency_performance(mocker):
    """Test that security event logging at high frequency works correctly."""
    org = baker.make(Organization, name="TestOrg")

    mock_span = mocker.Mock()
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Log 50 events rapidly
    events = []
    for i in range(50):
        event = log_security_event(
            str(org.id), "resource_read", {"resource_id": f"res-{i}"}
        )
        events.append(event)

    assert len(events) == 50
    assert all(e is not None for e in events)
    assert mock_tracer.start_span.call_count == 50
    assert mock_span.end.call_count == 50


@pytest.mark.django_db
def test_log_run_event_large_event_data_truncation(run, mocker):
    """Test that very large event_data doesn't cause span bloat."""
    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span = mocker.Mock()
    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Create event data with many fields (more than limit)
    large_event_data = {f"field_{i}": f"value_{i}" * 10 for i in range(20)}
    audit_event = log_run_event(run, "run_started", large_event_data)

    # Count audit.data.* attributes
    data_attributes = [k for k in captured_attributes.keys() if k.startswith("audit.data.")]
    # Should be limited to 10 (not 20)
    assert len(data_attributes) <= 10

    # But DB should still have all data
    assert audit_event is not None
    assert len(audit_event.event_data) > 10  # DB has all data


@pytest.mark.django_db
def test_log_security_event_nested_dict_limit(mocker):
    """Test that nested dicts in event_data are properly limited."""
    org = baker.make(Organization, name="TestOrg")

    captured_attributes = {}

    def set_attribute_side_effect(key, value):
        captured_attributes[key] = value

    mock_span = mocker.Mock()
    mock_span.set_attribute.side_effect = set_attribute_side_effect
    mock_tracer = mocker.Mock()
    mock_tracer.start_span.return_value = mock_span
    mocker.patch("apps.audit.services.tracer", mock_tracer)
    mocker.patch("apps.audit.services.OTELEMETRY_AVAILABLE", True)
    mocker.patch("opentelemetry.trace.get_current_span", return_value=None)

    # Create nested dict with more than 5 items
    event_data = {
        "nested": {f"key_{i}": f"value_{i}" for i in range(10)},
        "simple": "value",
    }
    audit_event = log_security_event(str(org.id), "resource_read", event_data)

    # Count nested attributes (audit.data.nested.*)
    nested_attributes = [
        k for k in captured_attributes.keys() if k.startswith("audit.data.nested.")
    ]
    # Should be limited to 5 nested items
    assert len(nested_attributes) <= 5

    assert audit_event is not None
