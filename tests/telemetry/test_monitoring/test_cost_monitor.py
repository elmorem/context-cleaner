"""Tests for real-time cost monitoring."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from src.context_cleaner.telemetry.monitoring.cost_monitor import (
    RealTimeCostMonitor,
    BurnRateData,
    CostProjection,
    CostAlert,
    AlertLevel,
)


class TestRealTimeCostMonitor:
    """Test suite for RealTimeCostMonitor."""
    
    @pytest.fixture
    def cost_monitor(self, mock_telemetry_client, sample_budget_config):
        """Create cost monitor with mocked dependencies."""
        return RealTimeCostMonitor(mock_telemetry_client, sample_budget_config)
    
    @pytest.mark.asyncio
    async def test_get_current_burn_rate(self, cost_monitor, mock_telemetry_client, sample_session_metrics):
        """Test burn rate calculation."""
        # Setup session that started 1 hour ago with $2.50 cost
        session_metrics = sample_session_metrics
        session_metrics.start_time = datetime.now() - timedelta(hours=1)
        session_metrics.total_cost = 2.5
        
        mock_telemetry_client.get_session_metrics = AsyncMock(return_value=session_metrics)
        mock_telemetry_client.get_model_usage_stats = AsyncMock(return_value={
            "claude-sonnet-4-20250514": {"total_cost": 2.0},
            "claude-3-5-haiku-20241022": {"total_cost": 0.5}
        })
        
        burn_rate_data = await cost_monitor.get_current_burn_rate("test-session")
        
        assert burn_rate_data.current_cost == 2.5
        assert abs(burn_rate_data.burn_rate_per_hour - 2.5) < 0.1  # Should be ~$2.50/hour
        assert burn_rate_data.projected_session_cost > 0
        assert "SONNET" in burn_rate_data.model_breakdown
        assert "HAIKU" in burn_rate_data.model_breakdown
        assert 0 <= burn_rate_data.efficiency_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_budget_alert_generation(self, cost_monitor, mock_telemetry_client):
        """Test budget threshold alert generation."""
        # Mock high session cost (90% of budget)
        mock_telemetry_client.get_current_session_cost = AsyncMock(return_value=4.5)  # 90% of $5 budget
        
        alerts = await cost_monitor.check_budget_alerts("expensive-session")
        
        assert len(alerts) > 0
        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        assert len(critical_alerts) > 0
        
        alert = critical_alerts[0]
        assert alert.session_id == "expensive-session"
        assert "90%" in alert.message
        assert alert.recommended_action is not None
    
    @pytest.mark.asyncio
    async def test_cost_projection(self, cost_monitor, mock_telemetry_client, sample_session_metrics):
        """Test cost projection calculations."""
        # Setup session with steady burn rate
        session_metrics = sample_session_metrics
        session_metrics.start_time = datetime.now() - timedelta(minutes=30)
        session_metrics.total_cost = 1.25  # $2.50/hour burn rate
        
        mock_telemetry_client.get_session_metrics = AsyncMock(return_value=session_metrics)
        mock_telemetry_client.get_model_usage_stats = AsyncMock(return_value={})
        
        projection = await cost_monitor.get_cost_projection("test-session")
        
        assert projection.next_hour_cost > projection.end_of_session_cost / 2  # Should be reasonable
        assert projection.end_of_day_cost > projection.end_of_session_cost
        assert 0 <= projection.confidence <= 1.0
        assert len(projection.factors) > 0
    
    @pytest.mark.asyncio
    async def test_efficiency_score_calculation(self, cost_monitor):
        """Test efficiency score calculation logic."""
        # Test high efficiency (lots of Haiku usage)
        high_efficiency = cost_monitor._calculate_efficiency_score(
            cost=1.0, api_calls=100, model_breakdown={"HAIKU": 0.8, "SONNET": 0.2}
        )
        
        # Test low efficiency (lots of Sonnet usage)
        low_efficiency = cost_monitor._calculate_efficiency_score(
            cost=3.0, api_calls=50, model_breakdown={"HAIKU": 0.1, "SONNET": 2.9}
        )
        
        assert high_efficiency > low_efficiency
        assert 0 <= high_efficiency <= 1.0
        assert 0 <= low_efficiency <= 1.0
    
    @pytest.mark.asyncio
    async def test_cost_acceleration_tracking(self, cost_monitor):
        """Test cost acceleration (change in burn rate) tracking."""
        session_id = "test-session"
        
        # Simulate increasing burn rate
        acceleration1 = cost_monitor._calculate_cost_acceleration(session_id, 2.0)
        acceleration2 = cost_monitor._calculate_cost_acceleration(session_id, 2.5)
        acceleration3 = cost_monitor._calculate_cost_acceleration(session_id, 3.0)
        
        # First call should be 0 (no history)
        assert acceleration1 == 0.0
        
        # Second call should show positive acceleration
        assert acceleration2 > 0
        
        # Third call should also show positive acceleration
        assert acceleration3 > 0
    
    @pytest.mark.asyncio
    async def test_alert_cooldown(self, cost_monitor, mock_telemetry_client):
        """Test alert cooldown mechanism."""
        mock_telemetry_client.get_current_session_cost = AsyncMock(return_value=4.5)
        
        # First call should generate alerts
        alerts1 = await cost_monitor.check_budget_alerts("test-session")
        assert len(alerts1) > 0
        
        # Immediate second call should not generate alerts (cooldown)
        alerts2 = await cost_monitor.check_budget_alerts("test-session")
        assert len([a for a in alerts2 if a.level == AlertLevel.CRITICAL]) == 0
    
    def test_alert_callback_registration(self, cost_monitor):
        """Test alert callback registration and execution."""
        callback_called = False
        received_alert = None
        
        def test_callback(alert: CostAlert):
            nonlocal callback_called, received_alert
            callback_called = True
            received_alert = alert
        
        cost_monitor.register_alert_callback(test_callback)
        
        # Create a test alert
        test_alert = CostAlert(
            level=AlertLevel.WARNING,
            message="Test alert",
            current_cost=3.0,
            threshold=2.5,
            session_id="test-session"
        )
        
        # Manually trigger callback (in real scenario, would be called by check_budget_alerts)
        for callback in cost_monitor._alert_callbacks:
            callback(test_alert)
        
        assert callback_called
        assert received_alert == test_alert
    
    @pytest.mark.asyncio
    async def test_error_handling(self, cost_monitor, mock_telemetry_client):
        """Test error handling in cost monitoring."""
        # Mock telemetry client to raise exception
        mock_telemetry_client.get_session_metrics = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        # Should return safe defaults instead of crashing
        burn_rate_data = await cost_monitor.get_current_burn_rate("failing-session")
        
        assert burn_rate_data.current_cost == 0.0
        assert burn_rate_data.burn_rate_per_hour == 0.0
        assert burn_rate_data.efficiency_score == 0.0
    
    def test_burn_rate_data_structure(self):
        """Test BurnRateData dataclass structure."""
        data = BurnRateData(
            current_cost=2.5,
            burn_rate_per_hour=2.0,
            burn_rate_per_minute=2.0/60,
            projected_session_cost=4.0,
            projected_daily_cost=16.0,
            time_to_budget_exhaustion=timedelta(hours=1.5),
            cost_acceleration=0.2,
            model_breakdown={"SONNET": 2.0, "HAIKU": 0.5},
            efficiency_score=0.7
        )
        
        assert data.current_cost == 2.5
        assert data.burn_rate_per_hour == 2.0
        assert data.time_to_budget_exhaustion == timedelta(hours=1.5)
        assert "SONNET" in data.model_breakdown
    
    def test_cost_projection_structure(self):
        """Test CostProjection dataclass structure."""
        projection = CostProjection(
            next_hour_cost=3.0,
            end_of_session_cost=5.0,
            end_of_day_cost=20.0,
            confidence=0.8,
            factors=["High burn rate", "Stable usage pattern"]
        )
        
        assert projection.next_hour_cost == 3.0
        assert projection.confidence == 0.8
        assert "High burn rate" in projection.factors
    
    def test_cost_alert_structure(self):
        """Test CostAlert dataclass structure."""
        alert = CostAlert(
            level=AlertLevel.WARNING,
            message="Budget warning",
            current_cost=3.5,
            threshold=3.0,
            session_id="test-session",
            recommended_action="Consider switching to Haiku"
        )
        
        assert alert.level == AlertLevel.WARNING
        assert alert.current_cost == 3.5
        assert alert.recommended_action is not None
        assert isinstance(alert.timestamp, datetime)