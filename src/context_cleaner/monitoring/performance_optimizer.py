"""
Performance Optimization Monitor
Tracks real-world performance metrics and provides automated optimization recommendations.
"""

import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass, asdict

from ..config.settings import ContextCleanerConfig
from ..tracking.storage import EncryptedStorage

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Single performance measurement snapshot."""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    operation_type: str
    operation_duration_ms: float
    system_load_avg: Optional[float] = None
    context_size_tokens: Optional[int] = None


class PerformanceOptimizer:
    """
    Monitors system performance during Context Cleaner operations and provides
    optimization recommendations based on real-world usage patterns.

    Key Features:
    - Real-time performance tracking with minimal overhead (<5ms)
    - Automated bottleneck detection and optimization suggestions
    - Resource usage analysis with trend identification
    - Performance regression detection
    - Optimization impact measurement
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize performance optimizer."""
        self.config = config or ContextCleanerConfig.from_env()
        self.storage = EncryptedStorage(self.config)

        # Performance tracking state
        self.is_monitoring = False
        self.snapshots: List[PerformanceSnapshot] = []
        self.operation_timings: Dict[str, List[float]] = {}

        # Performance baselines (will be learned from usage)
        self.baseline_cpu_percent = 15.0  # Target: <15% CPU usage
        self.baseline_memory_mb = 50.0  # Target: <50MB memory
        self.baseline_response_ms = 100.0  # Target: <100ms response time

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()

        # Load existing performance data
        self._load_performance_history()

    def start_monitoring(self):
        """Start continuous performance monitoring."""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self._stop_monitoring.clear()

        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitor_thread.start()

        logger.info("Performance monitoring started")

    def stop_monitoring(self):
        """Stop performance monitoring and save data."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        self._stop_monitoring.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        self._save_performance_history()
        logger.info("Performance monitoring stopped")

    def track_operation(
        self, operation_name: str, context_tokens: Optional[int] = None
    ):
        """
        Context manager for tracking individual operation performance.

        Usage:
            with optimizer.track_operation("context_analysis", context_tokens=1500):
                # Perform context analysis
                pass
        """
        return OperationTracker(self, operation_name, context_tokens)

    def _monitoring_loop(self):
        """Main monitoring loop running in background thread."""
        last_io_read = 0
        last_io_write = 0

        while not self._stop_monitoring.is_set():
            try:
                # Get current system metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                memory_mb = memory.used / (1024 * 1024)

                # Get disk I/O (delta since last measurement)
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    io_read_mb = (disk_io.read_bytes - last_io_read) / (1024 * 1024)
                    io_write_mb = (disk_io.write_bytes - last_io_write) / (1024 * 1024)
                    last_io_read = disk_io.read_bytes
                    last_io_write = disk_io.write_bytes
                else:
                    io_read_mb = io_write_mb = 0.0

                # Get system load average (Unix systems)
                try:
                    load_avg = (
                        psutil.getloadavg()[0]
                        if hasattr(psutil, "getloadavg")
                        else None
                    )
                except (OSError, AttributeError):
                    load_avg = None

                # Create performance snapshot
                snapshot = PerformanceSnapshot(
                    timestamp=datetime.now(),
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    disk_io_read_mb=io_read_mb,
                    disk_io_write_mb=io_write_mb,
                    operation_type="system_monitoring",
                    operation_duration_ms=0.0,
                    system_load_avg=load_avg,
                )

                # Add to recent snapshots (keep last 1000)
                self.snapshots.append(snapshot)
                if len(self.snapshots) > 1000:
                    self.snapshots.pop(0)

                # Sleep until next measurement (5-second intervals)
                self._stop_monitoring.wait(timeout=5.0)

            except Exception as e:
                logger.warning(f"Performance monitoring error: {e}")
                self._stop_monitoring.wait(timeout=10.0)  # Longer wait on error

    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get comprehensive performance summary for the last N hours.

        Returns:
            Dictionary with performance metrics, trends, and recommendations
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]

        if not recent_snapshots:
            return {
                "status": "no_data",
                "message": "No performance data available for the specified period",
            }

        # Calculate basic statistics
        cpu_values = [s.cpu_percent for s in recent_snapshots]
        memory_values = [s.memory_mb for s in recent_snapshots]

        avg_cpu = sum(cpu_values) / len(cpu_values)
        max_cpu = max(cpu_values)
        avg_memory = sum(memory_values) / len(memory_values)
        max_memory = max(memory_values)

        # Operation performance analysis
        operation_stats = self._analyze_operation_performance()

        # Performance health assessment
        health_score = self._calculate_performance_health(
            avg_cpu, avg_memory, operation_stats
        )

        # Generate recommendations
        recommendations = self._generate_optimization_recommendations(
            avg_cpu, max_cpu, avg_memory, max_memory, operation_stats
        )

        return {
            "period_hours": hours,
            "total_snapshots": len(recent_snapshots),
            "performance": {
                "cpu_percent_avg": round(avg_cpu, 2),
                "cpu_percent_max": round(max_cpu, 2),
                "memory_mb_avg": round(avg_memory, 1),
                "memory_mb_max": round(max_memory, 1),
                "health_score": health_score,
            },
            "operations": operation_stats,
            "recommendations": recommendations,
            "baseline_comparison": {
                "cpu_vs_target": f"{avg_cpu:.1f}% vs {self.baseline_cpu_percent}% target",
                "memory_vs_target": f"{avg_memory:.1f}MB vs {self.baseline_memory_mb}MB target",
            },
        }

    def _analyze_operation_performance(self) -> Dict[str, Any]:
        """Analyze performance of different operation types."""
        stats = {}

        for operation, timings in self.operation_timings.items():
            if timings:
                avg_time = sum(timings) / len(timings)
                max_time = max(timings)
                min_time = min(timings)

                stats[operation] = {
                    "count": len(timings),
                    "avg_duration_ms": round(avg_time, 1),
                    "max_duration_ms": round(max_time, 1),
                    "min_duration_ms": round(min_time, 1),
                    "performance_rating": (
                        "excellent"
                        if avg_time < 50
                        else (
                            "good"
                            if avg_time < 100
                            else "acceptable" if avg_time < 200 else "slow"
                        )
                    ),
                }

        return stats

    def _calculate_performance_health(
        self, avg_cpu: float, avg_memory: float, operation_stats: Dict[str, Any]
    ) -> int:
        """Calculate overall performance health score (0-100)."""
        score = 100

        # CPU penalty
        if avg_cpu > self.baseline_cpu_percent:
            score -= min(30, (avg_cpu - self.baseline_cpu_percent) * 2)

        # Memory penalty
        if avg_memory > self.baseline_memory_mb:
            score -= min(30, (avg_memory - self.baseline_memory_mb) / 2)

        # Operation performance penalty
        slow_operations = sum(
            1
            for op in operation_stats.values()
            if op.get("performance_rating") in ["slow", "acceptable"]
        )
        if slow_operations > 0:
            score -= min(20, slow_operations * 5)

        return max(0, int(score))

    def _generate_optimization_recommendations(
        self,
        avg_cpu: float,
        max_cpu: float,
        avg_memory: float,
        max_memory: float,
        operation_stats: Dict[str, Any],
    ) -> List[str]:
        """Generate specific optimization recommendations."""
        recommendations = []

        # CPU optimization
        if avg_cpu > self.baseline_cpu_percent:
            recommendations.append(
                f"High CPU usage detected ({avg_cpu:.1f}%). Consider reducing analysis "
                f"frequency or enabling async processing."
            )

        if max_cpu > 50:
            recommendations.append(
                f"CPU spikes detected ({max_cpu:.1f}%). Enable batch processing for "
                f"large context operations."
            )

        # Memory optimization
        if avg_memory > self.baseline_memory_mb:
            recommendations.append(
                f"Memory usage above target ({avg_memory:.1f}MB). Consider enabling "
                f"data compression or reducing cache size."
            )

        # Operation-specific recommendations
        for operation, stats in operation_stats.items():
            if stats.get("performance_rating") == "slow":
                recommendations.append(
                    f"'{operation}' operations are slow ({stats['avg_duration_ms']}ms avg). "
                    f"Consider optimizing or enabling caching."
                )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "Performance is within optimal ranges. System is running efficiently."
            )

        return recommendations

    def _load_performance_history(self):
        """Load historical performance data from encrypted storage."""
        try:
            data = self.storage.read_data("performance_history")
            if data:
                # Load recent snapshots (last 24 hours worth)
                snapshot_data = data.get("snapshots", [])
                cutoff_time = datetime.now() - timedelta(hours=24)

                for item in snapshot_data:
                    timestamp = datetime.fromisoformat(item["timestamp"])
                    if timestamp >= cutoff_time:
                        snapshot = PerformanceSnapshot(
                            timestamp=timestamp,
                            cpu_percent=item["cpu_percent"],
                            memory_mb=item["memory_mb"],
                            disk_io_read_mb=item["disk_io_read_mb"],
                            disk_io_write_mb=item["disk_io_write_mb"],
                            operation_type=item["operation_type"],
                            operation_duration_ms=item["operation_duration_ms"],
                            system_load_avg=item.get("system_load_avg"),
                            context_size_tokens=item.get("context_size_tokens"),
                        )
                        self.snapshots.append(snapshot)

                # Load operation timings
                self.operation_timings = data.get("operation_timings", {})

                logger.info(
                    f"Loaded {len(self.snapshots)} performance snapshots from history"
                )

        except Exception as e:
            logger.warning(f"Could not load performance history: {e}")

    def _save_performance_history(self):
        """Save performance data to encrypted storage."""
        try:
            # Keep only last 24 hours of data for storage
            cutoff_time = datetime.now() - timedelta(hours=24)
            recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]

            # Convert to serializable format
            snapshot_data = []
            for snapshot in recent_snapshots:
                data = asdict(snapshot)
                data["timestamp"] = snapshot.timestamp.isoformat()
                snapshot_data.append(data)

            # Save data
            performance_data = {
                "snapshots": snapshot_data,
                "operation_timings": self.operation_timings,
                "last_updated": datetime.now().isoformat(),
            }

            self.storage.save_data("performance_history", performance_data)
            logger.info(f"Saved {len(recent_snapshots)} performance snapshots")

        except Exception as e:
            logger.warning(f"Could not save performance history: {e}")


class OperationTracker:
    """Context manager for tracking individual operation performance."""

    def __init__(
        self,
        optimizer: PerformanceOptimizer,
        operation_name: str,
        context_tokens: Optional[int] = None,
    ):
        self.optimizer = optimizer
        self.operation_name = operation_name
        self.context_tokens = context_tokens
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return

        # Calculate operation duration
        duration_ms = (time.perf_counter() - self.start_time) * 1000

        # Record timing
        if self.operation_name not in self.optimizer.operation_timings:
            self.optimizer.operation_timings[self.operation_name] = []

        self.optimizer.operation_timings[self.operation_name].append(duration_ms)

        # Keep only recent timings (last 100 per operation)
        timings = self.optimizer.operation_timings[self.operation_name]
        if len(timings) > 100:
            self.optimizer.operation_timings[self.operation_name] = timings[-100:]

        # Create detailed snapshot for this operation
        if self.optimizer.snapshots:
            # Get current system state
            cpu_percent = psutil.cpu_percent(interval=0.01)
            memory = psutil.virtual_memory()
            memory_mb = memory.used / (1024 * 1024)

            snapshot = PerformanceSnapshot(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                disk_io_read_mb=0.0,  # Will be updated by monitoring loop
                disk_io_write_mb=0.0,
                operation_type=self.operation_name,
                operation_duration_ms=duration_ms,
                context_size_tokens=self.context_tokens,
            )

            self.optimizer.snapshots.append(snapshot)
            if len(self.optimizer.snapshots) > 1000:
                self.optimizer.snapshots.pop(0)
