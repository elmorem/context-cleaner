"""
Advanced Memory Profiling and Monitoring System

Provides comprehensive memory usage analysis, leak detection, and optimization
for handling large token datasets (2.768B tokens) efficiently.
"""

import gc
import os
import psutil
import sys
import time
import tracemalloc
import weakref
import logging
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from functools import wraps
from contextlib import contextmanager
from collections import defaultdict, deque
import threading
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot at a specific point in time"""

    timestamp: datetime
    rss_mb: float  # Resident Set Size (physical memory)
    vms_mb: float  # Virtual Memory Size
    percent: float  # Memory percentage of system
    available_mb: float  # Available system memory
    gc_objects: int  # Number of tracked objects
    gc_collections: Dict[int, int]  # GC collections by generation
    tracemalloc_current_mb: float = 0.0
    tracemalloc_peak_mb: float = 0.0
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryLeak:
    """Detected memory leak information"""

    object_type: str
    count: int
    size_mb: float
    growth_rate: float  # Objects per second
    first_seen: datetime
    last_seen: datetime
    stack_trace: List[str] = field(default_factory=list)


class MemoryTracker:
    """Track memory usage of specific objects and operations"""

    def __init__(self):
        self.tracked_objects: Dict[str, Set[weakref.ref]] = defaultdict(set)
        self.object_counters: Dict[str, int] = defaultdict(int)
        self.allocation_history: Dict[str, List[Tuple[datetime, int]]] = defaultdict(
            list
        )
        self._lock = threading.Lock()

    def track_object(self, obj: Any, category: str = "default"):
        """Track an object for memory monitoring"""
        with self._lock:

            def cleanup_callback(ref):
                self.tracked_objects[category].discard(ref)

            weak_ref = weakref.ref(obj, cleanup_callback)
            self.tracked_objects[category].add(weak_ref)
            self.object_counters[category] += 1

            # Record allocation history
            now = datetime.now()
            self.allocation_history[category].append(
                (now, self.object_counters[category])
            )

            # Keep only last 1000 allocations
            if len(self.allocation_history[category]) > 1000:
                self.allocation_history[category] = self.allocation_history[category][
                    -1000:
                ]

    def get_tracked_counts(self) -> Dict[str, int]:
        """Get current counts of tracked objects by category"""
        with self._lock:
            return {
                category: len([ref for ref in refs if ref() is not None])
                for category, refs in self.tracked_objects.items()
            }

    def get_allocation_rate(self, category: str, window_minutes: int = 5) -> float:
        """Get allocation rate for a category (objects per minute)"""
        with self._lock:
            if category not in self.allocation_history:
                return 0.0

            cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
            recent_allocations = [
                (timestamp, count)
                for timestamp, count in self.allocation_history[category]
                if timestamp >= cutoff_time
            ]

            if len(recent_allocations) < 2:
                return 0.0

            time_span = (
                recent_allocations[-1][0] - recent_allocations[0][0]
            ).total_seconds() / 60
            count_diff = recent_allocations[-1][1] - recent_allocations[0][1]

            return count_diff / max(time_span, 0.1)  # Avoid division by zero


class MemoryProfiler:
    """Advanced memory profiling and leak detection system"""

    def __init__(
        self,
        sampling_interval: float = 30.0,
        history_size: int = 1000,
        enable_tracemalloc: bool = True,
    ):
        self.sampling_interval = sampling_interval
        self.history_size = history_size
        self.enable_tracemalloc = enable_tracemalloc

        # Memory snapshots history
        self.snapshots: deque = deque(maxlen=history_size)

        # Leak detection
        self.potential_leaks: Dict[str, MemoryLeak] = {}
        self.leak_threshold_objects = 1000  # Objects
        self.leak_threshold_growth = 10  # Objects per minute

        # Memory tracker for specific objects
        self.tracker = MemoryTracker()

        # Monitoring state
        self.monitoring_active = False
        self.monitoring_task = None
        self._process = psutil.Process()

        # Performance impact tracking
        self.profiler_overhead_ms = 0.0
        self.profile_start_time = None

        if enable_tracemalloc:
            tracemalloc.start()

        logger.info("Memory profiler initialized")

    def start_monitoring(self):
        """Start continuous memory monitoring"""
        if self.monitoring_active:
            logger.warning("Memory monitoring already active")
            return

        self.monitoring_active = True
        self.profile_start_time = time.time()

        # Start background monitoring task
        if asyncio.get_event_loop().is_running():
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        else:
            # Fallback to threading for non-async environments
            self.monitoring_task = threading.Thread(
                target=self._sync_monitoring_loop, daemon=True
            )
            self.monitoring_task.start()

        logger.info("Memory monitoring started")

    def stop_monitoring(self):
        """Stop memory monitoring"""
        if not self.monitoring_active:
            return

        self.monitoring_active = False

        if self.monitoring_task:
            if asyncio.iscoroutine(self.monitoring_task):
                self.monitoring_task.cancel()
            elif hasattr(self.monitoring_task, "join"):
                self.monitoring_task.join(timeout=5.0)

        # Calculate total profiler overhead
        if self.profile_start_time:
            total_time = time.time() - self.profile_start_time
            overhead_percent = (self.profiler_overhead_ms / 1000) / total_time * 100
            logger.info(
                f"Memory profiler overhead: {overhead_percent:.2f}% of total runtime"
            )

        logger.info("Memory monitoring stopped")

    async def _monitoring_loop(self):
        """Async monitoring loop"""
        while self.monitoring_active:
            try:
                await asyncio.sleep(self.sampling_interval)
                self._take_snapshot()
                self._detect_leaks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")

    def _sync_monitoring_loop(self):
        """Synchronous monitoring loop for threading"""
        while self.monitoring_active:
            try:
                time.sleep(self.sampling_interval)
                self._take_snapshot()
                self._detect_leaks()
            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")

    def _take_snapshot(self):
        """Take a memory usage snapshot"""
        start_time = time.time()

        try:
            # Get system memory info
            memory_info = self._process.memory_info()
            system_memory = psutil.virtual_memory()

            # Get garbage collection stats
            gc_stats = {}
            for i in range(3):  # Python has 3 GC generations
                gc_stats[i] = gc.get_count()[i]

            # Get tracemalloc info if enabled
            tracemalloc_current = 0.0
            tracemalloc_peak = 0.0
            if self.enable_tracemalloc and tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # Convert to MB
                tracemalloc_peak = peak / 1024 / 1024

            # Create snapshot
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
                percent=self._process.memory_percent(),
                available_mb=system_memory.available / 1024 / 1024,
                gc_objects=len(gc.get_objects()),
                gc_collections=gc_stats,
                tracemalloc_current_mb=tracemalloc_current,
                tracemalloc_peak_mb=tracemalloc_peak,
                custom_metrics={
                    "tracked_objects": self.tracker.get_tracked_counts(),
                    "gc_threshold": gc.get_threshold(),
                },
            )

            self.snapshots.append(snapshot)

            # Track profiler overhead
            overhead = (time.time() - start_time) * 1000
            self.profiler_overhead_ms += overhead

        except Exception as e:
            logger.error(f"Error taking memory snapshot: {e}")

    def _detect_leaks(self):
        """Detect potential memory leaks"""
        if len(self.snapshots) < 10:  # Need enough history
            return

        try:
            # Analyze tracked objects for leaks
            tracked_counts = self.tracker.get_tracked_counts()

            for category, count in tracked_counts.items():
                if count > self.leak_threshold_objects:
                    growth_rate = self.tracker.get_allocation_rate(
                        category, window_minutes=5
                    )

                    if growth_rate > self.leak_threshold_growth:
                        # Potential leak detected
                        if category not in self.potential_leaks:
                            self.potential_leaks[category] = MemoryLeak(
                                object_type=category,
                                count=count,
                                size_mb=0.0,  # Would need size estimation
                                growth_rate=growth_rate,
                                first_seen=datetime.now(),
                                last_seen=datetime.now(),
                            )
                            logger.warning(
                                f"Potential memory leak detected: {category} "
                                f"({count} objects, {growth_rate:.1f} obj/min)"
                            )
                        else:
                            # Update existing leak
                            leak = self.potential_leaks[category]
                            leak.count = count
                            leak.growth_rate = growth_rate
                            leak.last_seen = datetime.now()

            # Clean up resolved leaks
            resolved_leaks = []
            for category, leak in self.potential_leaks.items():
                current_count = tracked_counts.get(category, 0)
                growth_rate = self.tracker.get_allocation_rate(
                    category, window_minutes=5
                )

                if (
                    current_count < self.leak_threshold_objects
                    or growth_rate < self.leak_threshold_growth
                ):
                    resolved_leaks.append(category)
                    logger.info(f"Memory leak resolved: {category}")

            for category in resolved_leaks:
                del self.potential_leaks[category]

        except Exception as e:
            logger.error(f"Error in leak detection: {e}")

    @contextmanager
    def profile_operation(self, operation_name: str):
        """Context manager to profile a specific operation"""
        start_snapshot = self._get_current_memory_usage()
        start_time = time.time()

        try:
            yield
        finally:
            end_time = time.time()
            end_snapshot = self._get_current_memory_usage()

            memory_delta = end_snapshot["rss_mb"] - start_snapshot["rss_mb"]
            duration = end_time - start_time

            logger.info(
                f"Operation '{operation_name}' memory usage: "
                f"{memory_delta:+.2f} MB in {duration:.2f}s"
            )

            # Track significant memory operations
            if abs(memory_delta) > 10:  # More than 10MB change
                self.tracker.track_object(
                    {
                        "operation": operation_name,
                        "memory_delta": memory_delta,
                        "duration": duration,
                        "timestamp": datetime.now(),
                    },
                    "large_operations",
                )

    def _get_current_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage quickly"""
        memory_info = self._process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": self._process.memory_percent(),
        }

    def get_memory_summary(self, window_minutes: int = 30) -> Dict[str, Any]:
        """Get comprehensive memory usage summary"""
        if not self.snapshots:
            return {"error": "No memory snapshots available"}

        # Filter snapshots within time window
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_snapshots = [s for s in self.snapshots if s.timestamp >= cutoff_time]

        if not recent_snapshots:
            recent_snapshots = list(self.snapshots)[-10:]  # Last 10 snapshots

        # Calculate statistics
        rss_values = [s.rss_mb for s in recent_snapshots]
        percent_values = [s.percent for s in recent_snapshots]

        current = recent_snapshots[-1]

        return {
            "current_usage": {
                "rss_mb": current.rss_mb,
                "vms_mb": current.vms_mb,
                "percent": current.percent,
                "available_mb": current.available_mb,
                "gc_objects": current.gc_objects,
            },
            "statistics": {
                "rss_min_mb": min(rss_values),
                "rss_max_mb": max(rss_values),
                "rss_avg_mb": sum(rss_values) / len(rss_values),
                "percent_min": min(percent_values),
                "percent_max": max(percent_values),
                "percent_avg": sum(percent_values) / len(percent_values),
            },
            "tracemalloc": {
                "current_mb": current.tracemalloc_current_mb,
                "peak_mb": current.tracemalloc_peak_mb,
                "enabled": self.enable_tracemalloc,
            },
            "potential_leaks": len(self.potential_leaks),
            "leak_details": {
                category: {
                    "count": leak.count,
                    "growth_rate": leak.growth_rate,
                    "duration_minutes": (
                        leak.last_seen - leak.first_seen
                    ).total_seconds()
                    / 60,
                }
                for category, leak in self.potential_leaks.items()
            },
            "tracked_objects": self.tracker.get_tracked_counts(),
            "profiler_overhead_ms": self.profiler_overhead_ms,
            "snapshots_collected": len(self.snapshots),
            "monitoring_active": self.monitoring_active,
        }

    def force_gc_and_measure(self) -> Dict[str, Any]:
        """Force garbage collection and measure impact"""
        before = self._get_current_memory_usage()
        before_objects = len(gc.get_objects())

        start_time = time.time()

        # Force collection in all generations
        collected = []
        for generation in range(3):
            collected.append(gc.collect(generation))

        gc_time = time.time() - start_time
        after = self._get_current_memory_usage()
        after_objects = len(gc.get_objects())

        return {
            "memory_freed_mb": before["rss_mb"] - after["rss_mb"],
            "objects_before": before_objects,
            "objects_after": after_objects,
            "objects_collected": collected,
            "gc_time_ms": gc_time * 1000,
            "percent_reduction": (
                (before["rss_mb"] - after["rss_mb"]) / before["rss_mb"]
            )
            * 100,
        }

    def get_top_memory_consumers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top memory consuming objects using tracemalloc"""
        if not self.enable_tracemalloc or not tracemalloc.is_tracing():
            return []

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")

            consumers = []
            for index, stat in enumerate(top_stats[:limit]):
                consumers.append(
                    {
                        "rank": index + 1,
                        "filename": (
                            stat.traceback.format()[-1] if stat.traceback else "unknown"
                        ),
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "average_size_bytes": stat.size / max(stat.count, 1),
                    }
                )

            return consumers

        except Exception as e:
            logger.error(f"Error getting top memory consumers: {e}")
            return []

    def export_memory_report(self, filepath: str):
        """Export comprehensive memory report to file"""
        try:
            report = {
                "report_timestamp": datetime.now().isoformat(),
                "summary": self.get_memory_summary(),
                "top_consumers": self.get_top_memory_consumers(20),
                "gc_forced_cleanup": self.force_gc_and_measure(),
                "snapshots": [
                    {
                        "timestamp": s.timestamp.isoformat(),
                        "rss_mb": s.rss_mb,
                        "percent": s.percent,
                        "gc_objects": s.gc_objects,
                    }
                    for s in list(self.snapshots)[-100:]  # Last 100 snapshots
                ],
            }

            import json

            with open(filepath, "w") as f:
                json.dump(report, f, indent=2)

            logger.info(f"Memory report exported to {filepath}")

        except Exception as e:
            logger.error(f"Error exporting memory report: {e}")


# Global memory profiler instance
memory_profiler = MemoryProfiler()


def memory_profile(operation_name: str = None):
    """Decorator for profiling memory usage of functions"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with memory_profiler.profile_operation(name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with memory_profiler.profile_operation(name):
                return func(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def track_memory_object(obj: Any, category: str = "default"):
    """Convenience function to track an object's memory usage"""
    memory_profiler.tracker.track_object(obj, category)


def get_memory_summary() -> Dict[str, Any]:
    """Get current memory usage summary"""
    return memory_profiler.get_memory_summary()


async def memory_health_check() -> Dict[str, Any]:
    """Perform memory system health check"""
    try:
        summary = memory_profiler.get_memory_summary()

        # Determine health status
        current_percent = summary["current_usage"]["percent"]
        potential_leaks = summary["potential_leaks"]

        healthy = current_percent < 80 and potential_leaks == 0

        return {
            "memory_system_healthy": healthy,
            "current_memory_percent": current_percent,
            "potential_leaks_detected": potential_leaks,
            "monitoring_active": summary["monitoring_active"],
            "tracemalloc_enabled": summary["tracemalloc"]["enabled"],
            "recommendations": _get_memory_recommendations(summary),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return {
            "memory_system_healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def _get_memory_recommendations(summary: Dict[str, Any]) -> List[str]:
    """Generate memory optimization recommendations"""
    recommendations = []

    current_percent = summary["current_usage"]["percent"]
    if current_percent > 80:
        recommendations.append(
            "High memory usage detected - consider reducing dataset size or enabling streaming"
        )

    if summary["potential_leaks"] > 0:
        recommendations.append(
            "Memory leaks detected - review object lifecycle management"
        )

    if not summary["tracemalloc"]["enabled"]:
        recommendations.append("Enable tracemalloc for detailed memory analysis")

    if summary["profiler_overhead_ms"] > 1000:
        recommendations.append(
            "Consider reducing profiling frequency to reduce overhead"
        )

    return recommendations
