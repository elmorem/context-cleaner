"""Tests for telemetry dashboard widgets."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.context_cleaner.telemetry.dashboard.widgets import (
    TelemetryWidgetManager,
    TelemetryWidgetType,
    WidgetData,
    ErrorMonitorData,
    CostTrackerData,
    TimeoutRiskData,
    ToolOptimizerData,
    ModelEfficiencyData,
)


class TestTelemetryWidgetManager:
    """Test suite for TelemetryWidgetManager."""
    
    @pytest.fixture
    def widget_manager(self, mock_telemetry_client, sample_budget_config):
        """Create widget manager with mocked dependencies."""
        from src.context_cleaner.telemetry.cost_optimization.engine import CostOptimizationEngine
        from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
        
        cost_engine = CostOptimizationEngine(mock_telemetry_client, sample_budget_config)
        recovery_manager = ErrorRecoveryManager(mock_telemetry_client)
        
        return TelemetryWidgetManager(
            mock_telemetry_client,
            cost_engine,
            recovery_manager
        )
    
    @pytest.fixture
    def sample_budget_config(self):
        """Create sample budget configuration."""
        from src.context_cleaner.telemetry.cost_optimization.models import BudgetConfig
        return BudgetConfig(
            session_limit=5.0,
            daily_limit=25.0,
            auto_switch_haiku=True,
            auto_context_optimization=True
        )
    
    @pytest.mark.asyncio
    async def test_get_error_monitor_widget(self, widget_manager, mock_telemetry_client):
        """Test error monitoring widget data generation."""
        # Mock error data
        from src.context_cleaner.telemetry.clients.base import ErrorEvent
        mock_errors = [
            ErrorEvent(
                timestamp=datetime.now(),
                session_id="test-session",
                error_type="Request was aborted",
                duration_ms=5000,
                model="claude-sonnet-4-20250514",
                input_tokens=2000,
                terminal_type="vscode"
            )
        ]
        
        mock_telemetry_client.get_recent_errors = AsyncMock(return_value=mock_errors)
        mock_telemetry_client.execute_query = AsyncMock(return_value=[{"session_id": "test-session"}])
        
        widget_manager.recovery_manager.get_recovery_statistics = AsyncMock(
            return_value={"recovery_success_rate": 0.9}
        )
        
        widget_data = await widget_manager.get_widget_data(TelemetryWidgetType.ERROR_MONITOR)
        
        assert widget_data.widget_type == TelemetryWidgetType.ERROR_MONITOR
        assert widget_data.title == "API Error Monitor"
        assert widget_data.status in ["healthy", "warning", "critical"]
        assert "current_error_rate" in widget_data.data
        assert "recent_errors" in widget_data.data
    
    @pytest.mark.asyncio
    async def test_get_cost_tracker_widget(self, widget_manager, mock_telemetry_client):
        """Test cost tracking widget data generation."""
        # Mock cost data
        mock_telemetry_client.get_current_session_cost = AsyncMock(return_value=2.5)
        mock_telemetry_client.get_model_usage_stats = AsyncMock(return_value={
            "claude-sonnet-4-20250514": {"total_cost": 2.0},
            "claude-3-5-haiku-20241022": {"total_cost": 0.5}
        })
        
        # Mock session metrics
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        session_metrics = SessionMetrics(
            session_id="test-session",
            start_time=datetime.now() - timedelta(hours=1),
            end_time=None,
            api_calls=10,
            total_cost=2.5,
            total_input_tokens=5000,
            total_output_tokens=1000,
            error_count=0,
            tools_used=["Read", "Edit"]
        )
        
        mock_telemetry_client.get_session_metrics = AsyncMock(return_value=session_metrics)
        
        widget_data = await widget_manager.get_widget_data(TelemetryWidgetType.COST_TRACKER)
        
        assert widget_data.widget_type == TelemetryWidgetType.COST_TRACKER
        assert widget_data.title == "Cost Burn Rate Monitor"
        assert "current_session_cost" in widget_data.data
        assert "burn_rate_per_hour" in widget_data.data
        assert "model_breakdown" in widget_data.data
    
    @pytest.mark.asyncio
    async def test_get_timeout_risk_widget(self, widget_manager, mock_telemetry_client):
        """Test timeout risk assessment widget."""
        # Mock performance data
        mock_telemetry_client.execute_query = AsyncMock(return_value=[{
            "avg_duration": 6000,  # 6 seconds average
            "request_count": 20,
            "slow_requests": 2
        }])
        
        mock_telemetry_client.get_model_usage_stats = AsyncMock(return_value={
            "claude-sonnet-4-20250514": {"request_count": 15}
        })
        
        widget_data = await widget_manager.get_widget_data(TelemetryWidgetType.TIMEOUT_RISK)
        
        assert widget_data.widget_type == TelemetryWidgetType.TIMEOUT_RISK
        assert widget_data.title == "Timeout Risk Assessment"
        assert "risk_level" in widget_data.data
        assert "avg_response_time" in widget_data.data
        assert "recommended_actions" in widget_data.data
    
    @pytest.mark.asyncio
    async def test_get_tool_optimizer_widget(self, widget_manager, mock_telemetry_client):
        """Test tool sequence optimizer widget."""
        # Mock tool usage data
        mock_telemetry_client.execute_query = AsyncMock(return_value=[
            {"tool_name": "Read", "usage_count": 25},
            {"tool_name": "Edit", "usage_count": 20},
            {"tool_name": "Grep", "usage_count": 15}
        ])
        
        widget_data = await widget_manager.get_widget_data(TelemetryWidgetType.TOOL_OPTIMIZER)
        
        assert widget_data.widget_type == TelemetryWidgetType.TOOL_OPTIMIZER
        assert widget_data.title == "Tool Sequence Optimizer"
        assert "efficiency_score" in widget_data.data
        assert "tool_usage_stats" in widget_data.data
        assert "optimization_suggestions" in widget_data.data
    
    @pytest.mark.asyncio
    async def test_get_model_efficiency_widget(self, widget_manager, mock_telemetry_client):
        """Test model efficiency comparison widget."""
        # Mock model statistics
        mock_telemetry_client.get_model_usage_stats = AsyncMock(return_value={
            "claude-sonnet-4-20250514": {
                "request_count": 10,
                "total_cost": 3.0,
                "cost_per_token": 0.001
            },
            "claude-3-5-haiku-20241022": {
                "request_count": 15,
                "total_cost": 0.5,
                "cost_per_token": 0.000025
            }
        })
        
        widget_data = await widget_manager.get_widget_data(TelemetryWidgetType.MODEL_EFFICIENCY)
        
        assert widget_data.widget_type == TelemetryWidgetType.MODEL_EFFICIENCY
        assert widget_data.title == "Model Efficiency Tracker"
        assert "sonnet_stats" in widget_data.data
        assert "haiku_stats" in widget_data.data
        assert "efficiency_ratio" in widget_data.data
        assert "recommendation" in widget_data.data
    
    @pytest.mark.asyncio
    async def test_get_all_widget_data(self, widget_manager, mock_telemetry_client):
        """Test getting all widget data at once."""
        # Setup basic mocks
        mock_telemetry_client.get_recent_errors = AsyncMock(return_value=[])
        mock_telemetry_client.execute_query = AsyncMock(return_value=[])
        mock_telemetry_client.get_current_session_cost = AsyncMock(return_value=1.0)
        mock_telemetry_client.get_model_usage_stats = AsyncMock(return_value={})
        mock_telemetry_client.get_session_metrics = AsyncMock(return_value=None)
        
        widget_manager.recovery_manager.get_recovery_statistics = AsyncMock(
            return_value={"recovery_success_rate": 0.9}
        )
        
        all_widgets = await widget_manager.get_all_widget_data()
        
        assert len(all_widgets) == len(TelemetryWidgetType)
        
        for widget_type in TelemetryWidgetType:
            assert widget_type.value in all_widgets
            widget_data = all_widgets[widget_type.value]
            assert hasattr(widget_data, 'widget_type')
            assert hasattr(widget_data, 'title')
            assert hasattr(widget_data, 'status')
    
    @pytest.mark.asyncio
    async def test_widget_caching(self, widget_manager, mock_telemetry_client):
        """Test widget data caching functionality."""
        mock_telemetry_client.get_recent_errors = AsyncMock(return_value=[])
        mock_telemetry_client.execute_query = AsyncMock(return_value=[])
        widget_manager.recovery_manager.get_recovery_statistics = AsyncMock(
            return_value={"recovery_success_rate": 0.9}
        )
        
        # First call should hit the database
        widget_data_1 = await widget_manager.get_widget_data(TelemetryWidgetType.ERROR_MONITOR)
        
        # Second call should use cache
        widget_data_2 = await widget_manager.get_widget_data(TelemetryWidgetType.ERROR_MONITOR)
        
        # Should be called only once due to caching
        assert mock_telemetry_client.get_recent_errors.call_count == 1
        
        # Clear cache and try again
        widget_manager.clear_cache()
        widget_data_3 = await widget_manager.get_widget_data(TelemetryWidgetType.ERROR_MONITOR)
        
        # Should be called again after cache clear
        assert mock_telemetry_client.get_recent_errors.call_count == 2
    
    @pytest.mark.asyncio
    async def test_error_handling(self, widget_manager, mock_telemetry_client):
        """Test error handling in widget data generation."""
        # Mock an exception
        mock_telemetry_client.get_recent_errors = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        widget_data = await widget_manager.get_widget_data(TelemetryWidgetType.ERROR_MONITOR)
        
        assert widget_data.status == "warning"
        assert "Unable to fetch error data" in widget_data.alerts
        assert widget_data.data == {}
    
    def test_widget_data_dataclass(self):
        """Test WidgetData dataclass functionality."""
        from datetime import datetime
        
        widget = WidgetData(
            widget_type=TelemetryWidgetType.COST_TRACKER,
            title="Test Widget",
            status="healthy",
            data={"test": "value"},
            alerts=["Test alert"]
        )
        
        assert widget.widget_type == TelemetryWidgetType.COST_TRACKER
        assert widget.title == "Test Widget"
        assert widget.status == "healthy"
        assert widget.data["test"] == "value"
        assert "Test alert" in widget.alerts
        assert isinstance(widget.last_updated, datetime)