"""
Repository Pattern Implementation

Provides clean data access layer with proper separation of concerns,
abstracting ClickHouse operations and enabling easy testing and caching.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from .models import DashboardMetrics, WidgetData, SystemHealth
from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


class TelemetryRepository(ABC):
    """Abstract repository for telemetry data access"""

    @abstractmethod
    async def get_dashboard_metrics(self) -> DashboardMetrics:
        """Get comprehensive dashboard metrics"""
        pass

    @abstractmethod
    async def get_widget_data(
        self,
        widget_type: str,
        session_id: Optional[str] = None,
        time_range_days: int = 7,
    ) -> WidgetData:
        """Get data for a specific widget"""
        pass

    @abstractmethod
    async def get_system_health(self) -> SystemHealth:
        """Get current system health status"""
        pass

    @abstractmethod
    async def get_active_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get list of active sessions"""
        pass

    @abstractmethod
    async def get_cost_trends(self, days: int = 7) -> Dict[str, float]:
        """Get cost trends over specified period"""
        pass


class ClickHouseTelemetryRepository(TelemetryRepository):
    """ClickHouse implementation of telemetry repository"""

    def __init__(self, clickhouse_client: ClickHouseClient):
        self.client = clickhouse_client
        self._start_time = datetime.now()

    async def get_dashboard_metrics(self) -> DashboardMetrics:
        """Get comprehensive dashboard metrics with optimized single query"""
        try:
            # Single optimized query for all core metrics
            query = """
            WITH
                token_data AS (
                    SELECT COALESCE(SUM(Value), 0) as total_tokens
                    FROM otel.otel_metrics_sum
                    WHERE MetricName = 'claude_code.token.usage'
                      AND TimeUnix >= now() - INTERVAL 30 DAY
                ),
                session_data AS (
                    SELECT
                        COUNT(DISTINCT LogAttributes['session.id']) as total_sessions,
                        COALESCE(SUM(toFloat64OrNull(LogAttributes['cost_usd'])), 0) as total_cost,
                        COUNT(*) as total_requests,
                        SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as errors
                    FROM otel.otel_logs
                    WHERE Body IN ('claude_code.api_request', 'claude_code.api_error')
                      AND Timestamp >= now() - INTERVAL 30 DAY
                ),
                active_tools AS (
                    SELECT COUNT(DISTINCT LogAttributes['tool_name']) as active_agents
                    FROM otel.otel_logs
                    WHERE Body = 'claude_code.tool_decision'
                      AND LogAttributes['tool_name'] != ''
                      AND Timestamp >= now() - INTERVAL 7 DAY
                )
            SELECT
                t.total_tokens,
                s.total_sessions,
                s.total_cost,
                CASE
                    WHEN s.total_requests > 0
                    THEN (s.total_requests - s.errors) * 100.0 / s.total_requests
                    ELSE 100.0
                END as success_rate,
                a.active_agents
            FROM token_data t, session_data s, active_tools a
            """

            results = await self.client.execute_query(query)
            if not results:
                logger.warning("No metrics data available, returning defaults")
                return self._get_default_metrics()

            data = results[0]
            return DashboardMetrics(
                total_tokens=int(data.get("total_tokens", 0)),
                total_sessions=int(data.get("total_sessions", 0)),
                success_rate=float(data.get("success_rate", 100.0)),
                active_agents=int(data.get("active_agents", 0)),
                cost=Decimal(str(data.get("total_cost", 0.0))),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {e}")
            return self._get_default_metrics()

    async def get_widget_data(
        self,
        widget_type: str,
        session_id: Optional[str] = None,
        time_range_days: int = 7,
    ) -> WidgetData:
        """Get data for specific widget type with caching considerations"""
        try:
            # Widget-specific data queries
            data = {}
            status = "healthy"

            if widget_type == "error_monitor":
                data = await self._get_error_monitor_data(time_range_days)
                status = "critical" if data.get("error_count", 0) > 10 else "healthy"

            elif widget_type == "cost_tracker":
                data = await self._get_cost_tracker_data(time_range_days)
                # Determine status based on cost trends
                status = "warning" if data.get("daily_cost", 0) > 50 else "healthy"

            elif widget_type == "model_efficiency":
                data = await self._get_model_efficiency_data(time_range_days)
                status = "healthy"

            elif widget_type == "timeout_risk":
                data = await self._get_timeout_risk_data(time_range_days)
                avg_duration = data.get("avg_duration_ms", 0)
                status = (
                    "critical"
                    if avg_duration > 30000
                    else "warning" if avg_duration > 15000 else "healthy"
                )

            else:
                # Generic widget data
                data = {"message": f"Widget type {widget_type} not implemented yet"}
                status = "healthy"

            return WidgetData(
                widget_id=f"{widget_type}_{int(datetime.now().timestamp())}",
                widget_type=widget_type,
                title=self._get_widget_title(widget_type),
                status=status,
                data=data,
                last_updated=datetime.now(),
                metadata={"time_range_days": time_range_days, "session_id": session_id},
            )

        except Exception as e:
            logger.error(f"Error getting widget data for {widget_type}: {e}")
            return self._get_default_widget(widget_type)

    async def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health status"""
        try:
            # Check ClickHouse connection health
            health_check = await self.client.comprehensive_health_check()

            # Calculate uptime
            uptime_seconds = (datetime.now() - self._start_time).total_seconds()

            # Get error rate
            error_rate = await self._get_error_rate()

            return SystemHealth(
                overall_healthy=health_check.get("overall_healthy", False),
                database_status=health_check.get("connection_status", "unknown"),
                connection_status=(
                    "connected"
                    if health_check.get("database_accessible")
                    else "disconnected"
                ),
                response_time_ms=health_check.get("response_time_ms", 0.0),
                uptime_seconds=uptime_seconds,
                error_rate=error_rate,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return self._get_default_health()

    async def get_active_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get list of active sessions"""
        try:
            query = f"""
            SELECT DISTINCT
                LogAttributes['session.id'] as session_id,
                MAX(Timestamp) as last_activity,
                COUNT(*) as request_count,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as session_cost
            FROM otel.otel_logs
            WHERE Body = 'claude_code.api_request'
              AND Timestamp >= now() - INTERVAL 24 HOUR
              AND LogAttributes['session.id'] != ''
            GROUP BY LogAttributes['session.id']
            ORDER BY last_activity DESC
            LIMIT {limit}
            """

            results = await self.client.execute_query(query)
            return [
                {
                    "session_id": row["session_id"],
                    "last_activity": row["last_activity"],
                    "request_count": int(row["request_count"]),
                    "cost": float(row.get("session_cost", 0)),
                }
                for row in results
            ]

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    async def get_cost_trends(self, days: int = 7) -> Dict[str, float]:
        """Get cost trends over specified period"""
        try:
            query = f"""
            SELECT
                toDate(Timestamp) as date,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as daily_cost
            FROM otel.otel_logs
            WHERE Body = 'claude_code.api_request'
              AND Timestamp >= now() - INTERVAL {days} DAY
              AND LogAttributes['cost_usd'] != ''
            GROUP BY date
            ORDER BY date DESC
            """

            results = await self.client.execute_query(query)
            return {row["date"]: float(row["daily_cost"]) for row in results}

        except Exception as e:
            logger.error(f"Error getting cost trends: {e}")
            return {}

    # Private helper methods
    async def _get_error_monitor_data(self, time_range_days: int) -> Dict[str, Any]:
        """Get error monitoring data"""
        query = f"""
        SELECT
            COUNT(*) as error_count,
            COUNT(DISTINCT LogAttributes['session.id']) as affected_sessions,
            LogAttributes['error'] as error_type,
            COUNT(*) as count
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_error'
          AND Timestamp >= now() - INTERVAL {time_range_days} DAY
        GROUP BY LogAttributes['error']
        ORDER BY count DESC
        """

        results = await self.client.execute_query(query)
        total_errors = sum(row["count"] for row in results)

        return {
            "error_count": total_errors,
            "error_types": [
                {"type": row["error_type"], "count": row["count"]}
                for row in results[:5]
            ],
            "trend": "stable",  # Could be calculated from time series
        }

    async def _get_cost_tracker_data(self, time_range_days: int) -> Dict[str, Any]:
        """Get cost tracking data"""
        # Get model breakdown
        query = f"""
        SELECT
            LogAttributes['model'] as model,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as model_cost,
            COUNT(*) as request_count
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_request'
          AND Timestamp >= now() - INTERVAL {time_range_days} DAY
          AND LogAttributes['model'] != ''
        GROUP BY LogAttributes['model']
        ORDER BY model_cost DESC
        """

        results = await self.client.execute_query(query)
        total_cost = sum(float(row["model_cost"]) for row in results)

        return {
            "total_cost": total_cost,
            "daily_cost": total_cost / time_range_days,
            "model_breakdown": [
                {
                    "model": row["model"],
                    "cost": float(row["model_cost"]),
                    "requests": int(row["request_count"]),
                }
                for row in results
            ],
        }

    async def _get_model_efficiency_data(self, time_range_days: int) -> Dict[str, Any]:
        """Get model efficiency comparison data"""
        return await self.client.get_model_token_stats(time_range_days)

    async def _get_timeout_risk_data(self, time_range_days: int) -> Dict[str, Any]:
        """Get timeout risk assessment data"""
        query = f"""
        SELECT
            AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration_ms,
            MAX(toFloat64OrNull(LogAttributes['duration_ms'])) as max_duration_ms,
            COUNT(*) as total_requests,
            SUM(CASE WHEN toFloat64OrNull(LogAttributes['duration_ms']) > 30000 THEN 1 ELSE 0 END) as slow_requests
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_request'
          AND Timestamp >= now() - INTERVAL {time_range_days} DAY
          AND LogAttributes['duration_ms'] != ''
        """

        results = await self.client.execute_query(query)
        if results:
            data = results[0]
            return {
                "avg_duration_ms": float(data.get("avg_duration_ms", 0)),
                "max_duration_ms": float(data.get("max_duration_ms", 0)),
                "slow_request_ratio": float(data.get("slow_requests", 0))
                / max(float(data.get("total_requests", 1)), 1),
                "risk_level": (
                    "high" if float(data.get("avg_duration_ms", 0)) > 20000 else "low"
                ),
            }
        return {"avg_duration_ms": 0, "risk_level": "unknown"}

    async def _get_error_rate(self) -> float:
        """Calculate current error rate"""
        try:
            query = """
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as errors
            FROM otel.otel_logs
            WHERE Body IN ('claude_code.api_request', 'claude_code.api_error')
              AND Timestamp >= now() - INTERVAL 1 HOUR
            """

            results = await self.client.execute_query(query)
            if results:
                data = results[0]
                total = int(data.get("total_requests", 0))
                errors = int(data.get("errors", 0))
                return (errors / max(total, 1)) * 100.0
            return 0.0

        except Exception:
            return 0.0

    def _get_widget_title(self, widget_type: str) -> str:
        """Get human-readable title for widget type"""
        titles = {
            "error_monitor": "Error Monitor",
            "cost_tracker": "Cost Tracker",
            "model_efficiency": "Model Efficiency",
            "timeout_risk": "Timeout Risk Assessment",
            "tool_optimizer": "Tool Optimizer",
        }
        return titles.get(widget_type, widget_type.replace("_", " ").title())

    def _get_default_metrics(self) -> DashboardMetrics:
        """Return default metrics when data is unavailable"""
        return DashboardMetrics(
            total_tokens=0,
            total_sessions=0,
            success_rate=100.0,
            active_agents=0,
            cost=Decimal("0.00"),
            timestamp=datetime.now(),
        )

    def _get_default_widget(self, widget_type: str) -> WidgetData:
        """Return default widget when data is unavailable"""
        return WidgetData(
            widget_id=f"{widget_type}_default",
            widget_type=widget_type,
            title=self._get_widget_title(widget_type),
            status="unknown",
            data={"message": "Data temporarily unavailable"},
            last_updated=datetime.now(),
            metadata={},
        )

    def _get_default_health(self) -> SystemHealth:
        """Return default health status when check fails"""
        return SystemHealth(
            overall_healthy=False,
            database_status="unknown",
            connection_status="unknown",
            response_time_ms=0.0,
            uptime_seconds=0.0,
            error_rate=0.0,
            timestamp=datetime.now(),
        )
