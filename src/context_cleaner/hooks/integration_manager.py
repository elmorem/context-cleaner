"""
Hook Integration Manager

Manages integration between Context Cleaner and Claude Code hooks,
providing automatic session tracking and productivity monitoring.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from ..config.settings import ContextCleanerConfig
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class HookIntegrationManager:
    """
    Manages hook integration with circuit breaker protection.

    Key Features:
    - <50ms execution time guarantee via circuit breaker
    - Automatic session start/end tracking
    - Context health monitoring during development
    - Privacy-first local-only data collection
    - Graceful failure handling - never blocks Claude Code
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """
        Initialize hook integration manager.

        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ContextCleanerConfig.from_env()

        # Create circuit breaker for hook protection
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=0.050,  # 50ms max - critical for Claude Code performance
            recovery_timeout=30.0,
            name="hook_integration",
        )

        # Session tracking state
        self.current_session = None
        self.session_start_time = None

        # Performance monitoring
        self.hook_call_count = 0
        self.total_hook_time = 0.0

    @property
    def data_directory(self) -> Path:
        """Get data directory for session storage."""
        data_path = Path(self.config.data_directory)
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    @property
    def sessions_directory(self) -> Path:
        """Get sessions storage directory."""
        sessions_path = self.data_directory / "sessions"
        sessions_path.mkdir(parents=True, exist_ok=True)
        return sessions_path

    def handle_session_start(self, hook_data: Dict[str, Any]) -> bool:
        """
        Handle session start hook with circuit breaker protection.

        Args:
            hook_data: Hook event data from Claude Code

        Returns:
            True if handled successfully, False if failed/skipped
        """
        return (
            self.circuit_breaker.call(self._handle_session_start_impl, hook_data)
            is not None
        )

    def handle_session_end(self, hook_data: Dict[str, Any]) -> bool:
        """
        Handle session end hook with circuit breaker protection.

        Args:
            hook_data: Hook event data from Claude Code

        Returns:
            True if handled successfully, False if failed/skipped
        """
        return (
            self.circuit_breaker.call(self._handle_session_end_impl, hook_data)
            is not None
        )

    def handle_context_change(self, hook_data: Dict[str, Any]) -> bool:
        """
        Handle context change hook with circuit breaker protection.

        Args:
            hook_data: Hook event data from Claude Code

        Returns:
            True if handled successfully, False if failed/skipped
        """
        return (
            self.circuit_breaker.call(self._handle_context_change_impl, hook_data)
            is not None
        )

    def _handle_session_start_impl(self, hook_data: Dict[str, Any]) -> bool:
        """Internal session start handler implementation."""
        try:
            session_id = hook_data.get("session_id") or self._generate_session_id()

            self.current_session = {
                "session_id": session_id,
                "start_time": datetime.now().isoformat(),
                "start_timestamp": time.time(),
                "hook_data": self._sanitize_hook_data(hook_data),
                "context_events": [],
                "performance_metrics": {"hook_calls": 0, "total_hook_time_ms": 0},
            }

            self.session_start_time = time.time()

            logger.info(f"Started session tracking: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Session start failed: {e}")
            raise

    def _handle_session_end_impl(self, hook_data: Dict[str, Any]) -> bool:
        """Internal session end handler implementation."""
        try:
            if not self.current_session:
                logger.warning("Session end called but no active session")
                return False

            # Calculate session duration
            end_time = time.time()
            duration = (
                end_time - self.session_start_time if self.session_start_time else 0
            )

            # Finalize session data
            self.current_session.update(
                {
                    "end_time": datetime.now().isoformat(),
                    "end_timestamp": end_time,
                    "duration_seconds": duration,
                    "final_hook_data": self._sanitize_hook_data(hook_data),
                }
            )

            # Update performance metrics
            self.current_session["performance_metrics"].update(
                {
                    "hook_calls": self.hook_call_count,
                    "total_hook_time_ms": self.total_hook_time * 1000,
                    "average_hook_time_ms": (
                        self.total_hook_time / max(self.hook_call_count, 1)
                    )
                    * 1000,
                }
            )

            # Save session to disk
            self._save_session()

            session_id = self.current_session["session_id"]
            logger.info(f"Completed session tracking: {session_id} ({duration:.1f}s)")

            # Reset session state
            self.current_session = None
            self.session_start_time = None
            self.hook_call_count = 0
            self.total_hook_time = 0.0

            return True

        except Exception as e:
            logger.error(f"Session end failed: {e}")
            raise

    def _handle_context_change_impl(self, hook_data: Dict[str, Any]) -> bool:
        """Internal context change handler implementation."""
        try:
            if not self.current_session:
                # No active session - create a lightweight tracking entry
                logger.debug("Context change without active session - skipping")
                return True

            # Record context change event
            context_event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": "context_change",
                "context_size": len(str(hook_data)),  # Rough size estimate
                "sanitized_data": self._sanitize_hook_data(hook_data),
            }

            self.current_session["context_events"].append(context_event)

            # Limit context events to prevent excessive memory usage
            max_events = 100
            if len(self.current_session["context_events"]) > max_events:
                self.current_session["context_events"] = self.current_session[
                    "context_events"
                ][-max_events:]
                logger.debug(f"Trimmed context events to {max_events} most recent")

            return True

        except Exception as e:
            logger.error(f"Context change handling failed: {e}")
            raise

    def _sanitize_hook_data(self, hook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize hook data for privacy and storage efficiency.

        Removes sensitive information and limits data size.
        """
        try:
            # Define safe fields to extract
            safe_fields = {
                "session_id",
                "timestamp",
                "event_type",
                "model",
                "version",
                "workspace",
                "cost",
                "exceeds_200k_tokens",
            }

            sanitized = {}
            for field in safe_fields:
                if field in hook_data:
                    value = hook_data[field]

                    # Additional sanitization for specific fields
                    if field == "workspace" and isinstance(value, dict):
                        # Only keep directory info, not full paths
                        sanitized[field] = {
                            "has_current_dir": bool(value.get("current_dir")),
                            "has_project_dir": bool(value.get("project_dir")),
                        }
                    elif field == "cost" and isinstance(value, dict):
                        # Keep cost metrics but round for privacy
                        sanitized[field] = {
                            k: round(v, 4) if isinstance(v, (int, float)) else v
                            for k, v in value.items()
                        }
                    else:
                        sanitized[field] = value

            # Add metadata
            sanitized["_sanitized"] = True
            sanitized["_sanitized_at"] = datetime.now().isoformat()

            return sanitized

        except Exception as e:
            logger.warning(f"Data sanitization failed: {e}")
            return {
                "_sanitization_error": str(e),
                "_timestamp": datetime.now().isoformat(),
            }

    def _generate_session_id(self) -> str:
        """Generate a unique session identifier."""
        import uuid

        return str(uuid.uuid4())

    def _save_session(self):
        """Save current session data to disk."""
        if not self.current_session:
            return

        try:
            session_id = self.current_session["session_id"]
            session_file = self.sessions_directory / f"{session_id}.json"

            with open(session_file, "w") as f:
                json.dump(self.current_session, f, indent=2, default=str)

            logger.debug(f"Session saved: {session_file}")

        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent session data for analytics.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of recent session dictionaries
        """
        try:
            session_files = list(self.sessions_directory.glob("*.json"))
            session_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            sessions = []
            for session_file in session_files[:limit]:
                try:
                    with open(session_file, "r") as f:
                        session_data = json.load(f)
                        sessions.append(session_data)
                except Exception as e:
                    logger.warning(f"Failed to load session {session_file}: {e}")

            return sessions

        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get hook integration performance statistics."""
        circuit_state = self.circuit_breaker.get_state()

        return {
            "hook_integration": {
                "circuit_breaker": circuit_state,
                "current_session_active": self.current_session is not None,
                "sessions_directory": str(self.sessions_directory),
                "hook_call_count": self.hook_call_count,
                "total_hook_time_ms": self.total_hook_time * 1000,
                "average_hook_time_ms": (
                    self.total_hook_time / max(self.hook_call_count, 1)
                )
                * 1000,
            },
            "performance_guarantees": {
                "max_execution_time_ms": self.circuit_breaker.timeout * 1000,
                "failure_threshold": self.circuit_breaker.failure_threshold,
                "meets_performance_target": self.circuit_breaker.timeout <= 0.050,
            },
        }

    def cleanup_old_sessions(self, days_to_keep: int = None):
        """
        Clean up old session files based on retention policy.

        Args:
            days_to_keep: Number of days to retain (uses config default if None)
        """
        try:
            retention_days = days_to_keep or self.config.tracking.data_retention_days
            cutoff_time = time.time() - (retention_days * 24 * 60 * 60)

            session_files = list(self.sessions_directory.glob("*.json"))
            deleted_count = 0

            for session_file in session_files:
                if session_file.stat().st_mtime < cutoff_time:
                    session_file.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(
                    f"Cleaned up {deleted_count} old session files (>{retention_days} days)"
                )

        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")


# Global instance for hook scripts to use
_global_hook_manager = None


def get_hook_manager() -> HookIntegrationManager:
    """Get the global hook integration manager instance."""
    global _global_hook_manager
    if _global_hook_manager is None:
        _global_hook_manager = HookIntegrationManager()
    return _global_hook_manager
