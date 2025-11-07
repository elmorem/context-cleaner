"""
Session Comparison and Trend Analysis for Phase 2

Provides comprehensive session analytics, cross-session comparisons,
and trend analysis capabilities for productivity insights.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import statistics

from ..clients.clickhouse_client import ClickHouseClient
from ..clients.base import SessionMetrics

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend direction indicators"""

    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"


class MetricType(Enum):
    """Types of metrics for analysis"""

    COST = "cost"
    EFFICIENCY = "efficiency"
    ERROR_RATE = "error_rate"
    TOOL_USAGE = "tool_usage"
    DURATION = "duration"
    PRODUCTIVITY = "productivity"


@dataclass
class SessionComparison:
    """Comparison between two sessions"""

    session_a: str
    session_b: str
    cost_difference: float
    efficiency_difference: float
    duration_difference: float
    tool_usage_similarity: float
    productivity_score_diff: float
    insights: List[str] = field(default_factory=list)


@dataclass
class TrendAnalysis:
    """Trend analysis for a specific metric"""

    metric_type: MetricType
    direction: TrendDirection
    change_percentage: float
    confidence: float
    time_period: str
    data_points: List[Tuple[datetime, float]]
    insights: List[str] = field(default_factory=list)


@dataclass
class SessionInsights:
    """Comprehensive insights for a session"""

    session_id: str
    productivity_score: float
    cost_efficiency: float
    tool_effectiveness: float
    error_resilience: float
    time_management: float
    strengths: List[str] = field(default_factory=list)
    improvement_areas: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ProductivityTrend:
    """Productivity trend over time"""

    period: str  # "daily", "weekly", "monthly"
    average_score: float
    trend_direction: TrendDirection
    best_session: Optional[str]
    worst_session: Optional[str]
    consistency_score: float  # How consistent productivity is
    peak_hours: List[int]  # Hours of day with best productivity
    factors: Dict[str, float]  # Factors affecting productivity


class SessionAnalyticsEngine:
    """Advanced session analytics and comparison engine"""

    def __init__(self, telemetry_client: ClickHouseClient):
        self.telemetry = telemetry_client

        # Analysis parameters
        self.min_sessions_for_trend = 5
        self.trend_confidence_threshold = 0.7
        self.similarity_threshold = 0.8

        # Cached data for performance
        self._session_cache: Dict[str, SessionMetrics] = {}
        self._trend_cache: Dict[str, TrendAnalysis] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._last_cache_update = datetime.now()

    async def compare_sessions(
        self, session_a: str, session_b: str
    ) -> SessionComparison:
        """Compare two sessions across multiple dimensions"""
        try:
            # Get session data
            metrics_a = await self._get_session_metrics(session_a)
            metrics_b = await self._get_session_metrics(session_b)

            if not metrics_a or not metrics_b:
                raise ValueError("One or both sessions not found")

            # Calculate differences
            cost_diff = metrics_b.total_cost - metrics_a.total_cost

            # Calculate efficiency (cost per token)
            efficiency_a = metrics_a.total_cost / max(metrics_a.total_input_tokens, 1)
            efficiency_b = metrics_b.total_cost / max(metrics_b.total_input_tokens, 1)
            efficiency_diff = efficiency_b - efficiency_a

            # Calculate duration difference
            duration_a = self._get_session_duration(metrics_a)
            duration_b = self._get_session_duration(metrics_b)
            duration_diff = duration_b - duration_a

            # Calculate tool usage similarity
            tool_similarity = self._calculate_tool_similarity(
                metrics_a.tools_used, metrics_b.tools_used
            )

            # Calculate productivity scores
            prod_a = await self._calculate_productivity_score(metrics_a)
            prod_b = await self._calculate_productivity_score(metrics_b)
            productivity_diff = prod_b - prod_a

            # Generate insights
            insights = self._generate_comparison_insights(
                metrics_a,
                metrics_b,
                cost_diff,
                efficiency_diff,
                duration_diff,
                tool_similarity,
                productivity_diff,
            )

            return SessionComparison(
                session_a=session_a,
                session_b=session_b,
                cost_difference=cost_diff,
                efficiency_difference=efficiency_diff,
                duration_difference=duration_diff,
                tool_usage_similarity=tool_similarity,
                productivity_score_diff=productivity_diff,
                insights=insights,
            )

        except Exception as e:
            logger.error(f"Error comparing sessions {session_a} and {session_b}: {e}")
            raise

    async def analyze_session_trends(
        self, days: int = 30, metric_type: MetricType = MetricType.PRODUCTIVITY
    ) -> TrendAnalysis:
        """Analyze trends for a specific metric over time"""
        try:
            # Get historical session data
            sessions = await self._get_recent_sessions(days)

            if len(sessions) < self.min_sessions_for_trend:
                raise ValueError(
                    f"Need at least {self.min_sessions_for_trend} sessions for trend analysis"
                )

            # Extract metric data
            data_points = []
            for session in sessions:
                timestamp = session.start_time
                value = await self._extract_metric_value(session, metric_type)
                data_points.append((timestamp, value))

            # Sort by timestamp
            data_points.sort(key=lambda x: x[0])

            # Analyze trend
            values = [point[1] for point in data_points]
            trend_direction = self._determine_trend_direction(values)
            change_percentage = self._calculate_change_percentage(values)
            confidence = self._calculate_trend_confidence(values)

            # Generate insights
            insights = self._generate_trend_insights(
                metric_type, trend_direction, change_percentage, data_points
            )

            return TrendAnalysis(
                metric_type=metric_type,
                direction=trend_direction,
                change_percentage=change_percentage,
                confidence=confidence,
                time_period=f"{days} days",
                data_points=data_points,
                insights=insights,
            )

        except Exception as e:
            logger.error(f"Error analyzing trends for {metric_type.value}: {e}")
            raise

    async def get_session_insights(self, session_id: str) -> SessionInsights:
        """Get comprehensive insights for a specific session"""
        try:
            session = await self._get_session_metrics(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            # Calculate various scores
            productivity_score = await self._calculate_productivity_score(session)
            cost_efficiency = self._calculate_cost_efficiency(session)
            tool_effectiveness = self._calculate_tool_effectiveness(session)
            error_resilience = self._calculate_error_resilience(session)
            time_management = self._calculate_time_management_score(session)

            # Identify strengths and areas for improvement
            strengths = []
            improvements = []
            recommendations = []

            # Analyze strengths
            if cost_efficiency > 0.8:
                strengths.append("Excellent cost efficiency")
            if tool_effectiveness > 0.8:
                strengths.append("Effective tool usage patterns")
            if error_resilience > 0.9:
                strengths.append("High error resilience")
            if time_management > 0.7:
                strengths.append("Good time management")

            # Identify improvement areas
            if cost_efficiency < 0.5:
                improvements.append("Cost optimization needed")
                recommendations.append("Consider using Haiku for routine tasks")
            if tool_effectiveness < 0.6:
                improvements.append("Tool usage could be more efficient")
                recommendations.append("Review common workflow patterns")
            if error_resilience < 0.7:
                improvements.append("Error handling needs attention")
                recommendations.append("Enable automatic error recovery")
            if time_management < 0.5:
                improvements.append("Session duration management")
                recommendations.append("Break complex tasks into shorter sessions")

            return SessionInsights(
                session_id=session_id,
                productivity_score=productivity_score,
                cost_efficiency=cost_efficiency,
                tool_effectiveness=tool_effectiveness,
                error_resilience=error_resilience,
                time_management=time_management,
                strengths=strengths,
                improvement_areas=improvements,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error(f"Error generating insights for session {session_id}: {e}")
            raise

    async def get_productivity_trends(
        self, period: str = "weekly"
    ) -> ProductivityTrend:
        """Get productivity trends over a specified period"""
        try:
            days = {"daily": 7, "weekly": 30, "monthly": 90}.get(period, 30)
            sessions = await self._get_recent_sessions(days)

            if not sessions:
                raise ValueError("No sessions found for trend analysis")

            # Calculate productivity scores
            productivity_scores = []
            hourly_scores = {hour: [] for hour in range(24)}

            for session in sessions:
                score = await self._calculate_productivity_score(session)
                productivity_scores.append(score)

                # Track by hour
                hour = session.start_time.hour
                hourly_scores[hour].append(score)

            # Calculate average and trend
            avg_score = statistics.mean(productivity_scores)
            trend_direction = self._determine_trend_direction(productivity_scores)

            # Find best and worst sessions
            best_session = max(
                sessions, key=lambda s: productivity_scores[sessions.index(s)]
            )
            worst_session = min(
                sessions, key=lambda s: productivity_scores[sessions.index(s)]
            )

            # Calculate consistency
            consistency_score = 1.0 - (
                statistics.stdev(productivity_scores) / max(avg_score, 0.01)
            )

            # Find peak hours
            peak_hours = []
            for hour, scores in hourly_scores.items():
                if scores:
                    avg_hour_score = statistics.mean(scores)
                    if avg_hour_score > avg_score * 1.1:  # 10% above average
                        peak_hours.append(hour)

            # Analyze factors affecting productivity
            factors = await self._analyze_productivity_factors(
                sessions, productivity_scores
            )

            return ProductivityTrend(
                period=period,
                average_score=avg_score,
                trend_direction=trend_direction,
                best_session=best_session.session_id,
                worst_session=worst_session.session_id,
                consistency_score=max(0.0, consistency_score),
                peak_hours=sorted(peak_hours),
                factors=factors,
            )

        except Exception as e:
            logger.error(f"Error analyzing productivity trends for {period}: {e}")
            raise

    async def _get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get session metrics with caching"""
        if session_id in self._session_cache:
            return self._session_cache[session_id]

        metrics = await self.telemetry.get_session_metrics(session_id)
        if metrics:
            self._session_cache[session_id] = metrics

        return metrics

    async def _get_recent_sessions(self, days: int) -> List[SessionMetrics]:
        """Get recent sessions for analysis"""
        try:
            # Query for recent sessions
            query = f"""
            SELECT DISTINCT session_id
            FROM claude_code_logs
            WHERE Timestamp >= now() - INTERVAL {days} DAY
            ORDER BY Timestamp DESC
            LIMIT 50
            """

            results = await self.telemetry.execute_query(query)
            sessions = []

            for result in results:
                session_id = result.get("session_id")
                if session_id:
                    metrics = await self._get_session_metrics(session_id)
                    if metrics:
                        sessions.append(metrics)

            return sessions

        except Exception as e:
            logger.error(f"Error fetching recent sessions: {e}")
            return []

    def _get_session_duration(self, session: SessionMetrics) -> float:
        """Get session duration in hours"""
        if session.end_time:
            return (session.end_time - session.start_time).total_seconds() / 3600
        else:
            # Session ongoing, calculate current duration
            return (datetime.now() - session.start_time).total_seconds() / 3600

    def _calculate_tool_similarity(
        self, tools_a: List[str], tools_b: List[str]
    ) -> float:
        """Calculate similarity between tool usage patterns"""
        if not tools_a or not tools_b:
            return 0.0

        set_a = set(tools_a)
        set_b = set(tools_b)

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        return intersection / union if union > 0 else 0.0

    async def _calculate_productivity_score(self, session: SessionMetrics) -> float:
        """Calculate productivity score for a session"""
        score = 0.0

        # Factor 1: Cost efficiency (30%)
        cost_per_call = session.total_cost / max(session.api_calls, 1)
        if cost_per_call < 0.01:
            score += 0.3
        elif cost_per_call < 0.02:
            score += 0.2
        elif cost_per_call < 0.05:
            score += 0.1

        # Factor 2: Error rate (25%)
        error_rate = session.error_count / max(session.api_calls, 1)
        if error_rate == 0:
            score += 0.25
        elif error_rate < 0.05:
            score += 0.2
        elif error_rate < 0.1:
            score += 0.1

        # Factor 3: Tool diversity (20%)
        tool_diversity = len(set(session.tools_used)) / 10  # Assume 10 is max diversity
        score += min(tool_diversity * 0.2, 0.2)

        # Factor 4: Duration appropriateness (25%)
        duration = self._get_session_duration(session)
        if 0.5 <= duration <= 3.0:  # Sweet spot: 30min - 3hours
            score += 0.25
        elif 0.25 <= duration <= 4.0:  # Acceptable range
            score += 0.15

        return min(score, 1.0)

    def _calculate_cost_efficiency(self, session: SessionMetrics) -> float:
        """Calculate cost efficiency score"""
        cost_per_token = session.total_cost / max(session.total_input_tokens, 1)

        # Scale based on typical costs (adjust thresholds as needed)
        if cost_per_token < 0.0001:  # Very efficient
            return 1.0
        elif cost_per_token < 0.0005:  # Good
            return 0.8
        elif cost_per_token < 0.001:  # Average
            return 0.6
        elif cost_per_token < 0.002:  # Poor
            return 0.4
        else:  # Very poor
            return 0.2

    def _calculate_tool_effectiveness(self, session: SessionMetrics) -> float:
        """Calculate tool usage effectiveness"""
        # Simple heuristic based on tool diversity and usage patterns
        unique_tools = len(set(session.tools_used))
        total_tools = len(session.tools_used)

        if total_tools == 0:
            return 0.0

        diversity_score = unique_tools / min(total_tools, 8)  # Max 8 different tools

        # Check for efficient patterns (Read -> Edit, Grep -> Read, etc.)
        efficiency_bonus = 0.0
        tools = session.tools_used
        for i in range(len(tools) - 1):
            if (tools[i] == "Read" and tools[i + 1] == "Edit") or (
                tools[i] == "Grep" and tools[i + 1] == "Read"
            ):
                efficiency_bonus += 0.1

        return min(diversity_score + efficiency_bonus, 1.0)

    def _calculate_error_resilience(self, session: SessionMetrics) -> float:
        """Calculate error resilience score"""
        if session.api_calls == 0:
            return 1.0

        error_rate = session.error_count / session.api_calls
        return max(
            0.0, 1.0 - (error_rate * 5)
        )  # Each 20% error rate reduces score by 100%

    def _calculate_time_management_score(self, session: SessionMetrics) -> float:
        """Calculate time management effectiveness"""
        duration = self._get_session_duration(session)
        calls_per_hour = session.api_calls / max(duration, 0.01)

        # Optimal range: 10-30 API calls per hour
        if 10 <= calls_per_hour <= 30:
            return 1.0
        elif 5 <= calls_per_hour <= 50:
            return 0.7
        elif 2 <= calls_per_hour <= 80:
            return 0.5
        else:
            return 0.3

    async def _extract_metric_value(
        self, session: SessionMetrics, metric_type: MetricType
    ) -> float:
        """Extract specific metric value from session"""
        if metric_type == MetricType.COST:
            return session.total_cost
        elif metric_type == MetricType.EFFICIENCY:
            return self._calculate_cost_efficiency(session)
        elif metric_type == MetricType.ERROR_RATE:
            return session.error_count / max(session.api_calls, 1)
        elif metric_type == MetricType.DURATION:
            return self._get_session_duration(session)
        elif metric_type == MetricType.PRODUCTIVITY:
            return await self._calculate_productivity_score(session)
        elif metric_type == MetricType.TOOL_USAGE:
            return len(set(session.tools_used))
        else:
            return 0.0

    def _determine_trend_direction(self, values: List[float]) -> TrendDirection:
        """Determine trend direction from a series of values"""
        if len(values) < 3:
            return TrendDirection.STABLE

        # Calculate simple linear trend
        n = len(values)
        x = list(range(n))

        # Simple correlation to determine direction
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(values)

        numerator = sum((x[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

        if denominator == 0:
            return TrendDirection.STABLE

        slope = numerator / denominator

        # Check for volatility
        if len(values) > 4:
            std_dev = statistics.stdev(values)
            mean_val = statistics.mean(values)
            if std_dev / mean_val > 0.5:  # High volatility
                return TrendDirection.VOLATILE

        # Determine direction based on slope
        if slope > 0.05:
            return TrendDirection.IMPROVING
        elif slope < -0.05:
            return TrendDirection.DECLINING
        else:
            return TrendDirection.STABLE

    def _calculate_change_percentage(self, values: List[float]) -> float:
        """Calculate percentage change from first to last value"""
        if len(values) < 2:
            return 0.0

        first_val = values[0]
        last_val = values[-1]

        if first_val == 0:
            return 100.0 if last_val > 0 else 0.0

        return ((last_val - first_val) / first_val) * 100

    def _calculate_trend_confidence(self, values: List[float]) -> float:
        """Calculate confidence in trend analysis"""
        if len(values) < 3:
            return 0.0

        # Based on data consistency and sample size
        consistency = 1.0 - (
            statistics.stdev(values) / max(statistics.mean(values), 0.01)
        )
        sample_size_factor = min(len(values) / 20, 1.0)  # More data = higher confidence

        return max(0.0, min(consistency * sample_size_factor, 1.0))

    def _generate_comparison_insights(
        self,
        metrics_a: SessionMetrics,
        metrics_b: SessionMetrics,
        cost_diff: float,
        efficiency_diff: float,
        duration_diff: float,
        tool_similarity: float,
        productivity_diff: float,
    ) -> List[str]:
        """Generate insights from session comparison"""
        insights = []

        # Cost insights
        if cost_diff > 1.0:
            insights.append(
                f"Session B was ${cost_diff:.2f} more expensive than Session A"
            )
        elif cost_diff < -1.0:
            insights.append(
                f"Session B was ${abs(cost_diff):.2f} less expensive than Session A"
            )

        # Efficiency insights
        if efficiency_diff > 0.0005:
            insights.append("Session B was less cost-efficient per token")
        elif efficiency_diff < -0.0005:
            insights.append("Session B was more cost-efficient per token")

        # Tool similarity insights
        if tool_similarity > 0.8:
            insights.append("Sessions used very similar tool patterns")
        elif tool_similarity < 0.3:
            insights.append("Sessions used quite different approaches")

        # Productivity insights
        if productivity_diff > 0.2:
            insights.append("Session B was significantly more productive")
        elif productivity_diff < -0.2:
            insights.append("Session A was significantly more productive")

        return insights

    def _generate_trend_insights(
        self,
        metric_type: MetricType,
        direction: TrendDirection,
        change_percentage: float,
        data_points: List[Tuple[datetime, float]],
    ) -> List[str]:
        """Generate insights from trend analysis"""
        insights = []

        metric_name = metric_type.value.replace("_", " ").title()

        if direction == TrendDirection.IMPROVING:
            insights.append(
                f"{metric_name} is improving over time ({change_percentage:+.1f}%)"
            )
        elif direction == TrendDirection.DECLINING:
            insights.append(
                f"{metric_name} is declining over time ({change_percentage:+.1f}%)"
            )
        elif direction == TrendDirection.VOLATILE:
            insights.append(
                f"{metric_name} shows high volatility - consider investigating causes"
            )
        else:
            insights.append(f"{metric_name} remains stable")

        # Additional insights based on metric type
        if metric_type == MetricType.COST and direction == TrendDirection.IMPROVING:
            insights.append(
                "Consider analyzing successful cost optimization strategies"
            )
        elif (
            metric_type == MetricType.ERROR_RATE
            and direction == TrendDirection.DECLINING
        ):
            insights.append("Error recovery strategies appear to be working well")

        return insights

    async def _analyze_productivity_factors(
        self, sessions: List[SessionMetrics], scores: List[float]
    ) -> Dict[str, float]:
        """Analyze factors that correlate with productivity"""
        factors = {}

        # Hour of day correlation
        hour_scores = {}
        for i, session in enumerate(sessions):
            hour = session.start_time.hour
            if hour not in hour_scores:
                hour_scores[hour] = []
            hour_scores[hour].append(scores[i])

        # Find best performing hours
        avg_score = statistics.mean(scores)
        for hour, hour_score_list in hour_scores.items():
            if len(hour_score_list) >= 2:  # Need multiple data points
                hour_avg = statistics.mean(hour_score_list)
                correlation = (hour_avg - avg_score) / avg_score
                if abs(correlation) > 0.1:  # Significant correlation
                    factors[f"Hour {hour}"] = correlation

        # Session duration correlation
        short_sessions = [
            scores[i]
            for i, s in enumerate(sessions)
            if self._get_session_duration(s) < 1.0
        ]
        long_sessions = [
            scores[i]
            for i, s in enumerate(sessions)
            if self._get_session_duration(s) > 3.0
        ]

        if short_sessions and len(short_sessions) >= 2:
            factors["Short sessions (<1h)"] = (
                statistics.mean(short_sessions) - avg_score
            ) / avg_score
        if long_sessions and len(long_sessions) >= 2:
            factors["Long sessions (>3h)"] = (
                statistics.mean(long_sessions) - avg_score
            ) / avg_score

        return factors
