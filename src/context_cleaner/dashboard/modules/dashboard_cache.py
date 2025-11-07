"""
Dashboard Cache Management

Phase 2.3 Extraction: Unified caching strategy and cache management
Extracted from cache-related methods in comprehensive_health_dashboard.py
Provides centralized cache coordination and delegation patterns

Contains:
- Session analytics cache with TTL
- Widget cache management
- Cache intelligence endpoint delegation
- Cache invalidation coordination
- Multi-level caching strategy
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from context_cleaner.api.cache import MultiLevelCache, CacheService

logger = logging.getLogger(__name__)


class DashboardCache:
    """
    Unified caching strategy for all dashboard components
    Extracted from cache-related methods in comprehensive dashboard
    Implements delegation pattern for different cache types
    """

    def __init__(
        self,
        cache_dashboard=None,
        telemetry_widgets=None,
        multi_level_cache: Optional[CacheService] = None,
    ):
        self.cache_dashboard = cache_dashboard
        self.telemetry_widgets = telemetry_widgets

        # Use MultiLevelCache for unified caching strategy
        self.multi_level_cache = multi_level_cache or MultiLevelCache()

        # Session analytics cache TTL configuration
        self._session_analytics_cache_ttl = 30  # Cache TTL in seconds

        # Cache configuration for different data types
        self.cache_config = {
            "session_analytics": {"ttl": 30},
            "widget_data": {"ttl": 60},
            "dashboard_metrics": {"ttl": 120},
            "performance_data": {"ttl": 300},
        }

        # Initialize legacy attributes for backward compatibility
        # These will be deprecated as we migrate to MultiLevelCache
        self.cache_store = {}
        self.cache_timestamps = {}
        self._session_analytics_cache = None
        self._session_analytics_cache_time = None

    async def get_session_analytics_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached session analytics using MultiLevelCache"""
        try:
            cached_data = await self.multi_level_cache.get("session_analytics")
            if cached_data:
                logger.debug(
                    f"Returning cached session analytics ({len(cached_data)} sessions)"
                )
            return cached_data
        except Exception as e:
            logger.warning(f"Error retrieving session analytics from cache: {e}")
            return None

    async def set_session_analytics_cache(self, data: List[Dict[str, Any]]) -> None:
        """Cache session analytics data using MultiLevelCache"""
        try:
            ttl = self.cache_config["session_analytics"]["ttl"]
            await self.multi_level_cache.set("session_analytics", data, ttl=ttl)
            logger.debug(
                f"Cached {len(data)} session analytics entries with {ttl}s TTL"
            )
        except Exception as e:
            logger.warning(f"Error caching session analytics: {e}")

    async def clear_session_analytics_cache(self) -> None:
        """Clear session analytics cache using MultiLevelCache"""
        try:
            await self.multi_level_cache.invalidate("session_analytics")
            # Legacy cleanup for backward compatibility
            self._session_analytics_cache = None
            self._session_analytics_cache_time = None
            logger.debug("Session analytics cache cleared via MultiLevelCache")
        except Exception as e:
            logger.warning(f"Error clearing session analytics cache: {e}")
            # Fallback to legacy clearing
            self._session_analytics_cache = None
            self._session_analytics_cache_time = None

    async def get_cache_intelligence(self) -> Optional[Dict[str, Any]]:
        """
        Delegate cache intelligence retrieval to cache dashboard
        Extracted from /api/cache-intelligence endpoint
        """
        if not self.cache_dashboard:
            logger.warning("Cache dashboard not available for intelligence retrieval")
            return None

        try:
            cache_data = await self.cache_dashboard.generate_dashboard(
                include_cross_session=True,
                max_sessions=30,
            )

            if cache_data:
                # Convert dataclass to dict for JSON serialization
                cache_dict = {
                    "context_size": cache_data.context_size,
                    "file_count": cache_data.file_count,
                    "session_count": cache_data.session_count,
                    "analysis_timestamp": cache_data.analysis_timestamp.isoformat(),
                    "health_metrics": {
                        "usage_weighted_focus_score": cache_data.health_metrics.usage_weighted_focus_score,
                        "efficiency_score": cache_data.health_metrics.efficiency_score,
                        "temporal_coherence_score": cache_data.health_metrics.temporal_coherence_score,
                        "cross_session_consistency": cache_data.health_metrics.cross_session_consistency,
                        "optimization_potential": cache_data.health_metrics.optimization_potential,
                        "waste_reduction_score": cache_data.health_metrics.waste_reduction_score,
                        "workflow_alignment": cache_data.health_metrics.workflow_alignment,
                        "overall_health_score": cache_data.health_metrics.overall_health_score,
                        "health_level": cache_data.health_metrics.health_level.value,
                    },
                    "usage_trends": cache_data.usage_trends,
                    "efficiency_trends": cache_data.efficiency_trends,
                    "insights": [
                        {
                            "type": insight.type,
                            "title": insight.title,
                            "description": insight.description,
                            "impact_score": insight.impact_score,
                            "recommendation": insight.recommendation,
                            "file_patterns": insight.file_patterns,
                            "session_correlation": insight.session_correlation,
                        }
                        for insight in cache_data.insights
                    ],
                    "optimization_recommendations": cache_data.optimization_recommendations,
                }
                return cache_dict
            else:
                logger.info("No cache intelligence data available")
                return None

        except Exception as e:
            logger.error(f"Cache intelligence retrieval failed: {e}")
            return None

    def clear_widget_cache(self) -> bool:
        """
        Delegate widget cache clearing to telemetry widgets
        Extracted from /api/telemetry/clear-cache endpoint
        """
        if not self.telemetry_widgets:
            logger.warning("Telemetry widgets not available for cache clearing")
            return False

        try:
            self.telemetry_widgets.clear_cache()
            logger.info("Widget cache cleared via delegation")
            return True
        except Exception as e:
            logger.error(f"Widget cache clear failed: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Get item from unified cache using MultiLevelCache"""
        try:
            # Try MultiLevelCache first
            cached_data = await self.multi_level_cache.get(key)
            if cached_data is not None:
                logger.debug(f"Cache hit for key '{key}' via MultiLevelCache")
                return cached_data
        except Exception as e:
            logger.warning(f"MultiLevelCache get failed for '{key}': {e}")

        # Fallback to legacy cache for backward compatibility
        if key not in self.cache_store:
            return None

        # Check TTL if configured
        if key in self.cache_timestamps and key in self.cache_config:
            ttl = self.cache_config[key].get("ttl", 300)  # Default 5 minutes
            cache_time = self.cache_timestamps[key]
            now = datetime.now()

            if (now - cache_time).total_seconds() > ttl:
                # Cache expired, remove it
                del self.cache_store[key]
                del self.cache_timestamps[key]
                if key in self.cache_config:
                    del self.cache_config[key]
                logger.debug(f"Legacy cache entry '{key}' expired and removed")
                return None

        return self.cache_store.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set item in unified cache using MultiLevelCache"""
        try:
            # Use MultiLevelCache as primary storage
            await self.multi_level_cache.set(key, value, ttl=ttl)
            logger.debug(f"Cache entry '{key}' set with TTL {ttl}s via MultiLevelCache")
        except Exception as e:
            logger.warning(f"MultiLevelCache set failed for '{key}': {e}")
            # Fallback to legacy cache
            self.cache_store[key] = value
            self.cache_timestamps[key] = datetime.now()
            self.cache_config[key] = {"ttl": ttl}
            logger.debug(f"Fallback: Legacy cache entry '{key}' set with TTL {ttl}s")

    async def invalidate(self, pattern: str = None) -> None:
        """Invalidate cache entries by pattern using MultiLevelCache"""
        try:
            if pattern is None:
                # Clear all caches
                await self.clear_all()
                return

            # Use MultiLevelCache pattern invalidation
            await self.multi_level_cache.invalidate(pattern)
            logger.debug(
                f"Invalidated cache entries matching pattern '{pattern}' via MultiLevelCache"
            )
        except Exception as e:
            logger.warning(
                f"MultiLevelCache invalidation failed for pattern '{pattern}': {e}"
            )

        # Fallback: Legacy pattern-based invalidation
        keys_to_remove = []
        for key in self.cache_store.keys():
            if pattern and pattern in key:
                keys_to_remove.append(key)
            elif pattern is None:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.cache_store[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
            if key in self.cache_config:
                del self.cache_config[key]

        logger.debug(
            f"Fallback: Invalidated {len(keys_to_remove)} legacy cache entries matching pattern '{pattern}'"
        )

    async def clear_all(self) -> None:
        """Clear all cache entries using MultiLevelCache"""
        try:
            # Clear MultiLevelCache
            await self.multi_level_cache.clear()
            logger.info("All MultiLevelCache entries cleared")
        except Exception as e:
            logger.warning(f"MultiLevelCache clear failed: {e}")

        # Clear legacy caches
        self.cache_store.clear()
        self.cache_timestamps.clear()
        self.cache_config.clear()
        await self.clear_session_analytics_cache()
        logger.info("All cache entries cleared (MultiLevelCache + legacy)")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics from MultiLevelCache and legacy caches"""
        now = datetime.now()
        expired_count = 0
        multilevel_stats = {}

        # Get MultiLevelCache statistics
        try:
            multilevel_stats = await self.multi_level_cache.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get MultiLevelCache stats: {e}")
            multilevel_stats = {"error": "MultiLevelCache stats unavailable"}

        # Count expired entries in legacy cache
        for key, cache_time in self.cache_timestamps.items():
            if key in self.cache_config:
                ttl = self.cache_config[key].get("ttl", 300)
                if (now - cache_time).total_seconds() > ttl:
                    expired_count += 1

        # Check if session analytics is cached
        session_analytics_cached = False
        session_analytics_size = 0
        try:
            cached_analytics = await self.multi_level_cache.get("session_analytics")
            if cached_analytics:
                session_analytics_cached = True
                session_analytics_size = (
                    len(cached_analytics) if isinstance(cached_analytics, list) else 1
                )
        except Exception:
            # Fallback to legacy check
            session_analytics_cached = self._session_analytics_cache is not None
            session_analytics_size = (
                len(self._session_analytics_cache)
                if self._session_analytics_cache
                else 0
            )

        return {
            "multilevel_cache": multilevel_stats,
            "legacy_cache": {
                "total_entries": len(self.cache_store),
                "expired_entries": expired_count,
            },
            "session_analytics_cached": session_analytics_cached,
            "session_analytics_cache_size": session_analytics_size,
            "session_analytics_cache_age_seconds": (
                (now - self._session_analytics_cache_time).total_seconds()
                if self._session_analytics_cache_time
                else None
            ),
            "cache_dashboard_available": self.cache_dashboard is not None,
            "telemetry_widgets_available": self.telemetry_widgets is not None,
        }


class CacheCoordinator:
    """
    Coordinates caching across multiple dashboard components
    Implements delegation pattern for complex cache orchestration
    """

    def __init__(self, dashboard_cache: DashboardCache):
        self.dashboard_cache = dashboard_cache

    async def refresh_all_caches(self) -> Dict[str, bool]:
        """Refresh all caches coordinately"""
        results = {}

        try:
            # Clear session analytics cache to force refresh
            await self.dashboard_cache.clear_session_analytics_cache()
            results["session_analytics"] = True
        except Exception as e:
            logger.error(f"Failed to clear session analytics cache: {e}")
            results["session_analytics"] = False

        try:
            # Clear widget cache if available
            widget_cleared = self.dashboard_cache.clear_widget_cache()
            results["widget_cache"] = widget_cleared
        except Exception as e:
            logger.error(f"Failed to clear widget cache: {e}")
            results["widget_cache"] = False

        try:
            # Clear general cache
            await self.dashboard_cache.clear_all()
            results["general_cache"] = True
        except Exception as e:
            logger.error(f"Failed to clear general cache: {e}")
            results["general_cache"] = False

        logger.info(f"Cache refresh completed: {results}")
        return results

    async def get_unified_cache_health(self) -> Dict[str, Any]:
        """Get unified cache health information"""
        stats = await self.dashboard_cache.get_cache_stats()

        # Get cache intelligence if available
        cache_intelligence = await self.dashboard_cache.get_cache_intelligence()

        # Determine overall health based on both MultiLevelCache and legacy cache
        multilevel_healthy = stats.get("multilevel_cache", {}).get("error") is None
        legacy_expired = stats.get("legacy_cache", {}).get("expired_entries", 0)
        overall_healthy = multilevel_healthy and legacy_expired == 0

        recommendations = []
        if not multilevel_healthy:
            recommendations.append("MultiLevelCache experiencing issues - check logs")
        if legacy_expired > 0:
            recommendations.append(
                f"Consider clearing {legacy_expired} expired legacy cache entries"
            )
        if not recommendations:
            recommendations.append("Cache operating normally")

        return {
            "cache_stats": stats,
            "cache_intelligence_available": cache_intelligence is not None,
            "overall_health": "healthy" if overall_healthy else "degraded",
            "multilevel_cache_healthy": multilevel_healthy,
            "legacy_cache_healthy": legacy_expired == 0,
            "recommendations": recommendations,
        }


class ModuleStatus:
    """Track module extraction status"""

    EXTRACTION_STATUS = "extracted"
    ORIGINAL_LINES = 200  # Cache-related methods scattered throughout
    TARGET_LINES = 200
    REDUCTION_TARGET = "Unified caching strategy, eliminate redundant implementations"


logger.info(
    f"dashboard_cache module extracted - Status: {ModuleStatus.EXTRACTION_STATUS}"
)
