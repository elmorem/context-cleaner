"""
Dashboard Real-time Updates and WebSocket Management

Phase 2.4 Extraction: WebSocket-first architecture with HTTP fallbacks
Extracted from SocketIO-related methods in comprehensive_health_dashboard.py
Implements sophisticated real-time communication patterns

Contains:
- SocketIO event setup and handlers
- Background task coordination and broadcasting
- WebSocket-first with HTTP polling fallbacks
- Real-time health and performance updates
- Connection management and error handling
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from dataclasses import asdict
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)


class RealtimeEventSerializer:
    """
    Handles serialization of complex objects for WebSocket transmission
    Extracted from SocketIO event handlers
    """

    @staticmethod
    def serialize_datetime(obj):
        """Recursively serialize datetime objects to ISO strings"""
        if isinstance(obj, dict):
            return {k: RealtimeEventSerializer.serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [RealtimeEventSerializer.serialize_datetime(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'value'):  # Handle enums
            return obj.value
        return obj

    @staticmethod
    def serialize_health_report(report) -> Dict[str, Any]:
        """Serialize comprehensive health report for transmission"""
        try:
            report_dict = asdict(report)
            return RealtimeEventSerializer.serialize_datetime(report_dict)
        except Exception as e:
            logger.warning(f"Health report serialization error: {e}")
            return {"status": "error", "message": "Failed to serialize health data"}


class DashboardRealtime:
    """
    Real-time updates and WebSocket management
    WebSocket-first architecture with HTTP polling fallbacks
    Critical: Preserves existing WebSocket event structure exactly
    """

    def __init__(self, socketio: SocketIO = None, dashboard_instance=None):
        self.socketio = socketio
        self.dashboard = dashboard_instance
        self.event_handlers = {}
        self.active_connections = set()

        # Background broadcasting infrastructure
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._performance_history: List[Dict[str, Any]] = []
        self._max_history_points = 100
        self._alerts_enabled = True

        # Initialize serializer
        self.serializer = RealtimeEventSerializer()

    def setup_socketio_events(self) -> None:
        """
        Setup SocketIO event handlers
        CRITICAL: Preserves exact event structure from original implementation
        """
        if not self.socketio:
            logger.warning("SocketIO not available for event setup")
            return

        @self.socketio.on("connect")
        def handle_connect():
            """Handle client connection with initial health data broadcast"""
            logger.info("Dashboard client connected via WebSocket")
            self.active_connections.add(id(self))  # Track connection

            try:
                # Send initial comprehensive health data
                if self.dashboard and hasattr(self.dashboard, 'generate_comprehensive_health_report'):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    report = loop.run_until_complete(
                        self.dashboard.generate_comprehensive_health_report()
                    )
                    loop.close()

                    # Serialize and emit
                    safe_report = self.serializer.serialize_health_report(report)
                    emit("health_update", safe_report)
                else:
                    emit("health_update", {"status": "dashboard_unavailable"})

            except Exception as e:
                logger.error(f"Initial health data broadcast failed: {e}")
                emit("error", {"message": str(e)})

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """Handle client disconnection"""
            logger.info("Dashboard client disconnected from WebSocket")
            self.active_connections.discard(id(self))

        @self.socketio.on("request_health_update")
        def handle_health_update_request():
            """
            Handle on-demand health update requests
            WebSocket-first: Immediate response via WebSocket
            """
            try:
                if self.dashboard and hasattr(self.dashboard, 'generate_comprehensive_health_report'):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    report = loop.run_until_complete(
                        self.dashboard.generate_comprehensive_health_report()
                    )
                    loop.close()

                    safe_report = self.serializer.serialize_health_report(report)
                    emit("health_update", safe_report)
                else:
                    emit("health_update", {"status": "dashboard_unavailable"})

            except Exception as e:
                logger.error(f"Health update request failed: {e}")
                emit("error", {"message": str(e)})

        @self.socketio.on("request_performance_update")
        def handle_performance_update_request():
            """
            Handle performance metrics requests
            WebSocket-first: Immediate metrics via WebSocket
            """
            try:
                metrics = self.get_current_performance_metrics()
                emit("performance_update", metrics)
            except Exception as e:
                logger.error(f"Performance update request failed: {e}")
                emit("error", {"message": str(e)})

        logger.info("✅ SocketIO events configured for WebSocket-first real-time updates")

    def start_background_broadcasting(self) -> None:
        """
        Start background thread for periodic health data broadcasting
        WebSocket-first: Broadcasts to all connected WebSocket clients
        """
        if self._update_thread and self._update_thread.is_alive():
            logger.warning("Background broadcasting already running")
            return

        self._stop_event.clear()
        self._update_thread = threading.Thread(
            target=self._real_time_update_loop,
            name="RealtimeDashboardUpdates",
            daemon=True
        )
        self._update_thread.start()
        logger.info("🚀 Background WebSocket broadcasting started")

    def stop_background_broadcasting(self) -> None:
        """Stop background broadcasting thread"""
        if self._update_thread:
            self._stop_event.set()
            self._update_thread.join(timeout=5.0)
            if self._update_thread.is_alive():
                logger.warning("Background thread did not stop gracefully")
        logger.info("🛑 Background broadcasting stopped")

    def _real_time_update_loop(self):
        """
        Background loop for collecting and broadcasting comprehensive health data
        WebSocket-first: Primary delivery via WebSocket broadcasting
        """
        while not self._stop_event.is_set():
            try:
                if not self.socketio or not self.dashboard:
                    self._stop_event.wait(timeout=10.0)
                    continue

                # Generate comprehensive health report
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                report = loop.run_until_complete(
                    self.dashboard.generate_comprehensive_health_report()
                )
                loop.close()

                # Store in performance history
                health_data = {
                    "timestamp": datetime.now().isoformat(),
                    "overall_health_score": report.overall_health_score,
                    "focus_score": report.focus_metrics.focus_score,
                    "redundancy_score": 1.0 - report.redundancy_analysis.duplicate_content_percentage,
                    "recency_score": report.recency_indicators.fresh_context_percentage,
                    "size_score": 1.0 - report.size_optimization.optimization_potential_percentage,
                }

                self._performance_history.append(health_data)

                # Trim history to max size
                if len(self._performance_history) > self._max_history_points:
                    self._performance_history = self._performance_history[-self._max_history_points:]

                # WebSocket-first: Broadcast to all connected clients
                safe_report = self.serializer.serialize_health_report(report)
                self.socketio.emit("health_update", safe_report)

                logger.debug(f"📡 Health update broadcasted to {len(self.active_connections)} WebSocket clients")

                # Update every 30 seconds
                self._stop_event.wait(timeout=30.0)

            except Exception as e:
                logger.warning(f"Real-time update loop error: {e}")
                self._stop_event.wait(timeout=10.0)

    def get_current_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics combining health and system data
        Used by both WebSocket and HTTP fallback endpoints
        """
        try:
            # Get latest health data from history
            if self._performance_history:
                latest = self._performance_history[-1]
                return {
                    "timestamp": datetime.now().isoformat(),
                    "health": {
                        "overall_score": latest.get("overall_health_score", 0.5),
                        "focus_score": latest.get("focus_score", 0.5),
                        "redundancy_score": latest.get("redundancy_score", 0.5),
                        "recency_score": latest.get("recency_score", 0.5),
                        "size_score": latest.get("size_score", 0.5),
                    },
                    "system": {
                        "alerts_enabled": self._alerts_enabled,
                        "history_points": len(self._performance_history),
                        "websocket_connections": len(self.active_connections),
                        "background_broadcasting": self._update_thread is not None and self._update_thread.is_alive(),
                    },
                }
            else:
                return {
                    "timestamp": datetime.now().isoformat(),
                    "health": {
                        "overall_score": 0.5,
                        "focus_score": 0.5,
                        "redundancy_score": 0.5,
                        "recency_score": 0.5,
                        "size_score": 0.5,
                    },
                    "system": {
                        "alerts_enabled": self._alerts_enabled,
                        "history_points": 0,
                        "websocket_connections": len(self.active_connections),
                        "background_broadcasting": False,
                    },
                }
        except Exception as e:
            logger.error(f"Performance metrics generation failed: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "system": {"websocket_connections": len(self.active_connections)}
            }

    def get_realtime_events_fallback(self) -> List[Dict[str, Any]]:
        """
        HTTP fallback: Generate events for polling clients
        When WebSocket unavailable, clients can poll this endpoint
        """
        events = []

        try:
            # Add performance metrics event
            metrics = self.get_current_performance_metrics()
            events.append({
                "type": "performance_update",
                "timestamp": datetime.now().isoformat(),
                "data": metrics
            })

            # Add dashboard metrics if available
            if self.dashboard and hasattr(self.dashboard, '_get_basic_dashboard_metrics'):
                try:
                    basic_metrics = self.dashboard._get_basic_dashboard_metrics()
                    events.append({
                        "type": "dashboard_metrics",
                        "timestamp": datetime.now().isoformat(),
                        "data": basic_metrics
                    })
                except Exception:
                    pass

            # Add health status event
            events.append({
                "type": "health_status",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "status": "healthy",
                    "websocket_available": self.socketio is not None,
                    "background_broadcasting": self._update_thread is not None and self._update_thread.is_alive(),
                    "connection_count": len(self.active_connections)
                }
            })

            # Add context window usage if available
            if self.dashboard and hasattr(self.dashboard, 'context_analyzer'):
                try:
                    if self.dashboard.context_analyzer:
                        context_usage = {
                            "tokens_used": 15000,  # Mock data
                            "tokens_available": 200000,
                            "usage_percentage": 7.5
                        }
                        events.append({
                            "type": "context_usage",
                            "timestamp": datetime.now().isoformat(),
                            "data": context_usage
                        })
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Realtime events fallback generation failed: {e}")
            events.append({
                "type": "error",
                "timestamp": datetime.now().isoformat(),
                "data": {"message": str(e)}
            })

        return events

    def broadcast_widget_update(self, widget_type: str, data: Dict[str, Any]) -> None:
        """
        Broadcast widget-specific updates
        WebSocket-first: Immediate broadcast to connected clients
        """
        if not self.socketio:
            logger.warning(f"Cannot broadcast {widget_type} update - WebSocket unavailable")
            return

        try:
            update_payload = {
                "widget_type": widget_type,
                "timestamp": datetime.now().isoformat(),
                "data": self.serializer.serialize_datetime(data)
            }

            self.socketio.emit("widget_update", update_payload)
            logger.debug(f"📡 Widget update broadcasted: {widget_type}")

        except Exception as e:
            logger.error(f"Widget broadcast failed for {widget_type}: {e}")

    def emit_custom_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """
        Emit custom events to connected WebSocket clients
        WebSocket-first: Direct real-time communication
        """
        if not self.socketio:
            logger.warning(f"Cannot emit {event_name} - WebSocket unavailable")
            return

        try:
            safe_data = self.serializer.serialize_datetime(data)
            self.socketio.emit(event_name, safe_data)
            logger.debug(f"📡 Custom event emitted: {event_name}")
        except Exception as e:
            logger.error(f"Custom event emission failed for {event_name}: {e}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get real-time connection statistics"""
        return {
            "websocket_available": self.socketio is not None,
            "active_connections": len(self.active_connections),
            "background_broadcasting": self._update_thread is not None and self._update_thread.is_alive(),
            "performance_history_size": len(self._performance_history),
            "alerts_enabled": self._alerts_enabled
        }


class RealtimeCoordinator:
    """
    Coordinates real-time communications across dashboard components
    WebSocket-first with intelligent fallback coordination
    """

    def __init__(self, realtime_manager: DashboardRealtime):
        self.realtime = realtime_manager

    def setup_realtime_infrastructure(self) -> None:
        """Setup complete real-time infrastructure"""
        # Setup WebSocket events (primary)
        self.realtime.setup_socketio_events()

        # Start background broadcasting
        self.realtime.start_background_broadcasting()

        logger.info("🚀 Real-time infrastructure established (WebSocket-first)")

    def shutdown_realtime_infrastructure(self) -> None:
        """Gracefully shutdown real-time infrastructure"""
        self.realtime.stop_background_broadcasting()
        logger.info("🛑 Real-time infrastructure shutdown complete")

    def get_transport_recommendation(self) -> Dict[str, Any]:
        """Recommend optimal transport method for clients"""
        stats = self.realtime.get_connection_stats()

        return {
            "recommended_transport": "websocket" if stats["websocket_available"] else "polling",
            "websocket_available": stats["websocket_available"],
            "fallback_endpoint": "/api/realtime/events",
            "websocket_endpoint": "/socket.io/",
            "polling_interval_ms": 5000 if not stats["websocket_available"] else None,
            "stats": stats
        }


class ModuleStatus:
    """Track module extraction status"""
    EXTRACTION_STATUS = "extracted"
    ORIGINAL_LINES = 400  # WebSocket, threading, and real-time logic
    TARGET_LINES = 400
    REDUCTION_TARGET = "WebSocket-first architecture with HTTP fallbacks"


logger.info(f"dashboard_realtime module extracted - Status: {ModuleStatus.EXTRACTION_STATUS}")