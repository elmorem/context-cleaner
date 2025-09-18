"""
Dashboard Models and Data Sources

Phase 2.2 Extraction: Core data models, enums, dataclasses, and data sources
Extracted from lines 212-769 of comprehensive_health_dashboard.py
Provides clean separation between data models and dashboard logic

Contains:
- Widget configuration models
- Health metric dataclasses
- Data source implementations
- Exception classes
- Enums for dashboard components
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class WidgetType(Enum):
    """Types of dashboard widgets"""

    METRIC_CARD = "metric_card"
    CHART = "chart"
    TABLE = "table"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    PROGRESS = "progress"
    LIST = "list"
    CUSTOM = "custom"


class UpdateFrequency(Enum):
    """Widget update frequencies"""

    REALTIME = "realtime"  # Updates immediately when data changes
    FAST = "fast"  # Every 5 seconds
    NORMAL = "normal"  # Every 30 seconds
    SLOW = "slow"  # Every 5 minutes
    MANUAL = "manual"  # Only when explicitly refreshed


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget"""

    widget_id: str
    widget_type: WidgetType
    title: str
    data_source: str
    position: Dict[str, int]  # x, y, width, height
    update_frequency: UpdateFrequency = UpdateFrequency.NORMAL
    config: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class DataSource:
    """Base class for dashboard data sources"""

    def __init__(self, source_id: str, config: Dict[str, Any]):
        self.source_id = source_id
        self.config = config
        self.cache = {}
        self.last_updated = None

    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get data from the source"""
        raise NotImplementedError

    async def get_schema(self) -> Dict[str, Any]:
        """Get data schema for the source"""
        raise NotImplementedError

    def invalidate_cache(self):
        """Invalidate cached data"""
        self.cache.clear()
        self.last_updated = None


class ProductivityDataSource(DataSource):
    """Data source for productivity metrics"""

    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get productivity data"""
        try:
            from context_cleaner.analytics.productivity_analyzer import ProductivityAnalyzer

            analyzer = ProductivityAnalyzer()

            # Apply date range filter if provided
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            if filters:
                if "start_date" in filters:
                    start_date = datetime.fromisoformat(filters["start_date"])
                if "end_date" in filters:
                    end_date = datetime.fromisoformat(filters["end_date"])

            # Generate mock session data for the date range
            mock_sessions = []
            current_date = start_date
            while current_date <= end_date:
                sessions_per_day = 3 + int(
                    (current_date.weekday() < 5) * 2
                )  # More sessions on weekdays

                for session_num in range(sessions_per_day):
                    session_start = current_date.replace(
                        hour=9 + session_num * 3, minute=0, second=0, microsecond=0
                    )

                    mock_sessions.append(
                        {
                            "timestamp": session_start,
                            "duration_minutes": 45 + (session_num * 15),
                            "active_time_minutes": 35 + (session_num * 12),
                            "context_switches": 5 + session_num,
                            "applications": ["code_editor", "browser", "terminal"][
                                : session_num + 1
                            ],
                        }
                    )

                current_date += timedelta(days=1)

            # Generate analysis from mock sessions (simplified approach)
            total_duration = sum(s["duration_minutes"] for s in mock_sessions)
            total_active = sum(s["active_time_minutes"] for s in mock_sessions)
            avg_productivity_score = min(100, (total_active / total_duration) * 100) if total_duration > 0 else 75

            analysis = {
                "overall_productivity_score": avg_productivity_score,
                "total_focus_time_hours": total_active / 60,
                "daily_productivity_averages": {},
                "productivity_trend": "stable",
                "efficiency_ratio": total_active / total_duration if total_duration > 0 else 0.85,
                "avg_context_switches_per_hour": sum(s["context_switches"] for s in mock_sessions) / len(mock_sessions),
                "peak_productivity_hours": [9, 10, 14, 15],
            }

            return {
                "productivity_score": analysis.get("overall_productivity_score", 75),
                "focus_time_hours": analysis.get("total_focus_time_hours", 6.5),
                "daily_averages": analysis.get("daily_productivity_averages", {}),
                "trend_direction": analysis.get("productivity_trend", "stable"),
                "efficiency_ratio": analysis.get("efficiency_ratio", 0.85),
                "context_switches_avg": analysis.get(
                    "avg_context_switches_per_hour", 12
                ),
                "most_productive_hours": analysis.get(
                    "peak_productivity_hours", [9, 10, 14, 15]
                ),
                "total_sessions": len(mock_sessions),
                "active_days": len(
                    set(session["timestamp"].date() for session in mock_sessions)
                ),
            }
        except ImportError:
            # Fallback if productivity analyzer is not available
            return {
                "productivity_score": 75,
                "focus_time_hours": 6.5,
                "daily_averages": {},
                "trend_direction": "stable",
                "efficiency_ratio": 0.85,
                "context_switches_avg": 12,
                "most_productive_hours": [9, 10, 14, 15],
                "total_sessions": 20,
                "active_days": 15,
            }

    async def get_schema(self) -> Dict[str, Any]:
        """Get schema for productivity data"""
        return {
            "productivity_score": {"type": "number", "min": 0, "max": 100, "unit": "%"},
            "focus_time_hours": {"type": "number", "min": 0, "unit": "hours"},
            "daily_averages": {"type": "object"},
            "trend_direction": {
                "type": "string",
                "enum": ["upward", "downward", "stable"],
            },
            "efficiency_ratio": {"type": "number", "min": 0, "max": 1},
            "context_switches_avg": {"type": "number", "min": 0},
            "most_productive_hours": {"type": "array", "items": {"type": "number"}},
            "total_sessions": {"type": "number", "min": 0},
            "active_days": {"type": "number", "min": 0},
        }


class HealthDataSource(DataSource):
    """Data source for health and wellness metrics"""

    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get health data"""
        base_date = datetime.now() - timedelta(days=30)
        daily_data = []

        for i in range(30):
            date = base_date + timedelta(days=i)
            daily_data.append(
                {
                    "date": date.date().isoformat(),
                    "sleep_hours": 6.5 + random.uniform(-1.5, 1.5),
                    "stress_level": random.randint(1, 10),
                    "energy_level": random.randint(1, 10),
                    "exercise_minutes": random.randint(0, 90),
                    "screen_time_hours": 8 + random.uniform(-2, 4),
                }
            )

        avg_sleep = sum(d["sleep_hours"] for d in daily_data) / len(daily_data)
        avg_stress = sum(d["stress_level"] for d in daily_data) / len(daily_data)
        avg_energy = sum(d["energy_level"] for d in daily_data) / len(daily_data)

        return {
            "average_sleep_hours": round(avg_sleep, 1),
            "average_stress_level": round(avg_stress, 1),
            "average_energy_level": round(avg_energy, 1),
            "total_exercise_minutes": sum(d["exercise_minutes"] for d in daily_data),
            "average_screen_time": round(
                sum(d["screen_time_hours"] for d in daily_data) / len(daily_data), 1
            ),
            "daily_data": daily_data,
            "sleep_quality_trend": (
                "improving" if sum(d["sleep_hours"] for d in daily_data[-7:]) > sum(d["sleep_hours"] for d in daily_data[:7]) else "stable"
            ),
            "wellness_score": min(
                100, max(0, (avg_energy * 10) - (avg_stress * 5) + (avg_sleep * 5))
            ),
        }

    async def get_schema(self) -> Dict[str, Any]:
        """Get schema for health data"""
        return {
            "average_sleep_hours": {
                "type": "number",
                "min": 0,
                "max": 12,
                "unit": "hours",
            },
            "average_stress_level": {
                "type": "number",
                "min": 1,
                "max": 10,
                "unit": "scale",
            },
            "average_energy_level": {
                "type": "number",
                "min": 1,
                "max": 10,
                "unit": "scale",
            },
            "total_exercise_minutes": {"type": "number", "min": 0, "unit": "minutes"},
            "average_screen_time": {"type": "number", "min": 0, "unit": "hours"},
            "daily_data": {"type": "array"},
            "sleep_quality_trend": {
                "type": "string",
                "enum": ["improving", "declining", "stable"],
            },
            "wellness_score": {"type": "number", "min": 0, "max": 100, "unit": "%"},
        }


class TaskDataSource(DataSource):
    """Data source for task and project management data"""

    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get task management data"""
        task_statuses = ["todo", "in_progress", "review", "completed"]
        priorities = ["low", "medium", "high", "urgent"]
        categories = [
            "development",
            "research",
            "documentation",
            "meetings",
            "planning",
        ]

        tasks = []
        task_counts = defaultdict(int)
        priority_counts = defaultdict(int)

        for i in range(50):
            status = random.choice(task_statuses)
            priority = random.choice(priorities)
            category = random.choice(categories)
            created_date = datetime.now() - timedelta(days=random.randint(1, 30))

            task = {
                "id": f"task_{i}",
                "title": f"Task {i}: {category.title()} Work",
                "status": status,
                "priority": priority,
                "category": category,
                "created_date": created_date.isoformat(),
                "estimated_hours": random.randint(1, 16),
                "actual_hours": random.randint(1, 20) if status == "completed" else 0,
                "progress": random.randint(0, 100) if status != "todo" else 0,
            }

            tasks.append(task)
            task_counts[status] += 1
            priority_counts[priority] += 1

        completed_tasks = [t for t in tasks if t["status"] == "completed"]
        completion_rate = len(completed_tasks) / len(tasks) * 100

        recent_completions = [
            t
            for t in completed_tasks
            if datetime.fromisoformat(t["created_date"])
            > datetime.now() - timedelta(days=7)
        ]

        return {
            "total_tasks": len(tasks),
            "task_counts_by_status": dict(task_counts),
            "priority_distribution": dict(priority_counts),
            "completion_rate": round(completion_rate, 1),
            "weekly_velocity": len(recent_completions),
            "average_task_duration": round(
                sum(t["actual_hours"] for t in completed_tasks)
                / max(len(completed_tasks), 1),
                1,
            ),
            "overdue_tasks": random.randint(2, 8),
            "upcoming_deadlines": random.randint(5, 15),
            "tasks_by_category": dict(
                defaultdict(
                    int,
                    {
                        cat: len([t for t in tasks if t["category"] == cat])
                        for cat in categories
                    },
                )
            ),
        }

    async def get_schema(self) -> Dict[str, Any]:
        """Get schema for task data"""
        return {
            "total_tasks": {"type": "number", "min": 0},
            "task_counts_by_status": {"type": "object"},
            "priority_distribution": {"type": "object"},
            "completion_rate": {"type": "number", "min": 0, "max": 100, "unit": "%"},
            "weekly_velocity": {"type": "number", "min": 0, "unit": "tasks/week"},
            "average_task_duration": {"type": "number", "min": 0, "unit": "hours"},
            "overdue_tasks": {"type": "number", "min": 0},
            "upcoming_deadlines": {"type": "number", "min": 0},
            "tasks_by_category": {"type": "object"},
        }


# Custom exceptions for better error handling
class ContextAnalysisError(Exception):
    """Base exception for context analysis errors."""

    pass


class SecurityError(ContextAnalysisError):
    """Raised when security validation fails."""

    pass


class DataValidationError(ContextAnalysisError):
    """Raised when context data validation fails."""

    pass


class HealthColor(Enum):
    """Color codes for health indicators."""

    EXCELLENT = "🟢"  # Green - 80%+
    GOOD = "🟡"  # Yellow - 60-79%
    POOR = "🔴"  # Red - <60%
    CRITICAL = "🔥"  # Fire - <30%


class ContextCategory(Enum):
    """Context content categories for analysis."""

    CURRENT_WORK = "current_work"
    ACTIVE_FILES = "active_files"
    TODOS = "todos"
    CONVERSATIONS = "conversations"
    ERRORS = "errors"
    COMPLETED_ITEMS = "completed_items"
    STALE_CONTENT = "stale_content"


@dataclass
class FocusMetrics:
    """Comprehensive focus metrics as per CLEAN-CONTEXT-GUIDE.md."""

    focus_score: float  # % context relevant to current work
    priority_alignment: float  # % important items in top 25%
    current_work_ratio: float  # % active tasks vs total context
    attention_clarity: float  # % clear next steps vs noise

    # Enhanced metrics with usage data
    usage_weighted_focus: float  # Focus score weighted by actual usage
    workflow_alignment: float  # % context aligned with typical workflows
    task_completion_clarity: float  # % clear completion criteria

    @property
    def overall_focus_health(self) -> HealthColor:
        """Determine overall focus health color."""
        avg_score = (
            self.focus_score
            + self.priority_alignment
            + self.current_work_ratio
            + self.attention_clarity
        ) / 4

        if avg_score >= 0.8:
            return HealthColor.EXCELLENT
        elif avg_score >= 0.6:
            return HealthColor.GOOD
        elif avg_score >= 0.3:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class RedundancyAnalysis:
    """Comprehensive redundancy analysis as per CLEAN-CONTEXT-GUIDE.md."""

    duplicate_content_percentage: float  # % repeated information detected
    stale_context_percentage: float  # % outdated information
    redundant_files_count: int  # Files read multiple times
    obsolete_todos_count: int  # Completed/irrelevant tasks

    # Enhanced analysis with usage patterns
    usage_redundancy_score: float  # Redundancy based on actual access
    content_overlap_analysis: Dict[str, float]  # Overlap between content types
    elimination_opportunity: float  # % context that could be removed safely

    @property
    def overall_redundancy_health(self) -> HealthColor:
        """Determine overall redundancy health color."""
        if self.duplicate_content_percentage < 0.1:
            return HealthColor.EXCELLENT
        elif self.duplicate_content_percentage < 0.25:
            return HealthColor.GOOD
        elif self.duplicate_content_percentage < 0.5:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class RecencyIndicators:
    """Comprehensive recency indicators as per CLEAN-CONTEXT-GUIDE.md."""

    fresh_context_percentage: float  # % modified within last hour
    recent_context_percentage: float  # % modified within last session
    aging_context_percentage: float  # % older than current session
    stale_context_percentage: float  # % from previous unrelated work

    # Enhanced indicators with usage weighting
    usage_weighted_freshness: float  # Freshness weighted by access frequency
    session_relevance_score: float  # % relevant to current session goals
    content_lifecycle_analysis: Dict[str, float]  # Lifecycle stage breakdown

    @property
    def overall_recency_health(self) -> HealthColor:
        """Determine overall recency health color."""
        current_relevance = (
            self.fresh_context_percentage + self.recent_context_percentage
        )

        if current_relevance >= 0.8:
            return HealthColor.EXCELLENT
        elif current_relevance >= 0.6:
            return HealthColor.GOOD
        elif current_relevance >= 0.3:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class SizeOptimizationMetrics:
    """Comprehensive size optimization metrics as per CLEAN-CONTEXT-GUIDE.md."""

    total_context_size_tokens: int  # Total context size in tokens
    optimization_potential_percentage: float  # % reduction possible
    critical_context_percentage: float  # % must preserve
    cleanup_impact_tokens: int  # Tokens that could be saved

    # Enhanced metrics with usage intelligence
    usage_based_optimization_score: float  # Optimization potential based on usage
    content_value_density: float  # Value per token metric
    optimization_risk_assessment: Dict[
        str, str
    ]  # Risk levels for different optimizations

    @property
    def overall_size_health(self) -> HealthColor:
        """Determine overall size health color."""
        if self.optimization_potential_percentage < 0.15:
            return HealthColor.EXCELLENT
        elif self.optimization_potential_percentage < 0.3:
            return HealthColor.GOOD
        elif self.optimization_potential_percentage < 0.5:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class ComprehensiveHealthReport:
    """Complete context health report combining all metrics."""

    # Core metric categories
    focus_metrics: FocusMetrics
    redundancy_analysis: RedundancyAnalysis
    recency_indicators: RecencyIndicators
    size_optimization: SizeOptimizationMetrics

    # Enhanced insights
    usage_insights: List[Dict[str, Any]]
    file_access_heatmap: Dict[str, Dict[str, float]]
    token_efficiency_trends: Dict[str, List[float]]
    optimization_recommendations: List[Dict[str, Any]]

    # Metadata
    analysis_timestamp: datetime
    context_analysis_duration: float
    confidence_score: float

    @property
    def overall_health_score(self) -> float:
        """Calculate overall health score (0-1)."""
        focus_score = (
            self.focus_metrics.focus_score
            + self.focus_metrics.priority_alignment
            + self.focus_metrics.current_work_ratio
            + self.focus_metrics.attention_clarity
        ) / 4

        redundancy_score = 1 - self.redundancy_analysis.duplicate_content_percentage
        recency_score = (
            self.recency_indicators.fresh_context_percentage
            + self.recency_indicators.recent_context_percentage
        ) / 2
        size_score = 1 - self.size_optimization.optimization_potential_percentage

        return (focus_score + redundancy_score + recency_score + size_score) / 4

    @property
    def overall_health_color(self) -> HealthColor:
        """Determine overall health color."""
        score = self.overall_health_score
        if score >= 0.8:
            return HealthColor.EXCELLENT
        elif score >= 0.6:
            return HealthColor.GOOD
        elif score >= 0.3:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


class ModuleStatus:
    """Track module extraction status"""
    EXTRACTION_STATUS = "extracted"
    ORIGINAL_LINES = 557  # Lines 212-769
    TARGET_LINES = 557
    REDUCTION_TARGET = "Consolidate data models, eliminate stub classes"


logger.info(f"dashboard_models module extracted - Status: {ModuleStatus.EXTRACTION_STATUS}")