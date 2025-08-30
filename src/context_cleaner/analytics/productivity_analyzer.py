"""
Productivity Analysis Engine for Context Cleaner.

Adapted from the Context Visualizer basic analyzer with enhanced features
for comprehensive productivity tracking and analysis.
"""

import json
import time
import logging
import statistics
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


@dataclass
class ContextAnalysisResult:
    """Structured result from context analysis."""

    health_score: int
    size_category: str
    estimated_tokens: int
    total_chars: int
    top_level_keys: int
    complexity_score: float
    analysis_timestamp: str
    analysis_duration: float
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "health_score": self.health_score,
            "size_category": self.size_category,
            "estimated_tokens": self.estimated_tokens,
            "total_chars": self.total_chars,
            "top_level_keys": self.top_level_keys,
            "complexity_score": self.complexity_score,
            "analysis_timestamp": self.analysis_timestamp,
            "analysis_duration": self.analysis_duration,
            "session_id": self.session_id,
        }


@dataclass
class ProductivityMetrics:
    """Productivity metrics for a development session."""

    session_duration_minutes: float
    context_health_trend: List[int]
    optimization_events: int
    avg_health_score: float
    productivity_score: float
    session_type: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_duration_minutes": self.session_duration_minutes,
            "context_health_trend": self.context_health_trend,
            "optimization_events": self.optimization_events,
            "avg_health_score": self.avg_health_score,
            "productivity_score": self.productivity_score,
            "session_type": self.session_type,
            "timestamp": self.timestamp,
        }


class CircuitBreaker:
    """Circuit breaker for protecting analysis operations."""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def can_proceed(self) -> bool:
        """Check if operation can proceed."""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time > self.timeout_seconds
            ):
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True

    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class ProductivityAnalyzer:
    """
    Advanced productivity analyzer with comprehensive context health assessment
    and productivity tracking capabilities.
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        self.config = config or ContextCleanerConfig.default()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.analysis.circuit_breaker_threshold
        )
        self._analysis_cache = {}
        self._cache_timeout = 300  # 5 minutes

    async def analyze_context_health(
        self, context_data: Dict[str, Any]
    ) -> Optional[ContextAnalysisResult]:
        """
        Analyze context health with comprehensive metrics.

        Args:
            context_data: Context data to analyze

        Returns:
            ContextAnalysisResult with health metrics, or None if analysis fails
        """
        if not self.circuit_breaker.can_proceed():
            logger.warning("Circuit breaker open, skipping analysis")
            return None

        start_time = time.time()

        try:
            # Basic validation
            if not isinstance(context_data, dict):
                context_data = {"data": str(context_data)}

            # Calculate metrics
            health_score = await self._calculate_health_score(context_data)
            size_metrics = self._calculate_size_metrics(context_data)
            complexity_score = self._calculate_complexity_score(context_data)

            analysis_duration = time.time() - start_time

            result = ContextAnalysisResult(
                health_score=health_score,
                size_category=size_metrics["category"],
                estimated_tokens=size_metrics["estimated_tokens"],
                total_chars=size_metrics["total_chars"],
                top_level_keys=size_metrics["top_level_keys"],
                complexity_score=complexity_score,
                analysis_timestamp=datetime.now().isoformat(),
                analysis_duration=analysis_duration,
                session_id=context_data.get("session_id"),
            )

            self.circuit_breaker.record_success()
            return result

        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            self.circuit_breaker.record_failure()
            return None

    async def _calculate_health_score(self, data: Dict[str, Any]) -> int:
        """Calculate comprehensive context health score."""
        try:
            # Size penalty
            data_str = json.dumps(data, default=str)
            size = len(data_str)

            if size < 10000:
                size_score = 100
            elif size < 50000:
                size_score = 85
            elif size < 100000:
                size_score = 70
            else:
                size_score = max(30, 100 - (size - 100000) // 10000 * 5)

            # Structure quality
            structure_score = self._assess_structure_quality(data)

            # Content freshness (if timestamp available)
            freshness_score = self._assess_content_freshness(data)

            # Weighted average
            health_score = int(
                size_score * 0.4 + structure_score * 0.4 + freshness_score * 0.2
            )

            return max(0, min(100, health_score))

        except Exception:
            return 50  # Default fallback score

    def _calculate_size_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate size-related metrics."""
        try:
            data_str = json.dumps(data, default=str)
            total_chars = len(data_str)
            estimated_tokens = int(
                total_chars * self.config.analysis.token_estimation_factor
            )
            top_level_keys = len(data) if isinstance(data, dict) else 1

            # Categorize size
            if total_chars < 20000:
                category = "small"
            elif total_chars < 50000:
                category = "medium"
            elif total_chars < 100000:
                category = "large"
            else:
                category = "very_large"

            return {
                "total_chars": total_chars,
                "estimated_tokens": estimated_tokens,
                "top_level_keys": top_level_keys,
                "category": category,
            }
        except Exception:
            return {
                "total_chars": 0,
                "estimated_tokens": 0,
                "top_level_keys": 0,
                "category": "unknown",
            }

    def _calculate_complexity_score(self, data: Dict[str, Any]) -> float:
        """Calculate context complexity score."""
        try:

            def _calculate_depth(obj, current_depth=0):
                if current_depth > 10:  # Prevent excessive recursion
                    return current_depth

                if isinstance(obj, dict):
                    if not obj:
                        return current_depth
                    return max(
                        _calculate_depth(v, current_depth + 1) for v in obj.values()
                    )
                elif isinstance(obj, (list, tuple)):
                    if not obj:
                        return current_depth
                    return max(
                        _calculate_depth(item, current_depth + 1) for item in obj
                    )
                else:
                    return current_depth

            depth = _calculate_depth(data)

            # Normalize depth to 0-1 scale
            complexity_score = min(1.0, depth / 10.0)

            return complexity_score

        except Exception:
            return 0.5  # Default complexity

    def _assess_structure_quality(self, data: Dict[str, Any]) -> int:
        """Assess the structural quality of context data."""
        try:
            score = 100

            # Penalize excessive nesting
            if isinstance(data, dict):
                # Check for reasonable key distribution
                if len(data) > 50:
                    score -= 10

                # Check for empty values
                empty_values = sum(1 for v in data.values() if not v)
                if empty_values > len(data) * 0.3:
                    score -= 15

            # Check for very long strings (possible unstructured content)
            data_str = json.dumps(data, default=str)
            if any(len(chunk) > 10000 for chunk in data_str.split("\n")):
                score -= 20

            return max(50, score)

        except Exception:
            return 75  # Default decent score

    def _assess_content_freshness(self, data: Dict[str, Any]) -> int:
        """Assess content freshness based on timestamps."""
        try:
            # Look for timestamp indicators
            timestamp_keys = ["timestamp", "created_at", "updated_at", "last_modified"]

            for key in timestamp_keys:
                if key in data:
                    try:
                        # Try to parse timestamp
                        if isinstance(data[key], str):
                            timestamp = datetime.fromisoformat(
                                data[key].replace("Z", "+00:00").replace("+00:00", "")
                            )
                            age_hours = (
                                datetime.now() - timestamp
                            ).total_seconds() / 3600

                            if age_hours < 1:
                                return 100
                            elif age_hours < 6:
                                return 90
                            elif age_hours < 24:
                                return 80
                            elif age_hours < 168:  # 1 week
                                return 70
                            else:
                                return 60
                    except Exception:
                        continue

            return 80  # Default - assume reasonably fresh

        except Exception:
            return 80

    def analyze_productivity_session(
        self, session_data: List[ContextAnalysisResult]
    ) -> ProductivityMetrics:
        """
        Analyze productivity metrics for a development session.

        Args:
            session_data: List of context analysis results from a session

        Returns:
            ProductivityMetrics with session analysis
        """
        if not session_data:
            return ProductivityMetrics(
                session_duration_minutes=0,
                context_health_trend=[],
                optimization_events=0,
                avg_health_score=0,
                productivity_score=0,
                session_type="unknown",
                timestamp=datetime.now().isoformat(),
            )

        # Calculate basic metrics
        health_scores = [result.health_score for result in session_data]
        avg_health = statistics.mean(health_scores) if health_scores else 0

        # Detect optimization events (health improvements)
        optimization_events = 0
        for i in range(1, len(health_scores)):
            if health_scores[i] > health_scores[i - 1] + 10:  # Significant improvement
                optimization_events += 1

        # Calculate session duration (approximate)
        if len(session_data) > 1:
            try:
                start_time = datetime.fromisoformat(session_data[0].analysis_timestamp)
                end_time = datetime.fromisoformat(session_data[-1].analysis_timestamp)
                duration_minutes = (end_time - start_time).total_seconds() / 60
            except Exception:
                duration_minutes = (
                    len(session_data) * 10
                )  # Estimate 10 min per analysis
        else:
            duration_minutes = 10

        # Determine session type based on patterns
        session_type = self._classify_session_type(
            health_scores, optimization_events, duration_minutes
        )

        # Calculate overall productivity score
        productivity_score = self._calculate_productivity_score(
            avg_health, optimization_events, duration_minutes, len(session_data)
        )

        return ProductivityMetrics(
            session_duration_minutes=duration_minutes,
            context_health_trend=health_scores,
            optimization_events=optimization_events,
            avg_health_score=avg_health,
            productivity_score=productivity_score,
            session_type=session_type,
            timestamp=datetime.now().isoformat(),
        )

    def _classify_session_type(
        self,
        health_scores: List[int],
        optimization_events: int,
        duration_minutes: float,
    ) -> str:
        """Classify the type of development session."""
        if not health_scores:
            return "unknown"

        avg_health = statistics.mean(health_scores)
        health_variance = (
            statistics.variance(health_scores) if len(health_scores) > 1 else 0
        )

        # Long session with high variance = debugging/problem-solving
        if duration_minutes > 120 and health_variance > 400:
            return "debugging_session"

        # High optimization events = cleanup/refactoring
        if optimization_events > 3:
            return "optimization_session"

        # Consistently high health = productive coding
        if avg_health > 85 and health_variance < 100:
            return "productive_coding"

        # Low health, short session = exploration/learning
        if avg_health < 60 and duration_minutes < 60:
            return "exploration"

        # Declining health = context bloat
        if len(health_scores) > 2 and health_scores[-1] < health_scores[0] - 20:
            return "context_bloated"

        # Fresh start pattern
        if len(health_scores) > 1 and health_scores[0] > 95:
            return "fresh_start"

        return "standard_session"

    def _calculate_productivity_score(
        self,
        avg_health: float,
        optimization_events: int,
        duration_minutes: float,
        analysis_count: int,
    ) -> float:
        """Calculate overall productivity score for a session."""
        try:
            # Base score from health
            base_score = min(100, avg_health)

            # Bonus for optimization activity
            optimization_bonus = min(20, optimization_events * 5)

            # Efficiency bonus (more analysis = more active development)
            if duration_minutes > 0:
                analysis_per_hour = (analysis_count / duration_minutes) * 60
                efficiency_bonus = min(15, analysis_per_hour * 2)
            else:
                efficiency_bonus = 0

            # Duration penalty for extremely long sessions (fatigue factor)
            if duration_minutes > 300:  # > 5 hours
                duration_penalty = (duration_minutes - 300) / 60 * 2
            else:
                duration_penalty = 0

            productivity_score = (
                base_score + optimization_bonus + efficiency_bonus - duration_penalty
            )

            return max(0, min(100, productivity_score))

        except Exception:
            return 50.0  # Default score if calculation fails

    def predict_optimal_break_time(self, recent_scores: List[int]) -> Optional[int]:
        """
        Use simple ML to predict optimal break timing based on context health trends.

        Args:
            recent_scores: Recent health scores (most recent first)

        Returns:
            Predicted minutes until optimal break time, or None if not applicable
        """
        if len(recent_scores) < 3:
            return None

        try:
            # Simple trend analysis - detect declining pattern
            recent_trend = []
            for i in range(1, min(len(recent_scores), 6)):
                trend = recent_scores[i - 1] - recent_scores[i]  # Positive = declining
                recent_trend.append(trend)

            avg_decline = statistics.mean(recent_trend)

            # If steadily declining, predict break timing
            if avg_decline > 5:  # Declining by 5+ points per measurement
                current_score = recent_scores[0]
                # Predict when score will hit 60 (break threshold)
                if current_score > 60:
                    minutes_to_break = int((current_score - 60) / avg_decline * 10)
                    return max(10, min(120, minutes_to_break))  # 10-120 minute range

            return None

        except Exception:
            return None

    def detect_productivity_patterns(
        self, session_history: List[ProductivityMetrics]
    ) -> Dict[str, Any]:
        """
        Detect patterns in productivity data using basic ML techniques.

        Args:
            session_history: List of productivity metrics from past sessions

        Returns:
            Dictionary with detected patterns and insights
        """
        if len(session_history) < 5:
            return {
                "status": "insufficient_data",
                "message": "Need at least 5 sessions for pattern analysis",
            }

        try:
            # Extract features
            durations = [s.session_duration_minutes for s in session_history]
            productivity_scores = [s.productivity_score for s in session_history]
            optimization_events = [s.optimization_events for s in session_history]

            # Calculate statistics
            patterns = {
                "optimal_session_length": {
                    "mean_duration": statistics.mean(durations),
                    "median_duration": statistics.median(durations),
                    "most_productive_duration_range": self._find_optimal_duration_range(
                        durations, productivity_scores
                    ),
                },
                "productivity_trends": {
                    "average_score": statistics.mean(productivity_scores),
                    "score_variance": (
                        statistics.variance(productivity_scores)
                        if len(productivity_scores) > 1
                        else 0
                    ),
                    "trend_direction": self._calculate_trend_direction(
                        productivity_scores
                    ),
                },
                "optimization_behavior": {
                    "average_optimizations": statistics.mean(optimization_events),
                    "optimization_correlation": self._calculate_correlation(
                        optimization_events, productivity_scores
                    ),
                },
                "session_type_distribution": self._analyze_session_types(
                    session_history
                ),
                "recommendations": self._generate_pattern_recommendations(
                    session_history
                ),
            }

            return patterns

        except Exception as e:
            return {"status": "error", "message": f"Pattern analysis failed: {e}"}

    def _find_optimal_duration_range(
        self, durations: List[float], scores: List[float]
    ) -> Dict[str, Any]:
        """Find the duration range with highest average productivity."""
        try:
            # Group sessions by duration ranges
            ranges = {
                "short": (0, 60),  # 0-1 hour
                "medium": (60, 180),  # 1-3 hours
                "long": (180, 360),  # 3-6 hours
                "extended": (360, 999),  # 6+ hours
            }

            range_scores = {}

            for range_name, (min_dur, max_dur) in ranges.items():
                range_productivity = [
                    scores[i]
                    for i, dur in enumerate(durations)
                    if min_dur <= dur < max_dur
                ]

                if range_productivity:
                    range_scores[range_name] = {
                        "average_score": statistics.mean(range_productivity),
                        "session_count": len(range_productivity),
                        "score_range": (
                            min(range_productivity),
                            max(range_productivity),
                        ),
                    }

            # Find best performing range
            if range_scores:
                best_range = max(
                    range_scores.keys(), key=lambda k: range_scores[k]["average_score"]
                )
                return {
                    "optimal_range": best_range,
                    "range_details": range_scores,
                    "recommendation": f"Your most productive sessions are typically {best_range} duration",
                }

            return {"status": "no_data"}

        except Exception:
            return {"status": "calculation_error"}

    def _calculate_trend_direction(self, scores: List[float]) -> str:
        """Calculate overall trend direction of productivity scores."""
        try:
            if len(scores) < 3:
                return "unknown"

            # Simple linear trend calculation
            recent_half = scores[: len(scores) // 2]
            earlier_half = scores[len(scores) // 2 :]

            recent_avg = statistics.mean(recent_half)
            earlier_avg = statistics.mean(earlier_half)

            diff = recent_avg - earlier_avg

            if diff > 5:
                return "improving"
            elif diff < -5:
                return "declining"
            else:
                return "stable"

        except Exception:
            return "unknown"

    def _calculate_correlation(self, list1: List[float], list2: List[float]) -> float:
        """Calculate simple correlation coefficient between two lists."""
        try:
            if len(list1) != len(list2) or len(list1) < 2:
                return 0.0

            mean1 = statistics.mean(list1)
            mean2 = statistics.mean(list2)

            numerator = sum((x - mean1) * (y - mean2) for x, y in zip(list1, list2))

            sum_sq1 = sum((x - mean1) ** 2 for x in list1)
            sum_sq2 = sum((x - mean2) ** 2 for x in list2)

            denominator = (sum_sq1 * sum_sq2) ** 0.5

            if denominator == 0:
                return 0.0

            correlation = numerator / denominator
            return max(-1.0, min(1.0, correlation))  # Clamp to [-1, 1]

        except Exception:
            return 0.0

    def _analyze_session_types(
        self, session_history: List[ProductivityMetrics]
    ) -> Dict[str, Any]:
        """Analyze distribution of session types."""
        try:
            type_counts = {}
            type_scores = {}

            for session in session_history:
                session_type = session.session_type
                type_counts[session_type] = type_counts.get(session_type, 0) + 1

                if session_type not in type_scores:
                    type_scores[session_type] = []
                type_scores[session_type].append(session.productivity_score)

            # Calculate averages for each type
            type_analysis = {}
            for session_type, count in type_counts.items():
                type_analysis[session_type] = {
                    "count": count,
                    "percentage": round((count / len(session_history)) * 100, 1),
                    "avg_productivity": round(
                        statistics.mean(type_scores[session_type]), 1
                    ),
                    "productivity_range": (
                        round(min(type_scores[session_type]), 1),
                        round(max(type_scores[session_type]), 1),
                    ),
                }

            # Find most common and most productive types
            most_common = max(type_counts.keys(), key=lambda k: type_counts[k])
            most_productive = max(
                type_analysis.keys(), key=lambda k: type_analysis[k]["avg_productivity"]
            )

            return {
                "type_breakdown": type_analysis,
                "insights": {
                    "most_common_type": most_common,
                    "most_productive_type": most_productive,
                    "diversity_score": len(type_counts) / 7.0,  # Max 7 session types
                },
            }

        except Exception:
            return {"status": "analysis_error"}

    def _generate_pattern_recommendations(
        self, session_history: List[ProductivityMetrics]
    ) -> List[str]:
        """Generate actionable recommendations based on detected patterns."""
        try:
            recommendations = []

            if len(session_history) < 5:
                return [
                    "Continue tracking sessions to generate personalized recommendations"
                ]

            # Analyze recent performance
            recent_scores = [
                s.productivity_score for s in session_history[:5]
            ]  # Last 5 sessions
            avg_recent = statistics.mean(recent_scores)

            # Duration analysis
            durations = [s.session_duration_minutes for s in session_history]
            avg_duration = statistics.mean(durations)

            # Optimization analysis
            optimization_events = [s.optimization_events for s in session_history]
            avg_optimizations = statistics.mean(optimization_events)

            # Generate specific recommendations
            if avg_recent < 60:
                recommendations.append(
                    "Your recent productivity is below average - consider taking breaks and optimizing context more frequently"
                )

            if avg_duration > 240:  # > 4 hours
                recommendations.append(
                    "Your sessions are quite long - consider breaking them into shorter, focused periods"
                )
            elif avg_duration < 45:
                recommendations.append(
                    "Your sessions are quite short - longer focused sessions might improve productivity"
                )

            if avg_optimizations < 1:
                recommendations.append(
                    "Try using context optimization more frequently to maintain code quality and productivity"
                )
            elif avg_optimizations > 5:
                recommendations.append(
                    "Great use of optimization tools! This correlates with higher productivity"
                )

            # Session type recommendations
            type_analysis = self._analyze_session_types(session_history)
            if "type_breakdown" in type_analysis:
                debugging_sessions = (
                    type_analysis["type_breakdown"]
                    .get("debugging_session", {})
                    .get("count", 0)
                )
                total_sessions = len(session_history)

                if debugging_sessions / total_sessions > 0.4:
                    recommendations.append(
                        "High frequency of debugging sessions detected - consider code review practices and testing"
                    )

            # Trend-based recommendations
            scores = [s.productivity_score for s in session_history]
            trend = self._calculate_trend_direction(scores)

            if trend == "declining":
                recommendations.append(
                    "Productivity trend is declining - consider adjusting work patterns or taking a longer break"
                )
            elif trend == "improving":
                recommendations.append(
                    "Great work! Your productivity trend is improving - keep up the current practices"
                )

            return recommendations or [
                "Keep up the good work! Continue tracking sessions for more insights"
            ]

        except Exception:
            return [
                "Unable to generate recommendations - continue tracking for better insights"
            ]
