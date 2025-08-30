"""
Memory Usage Optimizer

Advanced memory management and optimization for Context Cleaner to maintain
<50MB active memory usage with intelligent caching and data lifecycle management.
"""

import gc
import sys
import psutil
import weakref
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import deque, OrderedDict
import logging

from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot at a point in time."""

    timestamp: datetime
    total_mb: float
    available_mb: float
    process_mb: float
    process_percent: float
    cached_items: int
    gc_collections: Tuple[int, int, int]  # gen0, gen1, gen2 counts


@dataclass
class CacheEntry:
    """Cache entry with metadata for intelligent eviction."""

    key: str
    data: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    size_estimate: int = 0
    priority: int = 1  # 1=low, 2=medium, 3=high


class LRUCache:
    """
    Memory-efficient LRU cache with size-based eviction and priority handling.
    """

    def __init__(self, max_size: int = 100, max_memory_mb: int = 20):
        """
        Initialize LRU cache with memory constraints.

        Args:
            max_size: Maximum number of items
            max_memory_mb: Maximum memory usage in MB
        """
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._current_memory_mb = 0.0

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache, updating access patterns."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            entry.last_accessed = datetime.now()
            entry.access_count += 1

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.data

    def put(self, key: str, data: Any, priority: int = 1):
        """Put item in cache with intelligent eviction."""
        with self._lock:
            # Estimate size
            size_estimate = sys.getsizeof(data) + sys.getsizeof(key)
            size_mb = size_estimate / (1024 * 1024)

            # Check if single item exceeds max memory
            if size_mb > self.max_memory_mb:
                logger.warning(f"Cache item too large ({size_mb:.1f}MB), skipping")
                return

            # Remove existing entry if updating
            if key in self._cache:
                old_entry = self._cache[key]
                self._current_memory_mb -= old_entry.size_estimate / (1024 * 1024)
                del self._cache[key]

            # Evict items if necessary
            self._evict_if_needed(size_mb)

            # Add new entry
            entry = CacheEntry(
                key=key,
                data=data,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=1,
                size_estimate=size_estimate,
                priority=priority,
            )

            self._cache[key] = entry
            self._current_memory_mb += size_mb

    def _evict_if_needed(self, incoming_size_mb: float):
        """Evict items to make room for new entry."""
        # Evict by size constraint
        while (
            self._current_memory_mb + incoming_size_mb > self.max_memory_mb
            and len(self._cache) > 0
        ):
            self._evict_least_valuable()

        # Evict by count constraint
        while len(self._cache) >= self.max_size and len(self._cache) > 0:
            self._evict_least_valuable()

    def _evict_least_valuable(self):
        """Evict the least valuable item based on priority and access patterns."""
        if not self._cache:
            return

        # Calculate value scores for all items
        now = datetime.now()
        candidates = []

        for key, entry in self._cache.items():
            age_hours = (now - entry.created_at).total_seconds() / 3600
            time_since_access_hours = (now - entry.last_accessed).total_seconds() / 3600

            # Lower score = more likely to evict
            value_score = (
                entry.priority * 1000  # Priority boost
                + entry.access_count * 10  # Access frequency boost
                + max(0, 24 - age_hours) * 5  # Recent creation boost
                + max(0, 6 - time_since_access_hours) * 15  # Recent access boost
            )

            candidates.append((value_score, key, entry))

        # Sort by value score (ascending - lowest first)
        candidates.sort(key=lambda x: x[0])

        # Evict the least valuable
        if candidates:
            _, evict_key, evict_entry = candidates[0]
            self._current_memory_mb -= evict_entry.size_estimate / (1024 * 1024)
            del self._cache[evict_key]
            logger.debug(f"Evicted cache entry: {evict_key}")

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._current_memory_mb = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "total_items": len(self._cache),
                "memory_mb": round(self._current_memory_mb, 2),
                "memory_usage_percent": (
                    round((self._current_memory_mb / self.max_memory_mb) * 100, 1)
                    if self.max_memory_mb > 0
                    else 0
                ),
                "max_size": self.max_size,
                "max_memory_mb": self.max_memory_mb,
            }


class MemoryOptimizer:
    """
    Advanced memory optimizer maintaining <50MB active usage through
    intelligent caching, data lifecycle management, and garbage collection.
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize memory optimizer."""
        self.config = config or ContextCleanerConfig.from_env()

        # Memory constraints
        self.target_memory_mb = 45.0  # Target <50MB, aim for 45MB
        self.critical_memory_mb = 60.0  # Critical threshold
        self.cache_memory_mb = 20.0  # Maximum cache usage

        # Caching system
        self._caches: Dict[str, LRUCache] = {
            "analytics": LRUCache(max_size=50, max_memory_mb=8),
            "patterns": LRUCache(max_size=30, max_memory_mb=6),
            "sessions": LRUCache(max_size=100, max_memory_mb=4),
            "config": LRUCache(max_size=20, max_memory_mb=2),
        }

        # Memory tracking
        self._memory_snapshots: deque = deque(maxlen=100)  # Last 100 snapshots
        self._weak_references: Set[weakref.ref] = set()
        self._cleanup_tasks: List[callable] = []

        # Monitoring state
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()

        # Performance process reference
        self._process = psutil.Process()

        logger.info(f"Memory optimizer initialized (target: {self.target_memory_mb}MB)")

    def start_monitoring(self):
        """Start continuous memory monitoring and optimization."""
        if self._is_monitoring:
            return

        self._is_monitoring = True
        self._stop_monitoring.clear()

        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True, name="MemoryOptimizer"
        )
        self._monitor_thread.start()

        logger.info("Memory monitoring started")

    def stop_monitoring(self):
        """Stop memory monitoring."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False
        self._stop_monitoring.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3.0)

        logger.info("Memory monitoring stopped")

    def _monitoring_loop(self):
        """Main memory monitoring and optimization loop."""
        while not self._stop_monitoring.is_set():
            try:
                # Take memory snapshot
                snapshot = self._take_memory_snapshot()
                self._memory_snapshots.append(snapshot)

                # Check if optimization needed
                if snapshot.process_mb > self.target_memory_mb:
                    logger.debug(
                        f"Memory usage ({snapshot.process_mb:.1f}MB) above target, optimizing"
                    )
                    self._optimize_memory_usage()

                # Critical memory handling
                if snapshot.process_mb > self.critical_memory_mb:
                    logger.warning(
                        f"Critical memory usage ({snapshot.process_mb:.1f}MB), aggressive cleanup"
                    )
                    self._aggressive_cleanup()

                # Sleep until next check (30 seconds)
                self._stop_monitoring.wait(timeout=30.0)

            except Exception as e:
                logger.warning(f"Memory monitoring error: {e}")
                self._stop_monitoring.wait(timeout=60.0)  # Longer wait on error

    def _take_memory_snapshot(self) -> MemorySnapshot:
        """Take a current memory usage snapshot."""
        # System memory
        system_memory = psutil.virtual_memory()

        # Process memory
        memory_info = self._process.memory_info()
        process_mb = memory_info.rss / (1024 * 1024)

        # Cache statistics
        total_cached_items = sum(len(cache._cache) for cache in self._caches.values())

        # Garbage collection stats
        gc_stats = gc.get_stats()
        gc_collections = (
            gc_stats[0]["collections"] if len(gc_stats) > 0 else 0,
            gc_stats[1]["collections"] if len(gc_stats) > 1 else 0,
            gc_stats[2]["collections"] if len(gc_stats) > 2 else 0,
        )

        return MemorySnapshot(
            timestamp=datetime.now(),
            total_mb=system_memory.total / (1024 * 1024),
            available_mb=system_memory.available / (1024 * 1024),
            process_mb=process_mb,
            process_percent=system_memory.percent,
            cached_items=total_cached_items,
            gc_collections=gc_collections,
        )

    def _optimize_memory_usage(self):
        """Perform memory optimization to reduce usage."""
        # 1. Cache optimization - remove least valuable items
        for cache_name, cache in self._caches.items():
            if cache._current_memory_mb > cache.max_memory_mb * 0.8:
                # Reduce cache to 60% of max
                target_items = int(cache.max_size * 0.6)
                while len(cache._cache) > target_items:
                    cache._evict_least_valuable()
                logger.debug(f"Optimized {cache_name} cache: {len(cache._cache)} items")

        # 2. Cleanup weak references
        self._cleanup_weak_references()

        # 3. Run custom cleanup tasks
        for cleanup_task in self._cleanup_tasks:
            try:
                cleanup_task()
            except Exception as e:
                logger.warning(f"Cleanup task failed: {e}")

        # 4. Garbage collection
        collected = gc.collect()
        if collected > 0:
            logger.debug(f"Garbage collection freed {collected} objects")

    def _aggressive_cleanup(self):
        """Aggressive cleanup for critical memory situations."""
        logger.warning("Performing aggressive memory cleanup")

        # Clear most caches completely
        for cache_name, cache in self._caches.items():
            if cache_name not in ["config"]:  # Keep essential config cache
                cache.clear()
                logger.debug(f"Cleared {cache_name} cache")

        # Force garbage collection for all generations
        for generation in range(3):
            collected = gc.collect(generation)
            if collected > 0:
                logger.debug(f"GC generation {generation} freed {collected} objects")

        # Run all cleanup tasks
        self._optimize_memory_usage()

    def _cleanup_weak_references(self):
        """Clean up dead weak references."""
        dead_refs = [ref for ref in self._weak_references if ref() is None]
        for ref in dead_refs:
            self._weak_references.remove(ref)

        if dead_refs:
            logger.debug(f"Cleaned up {len(dead_refs)} dead weak references")

    def get_cache(self, cache_name: str) -> Optional[LRUCache]:
        """Get a named cache instance."""
        return self._caches.get(cache_name)

    def register_cleanup_task(self, cleanup_func: callable):
        """Register a custom cleanup task for memory optimization."""
        self._cleanup_tasks.append(cleanup_func)
        logger.debug(f"Registered cleanup task: {cleanup_func.__name__}")

    def register_weak_reference(self, obj: Any) -> weakref.ref:
        """Register a weak reference for lifecycle tracking."""
        weak_ref = weakref.ref(obj)
        self._weak_references.add(weak_ref)
        return weak_ref

    def get_memory_report(self) -> Dict[str, Any]:
        """Get comprehensive memory usage report."""
        current_snapshot = self._take_memory_snapshot()

        # Cache statistics
        cache_stats = {}
        total_cache_memory = 0
        for name, cache in self._caches.items():
            stats = cache.get_stats()
            cache_stats[name] = stats
            total_cache_memory += stats["memory_mb"]

        # Memory trend analysis
        if len(self._memory_snapshots) >= 2:
            recent_mb = [s.process_mb for s in list(self._memory_snapshots)[-10:]]
            memory_trend = "increasing" if recent_mb[-1] > recent_mb[0] else "stable"
            avg_memory = sum(recent_mb) / len(recent_mb)
        else:
            memory_trend = "unknown"
            avg_memory = current_snapshot.process_mb

        # Health assessment
        health_score = self._calculate_memory_health(current_snapshot)

        return {
            "current": {
                "process_mb": round(current_snapshot.process_mb, 1),
                "target_mb": self.target_memory_mb,
                "usage_percent": round(
                    (current_snapshot.process_mb / self.target_memory_mb) * 100, 1
                ),
                "health_score": health_score,
            },
            "system": {
                "total_mb": round(current_snapshot.total_mb, 1),
                "available_mb": round(current_snapshot.available_mb, 1),
                "system_usage_percent": round(current_snapshot.process_percent, 1),
            },
            "caches": {
                "total_memory_mb": round(total_cache_memory, 2),
                "total_items": sum(
                    stats["total_items"] for stats in cache_stats.values()
                ),
                "details": cache_stats,
            },
            "trends": {
                "memory_trend": memory_trend,
                "avg_memory_mb": round(avg_memory, 1),
                "snapshots_count": len(self._memory_snapshots),
            },
            "optimization": {
                "weak_references": len(self._weak_references),
                "cleanup_tasks": len(self._cleanup_tasks),
                "gc_collections": current_snapshot.gc_collections,
            },
        }

    def _calculate_memory_health(self, snapshot: MemorySnapshot) -> int:
        """Calculate memory health score (0-100)."""
        score = 100

        # Memory usage penalty
        if snapshot.process_mb > self.target_memory_mb:
            excess_mb = snapshot.process_mb - self.target_memory_mb
            penalty = min(50, excess_mb * 2)  # 2 points per MB over target
            score -= penalty

        # Critical memory penalty
        if snapshot.process_mb > self.critical_memory_mb:
            score -= 30

        # Cache efficiency bonus
        total_cache_memory = sum(
            cache._current_memory_mb for cache in self._caches.values()
        )
        if total_cache_memory <= self.cache_memory_mb:
            score += 10  # Bonus for efficient cache usage

        return max(0, int(score))

    def force_optimization(self):
        """Force immediate memory optimization."""
        logger.info("Forcing memory optimization")
        current_snapshot = self._take_memory_snapshot()

        if current_snapshot.process_mb > self.critical_memory_mb:
            self._aggressive_cleanup()
        else:
            self._optimize_memory_usage()

        # Return new snapshot for comparison
        return self._take_memory_snapshot()
