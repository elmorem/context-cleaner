"""
Real-Time Session Monitor

Provides live monitoring of session activity, context health, and productivity metrics
with WebSocket support for dashboard updates.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import logging

from ..config.settings import ContextCleanerConfig
from ..tracking.session_tracker import SessionTracker
from ..tracking.models import EventType

logger = logging.getLogger(__name__)


class RealTimeMonitor:
    """
    Real-time monitoring system for session tracking and productivity analytics.

    Features:
    - Live session monitoring with configurable update intervals
    - Real-time context health tracking
    - Productivity metric calculations
    - WebSocket event broadcasting for dashboard integration
    - Performance-optimized with minimal resource usage
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """
        Initialize real-time monitor.

        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ContextCleanerConfig.from_env()
        self.session_tracker = SessionTracker(config)
        
        # Persistent monitoring state file
        self.monitor_state_file = Path(self.config.data_directory) / ".monitor_state"
        self.monitor_state_file.parent.mkdir(parents=True, exist_ok=True)

        # Monitoring state
        self.is_monitoring = self._load_monitoring_state()
        self.monitor_task: Optional[asyncio.Task] = None

        # Update intervals (in seconds)
        self.session_update_interval = 30.0  # Update session metrics every 30s
        self.health_update_interval = 10.0  # Update context health every 10s
        self.activity_update_interval = 5.0  # Update activity status every 5s

        # Callbacks for event broadcasting
        self.event_callbacks: List[Callable] = []

        # Performance tracking
        self.last_update_times = {"session": 0.0, "health": 0.0, "activity": 0.0}

        # Cached data for efficient updates
        self.cached_session_data = {}
        self.cached_health_data = {}

    def add_event_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Add callback for real-time event broadcasting.

        Args:
            callback: Function to call with (event_type, event_data)
        """
        self.event_callbacks.append(callback)

    def remove_event_callback(self, callback: Callable):
        """Remove event callback."""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)

    def _broadcast_event(self, event_type: str, event_data: Dict[str, Any]):
        """Broadcast event to all registered callbacks."""
        for callback in self.event_callbacks:
            try:
                callback(event_type, event_data)
            except Exception as e:
                logger.warning(f"Event callback failed: {e}")

    def _load_monitoring_state(self) -> bool:
        """Load persistent monitoring state from file."""
        try:
            if self.monitor_state_file.exists():
                return self.monitor_state_file.read_text().strip() == "running"
            return False
        except Exception as e:
            logger.warning(f"Failed to load monitoring state: {e}")
            return False
    
    def _save_monitoring_state(self, is_running: bool):
        """Save persistent monitoring state to file."""
        try:
            if is_running:
                self.monitor_state_file.write_text("running")
            else:
                if self.monitor_state_file.exists():
                    self.monitor_state_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to save monitoring state: {e}")

    async def start_monitoring(self):
        """Start real-time monitoring."""
        if self.is_monitoring:
            logger.warning("Real-time monitoring already started")
            return

        self.is_monitoring = True
        self._save_monitoring_state(True)
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

        logger.info("Started real-time session monitoring")

        # Broadcast startup event
        self._broadcast_event(
            "monitor_started",
            {
                "timestamp": datetime.now().isoformat(),
                "intervals": {
                    "session_update_s": self.session_update_interval,
                    "health_update_s": self.health_update_interval,
                    "activity_update_s": self.activity_update_interval,
                },
            },
        )

    async def stop_monitoring(self):
        """Stop real-time monitoring."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        self._save_monitoring_state(False)

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
            self.monitor_task = None

        logger.info("Stopped real-time session monitoring")

        # Broadcast shutdown event
        self._broadcast_event(
            "monitor_stopped", {"timestamp": datetime.now().isoformat()}
        )

    async def _monitoring_loop(self):
        """Main monitoring loop with adaptive update intervals."""
        try:
            while self.is_monitoring:
                current_time = time.time()

                # Check what needs updating based on intervals
                tasks = []

                if (
                    current_time - self.last_update_times["activity"]
                    >= self.activity_update_interval
                ):
                    tasks.append(self._update_activity_status())

                if (
                    current_time - self.last_update_times["health"]
                    >= self.health_update_interval
                ):
                    tasks.append(self._update_context_health())

                if (
                    current_time - self.last_update_times["session"]
                    >= self.session_update_interval
                ):
                    tasks.append(self._update_session_metrics())

                # Run updates concurrently
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Sleep for minimum interval to avoid excessive polling
                await asyncio.sleep(
                    min(
                        self.activity_update_interval,
                        self.health_update_interval,
                        self.session_update_interval,
                    )
                )

        except asyncio.CancelledError:
            logger.debug("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}")
            self.is_monitoring = False

    async def _update_activity_status(self):
        """Update current activity and session status."""
        try:
            current_time = time.time()
            current_session = self.session_tracker.get_current_session()

            activity_data = {
                "timestamp": datetime.now().isoformat(),
                "current_session": {
                    "active": current_session is not None,
                    "session_id": (
                        current_session.session_id if current_session else None
                    ),
                    "duration_seconds": (
                        (current_time - current_session.start_time.timestamp())
                        if current_session
                        else 0
                    ),
                    "project_path": (
                        current_session.project_path if current_session else None
                    ),
                },
                "monitor_status": {
                    "is_monitoring": self.is_monitoring,
                    "uptime_seconds": current_time
                    - self.last_update_times.get("monitor_start", current_time),
                },
            }

            # Check for changes before broadcasting
            if activity_data != self.cached_session_data.get("activity"):
                self.cached_session_data["activity"] = activity_data
                self._broadcast_event("activity_update", activity_data)

            self.last_update_times["activity"] = current_time

        except Exception as e:
            logger.error(f"Activity status update failed: {e}")

    async def _update_context_health(self):
        """Update context health metrics."""
        try:
            current_time = time.time()

            # Get context health from dashboard component
            from ..visualization.basic_dashboard import BasicDashboard

            dashboard = BasicDashboard()
            health_data = dashboard.get_json_output()

            # Enhance with real-time data
            enhanced_health = {
                "timestamp": datetime.now().isoformat(),
                "health_score": health_data.get("health_score", 0),
                "health_status": health_data.get("health_status", "unknown"),
                "size_category": health_data.get("size_category", "unknown"),
                "estimated_tokens": health_data.get("estimated_tokens", 0),
                "trend_direction": health_data.get("trend_direction", "stable"),
                "recommendations": health_data.get("recommendations", []),
            }

            # Check for significant changes before broadcasting
            previous_health = self.cached_health_data.get("context_health")
            if (
                not previous_health
                or abs(
                    enhanced_health["health_score"]
                    - previous_health.get("health_score", 0)
                )
                >= 5
                or enhanced_health["health_status"]
                != previous_health.get("health_status")
            ):

                self.cached_health_data["context_health"] = enhanced_health
                self._broadcast_event("context_health_update", enhanced_health)

            self.last_update_times["health"] = current_time

        except Exception as e:
            logger.error(f"Context health update failed: {e}")

    async def _update_session_metrics(self):
        """Update session productivity metrics and analytics."""
        try:
            current_time = time.time()

            # Get recent productivity data
            summary = self.session_tracker.get_productivity_summary(
                days=1
            )  # Last 24 hours

            # Get current session metrics
            current_session = self.session_tracker.get_current_session()
            current_metrics = {}

            if current_session:
                current_metrics = {
                    "session_id": current_session.session_id,
                    "duration_seconds": current_session.duration_seconds,
                    "productivity_score": current_session.calculate_productivity_score(),
                    "events_count": len(current_session.context_events),
                    "last_event_time": (
                        max(
                            e.timestamp for e in current_session.context_events
                        ).isoformat()
                        if current_session.context_events
                        else None
                    ),
                }

                # Add metrics if available
                if current_session.metrics:
                    current_metrics.update(
                        {
                            "optimizations_applied": current_session.metrics.optimizations_applied,
                            "tools_used": current_session.metrics.tools_used,
                            "errors_encountered": current_session.metrics.errors_encountered,
                            "context_health_score": current_session.metrics.context_health_score,
                            "efficiency_score": current_session.metrics.efficiency_score,
                        }
                    )

            session_data = {
                "timestamp": datetime.now().isoformat(),
                "current_session": current_metrics,
                "daily_summary": summary,
                "performance_stats": self.session_tracker.get_stats(),
            }

            # Always broadcast session updates (they contain important metrics)
            self.cached_session_data["session_metrics"] = session_data
            self._broadcast_event("session_metrics_update", session_data)

            self.last_update_times["session"] = current_time

        except Exception as e:
            logger.error(f"Session metrics update failed: {e}")

    def get_monitor_status(self) -> Dict[str, Any]:
        """Get current monitoring status and configuration."""
        current_time = time.time()

        return {
            "monitoring": {
                "is_active": self.is_monitoring,
                "uptime_seconds": current_time
                - self.last_update_times.get("monitor_start", current_time),
                "last_updates": {
                    k: datetime.fromtimestamp(v).isoformat() if v > 0 else None
                    for k, v in self.last_update_times.items()
                },
            },
            "configuration": {
                "session_update_interval_s": self.session_update_interval,
                "health_update_interval_s": self.health_update_interval,
                "activity_update_interval_s": self.activity_update_interval,
                "event_callbacks_count": len(self.event_callbacks),
            },
            "cache_status": {
                "session_data_cached": "session_metrics" in self.cached_session_data,
                "health_data_cached": "context_health" in self.cached_health_data,
                "activity_data_cached": "activity" in self.cached_session_data,
            },
        }

    async def trigger_context_event(
        self, event_type: EventType, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Manually trigger a context event for immediate tracking.

        Args:
            event_type: Type of context event
            metadata: Additional event metadata
        """
        try:
            # Track the event
            success = self.session_tracker.track_context_event(
                event_type=event_type,
                metadata=metadata or {},
                duration_ms=0.0,  # Manual trigger - no duration
            )

            if success:
                # Immediately update metrics to reflect the change
                await self._update_session_metrics()
                await self._update_context_health()

                logger.info(f"Triggered context event: {event_type.value}")

                # Broadcast immediate event
                self._broadcast_event(
                    "context_event_triggered",
                    {
                        "event_type": event_type.value,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": metadata or {},
                        "success": True,
                    },
                )
            else:
                logger.warning(f"Failed to trigger context event: {event_type.value}")

        except Exception as e:
            logger.error(f"Context event trigger failed: {e}")

    def get_live_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive live dashboard data."""
        return {
            "monitor_status": self.get_monitor_status(),
            "live_data": {
                "session_metrics": self.cached_session_data.get("session_metrics", {}),
                "context_health": self.cached_health_data.get("context_health", {}),
                "activity_status": self.cached_session_data.get("activity", {}),
            },
            "last_updated": datetime.now().isoformat(),
        }
