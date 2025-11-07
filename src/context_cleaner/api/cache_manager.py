"""
Advanced Cache Management with Intelligent Invalidation Strategies

Provides sophisticated caching patterns, invalidation strategies, and performance optimization
for high-frequency dashboard endpoints with real-time data requirements.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union, Set
from functools import wraps
from dataclasses import dataclass
from enum import Enum

from .cache import CacheService

logger = logging.getLogger(__name__)


class InvalidationStrategy(Enum):
    """Cache invalidation strategies for different data types"""

    IMMEDIATE = "immediate"  # Invalidate immediately on data change
    TIME_BASED = "time_based"  # Invalidate after TTL expires
    DEPENDENCY_BASED = "dependency"  # Invalidate based on data dependencies
    WRITE_THROUGH = "write_through"  # Update cache on write operations
    LAZY_EXPIRY = "lazy_expiry"  # Extend TTL on access


@dataclass
class CachePolicy:
    """Cache policy configuration for different endpoint types"""

    ttl_seconds: int = 300
    strategy: InvalidationStrategy = InvalidationStrategy.TIME_BASED
    max_size_mb: Optional[float] = None
    dependency_keys: List[str] = None
    refresh_ahead_factor: float = 0.8  # Refresh when TTL reaches 80%
    enable_compression: bool = False


class CacheKeyGenerator:
    """Intelligent cache key generation with collision avoidance"""

    @staticmethod
    def generate_key(
        endpoint: str,
        params: Dict[str, Any] = None,
        user_context: Dict[str, Any] = None,
        version: str = "v1",
    ) -> str:
        """Generate consistent cache key with hierarchical namespace"""

        # Base components
        components = [f"api:{version}", endpoint]

        # Add parameters hash if present
        if params:
            param_str = json.dumps(params, sort_keys=True, separators=(",", ":"))
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:12]
            components.append(f"params:{param_hash}")

        # Add user context hash if present
        if user_context:
            context_str = json.dumps(
                user_context, sort_keys=True, separators=(",", ":")
            )
            context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:8]
            components.append(f"ctx:{context_hash}")

        return ":".join(components)

    @staticmethod
    def generate_dependency_key(resource_type: str, resource_id: str) -> str:
        """Generate dependency tracking key"""
        return f"dep:{resource_type}:{resource_id}"

    @staticmethod
    def generate_pattern(endpoint: str, wildcard_params: List[str] = None) -> str:
        """Generate pattern for bulk invalidation"""
        pattern = f"api:*:{endpoint}"
        if wildcard_params:
            for param in wildcard_params:
                pattern += f":*{param}*"
        return pattern + "*"


class DependencyTracker:
    """Track cache dependencies for intelligent invalidation"""

    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        self._dependencies: Dict[str, Set[str]] = {}
        self._reverse_deps: Dict[str, Set[str]] = {}

    async def add_dependency(self, cache_key: str, dependency_key: str):
        """Add dependency relationship"""
        if dependency_key not in self._dependencies:
            self._dependencies[dependency_key] = set()
        self._dependencies[dependency_key].add(cache_key)

        if cache_key not in self._reverse_deps:
            self._reverse_deps[cache_key] = set()
        self._reverse_deps[cache_key].add(dependency_key)

    async def invalidate_dependents(self, dependency_key: str) -> int:
        """Invalidate all cache entries dependent on this key"""
        if dependency_key not in self._dependencies:
            return 0

        dependent_keys = self._dependencies[dependency_key].copy()
        invalidated_count = 0

        for cache_key in dependent_keys:
            try:
                await self.cache.invalidate(cache_key)
                invalidated_count += 1
                logger.debug(f"Invalidated dependent cache key: {cache_key}")
            except Exception as e:
                logger.warning(f"Failed to invalidate dependent key {cache_key}: {e}")

        # Clean up dependency tracking
        del self._dependencies[dependency_key]
        for cache_key in dependent_keys:
            if cache_key in self._reverse_deps:
                self._reverse_deps[cache_key].discard(dependency_key)
                if not self._reverse_deps[cache_key]:
                    del self._reverse_deps[cache_key]

        logger.info(
            f"Invalidated {invalidated_count} cache entries for dependency: {dependency_key}"
        )
        return invalidated_count

    async def remove_cache_dependencies(self, cache_key: str):
        """Remove all dependencies for a cache key"""
        if cache_key in self._reverse_deps:
            dependencies = self._reverse_deps[cache_key].copy()
            for dep_key in dependencies:
                if dep_key in self._dependencies:
                    self._dependencies[dep_key].discard(cache_key)
                    if not self._dependencies[dep_key]:
                        del self._dependencies[dep_key]
            del self._reverse_deps[cache_key]


class AdvancedCacheManager:
    """Advanced cache manager with intelligent strategies and invalidation"""

    def __init__(self, cache_service: CacheService):
        self.cache = cache_service
        self.dependency_tracker = DependencyTracker(cache_service)

        # Policy configurations for different endpoint types
        self.policies: Dict[str, CachePolicy] = {
            "dashboard_overview": CachePolicy(
                ttl_seconds=30,
                strategy=InvalidationStrategy.DEPENDENCY_BASED,
                dependency_keys=["metrics", "health", "widgets"],
                refresh_ahead_factor=0.9,
            ),
            "widget_data": CachePolicy(
                ttl_seconds=60,
                strategy=InvalidationStrategy.WRITE_THROUGH,
                dependency_keys=["sessions", "telemetry"],
                refresh_ahead_factor=0.8,
            ),
            "cost_analysis": CachePolicy(
                ttl_seconds=300,
                strategy=InvalidationStrategy.TIME_BASED,
                dependency_keys=["billing", "usage"],
                refresh_ahead_factor=0.7,
            ),
            "system_health": CachePolicy(
                ttl_seconds=15,
                strategy=InvalidationStrategy.IMMEDIATE,
                refresh_ahead_factor=0.95,
            ),
            "session_list": CachePolicy(
                ttl_seconds=120,
                strategy=InvalidationStrategy.LAZY_EXPIRY,
                dependency_keys=["sessions"],
                refresh_ahead_factor=0.6,
            ),
        }

        # Performance tracking
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "invalidations": 0,
            "refresh_ahead_hits": 0,
            "total_response_time_saved_ms": 0,
        }

    async def get_with_policy(
        self,
        endpoint: str,
        data_fetcher: Callable,
        params: Dict[str, Any] = None,
        user_context: Dict[str, Any] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Get cached data with intelligent policy application"""

        # Generate cache key
        cache_key = CacheKeyGenerator.generate_key(endpoint, params, user_context)
        policy = self.policies.get(endpoint, CachePolicy())

        start_time = datetime.now()

        # Try cache first unless forcing refresh
        if not force_refresh:
            cached_data = await self._get_with_refresh_ahead(
                cache_key, policy, data_fetcher
            )
            if cached_data is not None:
                self.stats["cache_hits"] += 1
                saved_time = (datetime.now() - start_time).total_seconds() * 1000
                self.stats["total_response_time_saved_ms"] += saved_time
                return cached_data

        # Cache miss - fetch fresh data
        self.stats["cache_misses"] += 1
        logger.debug(f"Cache miss for endpoint: {endpoint}")

        try:
            # Fetch fresh data
            if asyncio.iscoroutinefunction(data_fetcher):
                fresh_data = await data_fetcher()
            else:
                fresh_data = data_fetcher()

            # Store in cache with policy
            await self._store_with_policy(cache_key, fresh_data, policy, endpoint)

            return fresh_data

        except Exception as e:
            logger.error(f"Error fetching data for {endpoint}: {e}")
            # Try to return stale data if available
            stale_data = await self.cache.get(cache_key)
            if stale_data:
                logger.warning(f"Returning stale data for {endpoint}")
                return stale_data
            raise

    async def _get_with_refresh_ahead(
        self, cache_key: str, policy: CachePolicy, data_fetcher: Callable
    ) -> Optional[Dict[str, Any]]:
        """Get cached data with refresh-ahead strategy"""

        cached_entry = await self.cache.get(cache_key)
        if not cached_entry:
            return None

        # Check if refresh-ahead is needed
        if isinstance(cached_entry, dict) and "cached_at" in cached_entry:
            cached_at = datetime.fromisoformat(cached_entry["cached_at"])
            age_seconds = (datetime.now() - cached_at).total_seconds()
            refresh_threshold = policy.ttl_seconds * policy.refresh_ahead_factor

            if age_seconds >= refresh_threshold:
                # Trigger background refresh
                self.stats["refresh_ahead_hits"] += 1
                asyncio.create_task(
                    self._background_refresh(cache_key, data_fetcher, policy)
                )
                logger.debug(f"Background refresh triggered for key: {cache_key}")

        return (
            cached_entry.get("data") if isinstance(cached_entry, dict) else cached_entry
        )

    async def _background_refresh(
        self, cache_key: str, data_fetcher: Callable, policy: CachePolicy
    ):
        """Background refresh of cache data"""
        try:
            if asyncio.iscoroutinefunction(data_fetcher):
                fresh_data = await data_fetcher()
            else:
                fresh_data = data_fetcher()

            await self._store_with_policy(
                cache_key, fresh_data, policy, "background_refresh"
            )
            logger.debug(f"Background refresh completed for key: {cache_key}")

        except Exception as e:
            logger.warning(f"Background refresh failed for {cache_key}: {e}")

    async def _store_with_policy(
        self, cache_key: str, data: Any, policy: CachePolicy, endpoint: str
    ):
        """Store data in cache according to policy"""

        # Prepare cache entry with metadata
        cache_entry = {
            "data": data,
            "cached_at": datetime.now().isoformat(),
            "policy": policy.strategy.value,
            "endpoint": endpoint,
        }

        # Store in cache
        await self.cache.set(cache_key, cache_entry, ttl=policy.ttl_seconds)

        # Set up dependencies if configured
        if policy.dependency_keys:
            for dep_key in policy.dependency_keys:
                dependency_key = CacheKeyGenerator.generate_dependency_key(
                    dep_key, "global"
                )
                await self.dependency_tracker.add_dependency(cache_key, dependency_key)

    async def invalidate_by_dependency(
        self, resource_type: str, resource_id: str = "global"
    ) -> int:
        """Invalidate cache entries by dependency"""
        dependency_key = CacheKeyGenerator.generate_dependency_key(
            resource_type, resource_id
        )
        count = await self.dependency_tracker.invalidate_dependents(dependency_key)
        self.stats["invalidations"] += count
        return count

    async def invalidate_endpoint(
        self, endpoint: str, wildcard_params: List[str] = None
    ) -> int:
        """Invalidate all cache entries for an endpoint"""
        pattern = CacheKeyGenerator.generate_pattern(endpoint, wildcard_params)
        success = await self.cache.invalidate(pattern)
        if success:
            self.stats["invalidations"] += 1
            logger.info(f"Invalidated cache pattern: {pattern}")
        return 1 if success else 0

    async def warm_cache(self, warm_configs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Warm cache with predefined data sets"""
        results = {}

        for config in warm_configs:
            endpoint = config.get("endpoint")
            data_fetcher = config.get("data_fetcher")
            params = config.get("params", {})

            try:
                await self.get_with_policy(
                    endpoint, data_fetcher, params, force_refresh=True
                )
                results[endpoint] = True
                logger.debug(f"Cache warmed for endpoint: {endpoint}")
            except Exception as e:
                logger.error(f"Cache warming failed for {endpoint}: {e}")
                results[endpoint] = False

        successful = sum(1 for success in results.values() if success)
        logger.info(
            f"Cache warming completed: {successful}/{len(warm_configs)} successful"
        )
        return results

    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache performance statistics"""
        try:
            base_stats = await self.cache.get_stats()
        except:
            base_stats = {}

        total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = 0.0
        if total_requests > 0:
            hit_rate = (self.stats["cache_hits"] / total_requests) * 100

        return {
            "advanced_cache_manager": {
                "cache_hits": self.stats["cache_hits"],
                "cache_misses": self.stats["cache_misses"],
                "hit_rate_percent": round(hit_rate, 2),
                "invalidations": self.stats["invalidations"],
                "refresh_ahead_hits": self.stats["refresh_ahead_hits"],
                "total_response_time_saved_ms": self.stats[
                    "total_response_time_saved_ms"
                ],
                "average_time_saved_per_hit_ms": round(
                    self.stats["total_response_time_saved_ms"]
                    / max(self.stats["cache_hits"], 1),
                    2,
                ),
            },
            "base_cache_stats": base_stats,
            "policies_configured": len(self.policies),
            "dependency_tracking": {
                "dependencies_tracked": len(self.dependency_tracker._dependencies),
                "reverse_dependencies": len(self.dependency_tracker._reverse_deps),
            },
        }

    def register_policy(self, endpoint: str, policy: CachePolicy):
        """Register custom cache policy for endpoint"""
        self.policies[endpoint] = policy
        logger.info(f"Registered cache policy for endpoint: {endpoint}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache manager"""
        try:
            # Test basic cache operations
            test_key = "cache_manager:health_check"
            test_data = {"timestamp": datetime.now().isoformat(), "status": "healthy"}

            # Test set
            await self.cache.set(test_key, test_data, 60)

            # Test get
            retrieved = await self.cache.get(test_key)
            get_success = retrieved is not None

            # Test invalidation
            await self.cache.invalidate(test_key)

            return {
                "cache_manager_healthy": get_success,
                "policies_loaded": len(self.policies),
                "dependency_tracker_active": True,
                "stats": self.stats,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Cache manager health check failed: {e}")
            return {
                "cache_manager_healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


# Decorator for easy cache integration
def cached_endpoint(
    endpoint: str,
    ttl_seconds: int = 300,
    strategy: InvalidationStrategy = InvalidationStrategy.TIME_BASED,
    dependency_keys: List[str] = None,
):
    """Decorator to add caching to FastAPI endpoints"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This would need to be integrated with the FastAPI dependency injection
            # For now, it's a placeholder for the pattern
            return await func(*args, **kwargs)

        return wrapper

    return decorator
