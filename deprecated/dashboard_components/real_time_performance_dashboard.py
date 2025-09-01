"""
Real-Time Performance Dashboard

Interactive dashboard with WebSocket-based real-time updates for monitoring
memory and CPU optimization with live controls and alerts.
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import logging

from ..optimization.memory_optimizer import MemoryOptimizer
from ..optimization.cpu_optimizer import CPUOptimizer, TaskPriority
from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


class RealTimePerformanceDashboard:
    """
    Real-time performance monitoring dashboard with WebSocket updates,
    interactive controls, and automated alerts.
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize real-time performance dashboard."""
        self.config = config or ContextCleanerConfig.from_env()

        # Flask application
        self.app = Flask(__name__, template_folder="templates")
        self.app.config["SECRET_KEY"] = "context-cleaner-performance-dashboard"
        self.socketio = SocketIO(
            self.app, cors_allowed_origins="*", async_mode="threading"
        )

        # Performance optimizers
        self.memory_optimizer = MemoryOptimizer(config)
        self.cpu_optimizer = CPUOptimizer(config)

        # Dashboard state
        self._is_running = False
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Performance data storage
        self._performance_history: List[Dict[str, Any]] = []
        self._max_history_points = 200  # 10 minutes at 3-second intervals

        # Alert system
        self._alerts_enabled = True
        self._alert_thresholds = {
            "memory_mb": 50.0,
            "cpu_percent": 5.0,
            "memory_critical_mb": 60.0,
            "cpu_critical_percent": 8.0,
        }
        self._last_alerts: Dict[str, datetime] = {}
        self._alert_cooldown_minutes = 5

        # Setup Flask routes and SocketIO events
        self._setup_routes()
        self._setup_socketio_events()

        logger.info("Real-time performance dashboard initialized")

    def _setup_routes(self):
        """Setup Flask routes for the dashboard."""

        @self.app.route("/")
        def index():
            """Main dashboard page."""
            return render_template("performance_dashboard.html")

        @self.app.route("/api/performance/current")
        def get_current_performance():
            """Get current performance metrics."""
            return jsonify(self._get_current_metrics())

        @self.app.route("/api/performance/history")
        def get_performance_history():
            """Get performance history data."""
            return jsonify(
                {
                    "history": self._performance_history[-100:],  # Last 100 points
                    "total_points": len(self._performance_history),
                }
            )

        @self.app.route("/api/performance/optimize", methods=["POST"])
        def force_optimization():
            """Force immediate performance optimization."""
            try:
                data = request.get_json() or {}
                optimize_type = data.get("type", "both")

                results = {}
                if optimize_type in ["memory", "both"]:
                    memory_before = self.memory_optimizer._take_memory_snapshot()
                    memory_after = self.memory_optimizer.force_optimization()
                    results["memory"] = {
                        "before_mb": round(memory_before.process_mb, 1),
                        "after_mb": round(memory_after.process_mb, 1),
                        "saved_mb": round(
                            memory_before.process_mb - memory_after.process_mb, 1
                        ),
                    }

                if optimize_type in ["cpu", "both"]:
                    cpu_stats = self.cpu_optimizer.force_optimization()
                    results["cpu"] = cpu_stats

                return jsonify(
                    {
                        "success": True,
                        "results": results,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                logger.error(f"Force optimization failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/performance/settings", methods=["GET", "POST"])
        def performance_settings():
            """Get or update performance settings."""
            if request.method == "GET":
                return jsonify(
                    {
                        "alerts_enabled": self._alerts_enabled,
                        "thresholds": self._alert_thresholds,
                        "cooldown_minutes": self._alert_cooldown_minutes,
                        "max_history_points": self._max_history_points,
                    }
                )

            elif request.method == "POST":
                try:
                    data = request.get_json()

                    if "alerts_enabled" in data:
                        self._alerts_enabled = bool(data["alerts_enabled"])

                    if "thresholds" in data:
                        self._alert_thresholds.update(data["thresholds"])

                    if "cooldown_minutes" in data:
                        self._alert_cooldown_minutes = int(data["cooldown_minutes"])

                    return jsonify(
                        {"success": True, "message": "Settings updated successfully"}
                    )

                except Exception as e:
                    return jsonify({"success": False, "error": str(e)}), 400

    def _setup_socketio_events(self):
        """Setup SocketIO event handlers."""

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection."""
            logger.debug(f"Client connected: {request.sid}")
            # Send current performance data to new client
            emit("performance_update", self._get_current_metrics())

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection."""
            logger.debug(f"Client disconnected: {request.sid}")

        @self.socketio.on("request_optimization")
        def handle_optimization_request(data):
            """Handle optimization request from client."""
            try:
                optimize_type = data.get("type", "both")

                # Schedule optimization as background task
                if optimize_type in ["memory", "both"]:
                    self.cpu_optimizer.schedule_background_task(
                        name="dashboard_memory_optimization",
                        func=self.memory_optimizer.force_optimization,
                        priority=TaskPriority.HIGH,
                        max_duration_ms=5000,
                    )

                if optimize_type in ["cpu", "both"]:
                    self.cpu_optimizer.schedule_background_task(
                        name="dashboard_cpu_optimization",
                        func=self.cpu_optimizer.force_optimization,
                        priority=TaskPriority.HIGH,
                        max_duration_ms=2000,
                    )

                emit(
                    "optimization_scheduled",
                    {"type": optimize_type, "timestamp": datetime.now().isoformat()},
                )

            except Exception as e:
                emit(
                    "optimization_error",
                    {"error": str(e), "timestamp": datetime.now().isoformat()},
                )

        @self.socketio.on("update_settings")
        def handle_settings_update(data):
            """Handle settings update from client."""
            try:
                if "alerts_enabled" in data:
                    self._alerts_enabled = bool(data["alerts_enabled"])

                if "thresholds" in data:
                    self._alert_thresholds.update(data["thresholds"])

                emit(
                    "settings_updated",
                    {"success": True, "timestamp": datetime.now().isoformat()},
                )

            except Exception as e:
                emit(
                    "settings_error",
                    {"error": str(e), "timestamp": datetime.now().isoformat()},
                )

    def start(self, host: str = "127.0.0.1", port: int = 5002, debug: bool = False):
        """Start the real-time dashboard server."""
        if self._is_running:
            logger.warning("Dashboard already running")
            return

        # Start optimizers
        self.memory_optimizer.start_monitoring()
        self.cpu_optimizer.start()

        # Start performance data collection
        self._is_running = True
        self._stop_event.clear()

        self._update_thread = threading.Thread(
            target=self._performance_update_loop,
            daemon=True,
            name="PerformanceDashboard",
        )
        self._update_thread.start()

        logger.info(f"Starting real-time performance dashboard on {host}:{port}")

        # Run Flask-SocketIO server
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,  # Disable reloader to prevent threading issues
        )

    def stop(self):
        """Stop the dashboard server."""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        # Stop update thread
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=5.0)

        # Stop optimizers
        self.memory_optimizer.stop_monitoring()
        self.cpu_optimizer.stop()

        logger.info("Real-time performance dashboard stopped")

    def _performance_update_loop(self):
        """Background loop for collecting and broadcasting performance data."""
        while not self._stop_event.is_set():
            try:
                # Collect current metrics
                metrics = self._get_current_metrics()

                # Store in history
                self._performance_history.append(metrics)

                # Trim history to max size
                if len(self._performance_history) > self._max_history_points:
                    self._performance_history = self._performance_history[
                        -self._max_history_points :
                    ]

                # Check for alerts
                alerts = self._check_performance_alerts(metrics)
                if alerts:
                    metrics["alerts"] = alerts

                # Broadcast to all connected clients
                self.socketio.emit("performance_update", metrics)

                # Update every 3 seconds
                self._stop_event.wait(timeout=3.0)

            except Exception as e:
                logger.warning(f"Performance update loop error: {e}")
                self._stop_event.wait(timeout=10.0)

    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics from optimizers."""
        try:
            # Memory metrics
            memory_report = self.memory_optimizer.get_memory_report()

            # CPU metrics
            cpu_report = self.cpu_optimizer.get_performance_report()

            # Combined metrics
            return {
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "current_mb": memory_report["current"]["process_mb"],
                    "target_mb": memory_report["current"]["target_mb"],
                    "usage_percent": memory_report["current"]["usage_percent"],
                    "health_score": memory_report["current"]["health_score"],
                    "cache_memory_mb": memory_report["caches"]["total_memory_mb"],
                    "cache_items": memory_report["caches"]["total_items"],
                    "trend": memory_report["trends"]["memory_trend"],
                },
                "cpu": {
                    "current_percent": cpu_report["summary"]["current_cpu_percent"],
                    "target_percent": cpu_report["summary"]["target_cpu_percent"],
                    "avg_percent": cpu_report["summary"]["avg_cpu_percent"],
                    "max_percent": cpu_report["summary"]["max_cpu_percent"],
                    "health_score": cpu_report["summary"]["health_score"],
                    "throttle_level": cpu_report["scheduler"]["cpu"]["throttle_level"],
                    "pending_tasks": cpu_report["scheduler"]["scheduling"][
                        "total_pending_tasks"
                    ],
                    "trend": cpu_report["summary"]["trend"],
                },
                "system": {
                    "total_memory_mb": memory_report["system"]["total_mb"],
                    "available_memory_mb": memory_report["system"]["available_mb"],
                    "cpu_count": cpu_report["scheduler"]["performance"]["cpu_count"],
                    "active_threads": cpu_report["scheduler"]["scheduling"][
                        "active_threads"
                    ],
                },
                "overall_health": self._calculate_overall_health(
                    memory_report["current"]["health_score"],
                    cpu_report["summary"]["health_score"],
                ),
            }

        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "memory": {"current_mb": 0, "health_score": 0},
                "cpu": {"current_percent": 0, "health_score": 0},
                "overall_health": 0,
            }

    def _check_performance_alerts(
        self, metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for performance alerts based on thresholds."""
        if not self._alerts_enabled:
            return []

        alerts = []
        now = datetime.now()

        # Memory alerts
        memory_mb = metrics.get("memory", {}).get("current_mb", 0)
        if memory_mb > self._alert_thresholds["memory_critical_mb"]:
            alert_key = "memory_critical"
            if self._should_send_alert(alert_key, now):
                alerts.append(
                    {
                        "type": "critical",
                        "category": "memory",
                        "message": f'Critical memory usage: {memory_mb:.1f}MB (threshold: {self._alert_thresholds["memory_critical_mb"]}MB)',
                        "value": memory_mb,
                        "threshold": self._alert_thresholds["memory_critical_mb"],
                        "timestamp": now.isoformat(),
                    }
                )
                self._last_alerts[alert_key] = now

        elif memory_mb > self._alert_thresholds["memory_mb"]:
            alert_key = "memory_warning"
            if self._should_send_alert(alert_key, now):
                alerts.append(
                    {
                        "type": "warning",
                        "category": "memory",
                        "message": f'High memory usage: {memory_mb:.1f}MB (threshold: {self._alert_thresholds["memory_mb"]}MB)',
                        "value": memory_mb,
                        "threshold": self._alert_thresholds["memory_mb"],
                        "timestamp": now.isoformat(),
                    }
                )
                self._last_alerts[alert_key] = now

        # CPU alerts
        cpu_percent = metrics.get("cpu", {}).get("current_percent", 0)
        if cpu_percent > self._alert_thresholds["cpu_critical_percent"]:
            alert_key = "cpu_critical"
            if self._should_send_alert(alert_key, now):
                alerts.append(
                    {
                        "type": "critical",
                        "category": "cpu",
                        "message": f'Critical CPU usage: {cpu_percent:.1f}% (threshold: {self._alert_thresholds["cpu_critical_percent"]}%)',
                        "value": cpu_percent,
                        "threshold": self._alert_thresholds["cpu_critical_percent"],
                        "timestamp": now.isoformat(),
                    }
                )
                self._last_alerts[alert_key] = now

        elif cpu_percent > self._alert_thresholds["cpu_percent"]:
            alert_key = "cpu_warning"
            if self._should_send_alert(alert_key, now):
                alerts.append(
                    {
                        "type": "warning",
                        "category": "cpu",
                        "message": f'High CPU usage: {cpu_percent:.1f}% (threshold: {self._alert_thresholds["cpu_percent"]}%)',
                        "value": cpu_percent,
                        "threshold": self._alert_thresholds["cpu_percent"],
                        "timestamp": now.isoformat(),
                    }
                )
                self._last_alerts[alert_key] = now

        return alerts

    def _should_send_alert(self, alert_key: str, now: datetime) -> bool:
        """Check if enough time has passed since last alert of this type."""
        if alert_key not in self._last_alerts:
            return True

        time_since_last = now - self._last_alerts[alert_key]
        return time_since_last.total_seconds() >= (self._alert_cooldown_minutes * 60)

    def _calculate_overall_health(self, memory_health: int, cpu_health: int) -> int:
        """Calculate overall system health score."""
        # Weighted average with slight emphasis on memory
        return int((memory_health * 0.6) + (cpu_health * 0.4))

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard operational statistics."""
        return {
            "is_running": self._is_running,
            "performance_history_points": len(self._performance_history),
            "alerts_enabled": self._alerts_enabled,
            "alert_thresholds": self._alert_thresholds,
            "recent_alerts_count": len(
                [
                    alert_time
                    for alert_time in self._last_alerts.values()
                    if datetime.now() - alert_time < timedelta(hours=1)
                ]
            ),
            "memory_optimizer_active": self.memory_optimizer._is_monitoring,
            "cpu_optimizer_active": self.cpu_optimizer._scheduler._is_running,
        }


def main():
    """Main entry point for running the dashboard standalone."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Context Cleaner Real-Time Performance Dashboard"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5002, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and start dashboard
    dashboard = RealTimePerformanceDashboard()

    try:
        dashboard.start(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Shutting down dashboard...")
        dashboard.stop()


if __name__ == "__main__":
    main()
