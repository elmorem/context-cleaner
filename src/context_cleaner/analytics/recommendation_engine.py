"""
Recommendation Engine for Context Optimization

Advanced AI-powered recommendation system that analyzes productivity patterns,
context health metrics, and user behavior to provide intelligent optimization
suggestions with priority scoring and actionability assessment.
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import statistics

from .context_health_scorer import ContextHealthScorer, HealthScore, HealthScoringModel
from .productivity_analyzer import ProductivityAnalyzer, ProductivityMetrics
from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Types of optimization recommendations."""

    CONTEXT_SIZE_REDUCTION = "context_size_reduction"
    DEAD_CODE_REMOVAL = "dead_code_removal"
    STRUCTURE_IMPROVEMENT = "structure_improvement"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    BREAK_TIMING = "break_timing"
    WORKFLOW_ADJUSTMENT = "workflow_adjustment"
    TOOL_SUGGESTION = "tool_suggestion"
    PATTERN_OPTIMIZATION = "pattern_optimization"


class Priority(Enum):
    """Recommendation priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass
class Recommendation:
    """Individual optimization recommendation."""

    id: str
    type: RecommendationType
    title: str
    description: str
    rationale: str
    priority: Priority
    impact_score: float  # 0-100, expected improvement
    confidence: float  # 0-100, confidence in recommendation
    actionable: bool
    estimated_time_savings: Optional[int] = None  # minutes per day
    implementation_effort: Optional[str] = None  # "low", "medium", "high"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "priority": self.priority.value,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "actionable": self.actionable,
            "estimated_time_savings": self.estimated_time_savings,
            "implementation_effort": self.implementation_effort,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class RecommendationEngine:
    """
    AI-powered recommendation system for context optimization.

    Analyzes productivity patterns, context health, and usage data to generate
    intelligent, actionable optimization recommendations with priority scoring.
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """
        Initialize recommendation engine.

        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ContextCleanerConfig.from_env()
        self.health_scorer = ContextHealthScorer(config)
        self.productivity_analyzer = ProductivityAnalyzer(config)

        # Recommendation generation parameters
        self.min_confidence_threshold = (
            70.0  # Only show high-confidence recommendations
        )
        self.max_recommendations_per_session = 5
        self.pattern_analysis_window_days = 14

        logger.info("RecommendationEngine initialized")

    def generate_recommendations(
        self,
        context_data: Dict[str, Any],
        session_history: List[Dict[str, Any]] = None,
        productivity_metrics: Optional[ProductivityMetrics] = None,
    ) -> List[Recommendation]:
        """
        Generate comprehensive optimization recommendations.

        Args:
            context_data: Current context information
            session_history: Historical session data for pattern analysis
            productivity_metrics: Current productivity metrics

        Returns:
            List of prioritized Recommendation objects
        """
        try:
            recommendations = []
            session_history = session_history or []

            # Get current health score for context analysis
            health_score = self.health_scorer.calculate_health_score(
                context_data, HealthScoringModel.PRODUCTIVITY_FOCUSED
            )

            # Generate different types of recommendations
            recommendations.extend(
                self._context_size_recommendations(context_data, health_score)
            )
            recommendations.extend(
                self._structure_recommendations(context_data, health_score)
            )
            recommendations.extend(
                self._performance_recommendations(context_data, health_score)
            )

            if session_history:
                recommendations.extend(
                    self._pattern_based_recommendations(session_history)
                )
                recommendations.extend(self._timing_recommendations(session_history))

            if productivity_metrics:
                recommendations.extend(
                    self._productivity_recommendations(productivity_metrics)
                )

            # Filter and prioritize recommendations
            recommendations = self._filter_and_prioritize(recommendations)

            logger.info(
                f"Generated {len(recommendations)} optimization recommendations"
            )
            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    def _context_size_recommendations(
        self, context_data: Dict[str, Any], health_score: HealthScore
    ) -> List[Recommendation]:
        """Generate recommendations for context size optimization."""
        recommendations = []

        context_size = context_data.get("size", 0)
        size_component = health_score.component_scores.get("size", 0)

        # Large context size warning
        if context_size > 50000 and size_component < 60:
            recommendations.append(
                Recommendation(
                    id="context_size_large",
                    type=RecommendationType.CONTEXT_SIZE_REDUCTION,
                    title="Reduce Large Context Size",
                    description=f"Your context is {context_size:,} tokens, which may impact performance",
                    rationale=f"Large contexts (>{50000:,} tokens) can slow processing and reduce accuracy",
                    priority=Priority.HIGH,
                    impact_score=80.0,
                    confidence=90.0,
                    actionable=True,
                    estimated_time_savings=15,
                    implementation_effort="medium",
                    tags=["performance", "context_management"],
                    metadata={"current_size": context_size, "recommended_max": 50000},
                )
            )

        # Extremely large context critical warning
        if context_size > 100000:
            recommendations.append(
                Recommendation(
                    id="context_size_critical",
                    type=RecommendationType.CONTEXT_SIZE_REDUCTION,
                    title="Critical: Context Size Exceeds Limits",
                    description=f"Context size of {context_size:,} tokens may cause processing failures",
                    rationale="Contexts over 100k tokens often lead to timeouts and degraded performance",
                    priority=Priority.CRITICAL,
                    impact_score=95.0,
                    confidence=95.0,
                    actionable=True,
                    estimated_time_savings=30,
                    implementation_effort="high",
                    tags=["critical", "performance", "reliability"],
                    metadata={
                        "current_size": context_size,
                        "critical_threshold": 100000,
                    },
                )
            )

        return recommendations

    def _structure_recommendations(
        self, context_data: Dict[str, Any], health_score: HealthScore
    ) -> List[Recommendation]:
        """Generate recommendations for context structure improvements."""
        recommendations = []

        structure_score = health_score.component_scores.get("structure", 0)
        file_count = context_data.get("file_count", 0)

        # Poor structure score
        if structure_score < 50:
            recommendations.append(
                Recommendation(
                    id="structure_improvement",
                    type=RecommendationType.STRUCTURE_IMPROVEMENT,
                    title="Improve Context Organization",
                    description="Context structure could be better organized for clarity",
                    rationale=f"Structure score of {structure_score:.1f}% indicates room for improvement",
                    priority=Priority.MEDIUM,
                    impact_score=65.0,
                    confidence=75.0,
                    actionable=True,
                    estimated_time_savings=10,
                    implementation_effort="low",
                    tags=["organization", "clarity"],
                    metadata={"structure_score": structure_score},
                )
            )

        # Too many scattered files
        if file_count > 20:
            recommendations.append(
                Recommendation(
                    id="file_consolidation",
                    type=RecommendationType.STRUCTURE_IMPROVEMENT,
                    title="Consider File Consolidation",
                    description=f"Context contains {file_count} files, consider grouping related content",
                    rationale="Many files can create cognitive overhead and reduce focus",
                    priority=Priority.LOW,
                    impact_score=45.0,
                    confidence=70.0,
                    actionable=True,
                    estimated_time_savings=5,
                    implementation_effort="medium",
                    tags=["organization", "focus"],
                    metadata={"file_count": file_count, "recommended_max": 20},
                )
            )

        return recommendations

    def _performance_recommendations(
        self, context_data: Dict[str, Any], health_score: HealthScore
    ) -> List[Recommendation]:
        """Generate performance optimization recommendations."""
        recommendations = []

        # Check for potential dead code or unused imports
        complexity = context_data.get("complexity_score", 0)

        if complexity > 80:
            recommendations.append(
                Recommendation(
                    id="complexity_reduction",
                    type=RecommendationType.PERFORMANCE_OPTIMIZATION,
                    title="Reduce Code Complexity",
                    description="High complexity detected, consider refactoring for maintainability",
                    rationale=f"Complexity score of {complexity} may impact development speed",
                    priority=Priority.MEDIUM,
                    impact_score=70.0,
                    confidence=80.0,
                    actionable=True,
                    estimated_time_savings=20,
                    implementation_effort="high",
                    tags=["maintainability", "complexity"],
                    metadata={"complexity_score": complexity},
                )
            )

        # Check freshness for potential dead code
        freshness_score = health_score.component_scores.get("freshness", 0)

        if freshness_score < 40:
            recommendations.append(
                Recommendation(
                    id="dead_code_removal",
                    type=RecommendationType.DEAD_CODE_REMOVAL,
                    title="Review Stale Code",
                    description="Some content appears outdated and may be removable",
                    rationale=f"Freshness score of {freshness_score:.1f}% suggests stale content",
                    priority=Priority.MEDIUM,
                    impact_score=60.0,
                    confidence=65.0,
                    actionable=True,
                    estimated_time_savings=25,
                    implementation_effort="medium",
                    tags=["cleanup", "maintenance"],
                    metadata={"freshness_score": freshness_score},
                )
            )

        return recommendations

    def _pattern_based_recommendations(
        self, session_history: List[Dict[str, Any]]
    ) -> List[Recommendation]:
        """Generate recommendations based on usage patterns."""
        recommendations = []

        if len(session_history) < 5:
            return recommendations  # Need sufficient data for pattern analysis

        try:
            # Analyze session durations for break recommendations
            durations = []
            context_sizes = []

            for session in session_history[-14:]:  # Last 2 weeks
                duration = session.get("duration_minutes", 0)
                size = session.get("context_size", 0)

                if duration > 0:
                    durations.append(duration)
                if size > 0:
                    context_sizes.append(size)

            # Long session pattern detected
            if durations and statistics.mean(durations) > 120:  # 2+ hour sessions
                recommendations.append(
                    Recommendation(
                        id="break_pattern_long_sessions",
                        type=RecommendationType.WORKFLOW_ADJUSTMENT,
                        title="Consider More Frequent Breaks",
                        description=f"Average session duration: {statistics.mean(durations):.1f} minutes",
                        rationale="Long sessions without breaks can reduce productivity and increase errors",
                        priority=Priority.MEDIUM,
                        impact_score=60.0,
                        confidence=80.0,
                        actionable=True,
                        estimated_time_savings=15,
                        implementation_effort="low",
                        tags=["productivity", "wellness", "breaks"],
                        metadata={
                            "average_session_minutes": statistics.mean(durations)
                        },
                    )
                )

            # Growing context size pattern
            if len(context_sizes) >= 7:
                recent_avg = statistics.mean(context_sizes[-3:])
                older_avg = statistics.mean(context_sizes[:3])

                if recent_avg > older_avg * 1.5:  # 50% increase
                    recommendations.append(
                        Recommendation(
                            id="pattern_context_growth",
                            type=RecommendationType.PATTERN_OPTIMIZATION,
                            title="Context Size Trending Upward",
                            description="Context size has been steadily increasing",
                            rationale="Growing contexts may indicate need for better organization",
                            priority=Priority.LOW,
                            impact_score=50.0,
                            confidence=75.0,
                            actionable=True,
                            estimated_time_savings=10,
                            implementation_effort="medium",
                            tags=["trends", "organization"],
                            metadata={
                                "recent_average": recent_avg,
                                "older_average": older_avg,
                                "growth_rate": ((recent_avg - older_avg) / older_avg)
                                * 100,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")

        return recommendations

    def _timing_recommendations(
        self, session_history: List[Dict[str, Any]]
    ) -> List[Recommendation]:
        """Generate timing-based recommendations."""
        recommendations = []

        # Analyze time-of-day productivity patterns
        try:
            hourly_productivity = {}

            for session in session_history[-10:]:  # Recent sessions
                hour = session.get("start_hour", 12)  # Default to noon
                productivity = session.get("productivity_score", 50)

                if hour not in hourly_productivity:
                    hourly_productivity[hour] = []
                hourly_productivity[hour].append(productivity)

            # Find best productivity hours
            if len(hourly_productivity) >= 3:
                hourly_averages = {
                    hour: statistics.mean(scores)
                    for hour, scores in hourly_productivity.items()
                    if len(scores) >= 2
                }

                if hourly_averages:
                    best_hour = max(hourly_averages.items(), key=lambda x: x[1])
                    worst_hour = min(hourly_averages.items(), key=lambda x: x[1])

                    # Significant difference in productivity by time
                    if best_hour[1] - worst_hour[1] > 20:
                        recommendations.append(
                            Recommendation(
                                id="timing_optimization",
                                type=RecommendationType.WORKFLOW_ADJUSTMENT,
                                title="Optimize Work Timing",
                                description=f"You're most productive around {best_hour[0]:02d}:00",
                                rationale=f"Productivity varies by {best_hour[1] - worst_hour[1]:.1f}% throughout the day",
                                priority=Priority.LOW,
                                impact_score=40.0,
                                confidence=70.0,
                                actionable=True,
                                estimated_time_savings=20,
                                implementation_effort="low",
                                tags=["timing", "productivity", "scheduling"],
                                metadata={
                                    "best_hour": best_hour[0],
                                    "best_productivity": best_hour[1],
                                    "worst_hour": worst_hour[0],
                                    "worst_productivity": worst_hour[1],
                                },
                            )
                        )

        except Exception as e:
            logger.error(f"Timing analysis failed: {e}")

        return recommendations

    def _productivity_recommendations(
        self, metrics: ProductivityMetrics
    ) -> List[Recommendation]:
        """Generate recommendations based on current productivity metrics."""
        recommendations = []

        # Low focus time recommendation
        if metrics.focus_time_minutes < 30:
            recommendations.append(
                Recommendation(
                    id="focus_time_low",
                    type=RecommendationType.WORKFLOW_ADJUSTMENT,
                    title="Increase Focus Time",
                    description=f"Only {metrics.focus_time_minutes} minutes of focused work detected",
                    rationale="Short focus periods may indicate distractions or task switching",
                    priority=Priority.MEDIUM,
                    impact_score=75.0,
                    confidence=85.0,
                    actionable=True,
                    estimated_time_savings=30,
                    implementation_effort="low",
                    tags=["focus", "productivity", "distractions"],
                    metadata={"current_focus_minutes": metrics.focus_time_minutes},
                )
            )

        # High interruption rate
        if metrics.interruption_count > 5:
            recommendations.append(
                Recommendation(
                    id="interruptions_high",
                    type=RecommendationType.WORKFLOW_ADJUSTMENT,
                    title="Reduce Interruptions",
                    description=f"{metrics.interruption_count} interruptions detected",
                    rationale="Frequent interruptions can significantly impact productivity",
                    priority=Priority.HIGH,
                    impact_score=80.0,
                    confidence=90.0,
                    actionable=True,
                    estimated_time_savings=25,
                    implementation_effort="medium",
                    tags=["interruptions", "focus", "environment"],
                    metadata={"interruption_count": metrics.interruption_count},
                )
            )

        return recommendations

    def _filter_and_prioritize(
        self, recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """Filter and prioritize recommendations."""
        # Filter by confidence threshold
        high_confidence = [
            r for r in recommendations if r.confidence >= self.min_confidence_threshold
        ]

        # Sort by priority and impact score
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
            Priority.INFORMATIONAL: 4,
        }

        sorted_recommendations = sorted(
            high_confidence,
            key=lambda r: (priority_order[r.priority], -r.impact_score, -r.confidence),
        )

        # Limit to maximum recommendations per session
        return sorted_recommendations[: self.max_recommendations_per_session]

    def get_recommendation_summary(
        self, recommendations: List[Recommendation]
    ) -> Dict[str, Any]:
        """Get summary statistics for recommendations."""
        if not recommendations:
            return {"total": 0, "actionable": 0, "potential_time_savings": 0}

        total_time_savings = sum(
            r.estimated_time_savings or 0
            for r in recommendations
            if r.estimated_time_savings
        )

        priority_counts = {}
        for priority in Priority:
            count = sum(1 for r in recommendations if r.priority == priority)
            if count > 0:
                priority_counts[priority.value] = count

        return {
            "total": len(recommendations),
            "actionable": sum(1 for r in recommendations if r.actionable),
            "potential_time_savings_minutes": total_time_savings,
            "average_confidence": statistics.mean(
                r.confidence for r in recommendations
            ),
            "average_impact": statistics.mean(r.impact_score for r in recommendations),
            "priority_breakdown": priority_counts,
            "recommendation_types": list(set(r.type.value for r in recommendations)),
        }
