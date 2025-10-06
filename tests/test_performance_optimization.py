"""
Tests for Performance Optimization Monitor (Phase 3 component).
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from context_cleaner.monitoring.performance_optimizer import (
    PerformanceOptimizer,
    PerformanceSnapshot,
    OperationTracker,
)


@pytest.fixture
def performance_optimizer(test_config):
    """Create PerformanceOptimizer instance for testing."""
    return PerformanceOptimizer(test_config)


class TestPerformanceOptimizer:
    """Test suite for PerformanceOptimizer class."""

    def test_initialization(self, performance_optimizer):
        """Test proper initialization of performance optimizer."""
        assert performance_optimizer.is_monitoring is False
        assert performance_optimizer.baseline_cpu_percent == 15.0
        assert performance_optimizer.baseline_memory_mb == 50.0
        assert performance_optimizer.baseline_response_ms == 100.0
        assert len(performance_optimizer.snapshots) == 0
        assert len(performance_optimizer.operation_timings) == 0

    def test_start_stop_monitoring(self, performance_optimizer):
        """Test starting and stopping monitoring."""
        # Test start
        performance_optimizer.start_monitoring()
        assert performance_optimizer.is_monitoring is True
        assert performance_optimizer._monitor_thread is not None
        assert performance_optimizer._monitor_thread.is_alive()

        # Test stop
        performance_optimizer.stop_monitoring()
        assert performance_optimizer.is_monitoring is False

    def test_operation_tracker_context_manager(self, performance_optimizer):
        """Test operation tracking context manager."""
        # Track a quick operation
        with performance_optimizer.track_operation(
            "test_operation", context_tokens=1000
        ):
            time.sleep(0.1)  # Simulate work

        # Verify timing was recorded
        assert "test_operation" in performance_optimizer.operation_timings
        timings = performance_optimizer.operation_timings["test_operation"]
        assert len(timings) == 1
        assert timings[0] >= 100.0  # Should be at least 100ms

    def test_performance_summary_empty_data(self, performance_optimizer):
        """Test performance summary with no data."""
        summary = performance_optimizer.get_performance_summary(hours=24)

        assert summary["status"] == "no_data"
        assert (
            summary["message"]
            == "No performance data available for the specified period"
        )

    def test_performance_summary_with_data(self, performance_optimizer):
        """Test performance summary with mock data."""
        # Add mock snapshots
        base_time = datetime.now()
        for i in range(5):
            snapshot = PerformanceSnapshot(
                timestamp=base_time - timedelta(minutes=i * 10),
                cpu_percent=10.0 + i,
                memory_mb=40.0 + i * 2,
                disk_io_read_mb=0.1,
                disk_io_write_mb=0.05,
                operation_type="mock_operation",
                operation_duration_ms=50.0 + i * 10,
            )
            performance_optimizer.snapshots.append(snapshot)

        # Add operation timings
        performance_optimizer.operation_timings["mock_operation"] = [
            50.0,
            60.0,
            70.0,
            80.0,
            90.0,
        ]

        summary = performance_optimizer.get_performance_summary(hours=1)

        # Verify summary structure
        assert "period_hours" in summary
        assert "performance" in summary
        assert "operations" in summary
        assert "recommendations" in summary
        assert "baseline_comparison" in summary
        if "histograms" in summary:
            assert isinstance(summary["histograms"], dict)

        # Verify performance metrics
        perf = summary["performance"]
        assert "cpu_percent_avg" in perf
        assert "memory_mb_avg" in perf
        assert "health_score" in perf
        assert 0 <= perf["health_score"] <= 100

    def test_optimization_recommendations(self, performance_optimizer):
        """Test generation of optimization recommendations."""
        # Test with high CPU usage
        recommendations = performance_optimizer._generate_optimization_recommendations(
            avg_cpu=25.0,  # Above baseline of 15%
            max_cpu=60.0,  # High spike
            avg_memory=30.0,  # Below baseline
            max_memory=40.0,  # Below baseline
            operation_stats={},
        )

        assert len(recommendations) >= 2  # Should have CPU recommendations
        assert any("High CPU usage" in rec for rec in recommendations)
        assert any("CPU spikes" in rec for rec in recommendations)

    def test_performance_health_calculation(self, performance_optimizer):
        """Test performance health score calculation."""
        # Test perfect performance
        score = performance_optimizer._calculate_performance_health(
            avg_cpu=10.0,  # Below baseline
            avg_memory=30.0,  # Below baseline
            operation_stats={"test_op": {"performance_rating": "excellent"}},
        )
        assert score == 100

        # Test degraded performance
        score = performance_optimizer._calculate_performance_health(
            avg_cpu=30.0,  # Above baseline
            avg_memory=80.0,  # Above baseline
            operation_stats={"test_op": {"performance_rating": "slow"}},
        )
        assert score < 100

    def test_operation_performance_analysis(self, performance_optimizer):
        """Test analysis of operation performance."""
        # Add various operation timings
        performance_optimizer.operation_timings = {
            "fast_operation": [25.0, 30.0, 35.0],
            "medium_operation": [75.0, 80.0, 85.0],
            "slow_operation": [150.0, 200.0, 250.0],
        }

        stats = performance_optimizer._analyze_operation_performance()

        # Verify all operations are analyzed
        assert "fast_operation" in stats
        assert "medium_operation" in stats
        assert "slow_operation" in stats

        # Verify performance ratings
        assert stats["fast_operation"]["performance_rating"] == "excellent"
        assert stats["medium_operation"]["performance_rating"] == "good"
        assert stats["slow_operation"]["performance_rating"] == "slow"

        # Verify statistics
        assert stats["fast_operation"]["avg_duration_ms"] == 30.0
        assert stats["fast_operation"]["count"] == 3


class TestPerformanceSnapshot:
    """Test suite for PerformanceSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creation of performance snapshot."""
        timestamp = datetime.now()
        snapshot = PerformanceSnapshot(
            timestamp=timestamp,
            cpu_percent=15.5,
            memory_mb=45.2,
            disk_io_read_mb=0.1,
            disk_io_write_mb=0.05,
            operation_type="test_operation",
            operation_duration_ms=125.5,
            system_load_avg=0.8,
            context_size_tokens=1500,
        )

        assert snapshot.timestamp == timestamp
        assert snapshot.cpu_percent == 15.5
        assert snapshot.memory_mb == 45.2
        assert snapshot.operation_type == "test_operation"
        assert snapshot.operation_duration_ms == 125.5
        assert snapshot.system_load_avg == 0.8
        assert snapshot.context_size_tokens == 1500


class TestOperationTracker:
    """Test suite for OperationTracker context manager."""

    def test_operation_tracking(self, performance_optimizer):
        """Test operation tracking functionality."""
        operation_name = "test_tracking_operation"
        context_tokens = 2000

        # Use operation tracker
        with OperationTracker(performance_optimizer, operation_name, context_tokens):
            time.sleep(0.05)  # 50ms operation

        # Verify timing was recorded
        assert operation_name in performance_optimizer.operation_timings
        timings = performance_optimizer.operation_timings[operation_name]
        assert len(timings) == 1
        assert 45.0 <= timings[0] <= 100.0  # Should be around 50ms with tolerance
    def test_operation_tracker_exception_handling(self, performance_optimizer):
        """Test operation tracker handles exceptions gracefully."""
        operation_name = "failing_operation"

        try:
            with OperationTracker(performance_optimizer, operation_name):
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected

        # Timing should still be recorded despite exception
        assert operation_name in performance_optimizer.operation_timings
        assert len(performance_optimizer.operation_timings[operation_name]) == 1


@pytest.mark.integration
class TestPerformanceOptimizationIntegration:
    """Integration tests for performance optimization system."""

    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_io_counters")
    def test_monitoring_loop_integration(
        self, mock_disk_io, mock_memory, mock_cpu, performance_optimizer
    ):
        """Test the monitoring loop with mocked system calls."""
        # Setup mocks
        mock_cpu.return_value = 12.5
        mock_memory.return_value = MagicMock(used=52428800)  # 50MB
        mock_disk_io.return_value = MagicMock(read_bytes=1024, write_bytes=512)

        # Start monitoring briefly
        performance_optimizer.start_monitoring()
        time.sleep(0.2)  # Let monitoring run briefly
        performance_optimizer.stop_monitoring()

        # Verify snapshots were created
        assert len(performance_optimizer.snapshots) > 0

        # Verify snapshot data
        snapshot = performance_optimizer.snapshots[0]
        assert snapshot.cpu_percent == 12.5
        assert snapshot.memory_mb == 50.0  # 52428800 bytes / 1024^2
        assert snapshot.operation_type == "system_monitoring"

    def test_performance_optimization_workflow(self, performance_optimizer):
        """Test complete performance optimization workflow."""
        # Simulate multiple operations
        operations = [
            ("context_analysis", 1500, 0.08),
            ("dashboard_render", 500, 0.12),
            ("data_export", 2000, 0.15),
            ("optimization_apply", 1200, 0.06),
        ]

        for op_name, tokens, duration in operations:
            with performance_optimizer.track_operation(op_name, tokens):
                time.sleep(duration)

        # Generate performance summary
        performance_optimizer.snapshots.append(
            PerformanceSnapshot(
                timestamp=datetime.now(),
                cpu_percent=15.0,
                memory_mb=48.0,
                disk_io_read_mb=0.1,
                disk_io_write_mb=0.05,
                operation_type="system_monitoring",
                operation_duration_ms=0.0,
            )
        )

        summary = performance_optimizer.get_performance_summary(hours=1)

        # Verify comprehensive summary
        assert summary.get("status", "") != "no_data"
        assert len(summary["operations"]) == 4
        assert all(op in summary["operations"] for op, _, _ in operations)

        # Verify recommendations are generated
        assert len(summary["recommendations"]) > 0

        # Verify health score is calculated
        assert 0 <= summary["performance"]["health_score"] <= 100

    def test_storage_integration(self, performance_optimizer):
        """Test integration with encrypted storage system."""
        # Add some performance data
        with performance_optimizer.track_operation("storage_test", 1000):
            time.sleep(0.05)

        # Test save functionality (should not raise exceptions)
        try:
            performance_optimizer._save_performance_history()
        except Exception as e:
            pytest.fail(f"Storage save failed: {e}")

        # Test load functionality
        try:
            performance_optimizer._load_performance_history()
        except Exception as e:
            pytest.fail(f"Storage load failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
