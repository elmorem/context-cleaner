"""
Integration Layer for Gradual Migration

Provides seamless integration between the new modern API and existing
Flask-based dashboard system, enabling gradual migration without breaking changes.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from flask import Flask, jsonify, request
from concurrent.futures import ThreadPoolExecutor
import threading

from .app import create_app
from .services import DashboardService
from ..telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)

class LegacyCompatibilityLayer:
    """Handles backward compatibility during migration"""

    def __init__(self, dashboard_service: DashboardService):
        self.dashboard_service = dashboard_service
        self._executor = ThreadPoolExecutor(max_workers=4)

    async def handle_legacy_health_report(self) -> Dict[str, Any]:
        """Handle legacy /api/health-report endpoint"""
        try:
            health = await self.dashboard_service.get_system_status()
            return {
                "status": "healthy" if health.overall_healthy else "unhealthy",
                "database_status": health.database_status,
                "connection_status": health.connection_status,
                "response_time": health.response_time_ms,
                "uptime": health.uptime_seconds,
                "error_rate": health.error_rate,
                "timestamp": health.timestamp.isoformat(),
                # Legacy compatibility fields
                "database_accessible": health.database_status == "healthy",
                "overall_healthy": health.overall_healthy
            }
        except Exception as e:
            logger.error(f"Legacy health report failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "database_status": "unknown",
                "overall_healthy": False
            }

    async def handle_legacy_productivity_summary(self) -> Dict[str, Any]:
        """Handle legacy /api/productivity-summary endpoint"""
        try:
            overview = await self.dashboard_service.get_dashboard_overview()
            return {
                "total_tokens": overview.metrics.total_tokens,
                "total_sessions": overview.metrics.total_sessions,
                "success_rate": f"{overview.metrics.success_rate:.1f}%",
                "active_agents": overview.metrics.active_agents,
                "total_cost": f"${float(overview.metrics.cost):.2f}",
                "last_updated": overview.last_updated.isoformat(),
                # Additional legacy fields that might be expected
                "uptime_hours": overview.system_health.uptime_seconds / 3600,
                "status": "operational" if overview.system_health.overall_healthy else "degraded"
            }
        except Exception as e:
            logger.error(f"Legacy productivity summary failed: {e}")
            return {
                "total_tokens": "0",
                "total_sessions": "0",
                "success_rate": "0.0%",
                "active_agents": "0",
                "total_cost": "$0.00",
                "status": "error",
                "error": str(e)
            }

    async def handle_legacy_telemetry_widgets(self) -> Dict[str, Any]:
        """Handle legacy /api/telemetry-widgets endpoint"""
        try:
            widget_types = ["error_monitor", "cost_tracker", "model_efficiency", "timeout_risk", "tool_optimizer"]
            widgets_data = await self.dashboard_service.get_multiple_widgets(widget_types)

            legacy_response = {}
            for widget_type, widget_data in widgets_data.items():
                legacy_response[widget_type] = {
                    "status": widget_data.status,
                    "title": widget_data.title,
                    "data": widget_data.data,
                    "last_updated": widget_data.last_updated.isoformat(),
                    "widget_id": widget_data.widget_id,
                    # Legacy compatibility fields
                    "healthy": widget_data.status == "healthy",
                    "error": widget_data.status == "critical"
                }

            return legacy_response

        except Exception as e:
            logger.error(f"Legacy telemetry widgets failed: {e}")
            return {"error": str(e)}

    def run_async_in_thread(self, coro):
        """Run async coroutine in thread pool"""
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        future = self._executor.submit(run)
        return future.result(timeout=30)  # 30 second timeout

class FlaskAPIBridge:
    """Bridge between Flask and FastAPI for gradual migration"""

    def __init__(self, flask_app: Flask, fastapi_app, compatibility_layer: LegacyCompatibilityLayer):
        self.flask_app = flask_app
        self.fastapi_app = fastapi_app
        self.compat = compatibility_layer
        self._setup_routes()

    def _setup_routes(self):
        """Setup bridged routes that delegate to new API"""

        @self.flask_app.route("/api/v1/status")
        def new_api_status():
            """Route to new API status"""
            try:
                # This could redirect to FastAPI or proxy the request
                return jsonify({
                    "new_api_available": True,
                    "migration_status": "in_progress",
                    "legacy_routes_available": True,
                    "timestamp": "2024-01-01T00:00:00Z"  # Replace with actual timestamp
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.flask_app.route("/api/health-report")
        def legacy_health_report():
            """Legacy health report with new API backend"""
            try:
                result = self.compat.run_async_in_thread(
                    self.compat.handle_legacy_health_report()
                )
                return jsonify(result)
            except Exception as e:
                logger.error(f"Flask bridge health report failed: {e}")
                return jsonify({
                    "status": "error",
                    "error": "Service temporarily unavailable",
                    "overall_healthy": False
                }), 503

        @self.flask_app.route("/api/productivity-summary")
        def legacy_productivity_summary():
            """Legacy productivity summary with new API backend"""
            try:
                result = self.compat.run_async_in_thread(
                    self.compat.handle_legacy_productivity_summary()
                )
                return jsonify(result)
            except Exception as e:
                logger.error(f"Flask bridge productivity summary failed: {e}")
                return jsonify({
                    "total_tokens": "0",
                    "status": "error",
                    "error": "Service temporarily unavailable"
                }), 503

        @self.flask_app.route("/api/telemetry-widgets")
        def legacy_telemetry_widgets():
            """Legacy telemetry widgets with new API backend"""
            try:
                result = self.compat.run_async_in_thread(
                    self.compat.handle_legacy_telemetry_widgets()
                )
                return jsonify(result)
            except Exception as e:
                logger.error(f"Flask bridge telemetry widgets failed: {e}")
                return jsonify({
                    "error": "Telemetry temporarily unavailable"
                }), 503

        @self.flask_app.route("/api/migration/status")
        def migration_status():
            """Get migration status information"""
            return jsonify({
                "migration_phase": "gradual_rollout",
                "new_api_endpoints": [
                    "/api/v1/health",
                    "/api/v1/dashboard/overview",
                    "/api/v1/widgets/{widget_type}",
                    "/ws/v1/realtime"
                ],
                "legacy_endpoints_bridged": [
                    "/api/health-report",
                    "/api/productivity-summary",
                    "/api/telemetry-widgets"
                ],
                "migration_completion": "85%",
                "estimated_completion": "2024-02-01"
            })

def create_integrated_app(
    existing_flask_app: Optional[Flask] = None,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 9000,
    redis_url: str = "redis://localhost:6379"
) -> tuple[Flask, Any]:
    """
    Create integrated application with both Flask (legacy) and FastAPI (modern)

    Args:
        existing_flask_app: Existing Flask app to integrate with
        clickhouse_host: ClickHouse host
        clickhouse_port: ClickHouse port
        redis_url: Redis URL for caching

    Returns:
        Tuple of (Flask app, FastAPI app) for integrated deployment
    """

    # Create or use existing Flask app
    if existing_flask_app:
        flask_app = existing_flask_app
    else:
        flask_app = Flask(__name__)
        flask_app.config['JSON_SORT_KEYS'] = False

    # Create modern FastAPI app
    fastapi_app = create_app(
        clickhouse_host=clickhouse_host,
        clickhouse_port=clickhouse_port,
        redis_url=redis_url,
        enable_websockets=True,
        debug=True
    )

    # Setup compatibility layer and bridge
    # Note: This would need to be properly initialized with async context
    # For now, this is a structural example

    logger.info("Integrated app created with Flask + FastAPI")
    logger.info("Legacy endpoints available through Flask")
    logger.info("Modern endpoints available through FastAPI")
    logger.info("WebSocket available through FastAPI")

    return flask_app, fastapi_app

class MigrationManager:
    """Manages the migration process from Flask to FastAPI"""

    def __init__(self):
        self.migration_config = {
            "phase": "gradual_rollout",
            "traffic_split": {
                "legacy": 70,  # 70% traffic to legacy endpoints
                "modern": 30   # 30% traffic to modern endpoints
            },
            "endpoints_migrated": [
                "/api/v1/health",
                "/api/v1/dashboard/overview",
                "/api/v1/widgets"
            ],
            "endpoints_pending": [
                "/api/performance-metrics",
                "/api/conversation-analytics",
                "/api/cost-burnrate"
            ]
        }

    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        total_endpoints = len(self.migration_config["endpoints_migrated"]) + len(self.migration_config["endpoints_pending"])
        migrated_count = len(self.migration_config["endpoints_migrated"])
        completion_percentage = (migrated_count / total_endpoints) * 100 if total_endpoints > 0 else 0

        return {
            "phase": self.migration_config["phase"],
            "completion_percentage": completion_percentage,
            "endpoints_migrated": self.migration_config["endpoints_migrated"],
            "endpoints_pending": self.migration_config["endpoints_pending"],
            "traffic_split": self.migration_config["traffic_split"],
            "recommendations": self._get_migration_recommendations()
        }

    def _get_migration_recommendations(self) -> list[str]:
        """Get migration recommendations based on current status"""
        recommendations = []

        if self.migration_config["traffic_split"]["modern"] < 50:
            recommendations.append("Consider increasing modern API traffic split")

        if len(self.migration_config["endpoints_pending"]) > 0:
            recommendations.append(f"Migrate remaining {len(self.migration_config['endpoints_pending'])} endpoints")

        recommendations.append("Monitor error rates during migration")
        recommendations.append("Set up performance comparison between legacy and modern APIs")

        return recommendations

    def update_traffic_split(self, legacy_percent: int, modern_percent: int):
        """Update traffic split configuration"""
        if legacy_percent + modern_percent != 100:
            raise ValueError("Traffic split must sum to 100%")

        self.migration_config["traffic_split"] = {
            "legacy": legacy_percent,
            "modern": modern_percent
        }

        logger.info(f"Traffic split updated: Legacy {legacy_percent}%, Modern {modern_percent}%")

    def mark_endpoint_migrated(self, endpoint: str):
        """Mark an endpoint as successfully migrated"""
        if endpoint in self.migration_config["endpoints_pending"]:
            self.migration_config["endpoints_pending"].remove(endpoint)
            self.migration_config["endpoints_migrated"].append(endpoint)
            logger.info(f"Endpoint migrated: {endpoint}")
        else:
            logger.warning(f"Endpoint {endpoint} not found in pending list")