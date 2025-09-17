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

logger = logging.getLogger(__name__)


class DashboardCache:
    """
    Unified caching strategy for all dashboard components
    Extracted from cache-related methods in comprehensive dashboard
    Implements delegation pattern for different cache types
    """

    def __init__(self, cache_dashboard=None, telemetry_widgets=None):
        self.cache_dashboard = cache_dashboard
        self.telemetry_widgets = telemetry_widgets

        # Session analytics cache for performance optimization
        self._session_analytics_cache: Optional[List[Dict[str, Any]]] = None
        self._session_analytics_cache_time: Optional[datetime] = None
        self._session_analytics_cache_ttl = 30  # Cache TTL in seconds

        # General cache store for other data
        self.cache_store = {}
        self.cache_timestamps = {}
        self.cache_config = {}

    def get_session_analytics_cache(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached session analytics if still valid"""
        now = datetime.now()
        if (self._session_analytics_cache is not None and
            self._session_analytics_cache_time is not None and
            (now - self._session_analytics_cache_time).total_seconds() < self._session_analytics_cache_ttl):
            logger.debug(f"Returning cached session analytics ({len(self._session_analytics_cache)} sessions)")
            return self._session_analytics_cache
        return None

    def set_session_analytics_cache(self, data: List[Dict[str, Any]]) -> None:
        """Cache session analytics data with timestamp"""
        self._session_analytics_cache = data
        self._session_analytics_cache_time = datetime.now()
        logger.debug(f"Cached {len(data)} session analytics entries")

    def clear_session_analytics_cache(self) -> None:
        """Clear session analytics cache"""
        self._session_analytics_cache = None
        self._session_analytics_cache_time = None
        logger.debug("Session analytics cache cleared")

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

    def get(self, key: str) -> Optional[Any]:
        """Get item from general cache with TTL check"""
        if key not in self.cache_store:
            return None

        # Check TTL if configured
        if key in self.cache_timestamps and key in self.cache_config:
            ttl = self.cache_config[key].get('ttl', 300)  # Default 5 minutes
            cache_time = self.cache_timestamps[key]
            now = datetime.now()

            if (now - cache_time).total_seconds() > ttl:
                # Cache expired, remove it
                del self.cache_store[key]
                del self.cache_timestamps[key]
                if key in self.cache_config:
                    del self.cache_config[key]
                logger.debug(f"Cache entry '{key}' expired and removed")
                return None

        return self.cache_store.get(key)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set item in general cache with TTL"""
        self.cache_store[key] = value
        self.cache_timestamps[key] = datetime.now()
        self.cache_config[key] = {'ttl': ttl}
        logger.debug(f"Cache entry '{key}' set with TTL {ttl}s")

    def invalidate(self, pattern: str = None) -> None:
        """Invalidate cache entries by pattern"""
        if pattern is None:
            # Clear all caches
            self.clear_all()
            return

        # Pattern-based invalidation
        keys_to_remove = []
        for key in self.cache_store.keys():
            if pattern in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.cache_store[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
            if key in self.cache_config:
                del self.cache_config[key]

        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries matching pattern '{pattern}'")

    def clear_all(self) -> None:
        """Clear all cache entries"""
        self.cache_store.clear()
        self.cache_timestamps.clear()
        self.cache_config.clear()
        self.clear_session_analytics_cache()
        logger.info("All cache entries cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = datetime.now()
        expired_count = 0

        for key, cache_time in self.cache_timestamps.items():
            if key in self.cache_config:
                ttl = self.cache_config[key].get('ttl', 300)
                if (now - cache_time).total_seconds() > ttl:
                    expired_count += 1

        return {
            "total_entries": len(self.cache_store),
            "expired_entries": expired_count,
            "session_analytics_cached": self._session_analytics_cache is not None,
            "session_analytics_cache_size": len(self._session_analytics_cache) if self._session_analytics_cache else 0,
            "session_analytics_cache_age_seconds": (
                (now - self._session_analytics_cache_time).total_seconds()
                if self._session_analytics_cache_time else None
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

        # Clear session analytics cache to force refresh
        self.dashboard_cache.clear_session_analytics_cache()
        results["session_analytics"] = True

        # Clear widget cache if available
        widget_cleared = self.dashboard_cache.clear_widget_cache()
        results["widget_cache"] = widget_cleared

        # Clear general cache
        self.dashboard_cache.clear_all()
        results["general_cache"] = True

        logger.info(f"Cache refresh completed: {results}")
        return results

    async def get_unified_cache_health(self) -> Dict[str, Any]:
        """Get unified cache health information"""
        stats = self.dashboard_cache.get_cache_stats()

        # Get cache intelligence if available
        cache_intelligence = await self.dashboard_cache.get_cache_intelligence()

        return {
            "cache_stats": stats,
            "cache_intelligence_available": cache_intelligence is not None,
            "overall_health": "healthy" if stats["expired_entries"] == 0 else "degraded",
            "recommendations": [
                "Consider clearing expired entries" if stats["expired_entries"] > 0 else "Cache operating normally"
            ]
        }


class ModuleStatus:
    """Track module extraction status"""
    EXTRACTION_STATUS = "extracted"
    ORIGINAL_LINES = 200  # Cache-related methods scattered throughout
    TARGET_LINES = 200
    REDUCTION_TARGET = "Unified caching strategy, eliminate redundant implementations"


logger.info(f"dashboard_cache module extracted - Status: {ModuleStatus.EXTRACTION_STATUS}")