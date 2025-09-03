"""Tests for ClickHouseClient."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class TestClickHouseClient:
    """Test suite for ClickHouseClient."""
    
    @pytest.fixture
    def clickhouse_client(self):
        """Create ClickHouseClient instance."""
        return ClickHouseClient()
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_execute_query_success(self, mock_subprocess, clickhouse_client):
        """Test successful query execution."""
        # Mock subprocess response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"count": 10}\n{"count": 5}\n'
        mock_result.stderr = ''
        mock_subprocess.return_value = mock_result
        
        result = await clickhouse_client.execute_query("SELECT count() FROM test_table")
        
        assert len(result) == 2
        assert result[0]["count"] == 10
        assert result[1]["count"] == 5
        
        # Verify subprocess was called correctly
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        assert "docker" in args
        assert "exec" in args
        assert "clickhouse-client" in args
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_execute_query_error(self, mock_subprocess, clickhouse_client):
        """Test query execution with error."""
        # Mock subprocess error response
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'DB::Exception: Table not found'
        mock_subprocess.return_value = mock_result
        
        result = await clickhouse_client.execute_query("SELECT * FROM nonexistent_table")
        
        assert result == []
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_execute_query_timeout(self, mock_subprocess, clickhouse_client):
        """Test query execution timeout."""
        from subprocess import TimeoutExpired
        
        # Mock subprocess timeout
        mock_subprocess.side_effect = TimeoutExpired(cmd=[], timeout=30)
        
        result = await clickhouse_client.execute_query("SELECT * FROM slow_table")
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_session_metrics_integration(self, clickhouse_client):
        """Test session metrics retrieval (integration test - requires running infrastructure)."""
        # This is more of an integration test - we'll mock the execute_query method
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            # Mock session metrics query result
            mock_execute.side_effect = [
                [{
                    'session_id': 'test-session-123',
                    'start_time': '2024-09-01T10:00:00.000Z',
                    'end_time': '2024-09-01T10:30:00.000Z', 
                    'api_calls': 15,
                    'total_cost': 2.25,
                    'total_input_tokens': 8000,
                    'total_output_tokens': 1500,
                    'error_count': 1
                }],
                [{'tool': 'Read'}, {'tool': 'Edit'}, {'tool': 'Bash'}]  # Tools query result
            ]
            
            metrics = await clickhouse_client.get_session_metrics('test-session-123')
            
            assert metrics is not None
            assert metrics.session_id == 'test-session-123'
            assert metrics.api_calls == 15
            assert metrics.total_cost == 2.25
            assert metrics.total_input_tokens == 8000
            assert metrics.error_count == 1
            assert len(metrics.tools_used) == 3
            assert 'Read' in metrics.tools_used
    
    @pytest.mark.asyncio
    async def test_get_recent_errors(self, clickhouse_client):
        """Test recent errors retrieval."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            # Mock error query result
            mock_execute.return_value = [{
                'Timestamp': '2024-09-01T10:15:30.000Z',
                'session_id': 'test-session-123',
                'error_type': 'Request was aborted',
                'duration_ms': 7200.0,
                'model': 'claude-sonnet-4-20250514',
                'input_tokens': 3500,
                'terminal_type': 'vscode'
            }]
            
            errors = await clickhouse_client.get_recent_errors(hours=24)
            
            assert len(errors) == 1
            error = errors[0]
            assert error.session_id == 'test-session-123'
            assert error.error_type == 'Request was aborted'
            assert error.duration_ms == 7200.0
            assert error.model == 'claude-sonnet-4-20250514'
            assert error.input_tokens == 3500
    
    @pytest.mark.asyncio
    async def test_get_cost_trends(self, clickhouse_client):
        """Test cost trends retrieval."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            # Mock cost trends query result
            mock_execute.return_value = [
                {'date': '2024-09-01', 'daily_cost': 3.25},
                {'date': '2024-08-31', 'daily_cost': 2.75},
                {'date': '2024-08-30', 'daily_cost': 1.90}
            ]
            
            trends = await clickhouse_client.get_cost_trends(days=7)
            
            assert len(trends) == 3
            assert trends['2024-09-01'] == 3.25
            assert trends['2024-08-31'] == 2.75
            assert trends['2024-08-30'] == 1.90
    
    @pytest.mark.asyncio
    async def test_get_current_session_cost(self, clickhouse_client):
        """Test current session cost retrieval."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            # Mock session cost query result
            mock_execute.return_value = [{'session_cost': 1.75}]
            
            cost = await clickhouse_client.get_current_session_cost('test-session-123')
            
            assert cost == 1.75
    
    @pytest.mark.asyncio
    async def test_get_current_session_cost_no_data(self, clickhouse_client):
        """Test current session cost when no data exists."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            # Mock empty result
            mock_execute.return_value = [{'session_cost': None}]
            
            cost = await clickhouse_client.get_current_session_cost('nonexistent-session')
            
            assert cost == 0.0
    
    @pytest.mark.asyncio
    async def test_get_model_usage_stats(self, clickhouse_client):
        """Test model usage statistics retrieval."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            # Mock model stats query result
            mock_execute.return_value = [
                {
                    'model': 'claude-sonnet-4-20250514',
                    'request_count': 25,
                    'total_cost': 3.75,
                    'avg_duration_ms': 5200.0,
                    'total_input_tokens': 15000,
                    'total_output_tokens': 3000
                },
                {
                    'model': 'claude-3-5-haiku-20241022', 
                    'request_count': 45,
                    'total_cost': 0.85,
                    'avg_duration_ms': 1800.0,
                    'total_input_tokens': 25000,
                    'total_output_tokens': 4500
                }
            ]
            
            stats = await clickhouse_client.get_model_usage_stats(days=7)
            
            assert len(stats) == 2
            
            sonnet_stats = stats['claude-sonnet-4-20250514']
            assert sonnet_stats['request_count'] == 25
            assert sonnet_stats['total_cost'] == 3.75
            assert sonnet_stats['avg_duration_ms'] == 5200.0
            assert sonnet_stats['cost_per_token'] == 3.75 / 15000
            
            haiku_stats = stats['claude-3-5-haiku-20241022']
            assert haiku_stats['request_count'] == 45
            assert haiku_stats['total_cost'] == 0.85
            assert haiku_stats['cost_per_token'] == 0.85 / 25000
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, clickhouse_client):
        """Test successful health check."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            mock_execute.return_value = [{'health': 1}]
            
            is_healthy = await clickhouse_client.health_check()
            
            assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, clickhouse_client):
        """Test failed health check.""" 
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            mock_execute.return_value = []  # Empty result indicates failure
            
            is_healthy = await clickhouse_client.health_check()
            
            assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_exception(self, clickhouse_client):
        """Test health check with exception."""
        with patch.object(clickhouse_client, 'execute_query') as mock_execute:
            mock_execute.side_effect = Exception("Connection failed")
            
            is_healthy = await clickhouse_client.health_check()
            
            assert is_healthy is False