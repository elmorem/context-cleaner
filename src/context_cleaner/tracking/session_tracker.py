"""
Session Tracker

High-level interface for session tracking that integrates with hook system.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

from ..config.settings import ContextCleanerConfig
from .models import (
    SessionModel,
    ContextEventModel,
    EventType,
    MetricsModel,
    SessionStatus,
)
from .storage import EncryptedStorage

logger = logging.getLogger(__name__)


class SessionTracker:
    """
    High-level session tracking interface.

    Provides a clean API for session lifecycle management,
    context event tracking, and productivity analytics.
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """
        Initialize session tracker.

        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ContextCleanerConfig.from_env()
        self.storage = EncryptedStorage(config)

        self.current_session: Optional[SessionModel] = None

    def start_session(
        self,
        session_id: Optional[str] = None,
        project_path: Optional[str] = None,
        model_name: Optional[str] = None,
        claude_version: Optional[str] = None,
    ) -> SessionModel:
        """
        Start a new tracking session.

        Args:
            session_id: Optional custom session ID
            project_path: Current project directory
            model_name: Claude model being used
            claude_version: Claude version

        Returns:
            Created SessionModel
        """
        try:
            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid.uuid4())

            # Create new session
            session = SessionModel(
                session_id=session_id,
                project_path=project_path,
                model_name=model_name,
                claude_version=claude_version,
                metrics=MetricsModel(),
            )

            # Save to storage
            if self.storage.save_session(session):
                self.current_session = session
                logger.info(f"Started session tracking: {session_id}")
                return session
            else:
                logger.error(f"Failed to save new session: {session_id}")
                raise RuntimeError("Session save failed")

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            raise

    def end_session(
        self,
        session_id: Optional[str] = None,
        status: SessionStatus = SessionStatus.COMPLETED,
    ) -> bool:
        """
        End the current tracking session.

        Args:
            session_id: Session to end (uses current if None)
            status: Final session status

        Returns:
            True if ended successfully, False otherwise
        """
        try:
            # Determine which session to end
            session = None
            if session_id:
                session = self.storage.load_session(session_id)
            elif self.current_session:
                session = self.current_session

            if not session:
                logger.warning("No session to end")
                return False

            # Complete the session
            session.complete_session()
            session.status = status

            # Save final state
            success = self.storage.save_session(session)

            if success:
                logger.info(
                    f"Ended session: {session.session_id} ({session.duration_seconds:.1f}s)"
                )
                if (
                    self.current_session
                    and self.current_session.session_id == session.session_id
                ):
                    self.current_session = None

            return success

        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            return False

    def track_context_event(
        self,
        event_type: EventType,
        context_size: Optional[int] = None,
        optimization_type: Optional[str] = None,
        tool_name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        before_health_score: Optional[int] = None,
        after_health_score: Optional[int] = None,
    ) -> bool:
        """
        Track a context change or optimization event.

        Args:
            event_type: Type of context event
            context_size: Size of context in tokens/characters
            optimization_type: Type of optimization applied
            tool_name: Name of tool used
            duration_ms: Event duration in milliseconds
            metadata: Additional event metadata
            before_health_score: Context health before event
            after_health_score: Context health after event

        Returns:
            True if tracked successfully, False otherwise
        """
        try:
            if not self.current_session:
                logger.debug("No active session - skipping event tracking")
                return False

            # Create event
            event = ContextEventModel(
                event_id=str(uuid.uuid4()),
                session_id=self.current_session.session_id,
                event_type=event_type,
                context_size=context_size,
                optimization_type=optimization_type,
                tool_name=tool_name,
                duration_ms=duration_ms,
                metadata=metadata or {},
                before_health_score=before_health_score,
                after_health_score=after_health_score,
            )

            # Add to current session
            self.current_session.add_context_event(event)

            # Update session metrics
            self._update_session_metrics(event)

            # Save event and updated session
            event_saved = self.storage.save_context_event(event)
            session_saved = self.storage.save_session(self.current_session)

            if event_saved and session_saved:
                logger.debug(f"Tracked {event_type.value} event: {event.event_id}")
                return True
            else:
                logger.warning(
                    f"Failed to save event or session: event={event_saved}, session={session_saved}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to track context event: {e}")
            return False

    def _update_session_metrics(self, event: ContextEventModel):
        """Update session metrics based on the new event."""
        if not self.current_session or not self.current_session.metrics:
            return

        metrics = self.current_session.metrics

        # Update based on event type
        if event.event_type == EventType.OPTIMIZATION_EVENT:
            metrics.optimizations_applied += 1

        elif event.event_type == EventType.TOOL_USE:
            metrics.tools_used += 1

        elif event.event_type == EventType.ERROR_EVENT:
            metrics.errors_encountered += 1

        # Update context health if available
        if event.after_health_score is not None:
            metrics.context_health_score = event.after_health_score

        # Update context size if available
        if event.context_size is not None:
            metrics.context_size_tokens = event.context_size

        # Update hook execution time
        if event.duration_ms is not None:
            metrics.hook_execution_time_ms = max(
                metrics.hook_execution_time_ms, event.duration_ms
            )

        # Calculate efficiency based on optimization/error ratio
        if metrics.optimizations_applied > 0 or metrics.errors_encountered > 0:
            metrics.efficiency_score = metrics.optimizations_applied / max(
                metrics.optimizations_applied + metrics.errors_encountered, 1
            )

        # Update completion rate (placeholder - would need more context)
        metrics.completion_rate = min(
            1.0, metrics.tools_used / 10.0
        )  # Rough approximation

        metrics.recorded_at = datetime.now()

    def get_current_session(self) -> Optional[SessionModel]:
        """Get the current active session."""
        return self.current_session

    def load_session(self, session_id: str) -> Optional[SessionModel]:
        """Load a specific session by ID."""
        return self.storage.load_session(session_id)

    def get_recent_sessions(
        self, limit: int = 10, days: int = 30
    ) -> List[SessionModel]:
        """Get recent sessions for analysis."""
        return self.storage.get_recent_sessions(limit=limit, days=days)

    def get_productivity_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get productivity summary for specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Productivity summary statistics
        """
        try:
            sessions = self.get_recent_sessions(limit=100, days=days)

            if not sessions:
                return {
                    "period_days": days,
                    "session_count": 0,
                    "total_time_hours": 0.0,
                    "average_productivity_score": 0.0,
                    "message": "No sessions found for the specified period",
                }

            # Calculate summary statistics
            total_time = sum(s.duration_seconds for s in sessions)
            productivity_scores = [s.calculate_productivity_score() for s in sessions]
            avg_productivity = sum(productivity_scores) / len(productivity_scores)

            # Count optimizations and tools
            total_optimizations = sum(
                s.metrics.optimizations_applied if s.metrics else 0 for s in sessions
            )
            total_tools = sum(
                s.metrics.tools_used if s.metrics else 0 for s in sessions
            )
            total_errors = sum(
                s.metrics.errors_encountered if s.metrics else 0 for s in sessions
            )

            # Find most productive session
            best_session = max(sessions, key=lambda s: s.calculate_productivity_score())

            return {
                "period_days": days,
                "session_count": len(sessions),
                "total_time_hours": round(total_time / 3600, 1),
                "average_session_duration_minutes": round(
                    total_time / len(sessions) / 60, 1
                ),
                "average_productivity_score": round(avg_productivity, 1),
                "total_optimizations": total_optimizations,
                "total_tools_used": total_tools,
                "total_errors": total_errors,
                "best_session": {
                    "session_id": best_session.session_id,
                    "productivity_score": best_session.calculate_productivity_score(),
                    "duration_minutes": round(best_session.duration_seconds / 60, 1),
                    "start_time": best_session.start_time.isoformat(),
                },
                "recommendations": self._generate_recommendations(sessions),
            }

        except Exception as e:
            logger.error(f"Failed to generate productivity summary: {e}")
            return {"error": str(e)}

    def _generate_recommendations(self, sessions: List[SessionModel]) -> List[str]:
        """Generate productivity recommendations based on session data."""
        recommendations = []

        if not sessions:
            return recommendations

        # Calculate averages for analysis
        avg_duration = sum(s.duration_seconds for s in sessions) / len(sessions)
        avg_productivity = sum(
            s.calculate_productivity_score() for s in sessions
        ) / len(sessions)

        optimization_rate = sum(
            s.metrics.optimizations_applied if s.metrics else 0 for s in sessions
        ) / len(sessions)

        error_rate = sum(
            s.metrics.errors_encountered if s.metrics else 0 for s in sessions
        ) / len(sessions)

        # Generate targeted recommendations
        if avg_productivity < 60:
            recommendations.append(
                "Consider using context optimization more frequently to improve productivity"
            )

        if optimization_rate < 1:
            recommendations.append(
                "Try using 'context-cleaner optimize --dashboard' to monitor context health"
            )

        if error_rate > 2:
            recommendations.append(
                "Focus on error reduction - consider shorter context windows and clearer prompts"
            )

        if avg_duration < 300:  # Less than 5 minutes
            recommendations.append(
                "Longer sessions tend to be more productive - consider batching related tasks"
            )

        if avg_duration > 7200:  # More than 2 hours
            recommendations.append(
                "Consider taking breaks or using context optimization during very long sessions"
            )

        # Always include a positive note
        if avg_productivity > 70:
            recommendations.append(
                "Great work! Your productivity is above average - keep using the optimization tools"
            )

        return recommendations

    def cleanup_old_sessions(self, retention_days: Optional[int] = None) -> int:
        """Clean up old session data based on retention policy."""
        return self.storage.cleanup_old_data(retention_days)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive tracking statistics."""
        storage_stats = self.storage.get_storage_stats()

        return {
            "session_tracker": {
                "current_session_active": self.current_session is not None,
                "current_session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
                "tracking_enabled": True,
                "privacy_compliant": True,
            },
            **storage_stats,
        }
