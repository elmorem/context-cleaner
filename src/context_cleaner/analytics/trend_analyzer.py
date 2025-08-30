"""
Trend Analysis and Pattern Detection System

Advanced analytics for identifying long-term productivity trends, behavioral patterns,
and optimization opportunities through statistical analysis and machine learning.
Provides insights into productivity cycles, usage patterns, and performance trends.
"""

import logging
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from .productivity_analyzer import ProductivityMetrics
from .context_health_scorer import HealthScore
from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Direction of detected trends."""

    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


class PatternType(Enum):
    """Types of detectable patterns."""

    DAILY_CYCLE = "daily_cycle"
    WEEKLY_CYCLE = "weekly_cycle"
    SESSION_LENGTH = "session_length"
    PRODUCTIVITY_RHYTHM = "productivity_rhythm"
    CONTEXT_SIZE_PATTERN = "context_size_pattern"
    BREAK_PATTERN = "break_pattern"
    FOCUS_PATTERN = "focus_pattern"
    INTERRUPTION_PATTERN = "interruption_pattern"


class TrendConfidence(Enum):
    """Confidence levels for trend analysis."""

    VERY_HIGH = "very_high"  # 90%+
    HIGH = "high"  # 75-89%
    MEDIUM = "medium"  # 60-74%
    LOW = "low"  # 40-59%
    VERY_LOW = "very_low"  # <40%


@dataclass
class TrendData:
    """Statistical trend information."""

    direction: TrendDirection
    strength: float  # 0-100, strength of trend
    confidence: TrendConfidence
    slope: float  # Rate of change
    r_squared: float  # Correlation coefficient
    start_value: float
    end_value: float
    data_points: int
    time_period_days: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Pattern:
    """Detected behavioral or productivity pattern."""

    type: PatternType
    name: str
    description: str
    strength: float  # 0-100, how strong/consistent the pattern is
    confidence: float  # 0-100, confidence in pattern detection
    frequency: str  # "daily", "weekly", "monthly", etc.
    peak_times: List[str]  # When pattern peaks occur
    characteristics: Dict[str, Any]
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendAnalysis:
    """Complete trend analysis results."""

    analysis_period: Tuple[datetime, datetime]
    data_quality_score: float  # 0-100, quality of underlying data

    # Productivity trends
    productivity_trend: TrendData
    focus_time_trend: TrendData
    session_count_trend: TrendData

    # Context health trends
    health_score_trend: TrendData
    context_size_trend: TrendData
    complexity_trend: TrendData

    # Detected patterns
    patterns: List[Pattern]

    # Key insights
    key_insights: List[str]
    anomalies: List[Dict[str, Any]]
    predictions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "analysis_period": {
                "start": self.analysis_period[0].isoformat(),
                "end": self.analysis_period[1].isoformat(),
            },
            "data_quality_score": self.data_quality_score,
            "trends": {
                "productivity": {
                    "direction": self.productivity_trend.direction.value,
                    "strength": self.productivity_trend.strength,
                    "confidence": self.productivity_trend.confidence.value,
                    "slope": self.productivity_trend.slope,
                    "change_percent": (
                        (
                            (
                                self.productivity_trend.end_value
                                - self.productivity_trend.start_value
                            )
                            / self.productivity_trend.start_value
                            * 100
                        )
                        if self.productivity_trend.start_value > 0
                        else 0
                    ),
                },
                "focus_time": {
                    "direction": self.focus_time_trend.direction.value,
                    "strength": self.focus_time_trend.strength,
                    "confidence": self.focus_time_trend.confidence.value,
                    "slope": self.focus_time_trend.slope,
                },
                "health_score": {
                    "direction": self.health_score_trend.direction.value,
                    "strength": self.health_score_trend.strength,
                    "confidence": self.health_score_trend.confidence.value,
                    "slope": self.health_score_trend.slope,
                },
            },
            "patterns": [
                {
                    "type": p.type.value,
                    "name": p.name,
                    "description": p.description,
                    "strength": p.strength,
                    "confidence": p.confidence,
                    "frequency": p.frequency,
                    "peak_times": p.peak_times,
                    "recommendations": p.recommendations,
                }
                for p in self.patterns
            ],
            "insights": self.key_insights,
            "anomalies": self.anomalies,
            "predictions": self.predictions,
        }


class TrendAnalyzer:
    """
    Advanced trend analysis and pattern detection system.

    Uses statistical analysis and machine learning techniques to identify:
    - Long-term productivity trends
    - Cyclical patterns in behavior
    - Optimal work timing
    - Context usage patterns
    - Performance anomalies
    """

    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """
        Initialize trend analyzer.

        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ContextCleanerConfig.from_env()

        # Analysis parameters
        self.minimum_data_points = 7  # Minimum data points for reliable trends
        self.trend_analysis_window = 30  # Days to look back for trends
        self.pattern_detection_window = 14  # Days to look back for patterns
        self.anomaly_threshold = 2.0  # Standard deviations for anomaly detection

        logger.info("TrendAnalyzer initialized")

    def analyze_trends(
        self,
        session_history: List[Dict[str, Any]],
        productivity_history: List[ProductivityMetrics] = None,
        health_history: List[HealthScore] = None,
    ) -> TrendAnalysis:
        """
        Perform comprehensive trend analysis.

        Args:
            session_history: Historical session data
            productivity_history: Historical productivity metrics
            health_history: Historical health scores

        Returns:
            TrendAnalysis with comprehensive insights
        """
        try:
            # Determine analysis period
            if not session_history:
                raise ValueError("No session history provided")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.trend_analysis_window)

            # Filter data to analysis window
            filtered_sessions = [
                s
                for s in session_history
                if self._parse_date(s.get("start_time", "")) >= start_date
            ]

            if len(filtered_sessions) < self.minimum_data_points:
                logger.warning(
                    f"Insufficient data for trend analysis: {len(filtered_sessions)} sessions"
                )
                return self._create_insufficient_data_analysis(start_date, end_date)

            # Calculate data quality score
            data_quality = self._assess_data_quality(filtered_sessions)

            # Analyze productivity trends
            productivity_trend = self._analyze_productivity_trend(
                filtered_sessions, productivity_history
            )
            focus_time_trend = self._analyze_focus_time_trend(filtered_sessions)
            session_count_trend = self._analyze_session_count_trend(filtered_sessions)

            # Analyze context health trends
            health_score_trend = self._analyze_health_score_trend(
                filtered_sessions, health_history
            )
            context_size_trend = self._analyze_context_size_trend(filtered_sessions)
            complexity_trend = self._analyze_complexity_trend(filtered_sessions)

            # Detect patterns
            patterns = self._detect_patterns(filtered_sessions)

            # Generate insights and anomalies
            insights = self._generate_key_insights(
                filtered_sessions, productivity_trend, health_score_trend, patterns
            )
            anomalies = self._detect_anomalies(filtered_sessions)

            # Generate predictions
            predictions = self._generate_predictions(
                productivity_trend, health_score_trend, patterns
            )

            analysis = TrendAnalysis(
                analysis_period=(start_date, end_date),
                data_quality_score=data_quality,
                productivity_trend=productivity_trend,
                focus_time_trend=focus_time_trend,
                session_count_trend=session_count_trend,
                health_score_trend=health_score_trend,
                context_size_trend=context_size_trend,
                complexity_trend=complexity_trend,
                patterns=patterns,
                key_insights=insights,
                anomalies=anomalies,
                predictions=predictions,
            )

            logger.info(
                f"Trend analysis completed for {len(filtered_sessions)} sessions"
            )
            return analysis

        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")
            return self._create_error_analysis(e)

    def _analyze_productivity_trend(
        self,
        sessions: List[Dict[str, Any]],
        productivity_history: Optional[List[ProductivityMetrics]] = None,
    ) -> TrendData:
        """Analyze productivity trend over time."""
        try:
            # Extract productivity data
            productivity_data = []

            for session in sessions:
                # Try to get productivity from session data
                productivity = session.get("productivity_score", 0)
                if productivity == 0 and productivity_history:
                    # Fallback to productivity history if available
                    session_date = self._parse_date(session.get("start_time", ""))
                    matching_metrics = [
                        m
                        for m in productivity_history
                        if abs((m.timestamp - session_date).total_seconds())
                        < 3600  # Within 1 hour
                    ]
                    if matching_metrics:
                        productivity = matching_metrics[0].overall_score

                if productivity > 0:
                    productivity_data.append(
                        (self._parse_date(session.get("start_time", "")), productivity)
                    )

            if len(productivity_data) < 3:
                return self._create_insufficient_trend_data("productivity")

            # Calculate trend
            return self._calculate_trend(productivity_data, "productivity")

        except Exception as e:
            logger.error(f"Productivity trend analysis failed: {e}")
            return self._create_error_trend_data("productivity", str(e))

    def _analyze_focus_time_trend(self, sessions: List[Dict[str, Any]]) -> TrendData:
        """Analyze focus time trend over time."""
        try:
            focus_data = []

            for session in sessions:
                focus_time = session.get("focus_time_minutes", 0)
                if focus_time > 0:
                    focus_data.append(
                        (self._parse_date(session.get("start_time", "")), focus_time)
                    )

            if len(focus_data) < 3:
                return self._create_insufficient_trend_data("focus_time")

            return self._calculate_trend(focus_data, "focus_time")

        except Exception as e:
            logger.error(f"Focus time trend analysis failed: {e}")
            return self._create_error_trend_data("focus_time", str(e))

    def _analyze_session_count_trend(self, sessions: List[Dict[str, Any]]) -> TrendData:
        """Analyze session frequency trend over time."""
        try:
            # Group sessions by day
            daily_counts = {}

            for session in sessions:
                session_date = self._parse_date(session.get("start_time", "")).date()
                daily_counts[session_date] = daily_counts.get(session_date, 0) + 1

            if len(daily_counts) < 3:
                return self._create_insufficient_trend_data("session_count")

            # Convert to time series data
            count_data = [
                (datetime.combine(date, datetime.min.time()), count)
                for date, count in sorted(daily_counts.items())
            ]

            return self._calculate_trend(count_data, "session_count")

        except Exception as e:
            logger.error(f"Session count trend analysis failed: {e}")
            return self._create_error_trend_data("session_count", str(e))

    def _analyze_health_score_trend(
        self,
        sessions: List[Dict[str, Any]],
        health_history: Optional[List[HealthScore]] = None,
    ) -> TrendData:
        """Analyze context health score trend over time."""
        try:
            health_data = []

            for session in sessions:
                # Try session data first
                health_score = session.get("health_score", 0)

                if health_score == 0 and health_history:
                    # Fallback to health history
                    session_date = self._parse_date(session.get("start_time", ""))
                    matching_health = [
                        h
                        for h in health_history
                        if abs((h.timestamp - session_date).total_seconds()) < 3600
                    ]
                    if matching_health:
                        health_score = matching_health[0].overall_score

                if health_score > 0:
                    health_data.append(
                        (self._parse_date(session.get("start_time", "")), health_score)
                    )

            if len(health_data) < 3:
                return self._create_insufficient_trend_data("health_score")

            return self._calculate_trend(health_data, "health_score")

        except Exception as e:
            logger.error(f"Health score trend analysis failed: {e}")
            return self._create_error_trend_data("health_score", str(e))

    def _analyze_context_size_trend(self, sessions: List[Dict[str, Any]]) -> TrendData:
        """Analyze context size trend over time."""
        try:
            size_data = []

            for session in sessions:
                context_size = session.get("context_size", 0)
                if context_size > 0:
                    size_data.append(
                        (self._parse_date(session.get("start_time", "")), context_size)
                    )

            if len(size_data) < 3:
                return self._create_insufficient_trend_data("context_size")

            return self._calculate_trend(size_data, "context_size")

        except Exception as e:
            logger.error(f"Context size trend analysis failed: {e}")
            return self._create_error_trend_data("context_size", str(e))

    def _analyze_complexity_trend(self, sessions: List[Dict[str, Any]]) -> TrendData:
        """Analyze code complexity trend over time."""
        try:
            complexity_data = []

            for session in sessions:
                complexity = session.get("complexity_score", 0)
                if complexity > 0:
                    complexity_data.append(
                        (self._parse_date(session.get("start_time", "")), complexity)
                    )

            if len(complexity_data) < 3:
                return self._create_insufficient_trend_data("complexity")

            return self._calculate_trend(complexity_data, "complexity")

        except Exception as e:
            logger.error(f"Complexity trend analysis failed: {e}")
            return self._create_error_trend_data("complexity", str(e))

    def _calculate_trend(
        self, data: List[Tuple[datetime, float]], metric_name: str
    ) -> TrendData:
        """Calculate statistical trend from time series data."""
        try:
            if len(data) < 2:
                return self._create_insufficient_trend_data(metric_name)

            # Sort data by time
            sorted_data = sorted(data, key=lambda x: x[0])

            # Convert to numerical arrays
            times = [(d[0] - sorted_data[0][0]).total_seconds() for d in sorted_data]
            values = [d[1] for d in sorted_data]

            # Calculate linear regression
            n = len(times)
            sum_x = sum(times)
            sum_y = sum(values)
            sum_xy = sum(x * y for x, y in zip(times, values))
            sum_x2 = sum(x * x for x in times)

            # Calculate slope and correlation
            slope = (
                (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                if (n * sum_x2 - sum_x * sum_x) != 0
                else 0
            )

            # Calculate R-squared
            mean_y = statistics.mean(values)
            ss_tot = sum((y - mean_y) ** 2 for y in values)
            ss_res = sum(
                (y - (slope * x + (sum_y - slope * sum_x) / n)) ** 2
                for x, y in zip(times, values)
            )
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Determine trend direction and strength
            direction = self._determine_trend_direction(slope, values)
            strength = min(
                abs(r_squared * 100), 100.0
            )  # Convert to percentage, cap at 100
            confidence = self._determine_confidence(r_squared, n)

            return TrendData(
                direction=direction,
                strength=strength,
                confidence=confidence,
                slope=slope,
                r_squared=r_squared,
                start_value=values[0],
                end_value=values[-1],
                data_points=n,
                time_period_days=(sorted_data[-1][0] - sorted_data[0][0]).days,
                metadata={
                    "metric": metric_name,
                    "values": values[-5:],
                },  # Last 5 values for context
            )

        except Exception as e:
            logger.error(f"Trend calculation failed for {metric_name}: {e}")
            return self._create_error_trend_data(metric_name, str(e))

    def _detect_patterns(self, sessions: List[Dict[str, Any]]) -> List[Pattern]:
        """Detect behavioral and productivity patterns."""
        patterns = []

        try:
            # Daily productivity pattern
            daily_pattern = self._detect_daily_productivity_pattern(sessions)
            if daily_pattern:
                patterns.append(daily_pattern)

            # Weekly activity pattern
            weekly_pattern = self._detect_weekly_activity_pattern(sessions)
            if weekly_pattern:
                patterns.append(weekly_pattern)

            # Session length pattern
            session_length_pattern = self._detect_session_length_pattern(sessions)
            if session_length_pattern:
                patterns.append(session_length_pattern)

            # Focus time pattern
            focus_pattern = self._detect_focus_time_pattern(sessions)
            if focus_pattern:
                patterns.append(focus_pattern)

        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")

        return patterns

    def _detect_daily_productivity_pattern(
        self, sessions: List[Dict[str, Any]]
    ) -> Optional[Pattern]:
        """Detect daily productivity patterns (e.g., morning vs afternoon productivity)."""
        try:
            hourly_productivity = {}

            for session in sessions:
                start_time = self._parse_date(session.get("start_time", ""))
                hour = start_time.hour
                productivity = session.get("productivity_score", 0)

                if productivity > 0:
                    if hour not in hourly_productivity:
                        hourly_productivity[hour] = []
                    hourly_productivity[hour].append(productivity)

            # Need at least 3 different hours with multiple data points
            valid_hours = {
                h: scores
                for h, scores in hourly_productivity.items()
                if len(scores) >= 2
            }

            if len(valid_hours) < 3:
                return None

            # Calculate average productivity by hour
            hourly_averages = {
                h: statistics.mean(scores) for h, scores in valid_hours.items()
            }

            # Find peak hours
            sorted_hours = sorted(
                hourly_averages.items(), key=lambda x: x[1], reverse=True
            )
            peak_hours = [f"{h:02d}:00" for h, _ in sorted_hours[:3]]  # Top 3 hours

            # Calculate pattern strength based on variance
            all_averages = list(hourly_averages.values())
            if len(all_averages) > 1:
                variance = statistics.variance(all_averages)
                strength = min(
                    variance / statistics.mean(all_averages) * 100, 100
                )  # Coefficient of variation as %
            else:
                strength = 0

            # Generate recommendations
            recommendations = []
            best_hour = sorted_hours[0][0]
            worst_hour = sorted_hours[-1][0]

            if sorted_hours[0][1] - sorted_hours[-1][1] > 15:  # Significant difference
                if best_hour < 12:
                    recommendations.append(
                        "Schedule important work in the morning hours"
                    )
                elif best_hour > 17:
                    recommendations.append(
                        "Take advantage of evening productivity peaks"
                    )
                else:
                    recommendations.append("Optimize midday work scheduling")

            return Pattern(
                type=PatternType.DAILY_CYCLE,
                name="Daily Productivity Cycle",
                description=f"Peak productivity hours: {', '.join(peak_hours)}",
                strength=strength,
                confidence=min(
                    len(valid_hours) * 10, 100
                ),  # More hours = higher confidence
                frequency="daily",
                peak_times=peak_hours,
                characteristics={
                    "best_hour": best_hour,
                    "best_productivity": sorted_hours[0][1],
                    "worst_hour": worst_hour,
                    "worst_productivity": sorted_hours[-1][1],
                    "productivity_variance": variance if "variance" in locals() else 0,
                },
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error(f"Daily pattern detection failed: {e}")
            return None

    def _detect_weekly_activity_pattern(
        self, sessions: List[Dict[str, Any]]
    ) -> Optional[Pattern]:
        """Detect weekly activity patterns."""
        try:
            daily_activity = {}

            for session in sessions:
                start_time = self._parse_date(session.get("start_time", ""))
                weekday = start_time.strftime("%A")

                if weekday not in daily_activity:
                    daily_activity[weekday] = []
                daily_activity[weekday].append(session.get("duration_minutes", 0))

            if len(daily_activity) < 5:  # Need most days of week
                return None

            # Calculate average session time by day
            daily_averages = {}
            for day, durations in daily_activity.items():
                if durations and len(durations) >= 2:
                    daily_averages[day] = statistics.mean(durations)

            if len(daily_averages) < 3:
                return None

            # Find peak activity days
            sorted_days = sorted(
                daily_averages.items(), key=lambda x: x[1], reverse=True
            )
            peak_days = [day for day, _ in sorted_days[:3]]

            # Calculate pattern strength
            all_averages = list(daily_averages.values())
            variance = statistics.variance(all_averages) if len(all_averages) > 1 else 0
            strength = (
                min(variance / statistics.mean(all_averages) * 50, 100)
                if all_averages
                else 0
            )

            return Pattern(
                type=PatternType.WEEKLY_CYCLE,
                name="Weekly Activity Pattern",
                description=f"Most active days: {', '.join(peak_days)}",
                strength=strength,
                confidence=min(len(daily_averages) * 12, 100),
                frequency="weekly",
                peak_times=peak_days,
                characteristics={
                    "daily_averages": daily_averages,
                    "total_days_with_data": len(daily_averages),
                },
                recommendations=["Plan intensive work during peak activity days"],
            )

        except Exception as e:
            logger.error(f"Weekly pattern detection failed: {e}")
            return None

    def _detect_session_length_pattern(
        self, sessions: List[Dict[str, Any]]
    ) -> Optional[Pattern]:
        """Detect session length patterns."""
        try:
            durations = [
                s.get("duration_minutes", 0)
                for s in sessions
                if s.get("duration_minutes", 0) > 0
            ]

            if len(durations) < 5:
                return None

            avg_duration = statistics.mean(durations)

            # Categorize sessions
            short_sessions = sum(1 for d in durations if d < 30)
            medium_sessions = sum(1 for d in durations if 30 <= d <= 120)
            long_sessions = sum(1 for d in durations if d > 120)

            total_sessions = len(durations)

            # Determine dominant pattern
            if short_sessions / total_sessions > 0.6:
                pattern_type = "short_burst"
                description = f"Prefers short sessions (avg: {avg_duration:.1f}min)"
            elif long_sessions / total_sessions > 0.4:
                pattern_type = "extended_focus"
                description = f"Prefers long sessions (avg: {avg_duration:.1f}min)"
            else:
                pattern_type = "mixed"
                description = f"Mixed session lengths (avg: {avg_duration:.1f}min)"

            return Pattern(
                type=PatternType.SESSION_LENGTH,
                name="Session Length Pattern",
                description=description,
                strength=max(short_sessions, medium_sessions, long_sessions)
                / total_sessions
                * 100,
                confidence=min(total_sessions * 5, 100),
                frequency="per_session",
                peak_times=[f"{avg_duration:.0f} minutes"],
                characteristics={
                    "pattern_type": pattern_type,
                    "average_duration": avg_duration,
                    "short_sessions_pct": short_sessions / total_sessions * 100,
                    "medium_sessions_pct": medium_sessions / total_sessions * 100,
                    "long_sessions_pct": long_sessions / total_sessions * 100,
                },
                recommendations=self._get_session_length_recommendations(
                    pattern_type, avg_duration
                ),
            )

        except Exception as e:
            logger.error(f"Session length pattern detection failed: {e}")
            return None

    def _detect_focus_time_pattern(
        self, sessions: List[Dict[str, Any]]
    ) -> Optional[Pattern]:
        """Detect focus time patterns."""
        try:
            focus_times = [
                s.get("focus_time_minutes", 0)
                for s in sessions
                if s.get("focus_time_minutes", 0) > 0
            ]

            if len(focus_times) < 5:
                return None

            avg_focus = statistics.mean(focus_times)
            focus_ratio = avg_focus / statistics.mean(
                [
                    s.get("duration_minutes", 1)
                    for s in sessions
                    if s.get("duration_minutes", 0) > 0
                ]
            )

            # Determine focus efficiency
            if focus_ratio > 0.8:
                efficiency = "high"
                description = f"High focus efficiency ({focus_ratio:.1%})"
            elif focus_ratio > 0.5:
                efficiency = "medium"
                description = f"Medium focus efficiency ({focus_ratio:.1%})"
            else:
                efficiency = "low"
                description = f"Low focus efficiency ({focus_ratio:.1%})"

            return Pattern(
                type=PatternType.FOCUS_PATTERN,
                name="Focus Efficiency Pattern",
                description=description,
                strength=focus_ratio * 100,
                confidence=min(len(focus_times) * 8, 100),
                frequency="per_session",
                peak_times=[f"{avg_focus:.0f} minutes average"],
                characteristics={
                    "efficiency_level": efficiency,
                    "focus_ratio": focus_ratio,
                    "average_focus_time": avg_focus,
                },
                recommendations=self._get_focus_recommendations(
                    efficiency, focus_ratio
                ),
            )

        except Exception as e:
            logger.error(f"Focus pattern detection failed: {e}")
            return None

    def _generate_key_insights(
        self,
        sessions: List[Dict[str, Any]],
        productivity_trend: TrendData,
        health_trend: TrendData,
        patterns: List[Pattern],
    ) -> List[str]:
        """Generate key insights from trend analysis."""
        insights = []

        # Productivity insights
        if (
            productivity_trend.direction == TrendDirection.IMPROVING
            and productivity_trend.confidence
            in [TrendConfidence.HIGH, TrendConfidence.VERY_HIGH]
        ):
            change_pct = (
                (
                    (productivity_trend.end_value - productivity_trend.start_value)
                    / productivity_trend.start_value
                    * 100
                )
                if productivity_trend.start_value > 0
                else 0
            )
            insights.append(
                f"Productivity has improved by {change_pct:.1f}% over the past {productivity_trend.time_period_days} days"
            )

        elif (
            productivity_trend.direction == TrendDirection.DECLINING
            and productivity_trend.confidence
            in [TrendConfidence.HIGH, TrendConfidence.VERY_HIGH]
        ):
            change_pct = (
                abs(
                    (productivity_trend.end_value - productivity_trend.start_value)
                    / productivity_trend.start_value
                    * 100
                )
                if productivity_trend.start_value > 0
                else 0
            )
            insights.append(
                f"Productivity has declined by {change_pct:.1f}% - consider reviewing work habits"
            )

        # Health score insights
        if (
            health_trend.direction == TrendDirection.DECLINING
            and health_trend.confidence
            in [TrendConfidence.MEDIUM, TrendConfidence.HIGH, TrendConfidence.VERY_HIGH]
        ):
            insights.append(
                "Context health scores are declining - consider optimizing context management"
            )

        # Pattern insights
        daily_patterns = [p for p in patterns if p.type == PatternType.DAILY_CYCLE]
        if daily_patterns and daily_patterns[0].strength > 50:
            peak_time = (
                daily_patterns[0].peak_times[0]
                if daily_patterns[0].peak_times
                else "unknown"
            )
            insights.append(
                f"You have a strong daily productivity pattern with peak performance around {peak_time}"
            )

        # Session insights
        if len(sessions) > 0:
            avg_session_length = statistics.mean(
                [
                    s.get("duration_minutes", 0)
                    for s in sessions
                    if s.get("duration_minutes", 0) > 0
                ]
            )
            if avg_session_length > 120:
                insights.append(
                    "You tend to work in long sessions - consider taking more breaks to maintain focus"
                )
            elif avg_session_length < 30:
                insights.append(
                    "Your sessions are quite short - you might benefit from longer focused work periods"
                )

        return insights[:5]  # Limit to top 5 insights

    def _detect_anomalies(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalous sessions or behaviors."""
        anomalies = []

        try:
            # Duration anomalies
            durations = [
                s.get("duration_minutes", 0)
                for s in sessions
                if s.get("duration_minutes", 0) > 0
            ]
            if len(durations) > 5:
                duration_mean = statistics.mean(durations)
                duration_std = statistics.stdev(durations)

                for session in sessions:
                    duration = session.get("duration_minutes", 0)
                    if duration > 0:
                        z_score = (
                            abs(duration - duration_mean) / duration_std
                            if duration_std > 0
                            else 0
                        )

                        if z_score > self.anomaly_threshold:
                            anomalies.append(
                                {
                                    "type": "duration_anomaly",
                                    "session_id": session.get("session_id", "unknown"),
                                    "date": session.get("start_time", ""),
                                    "value": duration,
                                    "expected_range": f"{duration_mean - duration_std:.1f}-{duration_mean + duration_std:.1f} minutes",
                                    "z_score": z_score,
                                    "description": f"Unusually {'long' if duration > duration_mean else 'short'} session duration",
                                }
                            )

            # Context size anomalies
            context_sizes = [
                s.get("context_size", 0)
                for s in sessions
                if s.get("context_size", 0) > 0
            ]
            if len(context_sizes) > 5:
                size_mean = statistics.mean(context_sizes)
                size_std = statistics.stdev(context_sizes)

                for session in sessions:
                    size = session.get("context_size", 0)
                    if size > 0:
                        z_score = (
                            abs(size - size_mean) / size_std if size_std > 0 else 0
                        )

                        if z_score > self.anomaly_threshold:
                            anomalies.append(
                                {
                                    "type": "context_size_anomaly",
                                    "session_id": session.get("session_id", "unknown"),
                                    "date": session.get("start_time", ""),
                                    "value": size,
                                    "expected_range": f"{size_mean - size_std:.0f}-{size_mean + size_std:.0f} tokens",
                                    "z_score": z_score,
                                    "description": f"Unusually {'large' if size > size_mean else 'small'} context size",
                                }
                            )

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")

        return anomalies[:10]  # Limit to top 10 anomalies

    def _generate_predictions(
        self,
        productivity_trend: TrendData,
        health_trend: TrendData,
        patterns: List[Pattern],
    ) -> Dict[str, Any]:
        """Generate simple predictions based on trends and patterns."""
        predictions = {}

        try:
            # Productivity prediction
            if (
                productivity_trend.direction != TrendDirection.INSUFFICIENT_DATA
                and productivity_trend.confidence
                in [
                    TrendConfidence.MEDIUM,
                    TrendConfidence.HIGH,
                    TrendConfidence.VERY_HIGH,
                ]
            ):

                # Simple linear extrapolation
                future_productivity = productivity_trend.end_value + (
                    productivity_trend.slope * 7
                )  # 7 days ahead
                future_productivity = max(
                    0, min(100, future_productivity)
                )  # Clamp to valid range

                predictions["productivity_next_week"] = {
                    "predicted_score": round(future_productivity, 1),
                    "confidence": productivity_trend.confidence.value,
                    "trend_direction": productivity_trend.direction.value,
                }

            # Health score prediction
            if (
                health_trend.direction != TrendDirection.INSUFFICIENT_DATA
                and health_trend.confidence
                in [
                    TrendConfidence.MEDIUM,
                    TrendConfidence.HIGH,
                    TrendConfidence.VERY_HIGH,
                ]
            ):

                future_health = health_trend.end_value + (health_trend.slope * 7)
                future_health = max(0, min(100, future_health))

                predictions["health_score_next_week"] = {
                    "predicted_score": round(future_health, 1),
                    "confidence": health_trend.confidence.value,
                    "trend_direction": health_trend.direction.value,
                }

            # Pattern-based predictions
            daily_patterns = [
                p
                for p in patterns
                if p.type == PatternType.DAILY_CYCLE and p.strength > 60
            ]
            if daily_patterns:
                best_hours = daily_patterns[0].characteristics.get("best_hour", 12)
                predictions["optimal_work_time"] = {
                    "recommended_hour": best_hours,
                    "confidence": daily_patterns[0].confidence,
                }

        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")

        return predictions

    # Helper methods

    def _parse_date(self, date_string: str) -> datetime:
        """Parse date string to datetime object."""
        try:
            # Try common formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
            ]:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue

            # Fallback to now if parsing fails
            return datetime.now()

        except Exception:
            return datetime.now()

    def _assess_data_quality(self, sessions: List[Dict[str, Any]]) -> float:
        """Assess quality of session data for analysis."""
        if not sessions:
            return 0.0

        quality_score = 0.0
        total_weight = 0.0

        # Data completeness (40% weight)
        completeness_weight = 40.0
        required_fields = ["start_time", "duration_minutes", "productivity_score"]
        field_scores = []

        for field in required_fields:
            present_count = sum(
                1 for s in sessions if s.get(field) is not None and s.get(field) != 0
            )
            field_score = (present_count / len(sessions)) * 100
            field_scores.append(field_score)

        completeness_score = statistics.mean(field_scores)
        quality_score += completeness_score * (completeness_weight / 100)
        total_weight += completeness_weight

        # Data volume (30% weight)
        volume_weight = 30.0
        volume_score = min((len(sessions) / 20) * 100, 100)  # 20+ sessions = 100%
        quality_score += volume_score * (volume_weight / 100)
        total_weight += volume_weight

        # Time coverage (30% weight)
        coverage_weight = 30.0
        if len(sessions) > 1:
            dates = [self._parse_date(s.get("start_time", "")).date() for s in sessions]
            unique_dates = len(set(dates))
            coverage_score = min((unique_dates / 14) * 100, 100)  # 14+ days = 100%
        else:
            coverage_score = 0

        quality_score += coverage_score * (coverage_weight / 100)
        total_weight += coverage_weight

        return min(quality_score, 100.0)

    def _determine_trend_direction(
        self, slope: float, values: List[float]
    ) -> TrendDirection:
        """Determine trend direction from slope and data variability."""
        if len(values) < 2:
            return TrendDirection.INSUFFICIENT_DATA

        # Calculate coefficient of variation to detect volatility
        mean_val = statistics.mean(values)
        if mean_val > 0:
            cv = statistics.stdev(values) / mean_val
            if cv > 0.3:  # High variability
                return TrendDirection.VOLATILE

        # Determine direction based on slope
        slope_threshold = 0.1  # Minimum slope to consider significant

        if slope > slope_threshold:
            return TrendDirection.IMPROVING
        elif slope < -slope_threshold:
            return TrendDirection.DECLINING
        else:
            return TrendDirection.STABLE

    def _determine_confidence(
        self, r_squared: float, data_points: int
    ) -> TrendConfidence:
        """Determine confidence level based on R-squared and data volume."""
        # Adjust confidence based on both correlation and data volume
        base_confidence = r_squared * 100

        # Volume adjustment
        if data_points < 5:
            volume_multiplier = 0.5
        elif data_points < 10:
            volume_multiplier = 0.7
        elif data_points < 20:
            volume_multiplier = 0.9
        else:
            volume_multiplier = 1.0

        adjusted_confidence = base_confidence * volume_multiplier

        if adjusted_confidence >= 90:
            return TrendConfidence.VERY_HIGH
        elif adjusted_confidence >= 75:
            return TrendConfidence.HIGH
        elif adjusted_confidence >= 60:
            return TrendConfidence.MEDIUM
        elif adjusted_confidence >= 40:
            return TrendConfidence.LOW
        else:
            return TrendConfidence.VERY_LOW

    def _get_session_length_recommendations(
        self, pattern_type: str, avg_duration: float
    ) -> List[str]:
        """Get recommendations based on session length patterns."""
        if pattern_type == "short_burst":
            return [
                "Consider combining short sessions for deeper focus",
                "Try time-blocking techniques to extend work periods",
                "Reduce context switching between tasks",
            ]
        elif pattern_type == "extended_focus":
            return [
                "Take regular breaks to maintain productivity",
                "Use the Pomodoro technique for better time management",
                "Monitor for signs of mental fatigue",
            ]
        else:
            return [
                "Optimize session length based on task complexity",
                "Match session duration to energy levels",
                "Experiment with different work rhythm patterns",
            ]

    def _get_focus_recommendations(
        self, efficiency: str, focus_ratio: float
    ) -> List[str]:
        """Get recommendations based on focus patterns."""
        if efficiency == "low":
            return [
                "Minimize distractions during work sessions",
                "Use website blockers or focus apps",
                "Create a dedicated work environment",
                "Practice mindfulness or meditation techniques",
            ]
        elif efficiency == "medium":
            return [
                "Identify and eliminate remaining distractions",
                "Optimize work environment for better focus",
                "Try different focus techniques like deep work blocks",
            ]
        else:
            return [
                "Maintain current excellent focus habits",
                "Consider mentoring others on focus techniques",
                "Monitor for any decline in focus efficiency",
            ]

    def _create_insufficient_trend_data(self, metric_name: str) -> TrendData:
        """Create trend data for insufficient data scenarios."""
        return TrendData(
            direction=TrendDirection.INSUFFICIENT_DATA,
            strength=0.0,
            confidence=TrendConfidence.VERY_LOW,
            slope=0.0,
            r_squared=0.0,
            start_value=0.0,
            end_value=0.0,
            data_points=0,
            time_period_days=0,
            metadata={"error": f"Insufficient data for {metric_name} trend analysis"},
        )

    def _create_error_trend_data(self, metric_name: str, error_msg: str) -> TrendData:
        """Create trend data for error scenarios."""
        return TrendData(
            direction=TrendDirection.INSUFFICIENT_DATA,
            strength=0.0,
            confidence=TrendConfidence.VERY_LOW,
            slope=0.0,
            r_squared=0.0,
            start_value=0.0,
            end_value=0.0,
            data_points=0,
            time_period_days=0,
            metadata={"error": error_msg, "metric": metric_name},
        )

    def _create_insufficient_data_analysis(
        self, start_date: datetime, end_date: datetime
    ) -> TrendAnalysis:
        """Create analysis for insufficient data scenarios."""
        insufficient_trend = self._create_insufficient_trend_data("insufficient_data")

        return TrendAnalysis(
            analysis_period=(start_date, end_date),
            data_quality_score=0.0,
            productivity_trend=insufficient_trend,
            focus_time_trend=insufficient_trend,
            session_count_trend=insufficient_trend,
            health_score_trend=insufficient_trend,
            context_size_trend=insufficient_trend,
            complexity_trend=insufficient_trend,
            patterns=[],
            key_insights=[
                "Insufficient data for trend analysis. Need at least 7 sessions over 7 days."
            ],
            anomalies=[],
            predictions={},
        )

    def _create_error_analysis(self, error: Exception) -> TrendAnalysis:
        """Create analysis for error scenarios."""
        error_trend = self._create_error_trend_data("error", str(error))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        return TrendAnalysis(
            analysis_period=(start_date, end_date),
            data_quality_score=0.0,
            productivity_trend=error_trend,
            focus_time_trend=error_trend,
            session_count_trend=error_trend,
            health_score_trend=error_trend,
            context_size_trend=error_trend,
            complexity_trend=error_trend,
            patterns=[],
            key_insights=[f"Trend analysis failed: {str(error)}"],
            anomalies=[],
            predictions={},
        )
