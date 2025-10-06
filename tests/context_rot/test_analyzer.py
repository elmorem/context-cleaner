"""Tests for the modern Context Rot Analyzer."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer, ContextRotMetric
from src.context_cleaner.telemetry.context_rot.monitor import QuickAssessment
from src.context_cleaner.telemetry.context_rot.ml_analysis import FrustrationAnalysis, SentimentScore
from src.context_cleaner.telemetry.context_rot.adaptive_thresholds import ThresholdConfig, UserBaseline
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
from tests.telemetry.conftest import MockTelemetryClient


@pytest.fixture
def mock_clickhouse_client():
    """Provide an async-aware ClickHouse client mock."""
    client = MagicMock(spec=ClickHouseClient)
    client.health_check = AsyncMock(return_value=True)
    client.execute_query = AsyncMock(return_value=[])
    client.bulk_insert = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_error_recovery_manager():
    """Provide an ErrorRecoveryManager wired with the telemetry test client."""
    telemetry_client = MockTelemetryClient()
    return ErrorRecoveryManager(telemetry_client, max_retries=3)


@pytest.fixture
def analyzer(mock_clickhouse_client, mock_error_recovery_manager, monkeypatch):
    """Create a ContextRotAnalyzer with production dependencies stubbed."""
    quick_assessment = QuickAssessment(
        rot_estimate=0.42,
        confidence=0.83,
        requires_attention=False,
        indicators={"repetition": 0.2, "efficiency": 0.7, "health": 0.9},
    )

    class MonitorStub:
        def __init__(self, *args, **kwargs):
            self.repetition_detector = MagicMock()
            self.repetition_detector.analyze_sequence.return_value = 0.3
            self.efficiency_tracker = MagicMock()
            self.efficiency_tracker.calculate_trend.return_value = 0.7
            self.session_health = MagicMock()
            self.session_health.get_health_score.return_value = 0.9
            self.session_health.add_success_indicator = MagicMock()
            self.session_health.add_error_indicator = MagicMock()
            self.reset_session_data = MagicMock()
            self.memory_limiter = MagicMock()
            self.memory_limiter.check_memory_limit.return_value = True
            self.memory_limiter.force_cleanup = MagicMock()
            self.secure_analyzer = MagicMock()
            self.secure_analyzer.validate_and_sanitize_input.side_effect = (
                lambda session_id, content, window_size=50: {
                    "session_id": session_id,
                    "content": content,
                }
            )
            self.circuit_breaker = MagicMock()
            self.circuit_breaker.call.side_effect = lambda fn, payload: fn(payload)
            self.analyze_lightweight = AsyncMock(return_value=quick_assessment)
            self.get_system_metrics = AsyncMock(
                return_value={
                    "circuit_breaker": {"uptime_ok": True},
                    "analysis_latency_ms": 24.5,
                    "memory_usage_mb": 18.2,
                }
            )

    class AdaptiveThresholdManagerStub:
        def __init__(self, *args, **kwargs):
            self.get_personalized_thresholds = AsyncMock(return_value=None)
            self.update_user_sensitivity = AsyncMock(return_value=True)
            self.user_baseline_tracker = MagicMock()
            self.user_baseline_tracker.get_user_baseline = AsyncMock(return_value=None)

    class MLFrustrationDetectorStub:
        def __init__(self, confidence_threshold=0.8):
            self.analyze_user_sentiment = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "src.context_cleaner.telemetry.context_rot.analyzer.ProductionReadyContextRotMonitor",
        MonitorStub,
    )
    monkeypatch.setattr(
        "src.context_cleaner.telemetry.context_rot.analyzer.AdaptiveThresholdManager",
        AdaptiveThresholdManagerStub,
    )
    monkeypatch.setattr(
        "src.context_cleaner.telemetry.context_rot.analyzer.MLFrustrationDetector",
        MLFrustrationDetectorStub,
    )

    return ContextRotAnalyzer(mock_clickhouse_client, mock_error_recovery_manager)


def test_analyzer_initialization(analyzer):
    """The analyzer wires modern components on construction."""
    assert analyzer.monitor is not None
    assert analyzer.statistical_analyzer is not None
    assert analyzer.ml_enabled is True
    assert hasattr(analyzer, "ml_frustration_detector")


@pytest.mark.asyncio
async def test_analyze_realtime_returns_metric(analyzer, mock_clickhouse_client):
    """Real-time analysis emits a ContextRotMetric and logs to ClickHouse."""
    metric = await analyzer.analyze_realtime("session-123", "Investigate context rot")

    assert isinstance(metric, ContextRotMetric)
    assert metric.session_id == "session-123"
    assert metric.rot_score == pytest.approx(0.42)
    assert mock_clickhouse_client.bulk_insert.await_count == 1


@pytest.mark.asyncio
async def test_analyze_session_health_synthesizes_metrics(analyzer, mock_clickhouse_client):
    """Session health aggregates ClickHouse data into the modern schema."""
    mock_clickhouse_client.execute_query.return_value = [
        {
            "avg_rot_score": 0.38,
            "max_rot_score": 0.81,
            "measurement_count": 6,
            "attention_alerts": 2,
            "avg_confidence": 0.74,
        }
    ]

    result = await analyzer.analyze_session_health("session-abc", 45)

    assert result["status"] == "healthy"
    assert result["metrics"]["measurement_count"] == 6
    assert result["metrics"]["average_rot_score"] == pytest.approx(0.38)
    assert result["metrics"]["attention_alerts"] == 2


@pytest.mark.asyncio
async def test_analyze_session_health_handles_no_data(analyzer, mock_clickhouse_client):
    """No measurements yields a no-data response rather than raising."""
    mock_clickhouse_client.execute_query.return_value = [
        {
            "avg_rot_score": 0.0,
            "max_rot_score": 0.0,
            "measurement_count": 0,
            "attention_alerts": 0,
            "avg_confidence": 0.0,
        }
    ]

    result = await analyzer.analyze_session_health("missing-session")

    assert result["status"] == "no_data"
    assert "message" in result


@pytest.mark.asyncio
async def test_get_recent_trends_returns_trend_analysis(analyzer, mock_clickhouse_client):
    """Trend analysis inspects hourly aggregates and reports directionality."""
    mock_clickhouse_client.execute_query.return_value = [
        {"hour": 8, "avg_rot": 0.6},
        {"hour": 9, "avg_rot": 0.55},
        {"hour": 10, "avg_rot": 0.5},
        {"hour": 11, "avg_rot": 0.4},
        {"hour": 12, "avg_rot": 0.35},
    ]

    result = await analyzer.get_recent_trends("session-123", hours=3)

    assert result["trend_analysis"]["status"] == "analyzed"
    assert result["trend_analysis"]["direction"] == "improving"


@pytest.mark.asyncio
async def test_get_analyzer_status_reports_component_health(analyzer):
    """Analyzer status surfaces component readiness for dashboards."""
    status = await analyzer.get_analyzer_status()

    assert status["status"] == "healthy"
    assert status["clickhouse_connection"] == "healthy"
    assert status["components"]["ml_frustration_detector"] == "active"
    assert status["system_metrics"]["analysis_latency_ms"] == pytest.approx(24.5)


@pytest.mark.asyncio
async def test_reset_session_invokes_monitor(analyzer):
    """Resetting a session delegates to the production monitor stub."""
    response = await analyzer.reset_session("session-z")

    analyzer.monitor.reset_session_data.assert_called_once_with("session-z")
    assert response["status"] == "reset"


@pytest.mark.asyncio
async def test_conversation_sentiment_analysis_uses_ml_outputs(analyzer):
    """Conversation sentiment uses ML detector and personalized thresholds."""
    analysis = FrustrationAnalysis(
        frustration_level=0.73,
        confidence=0.82,
        sentiment_breakdown={SentimentScore.FRUSTRATED: 0.7},
        evidence=["User expressed repeated frustration"],
        conversation_patterns={"repetition_index": 0.6},
        processing_time_ms=42.0,
    )
    thresholds = ThresholdConfig(
        user_id="user-1",
        warning_threshold=0.5,
        critical_threshold=0.7,
        confidence_required=0.6,
        last_optimized=datetime.now(),
    )

    analyzer.ml_frustration_detector.analyze_user_sentiment.return_value = analysis
    analyzer.adaptive_threshold_manager.get_personalized_thresholds.return_value = thresholds

    result = await analyzer.analyze_conversation_sentiment("user-1", ["This still isn't working"])

    assert result["status"] == "success"
    assert result["alert_level"] == "critical"
    assert result["analysis"]["frustration_level"] == pytest.approx(0.73)


@pytest.mark.asyncio
async def test_personalized_insights_include_behavioral_profile(analyzer):
    """Personalized insights surface thresholds and learned baselines."""
    thresholds = ThresholdConfig(
        user_id="user-42",
        warning_threshold=0.4,
        critical_threshold=0.65,
        confidence_required=0.6,
        last_optimized=datetime.now(),
    )
    baseline = UserBaseline(
        user_id="user-42",
        normal_level=0.35,
        variance=0.12,
        session_count=8,
        last_updated=datetime.now(),
        confidence=0.78,
        avg_session_length=42.0,
        avg_messages_per_session=28.0,
        typical_conversation_flow=0.73,
        sensitivity_factor=1.1,
    )

    analyzer.adaptive_threshold_manager.get_personalized_thresholds.return_value = thresholds
    analyzer.adaptive_threshold_manager.user_baseline_tracker.get_user_baseline.return_value = baseline

    insights = await analyzer.get_personalized_insights("user-42")

    assert insights["status"] == "success"
    assert insights["thresholds"]["critical"] == pytest.approx(0.65)
    assert insights["behavioral_profile"]["sensitivity_factor"] == pytest.approx(1.1)


@pytest.mark.asyncio
async def test_update_user_feedback_refreshes_thresholds(analyzer):
    """User feedback triggers sensitivity update and refreshed insights."""
    thresholds = ThresholdConfig(
        user_id="user-42",
        warning_threshold=0.45,
        critical_threshold=0.7,
        confidence_required=0.65,
        last_optimized=datetime.now(),
    )
    baseline = UserBaseline(
        user_id="user-42",
        normal_level=0.32,
        variance=0.15,
        session_count=10,
        last_updated=datetime.now(),
        confidence=0.8,
        avg_session_length=38.0,
        avg_messages_per_session=30.0,
        typical_conversation_flow=0.68,
        sensitivity_factor=0.95,
    )

    analyzer.adaptive_threshold_manager.get_personalized_thresholds.return_value = thresholds
    analyzer.adaptive_threshold_manager.user_baseline_tracker.get_user_baseline.return_value = baseline

    response = await analyzer.update_user_feedback("user-42", "too_sensitive", {"rot_score": 0.7})

    analyzer.adaptive_threshold_manager.update_user_sensitivity.assert_awaited_once()
    assert response["status"] == "success"
    assert response["feedback_processed"] == "too_sensitive"
