"""
Core Token Analysis Bridge Service Tests

Comprehensive unit tests for the Enhanced Token Analysis Bridge service,
covering core functionality, data validation, error handling, and health checks.
"""

import asyncio
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any

from src.context_cleaner.services.token_analysis_bridge import TokenAnalysisBridge, CircuitBreaker
from src.context_cleaner.models.token_bridge_models import (
    SessionTokenMetrics, BridgeResult, BridgeHealthStatus, BridgeConfiguration,
    BridgeOperationStatus, HealthStatus
)
from src.context_cleaner.exceptions.bridge_exceptions import (
    BridgeValidationError, BridgeStorageError, BridgeConnectionError, 
    BridgeCircuitBreakerError
)


class TestSessionTokenMetrics:
    """Test suite for SessionTokenMetrics data model."""
    
    def test_create_session_metrics(self):
        """Test creating basic session metrics."""
        metrics = SessionTokenMetrics(
            session_id="test-session-123",
            reported_input_tokens=1000,
            reported_output_tokens=500,
            calculated_total_tokens=1600
        )
        
        assert metrics.session_id == "test-session-123"
        assert metrics.total_reported_tokens == 1500
        assert metrics.calculated_total_tokens == 1600
    
    def test_calculate_accuracy_ratio(self):
        """Test accuracy ratio calculation."""
        metrics = SessionTokenMetrics(
            session_id="test-session",
            reported_input_tokens=800,
            reported_output_tokens=200,
            calculated_total_tokens=1200
        )
        
        metrics.calculate_accuracy_ratio()
        assert abs(metrics.accuracy_ratio - 1.2) < 0.001  # 1200 / 1000 = 1.2
    
    def test_calculate_undercount_percentage(self):
        """Test undercount percentage calculation."""
        metrics = SessionTokenMetrics(
            session_id="test-session",
            reported_input_tokens=800,
            reported_output_tokens=200,
            calculated_total_tokens=1500
        )
        
        metrics.calculate_undercount_percentage()
        expected = ((1500 - 1000) / 1500) * 100  # 33.33%
        assert abs(metrics.undercount_percentage - expected) < 0.1
    
    def test_validate_valid_metrics(self):
        """Test validation of valid session metrics."""
        metrics = SessionTokenMetrics(
            session_id="valid-session",
            reported_input_tokens=1000,
            reported_output_tokens=500,
            calculated_total_tokens=1400,
            accuracy_ratio=1.4,
            undercount_percentage=28.6,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=30)
        )
        
        errors = metrics.validate()
        assert len(errors) == 0
    
    def test_validate_invalid_metrics(self):
        """Test validation of invalid session metrics."""
        metrics = SessionTokenMetrics(
            session_id="",  # Invalid: empty session ID
            reported_input_tokens=-100,  # Invalid: negative tokens
            calculated_total_tokens=-50,  # Invalid: negative tokens
            accuracy_ratio=-0.5,  # Invalid: negative ratio
            undercount_percentage=150,  # Invalid: over 100%
            start_time=datetime.now(),
            end_time=datetime.now() - timedelta(hours=1)  # Invalid: end before start
        )
        
        errors = metrics.validate()
        assert len(errors) >= 6  # Should have multiple validation errors
        assert any("session_id" in error for error in errors)
        assert any("negative" in error for error in errors)
    
    def test_to_clickhouse_record(self):
        """Test conversion to ClickHouse record format."""
        metrics = SessionTokenMetrics(
            session_id="test-session",
            start_time=datetime(2024, 1, 1, 12, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 30, 0),
            reported_input_tokens=1000,
            reported_output_tokens=500,
            calculated_total_tokens=1800,
            content_categories={"claude_md": 500, "user_messages": 1000}
        )
        
        record = metrics.to_clickhouse_record()
        
        assert record["session_id"] == "test-session"
        assert "2024-01-01 12:00:00" in record["start_time"]
        assert "2024-01-01 12:30:00" in record["end_time"]
        assert record["reported_input_tokens"] == 1000
        assert record["total_reported_tokens"] == 1500
        assert "claude_md" in record["content_categories"]


class TestCircuitBreaker:
    """Test suite for CircuitBreaker functionality."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state (normal operation)."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        async def mock_operation():
            return "success"
        
        result = await breaker.call(mock_operation)
        assert result == "success"
        assert breaker.state == "closed"
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_tracking(self):
        """Test circuit breaker failure count tracking."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        async def failing_operation():
            raise Exception("Test failure")
        
        # First two failures should not open circuit
        for i in range(2):
            with pytest.raises(Exception, match="Test failure"):
                await breaker.call(failing_operation)
            assert breaker.state == "closed"
            assert breaker.failure_count == i + 1
        
        # Third failure should open circuit
        with pytest.raises(Exception, match="Test failure"):
            await breaker.call(failing_operation)
        assert breaker.state == "open"
        assert breaker.failure_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self):
        """Test circuit breaker in open state (failures blocked)."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        breaker.failure_count = 3
        breaker.state = "open"
        breaker.last_failure_time = datetime.now()
        
        async def mock_operation():
            return "should not be called"
        
        with pytest.raises(BridgeCircuitBreakerError):
            await breaker.call(mock_operation)


class TestTokenAnalysisBridge:
    """Test suite for TokenAnalysisBridge service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_clickhouse = AsyncMock()
        self.mock_enhanced_counter = AsyncMock()
        self.config = BridgeConfiguration(
            batch_size=10,
            max_retries=2,
            enable_validation=True
        )
        
        self.bridge = TokenAnalysisBridge(
            clickhouse_client=self.mock_clickhouse,
            enhanced_counter=self.mock_enhanced_counter,
            config=self.config
        )
    
    @pytest.mark.asyncio
    async def test_store_session_metrics_success(self):
        """Test successful storage of session metrics."""
        # Prepare test data
        metrics = SessionTokenMetrics(
            session_id="test-session-123",
            reported_input_tokens=1000,
            reported_output_tokens=500,
            calculated_total_tokens=1800
        )
        
        # Mock dependencies
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[])  # No existing session
        self.mock_clickhouse.bulk_insert = AsyncMock(return_value=True)
        
        # Execute operation
        result = await self.bridge.store_session_metrics(metrics)
        
        # Verify results
        assert result.success is True
        assert result.records_stored == 1
        assert result.total_tokens == 1800
        assert result.session_id == "test-session-123"
        assert result.status == BridgeOperationStatus.SUCCESS
        
        # Verify ClickHouse calls
        self.mock_clickhouse.bulk_insert.assert_called_once()
        call_args = self.mock_clickhouse.bulk_insert.call_args
        assert call_args[0][0] == "enhanced_token_summaries"
        assert len(call_args[0][1]) == 1  # One record
    
    @pytest.mark.asyncio
    async def test_store_session_metrics_validation_error(self):
        """Test storage failure due to validation errors."""
        # Create invalid metrics
        metrics = SessionTokenMetrics(
            session_id="",  # Invalid empty session ID
            reported_input_tokens=-100,  # Invalid negative tokens
            calculated_total_tokens=1000
        )
        
        # Execute and expect validation error
        with pytest.raises(BridgeValidationError) as exc_info:
            await self.bridge.store_session_metrics(metrics)
        
        assert "session_id" in str(exc_info.value)
        assert exc_info.value.session_id == ""
        assert len(exc_info.value.validation_failures) > 0
    
    @pytest.mark.asyncio
    async def test_store_session_metrics_duplicate_handling(self):
        """Test handling of duplicate session metrics."""
        metrics = SessionTokenMetrics(
            session_id="existing-session",
            calculated_total_tokens=1500
        )
        
        # Mock existing session found
        self.mock_clickhouse.execute_query = AsyncMock(
            return_value=[{"session_id": "existing-session"}]
        )
        
        result = await self.bridge.store_session_metrics(metrics)
        
        # Should skip storage and return warning
        assert result.success is True
        assert result.records_stored == 0
        assert len(result.warnings) > 0
        assert "already exists" in result.warnings[0]
        
        # Verify no bulk insert was attempted
        self.mock_clickhouse.bulk_insert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_store_session_metrics_force_update(self):
        """Test forced update of existing session metrics."""
        metrics = SessionTokenMetrics(
            session_id="existing-session",
            calculated_total_tokens=2000
        )
        
        # Mock existing session found
        self.mock_clickhouse.execute_query = AsyncMock(
            return_value=[{"session_id": "existing-session"}]
        )
        self.mock_clickhouse.bulk_insert = AsyncMock(return_value=True)
        
        result = await self.bridge.store_session_metrics(metrics, force_update=True)
        
        # Should proceed with storage despite existing session
        assert result.success is True
        assert result.records_stored == 1
        assert result.total_tokens == 2000
        
        # Verify storage was called
        self.mock_clickhouse.bulk_insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_session_metrics_storage_failure(self):
        """Test handling of database storage failures."""
        metrics = SessionTokenMetrics(
            session_id="test-session",
            calculated_total_tokens=1000
        )
        
        # Mock storage failure
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[])
        self.mock_clickhouse.bulk_insert = AsyncMock(return_value=False)
        
        with pytest.raises(BridgeStorageError) as exc_info:
            await self.bridge.store_session_metrics(metrics)
        
        assert "Failed to insert session record" in str(exc_info.value)
        assert exc_info.value.session_ids == ["test-session"]
    
    @pytest.mark.asyncio
    async def test_get_session_metrics_found(self):
        """Test successful retrieval of session metrics."""
        # Mock ClickHouse response
        mock_record = {
            "session_id": "test-session",
            "reported_input_tokens": 1000,
            "reported_output_tokens": 500,
            "calculated_total_tokens": 1800,
            "accuracy_ratio": 1.2,
            "undercount_percentage": 16.7,
            "content_categories": '{"claude_md": 500, "user_messages": 1000}',
            "created_at": "2024-01-01 12:00:00"
        }
        
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[mock_record])
        
        result = await self.bridge.get_session_metrics("test-session")
        
        assert result is not None
        assert result.session_id == "test-session"
        assert result.reported_input_tokens == 1000
        assert result.calculated_total_tokens == 1800
        assert "claude_md" in result.content_categories
    
    @pytest.mark.asyncio
    async def test_get_session_metrics_not_found(self):
        """Test retrieval when session metrics not found."""
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[])
        
        result = await self.bridge.get_session_metrics("nonexistent-session")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_bulk_store_sessions(self):
        """Test bulk storage of multiple session metrics."""
        sessions = [
            SessionTokenMetrics(session_id=f"session-{i}", calculated_total_tokens=1000 + i * 100)
            for i in range(25)  # 25 sessions, will be split into 3 batches of 10
        ]
        
        self.mock_clickhouse.bulk_insert = AsyncMock(return_value=True)
        
        progress_calls = []
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        results = await self.bridge.bulk_store_sessions(
            sessions, 
            batch_size=10, 
            progress_callback=progress_callback
        )
        
        # Verify results
        assert len(results) == 3  # 3 batches
        assert all(result.success for result in results)
        total_stored = sum(result.records_stored for result in results)
        assert total_stored == 25
        
        # Verify progress callbacks
        assert len(progress_calls) == 3
        assert progress_calls[-1] == (25, 25)  # Final progress should be complete
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when service is healthy."""
        # Mock healthy responses
        self.mock_clickhouse.health_check = AsyncMock(return_value=True)
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[
            {"total_sessions": 100, "total_tokens": 1500000}
        ])
        
        # Add some successful operation history
        self.bridge.operation_history = [
            {"timestamp": datetime.now(), "success": True, "processing_time": 0.1},
            {"timestamp": datetime.now(), "success": True, "processing_time": 0.15},
            {"timestamp": datetime.now(), "success": True, "processing_time": 0.08}
        ]
        
        health = await self.bridge.health_check()
        
        assert health.status == HealthStatus.HEALTHY
        assert health.database_connected is True
        assert health.database_response_time_ms is not None
        assert health.recent_success_rate == 100.0
        assert health.total_sessions_stored == 100
        assert health.total_tokens_stored == 1500000
    
    @pytest.mark.asyncio
    async def test_health_check_database_failure(self):
        """Test health check when database is unhealthy."""
        self.mock_clickhouse.health_check = AsyncMock(return_value=False)
        
        health = await self.bridge.health_check()
        
        assert health.status == HealthStatus.UNHEALTHY
        assert health.database_connected is False
        assert "Database connection failed" in health.message
    
    @pytest.mark.asyncio
    async def test_health_check_degraded_performance(self):
        """Test health check with degraded performance."""
        self.mock_clickhouse.health_check = AsyncMock(return_value=True)
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[
            {"total_sessions": 50, "total_tokens": 750000}
        ])
        
        # Add mixed operation history (low success rate)
        self.bridge.operation_history = [
            {"timestamp": datetime.now(), "success": True, "processing_time": 0.1},
            {"timestamp": datetime.now(), "success": False, "processing_time": 0.2},
            {"timestamp": datetime.now(), "success": False, "processing_time": 0.25},
            {"timestamp": datetime.now(), "success": True, "processing_time": 0.12}
        ]
        
        health = await self.bridge.health_check()
        
        assert health.status == HealthStatus.DEGRADED
        assert health.recent_success_rate == 50.0
        assert "Success rate below threshold" in health.message
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with bridge operations."""
        # Use a configuration with lower failure threshold for testing
        test_config = BridgeConfiguration(failure_threshold=3, enable_validation=False)
        bridge = TokenAnalysisBridge(
            clickhouse_client=self.mock_clickhouse,
            config=test_config
        )
        
        # Mock storage failures to trigger circuit breaker
        self.mock_clickhouse.execute_query = AsyncMock(return_value=[])
        self.mock_clickhouse.bulk_insert = AsyncMock(side_effect=Exception("Database error"))
        
        # First few failures should raise storage errors
        for i in range(3):
            with pytest.raises(BridgeStorageError):
                await bridge.store_session_metrics(
                    SessionTokenMetrics(session_id=f"session-{i}", calculated_total_tokens=1000)
                )
        
        # After threshold, should get circuit breaker error
        with pytest.raises(BridgeCircuitBreakerError):
            await bridge.store_session_metrics(
                SessionTokenMetrics(session_id="final-session", calculated_total_tokens=1000)
            )


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """Integration test scenarios for bridge service."""
    
    async def test_end_to_end_session_storage_and_retrieval(self):
        """Test complete flow from storage to retrieval."""
        # This would be an integration test that uses real ClickHouse
        # For now, we'll mock but test the complete flow
        
        mock_clickhouse = AsyncMock()
        bridge = TokenAnalysisBridge(clickhouse_client=mock_clickhouse)
        
        # Test data
        original_metrics = SessionTokenMetrics(
            session_id="integration-test-session",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=30),
            reported_input_tokens=2000,
            reported_output_tokens=800,
            calculated_total_tokens=3200,
            content_categories={"claude_md": 1000, "user_messages": 2000}
        )
        
        # Mock storage
        mock_clickhouse.execute_query = AsyncMock(return_value=[])  # No existing session
        mock_clickhouse.bulk_insert = AsyncMock(return_value=True)
        
        # Store session
        store_result = await bridge.store_session_metrics(original_metrics)
        assert store_result.success
        
        # Mock retrieval
        stored_record = original_metrics.to_clickhouse_record()
        mock_clickhouse.execute_query = AsyncMock(return_value=[stored_record])
        
        # Retrieve session
        retrieved_metrics = await bridge.get_session_metrics("integration-test-session")
        
        # Verify round-trip accuracy
        assert retrieved_metrics is not None
        assert retrieved_metrics.session_id == original_metrics.session_id
        assert retrieved_metrics.calculated_total_tokens == original_metrics.calculated_total_tokens
        assert retrieved_metrics.content_categories == original_metrics.content_categories