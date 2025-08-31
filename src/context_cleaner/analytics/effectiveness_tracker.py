"""
Effectiveness Tracking System for Context Cleaning Operations

This module tracks the effectiveness of context optimization operations,
measuring before/after metrics, user satisfaction, and ROI demonstration.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Use Dict[str, Any] for context data (consistent with existing codebase)
ContextData = Dict[str, Any]

from .. import __version__
from ..analytics.productivity_analyzer import ProductivityAnalyzer


class OptimizationOutcome(Enum):
    """Possible outcomes of optimization operations."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    USER_CANCELLED = "user_cancelled"
    NO_CHANGES_NEEDED = "no_changes_needed"


@dataclass
class EffectivenessMetrics:
    """Metrics measuring optimization effectiveness."""

    # Size and content metrics
    original_size_bytes: int
    optimized_size_bytes: int
    size_reduction_percentage: float

    # Context health metrics
    original_health_score: float
    optimized_health_score: float
    health_improvement: float

    # Focus metrics
    original_focus_score: float
    optimized_focus_score: float
    focus_improvement: float

    # Content analysis
    duplicates_removed: int
    stale_items_removed: int
    items_consolidated: int
    items_reordered: int

    # Performance metrics
    analysis_time_seconds: float
    optimization_time_seconds: float

    # User experience
    user_satisfaction_rating: Optional[int] = None  # 1-5 scale
    user_feedback: Optional[str] = None


@dataclass
class OptimizationSession:
    """Complete optimization session tracking."""

    session_id: str
    timestamp: datetime
    strategy_type: str
    outcome: OptimizationOutcome

    # Context information
    context_source: str
    context_type: str

    # Effectiveness metrics
    metrics: EffectivenessMetrics

    # User interaction
    operations_approved: int
    operations_rejected: int
    operations_modified: int
    total_operations_proposed: int

    # Time tracking
    total_session_time_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["outcome"] = self.outcome.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationSession":
        """Create from dictionary."""
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["outcome"] = OptimizationOutcome(data["outcome"])
        data["metrics"] = EffectivenessMetrics(**data["metrics"])
        return cls(**data)


class EffectivenessTracker:
    """
    Tracks and analyzes the effectiveness of context cleaning operations.

    Provides before/after metrics, user satisfaction tracking, and ROI analysis
    to demonstrate the value of Context Cleaner.
    """

    def __init__(self, data_directory: Optional[Path] = None):
        """Initialize effectiveness tracker."""
        self.data_directory = (
            data_directory or Path.home() / ".context_cleaner" / "effectiveness"
        )
        self.data_directory.mkdir(parents=True, exist_ok=True)

        self.sessions_file = self.data_directory / "optimization_sessions.jsonl"
        self.summary_file = self.data_directory / "effectiveness_summary.json"

        self.productivity_analyzer = ProductivityAnalyzer()

    def start_optimization_tracking(
        self,
        context_data: ContextData,
        strategy_type: str,
        context_source: str = "unknown",
    ) -> str:
        """
        Start tracking an optimization session.

        Returns session ID for continued tracking.
        """
        session_id = f"opt_{int(time.time() * 1000)}"

        # Store initial context metrics for later comparison
        self._store_initial_metrics(
            session_id, context_data, strategy_type, context_source
        )

        return session_id

    def complete_optimization_tracking(
        self,
        session_id: str,
        optimized_context: ContextData,
        outcome: OptimizationOutcome,
        operations_approved: int,
        operations_rejected: int,
        operations_modified: int,
        total_operations: int,
        session_time: float,
        user_rating: Optional[int] = None,
        user_feedback: Optional[str] = None,
    ) -> OptimizationSession:
        """Complete optimization tracking with final metrics."""

        # Load initial metrics
        initial_data = self._load_initial_metrics(session_id)
        if not initial_data:
            raise ValueError(f"No initial tracking data found for session {session_id}")

        # Calculate effectiveness metrics
        metrics = self._calculate_effectiveness_metrics(
            initial_data["context_data"],
            optimized_context,
            initial_data["analysis_time"],
            session_time - initial_data["analysis_time"],  # optimization time
            user_rating,
            user_feedback,
        )

        # Create session record
        session = OptimizationSession(
            session_id=session_id,
            timestamp=datetime.now(),
            strategy_type=initial_data["strategy_type"],
            outcome=outcome,
            context_source=initial_data["context_source"],
            context_type=initial_data["context_type"],
            metrics=metrics,
            operations_approved=operations_approved,
            operations_rejected=operations_rejected,
            operations_modified=operations_modified,
            total_operations_proposed=total_operations,
            total_session_time_seconds=session_time,
        )

        # Store session
        self._store_session(session)

        # Update summary statistics
        self._update_summary_statistics(session)

        # Cleanup initial data
        self._cleanup_initial_metrics(session_id)

        return session

    def get_effectiveness_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get effectiveness summary for the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        sessions = self._load_recent_sessions(cutoff_date)

        if not sessions:
            return {
                "total_sessions": 0,
                "message": "No optimization sessions found in the specified period",
            }

        # Calculate aggregate metrics
        total_size_reduction = sum(
            s.metrics.size_reduction_percentage for s in sessions
        )
        total_health_improvement = sum(s.metrics.health_improvement for s in sessions)
        total_focus_improvement = sum(s.metrics.focus_improvement for s in sessions)

        avg_size_reduction = total_size_reduction / len(sessions)
        avg_health_improvement = total_health_improvement / len(sessions)
        avg_focus_improvement = total_focus_improvement / len(sessions)

        # User satisfaction metrics
        rated_sessions = [
            s for s in sessions if s.metrics.user_satisfaction_rating is not None
        ]
        avg_satisfaction = (
            sum(s.metrics.user_satisfaction_rating for s in rated_sessions)
            / len(rated_sessions)
            if rated_sessions
            else None
        )

        # Strategy effectiveness
        strategy_stats = {}
        for session in sessions:
            strategy = session.strategy_type
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    "count": 0,
                    "total_size_reduction": 0,
                    "total_health_improvement": 0,
                    "success_rate": 0,
                }

            stats = strategy_stats[strategy]
            stats["count"] += 1
            stats["total_size_reduction"] += session.metrics.size_reduction_percentage
            stats["total_health_improvement"] += session.metrics.health_improvement
            stats["success_rate"] += (
                1 if session.outcome == OptimizationOutcome.SUCCESS else 0
            )

        # Calculate strategy averages
        for strategy, stats in strategy_stats.items():
            count = stats["count"]
            stats["avg_size_reduction"] = stats["total_size_reduction"] / count
            stats["avg_health_improvement"] = stats["total_health_improvement"] / count
            stats["success_rate"] = (stats["success_rate"] / count) * 100

        return {
            "period_days": days,
            "total_sessions": len(sessions),
            "successful_sessions": len(
                [s for s in sessions if s.outcome == OptimizationOutcome.SUCCESS]
            ),
            "success_rate_percentage": (
                len([s for s in sessions if s.outcome == OptimizationOutcome.SUCCESS])
                / len(sessions)
            )
            * 100,
            "average_metrics": {
                "size_reduction_percentage": round(avg_size_reduction, 2),
                "health_improvement": round(avg_health_improvement, 2),
                "focus_improvement": round(avg_focus_improvement, 2),
                "user_satisfaction": (
                    round(avg_satisfaction, 2) if avg_satisfaction else None
                ),
            },
            "total_impact": {
                "total_bytes_saved": sum(
                    s.metrics.original_size_bytes - s.metrics.optimized_size_bytes
                    for s in sessions
                ),
                "total_duplicates_removed": sum(
                    s.metrics.duplicates_removed for s in sessions
                ),
                "total_stale_items_removed": sum(
                    s.metrics.stale_items_removed for s in sessions
                ),
                "total_items_consolidated": sum(
                    s.metrics.items_consolidated for s in sessions
                ),
                "total_time_saved_estimate_hours": self._estimate_time_saved(sessions),
            },
            "strategy_effectiveness": strategy_stats,
            "sessions": [
                s.to_dict() for s in sessions[-10:]
            ],  # Last 10 sessions for detail
        }

    def get_session_details(self, session_id: str) -> Optional[OptimizationSession]:
        """Get details for a specific session."""
        sessions = self._load_all_sessions()
        for session in sessions:
            if session.session_id == session_id:
                return session
        return None

    def export_effectiveness_data(self, format: str = "json") -> Dict[str, Any]:
        """Export all effectiveness data."""
        sessions = self._load_all_sessions()
        summary = self.get_effectiveness_summary(365)  # Full year

        export_data = {
            "export_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_sessions": len(sessions),
                "format": format,
                "context_cleaner_version": __version__,
            },
            "effectiveness_summary": summary,
            "all_sessions": [s.to_dict() for s in sessions],
        }

        return export_data

    def _store_initial_metrics(
        self,
        session_id: str,
        context_data: ContextData,
        strategy_type: str,
        context_source: str,
    ) -> None:
        """Store initial context metrics for later comparison."""
        analysis_start = time.time()

        # Analyze initial context health
        initial_health = self._analyze_context_health(context_data)

        analysis_time = time.time() - analysis_start

        initial_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "strategy_type": strategy_type,
            "context_source": context_source,
            "context_type": self._determine_context_type(context_data),
            "context_data": self._serialize_context_data(context_data),
            "initial_health": initial_health,
            "analysis_time": analysis_time,
        }

        initial_file = self.data_directory / f"initial_{session_id}.json"
        with open(initial_file, "w") as f:
            json.dump(initial_data, f, indent=2)

    def _load_initial_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load initial metrics for a session."""
        initial_file = self.data_directory / f"initial_{session_id}.json"
        if initial_file.exists():
            with open(initial_file, "r") as f:
                return json.load(f)
        return None

    def _cleanup_initial_metrics(self, session_id: str) -> None:
        """Clean up initial metrics file after session completion."""
        initial_file = self.data_directory / f"initial_{session_id}.json"
        if initial_file.exists():
            initial_file.unlink()

    def _calculate_effectiveness_metrics(
        self,
        initial_context: Dict[str, Any],
        optimized_context: ContextData,
        analysis_time: float,
        optimization_time: float,
        user_rating: Optional[int],
        user_feedback: Optional[str],
    ) -> EffectivenessMetrics:
        """Calculate comprehensive effectiveness metrics."""

        # Size metrics
        original_size = initial_context.get("total_size", 0)
        optimized_size = len(str(optimized_context))
        size_reduction = (
            ((original_size - optimized_size) / original_size * 100)
            if original_size > 0
            else 0
        )

        # Health metrics
        original_health = initial_context.get("health_score", 50)
        optimized_health = self._analyze_context_health(optimized_context)[
            "health_score"
        ]
        health_improvement = optimized_health - original_health

        # Focus metrics
        original_focus = initial_context.get("focus_score", 50)
        optimized_focus_data = self._analyze_context_health(optimized_context)
        optimized_focus = optimized_focus_data.get("focus_score", 50)
        focus_improvement = optimized_focus - original_focus

        # Content analysis (mock data for now - would integrate with actual manipulation results)
        duplicates_removed = initial_context.get("duplicates_count", 0)
        stale_items = initial_context.get("stale_items_count", 0)

        return EffectivenessMetrics(
            original_size_bytes=original_size,
            optimized_size_bytes=optimized_size,
            size_reduction_percentage=size_reduction,
            original_health_score=original_health,
            optimized_health_score=optimized_health,
            health_improvement=health_improvement,
            original_focus_score=original_focus,
            optimized_focus_score=optimized_focus,
            focus_improvement=focus_improvement,
            duplicates_removed=duplicates_removed,
            stale_items_removed=stale_items,
            items_consolidated=0,  # Would be provided by manipulation engine
            items_reordered=0,  # Would be provided by manipulation engine
            analysis_time_seconds=analysis_time,
            optimization_time_seconds=optimization_time,
            user_satisfaction_rating=user_rating,
            user_feedback=user_feedback,
        )

    def _analyze_context_health(self, context_data: ContextData) -> Dict[str, Any]:
        """Analyze context health using existing analytics."""
        # Basic health analysis - would integrate with comprehensive health dashboard
        content_size = len(str(context_data))

        # Mock health scoring based on size and content characteristics
        health_score = max(10, min(100, 100 - (content_size / 1000)))
        focus_score = max(10, min(100, 90 - (content_size / 2000)))

        return {
            "health_score": health_score,
            "focus_score": focus_score,
            "total_size": content_size,
            "duplicates_count": 0,  # Would be calculated by actual analysis
            "stale_items_count": 0,  # Would be calculated by actual analysis
        }

    def _determine_context_type(self, context_data: ContextData) -> str:
        """Determine the type of context being processed."""
        # Simple heuristic - would be enhanced
        content_str = str(context_data)
        if "class " in content_str and "def " in content_str:
            return "code"
        elif "TODO" in content_str or "FIXME" in content_str:
            return "development_notes"
        elif len(content_str) > 10000:
            return "large_context"
        else:
            return "general"

    def _serialize_context_data(self, context_data: ContextData) -> Dict[str, Any]:
        """Serialize context data for storage."""
        # Safe serialization of context data
        return {
            "content_preview": (
                str(context_data)[:1000] + "..."
                if len(str(context_data)) > 1000
                else str(context_data)
            ),
            "total_size": len(str(context_data)),
            "type": self._determine_context_type(context_data),
        }

    def _store_session(self, session: OptimizationSession) -> None:
        """Store completed session to JSONL file."""
        with open(self.sessions_file, "a") as f:
            f.write(json.dumps(session.to_dict()) + "\n")

    def _load_recent_sessions(self, cutoff_date: datetime) -> List[OptimizationSession]:
        """Load sessions since cutoff date."""
        sessions = []
        if self.sessions_file.exists():
            with open(self.sessions_file, "r") as f:
                for line in f:
                    session_data = json.loads(line.strip())
                    session = OptimizationSession.from_dict(session_data)
                    if session.timestamp >= cutoff_date:
                        sessions.append(session)
        return sorted(sessions, key=lambda s: s.timestamp)

    def _load_all_sessions(self) -> List[OptimizationSession]:
        """Load all sessions."""
        sessions = []
        if self.sessions_file.exists():
            with open(self.sessions_file, "r") as f:
                for line in f:
                    session_data = json.loads(line.strip())
                    sessions.append(OptimizationSession.from_dict(session_data))
        return sorted(sessions, key=lambda s: s.timestamp)

    def _update_summary_statistics(self, session: OptimizationSession) -> None:
        """Update summary statistics file."""
        summary = {}
        if self.summary_file.exists():
            with open(self.summary_file, "r") as f:
                summary = json.load(f)

        # Update summary with new session
        summary["last_updated"] = datetime.now().isoformat()
        summary["total_sessions"] = summary.get("total_sessions", 0) + 1

        # Update strategy counts
        strategies = summary.get("strategy_counts", {})
        strategies[session.strategy_type] = strategies.get(session.strategy_type, 0) + 1
        summary["strategy_counts"] = strategies

        # Update outcome counts
        outcomes = summary.get("outcome_counts", {})
        outcomes[session.outcome.value] = outcomes.get(session.outcome.value, 0) + 1
        summary["outcome_counts"] = outcomes

        with open(self.summary_file, "w") as f:
            json.dump(summary, f, indent=2)

    def _estimate_time_saved(self, sessions: List[OptimizationSession]) -> float:
        """Estimate time saved through context optimization."""
        # Conservative estimate: 5 minutes saved per successful optimization
        successful_sessions = [
            s for s in sessions if s.outcome == OptimizationOutcome.SUCCESS
        ]
        return len(successful_sessions) * (5 / 60)  # Convert to hours
