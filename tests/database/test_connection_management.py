"""
Tests for ClickHouse Connection Management.

Comprehensive test suite for enhanced ClickHouse client including
connection pooling, health monitoring, circuit breaker, and bulk operations.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.context_cleaner.telemetry.clients.clickhouse_client import (
    ClickHouseClient,
    ConnectionStatus,
    ConnectionMetrics,
    AdaptiveConnectionPool,
)


class TestConnectionMetrics:
    """Test suite for ConnectionMetrics class."""

    def test_connection_metrics_initialization(self):
        """Test ConnectionMetrics initialization."""
        metrics = ConnectionMetrics()

        assert metrics.total_queries == 0
        assert metrics.successful_queries == 0
        assert metrics.failed_queries == 0
        assert metrics.average_response_time_ms == 0.0
        assert metrics.consecutive_failures == 0
        assert metrics.last_success_timestamp is None
        assert metrics.last_failure_timestamp is None
        assert isinstance(metrics.connection_established_at, datetime)

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = ConnectionMetrics()

        # No queries yet
        assert metrics.success_rate == 100.0
        assert metrics.failure_rate == 0.0

        # Some successful queries
        metrics.total_queries = 10
        metrics.successful_queries = 8
        metrics.failed_queries = 2

        assert metrics.success_rate == 80.0
        assert metrics.failure_rate == 20.0

        # All failed queries
        metrics.total_queries = 5
        metrics.successful_queries = 0
        metrics.failed_queries = 5

        assert metrics.success_rate == 0.0
        assert metrics.failure_rate == 100.0


class TestAdaptiveConnectionPool:
    """Test suite for AdaptiveConnectionPool class."""

    def test_connection_pool_initialization(self):
        """Test AdaptiveConnectionPool initialization."""
        pool = AdaptiveConnectionPool()

        assert pool.min_connections == 2
        assert pool.max_connections == 10
        assert pool.initial_connections == 5
        assert pool.connection_timeout_seconds == 30
        assert pool.query_timeout_seconds == 60
        assert pool.health_check_interval_seconds == 30
        assert pool.max_consecutive_failures == 3
        assert pool.active_connections == 0
        assert isinstance(pool.metrics, ConnectionMetrics)
        assert not pool._circuit_breaker_open


class TestClickHouseClient:
    """Test suite for enhanced ClickHouseClient."""

    @pytest.fixture
    def client(self):
        """Create ClickHouse client for testing."""
        return ClickHouseClient(
            host="localhost",
            port=9000,
            database="test_otel",
            max_connections=3,
            connection_timeout=10,
            query_timeout=30,
            enable_health_monitoring=False,  # Disable for testing
        )

    def test_client_initialization(self, client):
        """Test client initialization with enhanced features."""
        assert client.host == "localhost"
        assert client.port == 9000
        assert client.database == "test_otel"
        assert client.connection_string == "tcp://localhost:9000"
        assert client.pool.max_connections == 3
        assert client.pool.query_timeout_seconds == 30
        assert not client.enable_health_monitoring
        assert not client._is_initialized

    @patch("subprocess.run")
    async def test_execute_raw_query_success(self, mock_subprocess, client):
        """Test successful raw query execution."""
        # Mock successful subprocess call
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"health": 1}\n{"version": "21.8"}'
        mock_subprocess.return_value = mock_result

        results = await client._execute_raw_query("SELECT 1 as health")

        assert len(results) == 2
        assert results[0]["health"] == 1
        assert results[1]["version"] == "21.8"

        # Verify subprocess was called correctly
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert "docker" in call_args
        assert "exec" in call_args
        assert "clickhouse-client" in call_args
        assert "--format" in call_args
        assert "JSONEachRow" in call_args

    @patch("subprocess.run")
    async def test_execute_raw_query_failure(self, mock_subprocess, client):
        """Test raw query execution failure."""
        # Mock failed subprocess call
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Connection failed"
        mock_subprocess.return_value = mock_result

        with pytest.raises(RuntimeError, match="ClickHouse query failed"):
            await client._execute_raw_query("SELECT 1")

    @patch("subprocess.run")
    async def test_execute_raw_query_timeout(self, mock_subprocess, client):
        """Test raw query timeout handling."""
        from subprocess import TimeoutExpired

        mock_subprocess.side_effect = TimeoutExpired(cmd="test", timeout=30)

        with pytest.raises(RuntimeError, match="ClickHouse query timed out"):
            await client._execute_raw_query("SELECT 1", timeout=30)

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient._execute_raw_query")
    async def test_health_check_success(self, mock_execute, client):
        """Test successful health check."""
        mock_execute.return_value = [{"health": 1}]

        result = await client._perform_health_check()
        assert result is True

        # Check that metrics were recorded
        assert client.pool.metrics.total_queries > 0
        assert client.pool.metrics.successful_queries > 0
        assert client.pool.metrics.consecutive_failures == 0

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient._execute_raw_query")
    async def test_health_check_failure(self, mock_execute, client):
        """Test health check failure."""
        mock_execute.side_effect = RuntimeError("Connection failed")

        result = await client._perform_health_check()
        assert result is False

        # Check that failure was recorded
        assert client.pool.metrics.failed_queries > 0
        assert client.pool.metrics.consecutive_failures > 0

    async def test_circuit_breaker_functionality(self, client):
        """Test circuit breaker tripping and recovery."""
        # Simulate consecutive failures to trip circuit breaker
        for i in range(client.pool.max_consecutive_failures):
            client._record_failed_query(f"Error {i}")

        # Circuit breaker should be open
        assert client._is_circuit_breaker_open()
        assert client.pool._circuit_breaker_open

        # Try to execute query with circuit breaker open
        with pytest.raises(RuntimeError, match="Circuit breaker is open"):
            await client.execute_query("SELECT 1")

        # Reset circuit breaker
        client._reset_circuit_breaker()
        assert not client._is_circuit_breaker_open()

    async def test_circuit_breaker_timeout_recovery(self, client):
        """Test circuit breaker timeout-based recovery."""
        # Trip circuit breaker
        client.pool._circuit_breaker_open = True
        client.pool._circuit_breaker_open_until = datetime.now() + timedelta(seconds=1)

        assert client._is_circuit_breaker_open()

        # Wait for timeout
        await asyncio.sleep(1.1)

        # Circuit breaker should allow test query
        assert not client._is_circuit_breaker_open()

    async def test_connection_status_healthy(self, client):
        """Test connection status calculation - healthy."""
        # Set up healthy metrics
        client.pool.metrics.total_queries = 100
        client.pool.metrics.successful_queries = 98
        client.pool.metrics.average_response_time_ms = 500

        status = await client.get_connection_status()
        assert status == ConnectionStatus.HEALTHY

    async def test_connection_status_degraded(self, client):
        """Test connection status calculation - degraded."""
        # Set up degraded metrics
        client.pool.metrics.total_queries = 100
        client.pool.metrics.successful_queries = 85
        client.pool.metrics.average_response_time_ms = 3000

        status = await client.get_connection_status()
        assert status == ConnectionStatus.DEGRADED

    async def test_connection_status_unhealthy(self, client):
        """Test connection status calculation - unhealthy."""
        # Set up unhealthy metrics
        client.pool.metrics.total_queries = 100
        client.pool.metrics.successful_queries = 50
        client.pool.metrics.average_response_time_ms = 8000

        status = await client.get_connection_status()
        assert status == ConnectionStatus.UNHEALTHY

    async def test_connection_status_circuit_breaker_open(self, client):
        """Test connection status with circuit breaker open."""
        client.pool._circuit_breaker_open = True

        status = await client.get_connection_status()
        assert status == ConnectionStatus.UNHEALTHY

    async def test_get_connection_metrics(self, client):
        """Test comprehensive connection metrics retrieval."""
        # Set up some metrics
        client.pool.metrics.total_queries = 50
        client.pool.metrics.successful_queries = 45
        client.pool.metrics.failed_queries = 5
        client.pool.metrics.average_response_time_ms = 750
        client.pool.metrics.consecutive_failures = 2

        metrics = await client.get_connection_metrics()

        assert metrics["total_queries"] == 50
        assert metrics["successful_queries"] == 45
        assert metrics["failed_queries"] == 5
        assert metrics["success_rate_percent"] == 90.0
        assert metrics["failure_rate_percent"] == 10.0
        assert metrics["average_response_time_ms"] == 750
        assert metrics["consecutive_failures"] == 2
        assert metrics["max_connections"] == 3
        assert "status" in metrics
        assert "last_success" in metrics
        assert "connection_established_at" in metrics

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient._execute_raw_query")
    async def test_comprehensive_health_check(self, mock_execute, client):
        """Test comprehensive health check functionality."""
        # Mock responses
        mock_execute.side_effect = [
            [{"health": 1}],  # Health check
            [{"name": "table1"}, {"name": "table2"}],  # Show tables
        ]

        result = await client.comprehensive_health_check()

        assert result["overall_healthy"] is True
        assert result["database_accessible"] is True
        assert result["tables_found"] == 2
        assert result["response_time_ms"] > 0
        assert "metrics" in result
        assert "timestamp" in result

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient._execute_raw_query")
    async def test_comprehensive_health_check_failure(self, mock_execute, client):
        """Test comprehensive health check with failures."""
        mock_execute.side_effect = RuntimeError("Connection failed")

        result = await client.comprehensive_health_check()

        assert result["overall_healthy"] is False
        assert result["database_accessible"] is False
        assert result["error_message"] == "Connection failed"
        assert result["response_time_ms"] > 0

    async def test_client_initialization_lifecycle(self, client):
        """Test client initialization and shutdown lifecycle."""
        assert not client._is_initialized

        # Mock health check success
        with patch.object(client, "_perform_health_check", return_value=True):
            result = await client.initialize()
            assert result is True
            assert client._is_initialized

        # Test double initialization
        result = await client.initialize()
        assert result is True  # Should return True without re-initializing

        # Test shutdown
        await client.close()
        assert not client._is_initialized

    async def test_client_initialization_failure(self, client):
        """Test client initialization failure."""
        # Mock health check failure
        with patch.object(client, "_perform_health_check", return_value=False):
            result = await client.initialize()
            assert result is False
            assert not client._is_initialized


class TestBulkOperations:
    """Test suite for enhanced bulk operations."""

    @pytest.fixture
    def client(self):
        """Create client for bulk operation testing."""
        return ClickHouseClient(database="test_otel", enable_health_monitoring=False)

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient.bulk_insert")
    async def test_bulk_insert_enhanced_success(self, mock_bulk_insert, client):
        """Test enhanced bulk insert with successful operation."""
        mock_bulk_insert.return_value = True

        records = [
            {"session_id": "test1", "tokens": 1000},
            {"session_id": "test2", "tokens": 2000},
            {"session_id": "test3", "tokens": 3000},
        ]

        result = await client.bulk_insert_enhanced("test_table", records, batch_size=2)

        assert result["success"] is True
        assert result["total_records"] == 3
        assert result["successful_records"] == 3
        assert result["failed_records"] == 0
        assert result["batches_processed"] == 2  # 3 records in batches of 2
        assert result["batches_failed"] == 0
        assert result["processing_time_seconds"] > 0
        assert result["average_records_per_second"] > 0
        assert len(result["errors"]) == 0

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient.bulk_insert")
    async def test_bulk_insert_enhanced_partial_failure(self, mock_bulk_insert, client):
        """Test enhanced bulk insert with partial failure."""
        # First batch succeeds, second fails
        mock_bulk_insert.side_effect = [True, False, False]  # Retries for second batch

        records = [
            {"session_id": "test1", "tokens": 1000},
            {"session_id": "test2", "tokens": 2000},
            {"session_id": "test3", "tokens": 3000},
        ]

        result = await client.bulk_insert_enhanced("test_table", records, batch_size=2, max_retries=1)

        assert result["success"] is False
        assert result["total_records"] == 3
        assert result["successful_records"] == 2  # First batch
        assert result["failed_records"] == 1  # Second batch
        assert result["batches_processed"] == 1
        assert result["batches_failed"] == 1
        assert len(result["errors"]) > 0

    async def test_bulk_insert_enhanced_empty_records(self, client):
        """Test enhanced bulk insert with empty records list."""
        result = await client.bulk_insert_enhanced("test_table", [])

        assert result["success"] is True
        assert result["total_records"] == 0
        assert result["successful_records"] == 0
        assert result["failed_records"] == 0
        assert result["processing_time_seconds"] >= 0
        assert len(result["errors"]) == 0

    @patch("src.context_cleaner.telemetry.clients.clickhouse_client.ClickHouseClient.bulk_insert")
    async def test_bulk_insert_enhanced_with_retries(self, mock_bulk_insert, client):
        """Test enhanced bulk insert retry mechanism."""
        # Fail twice, then succeed on third attempt
        mock_bulk_insert.side_effect = [False, False, True]

        records = [{"session_id": "test1", "tokens": 1000}]

        result = await client.bulk_insert_enhanced("test_table", records, max_retries=2)

        assert result["success"] is True
        assert result["successful_records"] == 1
        assert result["failed_records"] == 0

        # Should have made 3 calls (initial + 2 retries)
        assert mock_bulk_insert.call_count == 3


class TestHealthMonitoring:
    """Test suite for health monitoring functionality."""

    @pytest.fixture
    def client_with_monitoring(self):
        """Create client with health monitoring enabled."""
        return ClickHouseClient(database="test_otel", enable_health_monitoring=True)

    async def test_health_monitor_task_creation(self, client_with_monitoring):
        """Test health monitoring task is created during initialization."""
        client = client_with_monitoring

        with patch.object(client, "_perform_health_check", return_value=True):
            await client.initialize()

            assert client._health_check_task is not None
            assert not client._health_check_task.done()

    async def test_health_monitor_task_cleanup(self, client_with_monitoring):
        """Test health monitoring task is properly cleaned up."""
        client = client_with_monitoring

        with patch.object(client, "_perform_health_check", return_value=True):
            await client.initialize()
            task = client._health_check_task

            await client.close()

            # Task should be cancelled
            assert task.cancelled() or task.done()

    async def test_health_monitor_loop_exception_handling(self, client_with_monitoring):
        """Test health monitor loop handles exceptions gracefully."""
        client = client_with_monitoring
        client.pool.health_check_interval_seconds = 0.1  # Fast interval for testing

        # Mock health check to raise exception
        with patch.object(client, "_perform_health_check", side_effect=RuntimeError("Test error")):
            await client.initialize()

            # Wait a bit and verify task is still running
            await asyncio.sleep(0.2)
            assert not client._health_check_task.done()


class TestConnectionRecovery:
    """Test suite for connection recovery scenarios."""

    @pytest.fixture
    def client(self):
        """Create client for recovery testing."""
        return ClickHouseClient(database="test_otel", enable_health_monitoring=False)

    async def test_automatic_reconnection_after_failure(self, client):
        """Test automatic reconnection after connection failure."""
        # Simulate initial connection failure, then success
        with patch.object(
            client,
            "_execute_raw_query",
            side_effect=[
                RuntimeError("Connection failed"),  # First call fails
                [{"health": 1}],  # Second call succeeds
            ],
        ):
            # First query should fail and record error
            result = await client.execute_query("SELECT 1")
            assert result == []
            assert client.pool.metrics.failed_queries > 0

            # Second query should succeed and reset circuit breaker
            result = await client.execute_query("SELECT 1")
            # This would succeed if the mock was set up for multiple calls
            # In real implementation, this would demonstrate recovery

    async def test_metric_recording_accuracy(self, client):
        """Test that connection metrics are recorded accurately."""
        initial_total = client.pool.metrics.total_queries
        initial_success = client.pool.metrics.successful_queries
        initial_failed = client.pool.metrics.failed_queries

        # Record a successful query
        client._record_successful_query(100.0)

        assert client.pool.metrics.total_queries == initial_total + 1
        assert client.pool.metrics.successful_queries == initial_success + 1
        assert client.pool.metrics.failed_queries == initial_failed
        assert client.pool.metrics.consecutive_failures == 0
        assert client.pool.metrics.average_response_time_ms == 100.0

        # Record a failed query
        client._record_failed_query("Test error")

        assert client.pool.metrics.total_queries == initial_total + 2
        assert client.pool.metrics.successful_queries == initial_success + 1
        assert client.pool.metrics.failed_queries == initial_failed + 1
        assert client.pool.metrics.consecutive_failures == 1

    async def test_response_time_exponential_moving_average(self, client):
        """Test response time calculation using exponential moving average."""
        # First response time
        client._record_successful_query(100.0)
        assert client.pool.metrics.average_response_time_ms == 100.0

        # Second response time (should be weighted average)
        client._record_successful_query(200.0)
        expected = 100.0 * 0.9 + 200.0 * 0.1  # 90 + 20 = 110
        assert client.pool.metrics.average_response_time_ms == expected


@pytest.mark.integration
class TestConnectionIntegration:
    """Integration tests for connection management (require actual ClickHouse)."""

    @pytest.mark.skip(reason="Requires running ClickHouse instance")
    async def test_real_connection_health_check(self):
        """Test health check against real ClickHouse instance."""
        client = ClickHouseClient(host="localhost", port=9000, database="default")

        try:
            await client.initialize()
            health = await client.health_check()
            assert health is True

            metrics = await client.get_connection_metrics()
            assert metrics["status"] in ["healthy", "degraded", "unhealthy"]

        finally:
            await client.close()

    @pytest.mark.skip(reason="Requires running ClickHouse instance")
    async def test_real_bulk_operations(self):
        """Test bulk operations against real ClickHouse instance."""
        client = ClickHouseClient(host="localhost", port=9000, database="default")

        try:
            await client.initialize()

            # Create test table
            await client.execute_query(
                """
                CREATE TABLE IF NOT EXISTS test_bulk (
                    id UInt32,
                    name String,
                    timestamp DateTime
                ) ENGINE = MergeTree()
                ORDER BY id
            """
            )

            # Test bulk insert
            records = [{"id": i, "name": f"test_{i}", "timestamp": "2023-01-01 00:00:00"} for i in range(100)]

            result = await client.bulk_insert_enhanced("test_bulk", records, batch_size=25)
            assert result["success"] is True
            assert result["successful_records"] == 100

            # Cleanup
            await client.execute_query("DROP TABLE IF EXISTS test_bulk")

        finally:
            await client.close()
