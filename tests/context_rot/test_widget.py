"""Comprehensive tests for Context Rot Widget components."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.context_cleaner.telemetry.context_rot.widget import ContextRotWidget
from src.context_cleaner.telemetry.dashboard.widgets import TelemetryWidgetType, WidgetData
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class TestContextRotWidget:
    """Test suite for Context Rot Widget."""

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client for testing."""
        client = AsyncMock(spec=ClickHouseClient)
        client.health_check.return_value = True
        client.execute_query.return_value = []
        return client

    @pytest.fixture
    def context_rot_widget(self, mock_clickhouse_client):
        """Create context rot widget for testing."""
        return ContextRotWidget(mock_clickhouse_client)

    @pytest.mark.asyncio
    async def test_widget_initialization(self, context_rot_widget):
        """Test widget initializes correctly."""
        assert context_rot_widget.widget_type == TelemetryWidgetType.CONTEXT_ROT_METER
        assert context_rot_widget.clickhouse_client is not None

    @pytest.mark.asyncio
    async def test_get_widget_data_with_session(self, context_rot_widget, mock_clickhouse_client):
        """Test getting widget data for specific session."""
        # Mock ClickHouse response with context rot data
        mock_clickhouse_client.execute_query.return_value = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.3,
                'confidence_score': 0.8,
                'indicator_breakdown': '{"repetition": 0.2, "frustration": 0.4}',
                'analysis_version': 1
            },
            {
                'timestamp': '2024-01-01 10:15:00', 
                'rot_score': 0.5,
                'confidence_score': 0.85,
                'indicator_breakdown': '{"repetition": 0.3, "frustration": 0.7}',
                'analysis_version': 1
            }
        ]
        
        widget_data = await context_rot_widget.get_widget_data(
            session_id='test-session-123',
            time_window_minutes=30
        )
        
        assert isinstance(widget_data, WidgetData)
        assert widget_data.widget_type == TelemetryWidgetType.CONTEXT_ROT_METER
        assert len(widget_data.data) == 2
        assert widget_data.data[0]['rot_score'] == 0.3
        assert widget_data.data[1]['rot_score'] == 0.5
        assert 'summary' in widget_data.metadata
        assert 'trends' in widget_data.metadata

    @pytest.mark.asyncio
    async def test_get_widget_data_no_session(self, context_rot_widget, mock_clickhouse_client):
        """Test getting widget data for current session (no session_id provided)."""
        # Mock global context rot data
        mock_clickhouse_client.execute_query.return_value = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.2,
                'confidence_score': 0.75,
                'indicator_breakdown': '{"repetition": 0.1, "frustration": 0.3}',
                'analysis_version': 1
            }
        ]
        
        widget_data = await context_rot_widget.get_widget_data(time_window_minutes=30)
        
        assert isinstance(widget_data, WidgetData)
        assert len(widget_data.data) == 1
        assert widget_data.data[0]['rot_score'] == 0.2

    @pytest.mark.asyncio
    async def test_get_widget_data_empty_response(self, context_rot_widget, mock_clickhouse_client):
        """Test handling empty response from ClickHouse."""
        mock_clickhouse_client.execute_query.return_value = []
        
        widget_data = await context_rot_widget.get_widget_data(session_id='empty-session')
        
        assert isinstance(widget_data, WidgetData)
        assert len(widget_data.data) == 0
        assert widget_data.metadata['status'] == 'no_data'
        assert widget_data.metadata['message'] == 'No context rot data available for the specified time window'

    @pytest.mark.asyncio
    async def test_format_widget_data(self, context_rot_widget):
        """Test widget data formatting."""
        raw_data = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.35,
                'confidence_score': 0.82,
                'indicator_breakdown': '{"repetition": 0.2, "frustration": 0.5, "confusion": 0.1}',
                'analysis_version': 1
            }
        ]
        
        formatted_data = context_rot_widget._format_widget_data(raw_data)
        
        assert isinstance(formatted_data, WidgetData)
        assert len(formatted_data.data) == 1
        
        data_point = formatted_data.data[0]
        assert data_point['timestamp'] == '2024-01-01 10:00:00'
        assert data_point['rot_score'] == 0.35
        assert data_point['confidence'] == 0.82
        assert isinstance(data_point['indicators'], dict)
        assert data_point['indicators']['repetition'] == 0.2
        assert data_point['indicators']['frustration'] == 0.5

    @pytest.mark.asyncio
    async def test_calculate_summary_statistics(self, context_rot_widget):
        """Test summary statistics calculation."""
        data_points = [
            {'rot_score': 0.2, 'confidence': 0.8},
            {'rot_score': 0.4, 'confidence': 0.85},
            {'rot_score': 0.3, 'confidence': 0.75},
            {'rot_score': 0.6, 'confidence': 0.9}
        ]
        
        summary = context_rot_widget._calculate_summary(data_points)
        
        assert summary['current_level'] == 0.6  # Latest score
        assert summary['average_level'] == 0.375  # (0.2 + 0.4 + 0.3 + 0.6) / 4
        assert summary['max_level'] == 0.6
        assert summary['min_level'] == 0.2
        assert summary['trend'] in ['increasing', 'decreasing', 'stable']
        assert 0.0 <= summary['average_confidence'] <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_trend_analysis(self, context_rot_widget):
        """Test trend analysis calculation."""
        # Test increasing trend
        increasing_scores = [0.2, 0.3, 0.4, 0.5, 0.6]
        trend = context_rot_widget._calculate_trend(increasing_scores)
        assert trend == 'increasing'
        
        # Test decreasing trend
        decreasing_scores = [0.6, 0.5, 0.4, 0.3, 0.2]
        trend = context_rot_widget._calculate_trend(decreasing_scores)
        assert trend == 'decreasing'
        
        # Test stable trend
        stable_scores = [0.4, 0.41, 0.39, 0.4, 0.41]
        trend = context_rot_widget._calculate_trend(stable_scores)
        assert trend == 'stable'

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, context_rot_widget):
        """Test recommendation generation based on data."""
        # High rot score data
        high_rot_data = [
            {'rot_score': 0.8, 'confidence': 0.9, 'indicators': {'frustration': 0.9, 'repetition': 0.7}}
        ]
        
        recommendations = context_rot_widget._generate_recommendations(high_rot_data)
        
        assert len(recommendations) > 0
        assert any('context' in rec.lower() for rec in recommendations)
        assert any('frustration' in rec.lower() or 'repetition' in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_get_widget_data_different_time_windows(self, context_rot_widget, mock_clickhouse_client):
        """Test widget data retrieval with different time windows."""
        mock_clickhouse_client.execute_query.return_value = [
            {'timestamp': '2024-01-01 10:00:00', 'rot_score': 0.3, 'confidence_score': 0.8, 
             'indicator_breakdown': '{}', 'analysis_version': 1}
        ]
        
        # Test different time windows
        time_windows = [15, 30, 60, 120]
        
        for window in time_windows:
            widget_data = await context_rot_widget.get_widget_data(
                session_id='test-session',
                time_window_minutes=window
            )
            
            assert isinstance(widget_data, WidgetData)
            # Verify the query was called with appropriate time parameters
            mock_clickhouse_client.execute_query.assert_called()

    @pytest.mark.asyncio
    async def test_error_handling_database_failure(self, context_rot_widget, mock_clickhouse_client):
        """Test error handling when database fails."""
        mock_clickhouse_client.execute_query.side_effect = Exception("Database connection failed")
        
        widget_data = await context_rot_widget.get_widget_data(session_id='test-session')
        
        assert isinstance(widget_data, WidgetData)
        assert widget_data.metadata['status'] == 'error'
        assert 'error' in widget_data.metadata['message'].lower()

    @pytest.mark.asyncio
    async def test_malformed_indicator_breakdown(self, context_rot_widget):
        """Test handling of malformed indicator breakdown JSON."""
        raw_data_with_bad_json = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.4,
                'confidence_score': 0.8,
                'indicator_breakdown': 'invalid json{',  # Malformed JSON
                'analysis_version': 1
            }
        ]
        
        formatted_data = context_rot_widget._format_widget_data(raw_data_with_bad_json)
        
        assert isinstance(formatted_data, WidgetData)
        assert len(formatted_data.data) == 1
        # Should handle gracefully with empty indicators
        assert formatted_data.data[0]['indicators'] == {}

    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self, context_rot_widget):
        """Test widget performance with large dataset."""
        # Generate large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'timestamp': f'2024-01-01 {i%24:02d}:{i%60:02d}:00',
                'rot_score': 0.1 + (i % 10) * 0.08,  # Vary between 0.1 and 0.9
                'confidence_score': 0.7 + (i % 3) * 0.1,
                'indicator_breakdown': '{"repetition": 0.2, "frustration": 0.3}',
                'analysis_version': 1
            })
        
        import time
        start_time = time.time()
        
        formatted_data = context_rot_widget._format_widget_data(large_dataset)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process efficiently
        assert processing_time < 1.0  # Less than 1 second for 1000 records
        assert len(formatted_data.data) == 1000
        assert 'summary' in formatted_data.metadata


class TestContextRotWidgetIntegration:
    """Integration tests for Context Rot Widget."""

    @pytest.fixture
    def real_clickhouse_client(self):
        """Real ClickHouse client (if available)."""
        return ClickHouseClient()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_widget_with_real_database(self, real_clickhouse_client):
        """Test widget with real ClickHouse database (if available)."""
        # Skip if ClickHouse is not available
        healthy = await real_clickhouse_client.health_check()
        if not healthy:
            pytest.skip("ClickHouse not available for integration test")
        
        widget = ContextRotWidget(real_clickhouse_client)
        
        # Test getting data (may be empty if no data exists)
        widget_data = await widget.get_widget_data(time_window_minutes=60)
        
        assert isinstance(widget_data, WidgetData)
        assert widget_data.widget_type == TelemetryWidgetType.CONTEXT_ROT_METER
        # Data may be empty but should not error
        assert isinstance(widget_data.data, list)

    @pytest.mark.asyncio
    async def test_widget_concurrent_requests(self, mock_clickhouse_client):
        """Test widget handling concurrent requests."""
        widget = ContextRotWidget(mock_clickhouse_client)
        
        # Mock response
        mock_clickhouse_client.execute_query.return_value = [
            {'timestamp': '2024-01-01 10:00:00', 'rot_score': 0.3, 'confidence_score': 0.8,
             'indicator_breakdown': '{}', 'analysis_version': 1}
        ]
        
        # Test concurrent requests
        tasks = []
        for i in range(20):
            task = widget.get_widget_data(session_id=f'concurrent-session-{i}')
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should handle all requests successfully
        successful_results = [r for r in results if isinstance(r, WidgetData)]
        assert len(successful_results) == 20

    @pytest.mark.asyncio
    async def test_widget_dashboard_integration(self, mock_clickhouse_client):
        """Test widget integration with dashboard system."""
        widget = ContextRotWidget(mock_clickhouse_client)
        
        # Mock response
        mock_clickhouse_client.execute_query.return_value = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.65,
                'confidence_score': 0.85,
                'indicator_breakdown': '{"frustration": 0.7, "repetition": 0.6}',
                'analysis_version': 1
            }
        ]
        
        # Test widget data structure matches dashboard expectations
        widget_data = await widget.get_widget_data(session_id='dashboard-test')
        
        assert isinstance(widget_data, WidgetData)
        assert hasattr(widget_data, 'widget_type')
        assert hasattr(widget_data, 'data')
        assert hasattr(widget_data, 'metadata')
        assert hasattr(widget_data, 'last_updated')
        
        # Verify data structure for dashboard consumption
        assert 'summary' in widget_data.metadata
        assert 'recommendations' in widget_data.metadata
        assert isinstance(widget_data.data, list)

    @pytest.mark.asyncio
    async def test_widget_alert_integration(self, mock_clickhouse_client):
        """Test widget integration with alert system."""
        widget = ContextRotWidget(mock_clickhouse_client)
        
        # Mock high rot score that should trigger alerts
        mock_clickhouse_client.execute_query.return_value = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.9,  # High rot score
                'confidence_score': 0.95,
                'indicator_breakdown': '{"frustration": 0.95, "repetition": 0.85}',
                'analysis_version': 1
            }
        ]
        
        widget_data = await widget.get_widget_data(session_id='alert-test')
        
        # Should include alert information in metadata
        assert 'alert_level' in widget_data.metadata
        assert widget_data.metadata['alert_level'] == 'critical'
        assert 'alert_message' in widget_data.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])