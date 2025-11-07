"""
Service Layer Implementation

Provides business logic layer with caching, event emission, and clean
separation between API routes and data access.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import asyncio
from decimal import Decimal

from .models import (
    DashboardMetrics,
    WidgetData,
    SystemHealth,
    EventType,
    WebSocketMessage,
    DashboardOverviewResponse,
)
from .repositories import TelemetryRepository
from .cache import CacheService
from .websocket import EventBus

logger = logging.getLogger(__name__)


class DashboardService:
    """Core dashboard service with business logic and caching"""

    def __init__(
        self,
        telemetry_repo: TelemetryRepository,
        cache_service: CacheService,
        event_bus: EventBus,
    ):
        self.telemetry_repo = telemetry_repo
        self.cache = cache_service
        self.event_bus = event_bus
        self._last_metrics = None
        self._metrics_lock = asyncio.Lock()

    async def get_dashboard_overview(self) -> DashboardOverviewResponse:
        """Get complete dashboard overview with caching and event emission"""
        cache_key = "dashboard:overview:v1"

        try:
            # Try cache first
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug("Returning cached dashboard overview")
                return DashboardOverviewResponse(**cached)

            # Fetch fresh data
            async with self._metrics_lock:
                logger.info("Fetching fresh dashboard overview data")

                # Parallel data fetching for performance
                metrics_task = self.telemetry_repo.get_dashboard_metrics()
                health_task = self.telemetry_repo.get_system_health()

                metrics, system_health = await asyncio.gather(
                    metrics_task, health_task, return_exceptions=True
                )

                # Handle potential exceptions
                if isinstance(metrics, Exception):
                    logger.error(f"Error fetching metrics: {metrics}")
                    metrics = self._get_fallback_metrics()

                if isinstance(system_health, Exception):
                    logger.error(f"Error fetching health: {system_health}")
                    system_health = self._get_fallback_health()

                # Get essential widgets
                essential_widgets = await self._get_essential_widgets()

                overview = DashboardOverviewResponse(
                    metrics=metrics,
                    widgets=essential_widgets,
                    system_health=system_health,
                    last_updated=datetime.now(),
                )

                # Cache the response
                await self.cache.set(cache_key, overview.dict(), ttl=30)

                # Emit update event if metrics changed significantly
                await self._maybe_emit_metrics_update(metrics)

                return overview

        except Exception as e:
            logger.error(f"Error getting dashboard overview: {e}")
            return self._get_fallback_overview()

    async def get_widget_data(
        self,
        widget_type: str,
        session_id: Optional[str] = None,
        time_range_days: int = 7,
        force_refresh: bool = False,
    ) -> WidgetData:
        """Get specific widget data with caching"""

        cache_key = f"widget:{widget_type}:{session_id or 'global'}:{time_range_days}"

        if not force_refresh:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug(f"Returning cached widget data for {widget_type}")
                return WidgetData(**cached)

        try:
            logger.info(f"Fetching fresh widget data for {widget_type}")
            widget_data = await self.telemetry_repo.get_widget_data(
                widget_type, session_id, time_range_days
            )

            # Cache widget data with appropriate TTL based on type
            ttl = self._get_widget_cache_ttl(widget_type)
            await self.cache.set(cache_key, widget_data.to_dict(), ttl=ttl)

            # Emit widget update event
            await self.event_bus.emit(
                EventType.WIDGET_DATA_UPDATED.value,
                {
                    "widget_type": widget_type,
                    "widget_id": widget_data.widget_id,
                    "status": widget_data.status,
                    "data": widget_data.data,
                    "timestamp": widget_data.last_updated.isoformat(),
                },
            )

            return widget_data

        except Exception as e:
            logger.error(f"Error getting widget data for {widget_type}: {e}")
            return self._get_fallback_widget(widget_type)

    async def get_multiple_widgets(
        self,
        widget_types: List[str],
        session_id: Optional[str] = None,
        time_range_days: int = 7,
    ) -> Dict[str, WidgetData]:
        """Get multiple widgets efficiently with parallel fetching"""

        logger.info(f"Fetching {len(widget_types)} widgets in parallel")

        # Create tasks for parallel execution
        tasks = {}
        for widget_type in widget_types:
            tasks[widget_type] = self.get_widget_data(
                widget_type, session_id, time_range_days
            )

        # Execute all tasks
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Process results
        widgets = {}
        for widget_type, result in zip(widget_types, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {widget_type}: {result}")
                widgets[widget_type] = self._get_fallback_widget(widget_type)
            else:
                widgets[widget_type] = result

        return widgets

    async def invalidate_cache(self, pattern: str = "dashboard:*") -> bool:
        """Invalidate cache entries matching pattern"""
        try:
            await self.cache.invalidate(pattern)
            logger.info(f"Cache invalidated for pattern: {pattern}")

            # Emit cache invalidation event
            await self.event_bus.emit(
                "cache.invalidated",
                {"pattern": pattern, "timestamp": datetime.now().isoformat()},
            )
            return True

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False

    async def get_system_status(self) -> SystemHealth:
        """Get current system health with caching"""
        cache_key = "system:health:v1"

        try:
            cached = await self.cache.get(cache_key)
            if cached:
                return SystemHealth(**cached)

            health = await self.telemetry_repo.get_system_health()
            await self.cache.set(
                cache_key, health.to_dict(), ttl=15
            )  # Short TTL for health

            # Emit health status change if significant
            await self._maybe_emit_health_change(health)

            return health

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return self._get_fallback_health()

    async def get_cost_analysis(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive cost analysis"""
        cache_key = f"cost:analysis:{days}"

        try:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached

            cost_trends = await self.telemetry_repo.get_cost_trends(days)

            # Calculate additional metrics
            daily_costs = list(cost_trends.values())
            total_cost = sum(daily_costs)
            avg_daily = total_cost / max(len(daily_costs), 1)

            analysis = {
                "total_cost": total_cost,
                "average_daily_cost": avg_daily,
                "daily_trends": cost_trends,
                "cost_velocity": self._calculate_cost_velocity(daily_costs),
                "projected_monthly": avg_daily * 30,
                "analysis_date": datetime.now().isoformat(),
            }

            await self.cache.set(cache_key, analysis, ttl=300)  # 5 min cache
            return analysis

        except Exception as e:
            logger.error(f"Error getting cost analysis: {e}")
            return {"error": str(e), "total_cost": 0.0}

    # Private helper methods
    async def _get_essential_widgets(self) -> List[WidgetData]:
        """Get essential widgets for dashboard overview"""
        essential_types = ["error_monitor", "cost_tracker", "model_efficiency"]
        widgets_data = await self.get_multiple_widgets(essential_types)
        return list(widgets_data.values())

    async def _maybe_emit_metrics_update(self, current_metrics: DashboardMetrics):
        """Emit metrics update event if significant change detected"""
        if not self._last_metrics:
            self._last_metrics = current_metrics
            return

        # Check for significant changes
        token_change = abs(
            current_metrics.total_tokens - self._last_metrics.total_tokens
        )
        cost_change = float(abs(current_metrics.cost - self._last_metrics.cost))

        if token_change > 1000 or cost_change > 1.0:  # Thresholds for "significant"
            await self.event_bus.emit(
                EventType.DASHBOARD_METRICS_UPDATED.value,
                {
                    "total_tokens": current_metrics.total_tokens,
                    "total_sessions": current_metrics.total_sessions,
                    "success_rate": current_metrics.success_rate,
                    "cost_change": cost_change,
                    "timestamp": current_metrics.timestamp.isoformat(),
                },
            )

        self._last_metrics = current_metrics

    async def _maybe_emit_health_change(self, health: SystemHealth):
        """Emit health change event if status changed"""
        cache_key = "system:last_health_status"
        last_status = await self.cache.get(cache_key)

        if last_status != health.overall_healthy:
            await self.event_bus.emit(
                EventType.HEALTH_STATUS_CHANGED.value,
                {
                    "healthy": health.overall_healthy,
                    "database_status": health.database_status,
                    "connection_status": health.connection_status,
                    "timestamp": health.timestamp.isoformat(),
                },
            )
            await self.cache.set(cache_key, health.overall_healthy, ttl=3600)

    def _get_widget_cache_ttl(self, widget_type: str) -> int:
        """Get appropriate cache TTL for widget type"""
        ttl_map = {
            "error_monitor": 30,  # Errors need quick updates
            "cost_tracker": 300,  # Cost can be cached longer
            "model_efficiency": 600,  # Efficiency metrics are stable
            "timeout_risk": 60,  # Performance needs regular updates
        }
        return ttl_map.get(widget_type, 120)  # Default 2 minutes

    def _calculate_cost_velocity(self, daily_costs: List[float]) -> str:
        """Calculate cost trend velocity"""
        if len(daily_costs) < 2:
            return "stable"

        recent_avg = sum(daily_costs[:3]) / min(3, len(daily_costs))
        older_avg = sum(daily_costs[-3:]) / min(3, len(daily_costs))

        if recent_avg > older_avg * 1.1:
            return "increasing"
        elif recent_avg < older_avg * 0.9:
            return "decreasing"
        else:
            return "stable"

    def _get_fallback_metrics(self) -> DashboardMetrics:
        """Fallback metrics when data unavailable"""
        return DashboardMetrics(
            total_tokens=0,
            total_sessions=0,
            success_rate=100.0,
            active_agents=0,
            cost=Decimal("0.00"),
            timestamp=datetime.now(),
        )

    def _get_fallback_health(self) -> SystemHealth:
        """Fallback health when data unavailable"""
        return SystemHealth(
            overall_healthy=False,
            database_status="unknown",
            connection_status="disconnected",
            response_time_ms=0.0,
            uptime_seconds=0.0,
            error_rate=0.0,
            timestamp=datetime.now(),
        )

    def _get_fallback_widget(self, widget_type: str) -> WidgetData:
        """Fallback widget when data unavailable"""
        return WidgetData(
            widget_id=f"{widget_type}_fallback",
            widget_type=widget_type,
            title=widget_type.replace("_", " ").title(),
            status="error",
            data={"error": "Data temporarily unavailable"},
            last_updated=datetime.now(),
            metadata={"fallback": True},
        )

    def _get_fallback_overview(self) -> DashboardOverviewResponse:
        """Fallback overview when all else fails"""
        return DashboardOverviewResponse(
            metrics=self._get_fallback_metrics(),
            widgets=[],
            system_health=self._get_fallback_health(),
            last_updated=datetime.now(),
        )


class TelemetryService:
    """Service for telemetry-specific operations"""

    def __init__(
        self, telemetry_repo: TelemetryRepository, cache_service: CacheService
    ):
        self.telemetry_repo = telemetry_repo
        self.cache = cache_service

    async def get_active_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get active sessions with caching"""
        cache_key = f"sessions:active:{limit}"

        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        sessions = await self.telemetry_repo.get_active_sessions(limit)
        await self.cache.set(cache_key, sessions, ttl=60)  # 1 minute cache

        return sessions

    async def get_session_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for specific session"""
        cache_key = f"session:metrics:{session_id}"

        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # This would need to be implemented in the repository
        # For now, return a placeholder
        metrics = {
            "session_id": session_id,
            "status": "active",
            "start_time": datetime.now().isoformat(),
            "request_count": 0,
            "cost": 0.0,
        }

        await self.cache.set(cache_key, metrics, ttl=120)
        return metrics
