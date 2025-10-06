"""Tests for the Context Rot dashboard widget in the orchestrated runtime."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.context_cleaner.telemetry.context_rot.widget import ContextRotWidget, ContextRotMeterData
from src.context_cleaner.telemetry.dashboard.widgets import WidgetData, TelemetryWidgetType
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer


@pytest.fixture
def mock_clickhouse_client():
    """Provide an async-aware ClickHouse client mock."""
    client = MagicMock(spec=ClickHouseClient)
    client.health_check = AsyncMock(return_value=True)
    client.execute_query = AsyncMock(return_value=[])
    return client


@pytest.fixture
def analyzer_stub():
    """Provide a ContextRotAnalyzer stub with async methods."""
    stub = MagicMock(spec=ContextRotAnalyzer)
    stub.get_analyzer_status = AsyncMock(
        return_value={
            "status": "healthy",
            "system_metrics": {"analysis_latency_ms": 20.0, "memory_usage_mb": 12.0},
            "components": {"ml_frustration_detector": "active"},
            "clickhouse_connection": "healthy",
        }
    )
    stub.analyze_session_health = AsyncMock(
        return_value={
            "status": "healthy",
            "metrics": {
                "average_rot_score": 0.42,
                "average_confidence": 0.8,
                "measurement_count": 9,
                "attention_alerts": 1,
            },
            "recommendations": ["Maintain current workflow"],
            "system_health": {"analysis_latency_ms": 21.0, "memory_usage_mb": 13.5},
        }
    )
    stub.get_recent_trends = AsyncMock(
        return_value={
            "trend_analysis": {"direction": "improving"},
            "hourly_trends": [{"hour": 9, "avg_rot": 0.45}],
        }
    )
    return stub


@pytest.fixture
def context_rot_widget(mock_clickhouse_client, analyzer_stub):
    """Create the widget under test."""
    return ContextRotWidget(mock_clickhouse_client, analyzer_stub)


@pytest.mark.asyncio
async def test_widget_initialization(context_rot_widget):
    """Widget initializes with the expected telemetry type."""
    assert context_rot_widget.widget_type == TelemetryWidgetType.CONTEXT_ROT_METER
    assert context_rot_widget.analyzer is not None


@pytest.mark.asyncio
async def test_get_widget_data_for_session(context_rot_widget, mock_clickhouse_client, analyzer_stub):
    """Session-scoped widget data shapes context metrics and system status."""
    mock_clickhouse_client.execute_query.return_value = [
        {
            "avg_rot_score": 0.42,
            "max_rot_score": 0.77,
            "measurement_count": 9,
            "attention_alerts": 1,
            "avg_confidence": 0.8,
        }
    ]

    widget_data = await context_rot_widget.get_widget_data(session_id="session-xyz", time_window_minutes=60)

    assert isinstance(widget_data, WidgetData)
    assert widget_data.status == "healthy"
    assert isinstance(widget_data.data["context_rot"], ContextRotMeterData)
    assert widget_data.data["context_rot"].current_rot_score == pytest.approx(0.42)
    analyzer_stub.analyze_session_health.assert_awaited_once()
    analyzer_stub.get_recent_trends.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_widget_data_global_overview(context_rot_widget, mock_clickhouse_client, analyzer_stub):
    """Global widget aggregation uses ClickHouse metrics and trend data."""
    mock_clickhouse_client.execute_query.side_effect = [
        [
            {
                "avg_rot_score": 0.55,
                "max_rot_score": 0.82,
                "total_measurements": 24,
                "total_alerts": 6,
                "avg_confidence": 0.72,
                "active_sessions": 12,
            }
        ],
        [
            {"hour": 8, "avg_rot": 0.6, "measurements": 8},
            {"hour": 9, "avg_rot": 0.5, "measurements": 10},
            {"hour": 10, "avg_rot": 0.45, "measurements": 6},
        ],
    ]

    widget_data = await context_rot_widget.get_widget_data(time_window_minutes=30)

    context_metrics = widget_data.data["context_rot"]
    assert context_metrics.session_health_status == "degraded"
    assert context_metrics.measurements_count == 24
    assert widget_data.status == "warning"
    assert any("attention" in alert.lower() for alert in widget_data.alerts)
    analyzer_stub.analyze_session_health.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_widget_data_handles_backend_error(context_rot_widget, analyzer_stub):
    """Analyzer failures propagate as critical widget states."""
    analyzer_stub.analyze_session_health.side_effect = RuntimeError("boom")

    widget_data = await context_rot_widget.get_widget_data(session_id="faulty")

    assert widget_data.status == "critical"
    context_metrics = widget_data.data["context_rot"]
    assert context_metrics.session_health_status == "error"
    assert any("boom" in rec for rec in context_metrics.recommendations)


@pytest.mark.asyncio
async def test_widget_cache_prevents_duplicate_queries(context_rot_widget, mock_clickhouse_client):
    """Widget caches global queries to avoid redundant ClickHouse work."""
    mock_clickhouse_client.execute_query.side_effect = [
        [
            {
                "avg_rot_score": 0.3,
                "max_rot_score": 0.6,
                "total_measurements": 5,
                "total_alerts": 0,
                "avg_confidence": 0.75,
                "active_sessions": 2,
            }
        ],
        [
            {"hour": 10, "avg_rot": 0.35, "measurements": 5},
        ],
    ]

    await context_rot_widget.get_widget_data(time_window_minutes=60)
    await context_rot_widget.get_widget_data(time_window_minutes=60)

    assert mock_clickhouse_client.execute_query.await_count == 2


@pytest.mark.asyncio
async def test_widget_status_summary_reuses_analyzer_status(context_rot_widget, analyzer_stub):
    """Widget status summary mirrors analyzer health for monitoring endpoints."""
    summary = await context_rot_widget.get_widget_status_summary()

    assert summary["status"] == "healthy"
    assert summary["widget_type"] == TelemetryWidgetType.CONTEXT_ROT_METER.value
    analyzer_stub.get_analyzer_status.assert_awaited()
