"""
Cache-Enhanced Context Health Dashboard

This module provides an intelligent dashboard that leverages cache analysis
to provide usage-based context health scoring and optimization insights.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from ..analysis import (
    CacheDiscoveryService,
    SessionCacheParser,
    UsagePatternAnalyzer,
    TokenEfficiencyAnalyzer,
    TemporalContextAnalyzer,
    EnhancedContextAnalyzer,
    CrossSessionCorrelationAnalyzer,
    UsagePatternSummary,
    TokenAnalysisSummary,
    TemporalInsights,
    CacheEnhancedAnalysis,
    CorrelationInsights,
)
from ..analytics.context_health_scorer import ContextHealthScorer, HealthScore
from ..analytics.advanced_patterns import AdvancedPatternRecognizer


class HealthLevel(Enum):
    """Context health levels based on usage patterns."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class UsageBasedHealthMetrics:
    """Usage-weighted context health metrics."""

    usage_weighted_focus_score: float
    efficiency_score: float
    temporal_coherence_score: float
    cross_session_consistency: float
    optimization_potential: float
    waste_reduction_score: float
    workflow_alignment: float

    @property
    def overall_health_score(self) -> float:
        """Calculate overall health score from component metrics."""
        weights = {
            "usage_weighted_focus_score": 0.25,
            "efficiency_score": 0.20,
            "temporal_coherence_score": 0.15,
            "cross_session_consistency": 0.15,
            "optimization_potential": 0.10,
            "waste_reduction_score": 0.10,
            "workflow_alignment": 0.05,
        }

        return sum(getattr(self, metric) * weight for metric, weight in weights.items())

    @property
    def health_level(self) -> HealthLevel:
        """Determine health level from overall score."""
        score = self.overall_health_score
        if score >= 0.9:
            return HealthLevel.EXCELLENT
        elif score >= 0.75:
            return HealthLevel.GOOD
        elif score >= 0.6:
            return HealthLevel.FAIR
        elif score >= 0.4:
            return HealthLevel.POOR
        else:
            return HealthLevel.CRITICAL


@dataclass
class UsageInsight:
    """Individual usage-based insight."""

    type: str
    title: str
    description: str
    impact_score: float
    recommendation: str
    file_patterns: List[str]
    session_correlation: float


@dataclass
class CacheEnhancedDashboardData:
    """Complete dashboard data with cache-enhanced metrics."""

    # Basic metrics
    context_size: int
    file_count: int
    session_count: int
    analysis_timestamp: datetime

    # Usage-based health metrics
    health_metrics: UsageBasedHealthMetrics

    # Cache analysis results
    usage_summary: UsagePatternSummary
    token_analysis: TokenAnalysisSummary
    temporal_insights: TemporalInsights
    enhanced_analysis: CacheEnhancedAnalysis
    correlation_insights: CorrelationInsights

    # Traditional health analysis (enhanced with cache data)
    traditional_health: HealthScore

    # Usage-based insights and recommendations
    insights: List[UsageInsight]
    optimization_recommendations: List[Dict[str, Any]]

    # Trending data
    usage_trends: Dict[str, List[float]]
    efficiency_trends: Dict[str, List[float]]


class CacheEnhancedDashboard:
    """
    Intelligent dashboard that combines traditional context analysis
    with cache-based usage patterns for enhanced insights.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the cache-enhanced dashboard."""
        self.cache_discovery = CacheDiscoveryService()
        self.session_parser = SessionCacheParser()
        self.usage_analyzer = UsagePatternAnalyzer()
        self.token_analyzer = TokenEfficiencyAnalyzer()
        self.temporal_analyzer = TemporalContextAnalyzer()
        self.enhanced_analyzer = EnhancedContextAnalyzer()
        self.correlation_analyzer = CrossSessionCorrelationAnalyzer()

        # Traditional analyzers (enhanced with cache data)
        self.health_scorer = ContextHealthScorer()
        self.pattern_analyzer = AdvancedPatternRecognizer()

        self._cache_dir = cache_dir
        self._analysis_cache: Dict[str, Any] = {}

    async def generate_dashboard(
        self,
        context_path: Optional[Path] = None,
        include_cross_session: bool = True,
        max_sessions: int = 50,
    ) -> CacheEnhancedDashboardData:
        """
        Generate comprehensive cache-enhanced dashboard data.

        Args:
            context_path: Path to context file (if analyzing specific context)
            include_cross_session: Whether to include cross-session analysis
            max_sessions: Maximum number of sessions to analyze

        Returns:
            Complete dashboard data with usage-based insights
        """
        try:
            # Discover cache locations
            cache_locations = await self._discover_cache_locations()

            if not cache_locations:
                return await self._generate_basic_dashboard(context_path)

            # Parse sessions from cache
            sessions = await self._parse_recent_sessions(cache_locations, max_sessions)

            if not sessions:
                return await self._generate_basic_dashboard(context_path)

            # Run all analyses in parallel for efficiency
            analysis_tasks = [
                self._analyze_usage_patterns(sessions),
                self._analyze_token_efficiency(sessions),
                self._analyze_temporal_patterns(sessions),
                self._analyze_enhanced_context(sessions, context_path),
            ]

            if include_cross_session:
                analysis_tasks.append(self._analyze_cross_session_correlation(sessions))

            analysis_results = await asyncio.gather(*analysis_tasks)

            # Unpack results
            usage_summary = analysis_results[0]
            token_analysis = analysis_results[1]
            temporal_insights = analysis_results[2]
            enhanced_analysis = analysis_results[3]
            correlation_insights = (
                analysis_results[4] if include_cross_session else None
            )

            # Generate traditional health analysis (enhanced with cache data)
            traditional_health = await self._generate_enhanced_health_analysis(
                context_path, enhanced_analysis
            )

            # Calculate usage-based health metrics
            health_metrics = self._calculate_usage_health_metrics(
                usage_summary,
                token_analysis,
                temporal_insights,
                enhanced_analysis,
                correlation_insights,
            )

            # Generate insights and recommendations
            insights = self._generate_usage_insights(
                usage_summary,
                token_analysis,
                temporal_insights,
                enhanced_analysis,
                correlation_insights,
            )

            recommendations = self._generate_optimization_recommendations(
                health_metrics, insights, enhanced_analysis
            )

            # Generate trending data
            usage_trends, efficiency_trends = self._calculate_trends(
                sessions, usage_summary, token_analysis
            )

            return CacheEnhancedDashboardData(
                context_size=(
                    enhanced_analysis.weighted_context_size if enhanced_analysis else 0
                ),
                file_count=len(usage_summary.file_patterns) if usage_summary else 0,
                session_count=len(sessions),
                analysis_timestamp=datetime.now(),
                health_metrics=health_metrics,
                usage_summary=usage_summary,
                token_analysis=token_analysis,
                temporal_insights=temporal_insights,
                enhanced_analysis=enhanced_analysis,
                correlation_insights=correlation_insights
                or CorrelationInsights(
                    session_clusters=[],
                    cross_session_patterns=[],
                    long_term_trends=[],
                    total_sessions_analyzed=0,
                    analysis_time_span_days=0,
                    file_usage_correlations={},
                    tool_usage_correlations={},
                    temporal_correlations={},
                    session_dependencies=[],
                    workflow_continuations=[],
                    complexity_evolution=[],
                    efficiency_evolution=[],
                    focus_evolution=[],
                    predicted_next_patterns=[],
                    recommended_session_timing=[],
                    optimal_workflow_sequences=[],
                    analysis_confidence=0.5,
                    data_completeness=0.5,
                ),
                traditional_health=traditional_health,
                insights=insights,
                optimization_recommendations=recommendations,
                usage_trends=usage_trends,
                efficiency_trends=efficiency_trends,
            )

        except Exception as e:
            # Fallback to basic dashboard on any error
            print(f"Cache analysis failed, using basic dashboard: {e}")
            return await self._generate_basic_dashboard(context_path)

    async def _discover_cache_locations(self) -> List[Path]:
        """Discover Claude Code cache locations."""
        try:
            locations = await asyncio.to_thread(
                self.cache_discovery.discover_cache_locations
            )
            return [loc.path for loc in locations if loc.path.exists()]
        except Exception:
            return []

    async def _parse_recent_sessions(
        self, cache_paths: List[Path], max_sessions: int
    ) -> List[Any]:
        """Parse recent sessions from cache files."""
        all_sessions = []

        for cache_path in cache_paths:
            try:
                sessions = await asyncio.to_thread(
                    self.session_parser.parse_cache_directory, cache_path, max_sessions
                )
                all_sessions.extend(sessions)
            except Exception:
                continue

        # Sort by timestamp and limit
        all_sessions.sort(key=lambda s: s.timestamp, reverse=True)
        return all_sessions[:max_sessions]

    async def _analyze_usage_patterns(self, sessions: List[Any]) -> UsagePatternSummary:
        """Analyze usage patterns from sessions."""
        return await asyncio.to_thread(
            self.usage_analyzer.analyze_usage_patterns, sessions
        )

    async def _analyze_token_efficiency(
        self, sessions: List[Any]
    ) -> TokenAnalysisSummary:
        """Analyze token efficiency from sessions."""
        return await asyncio.to_thread(
            self.token_analyzer.analyze_token_efficiency, sessions
        )

    async def _analyze_temporal_patterns(self, sessions: List[Any]) -> TemporalInsights:
        """Analyze temporal patterns from sessions."""
        return await asyncio.to_thread(
            self.temporal_analyzer.analyze_temporal_patterns, sessions
        )

    async def _analyze_enhanced_context(
        self, sessions: List[Any], context_path: Optional[Path]
    ) -> CacheEnhancedAnalysis:
        """Run enhanced context analysis with cache data."""
        return await asyncio.to_thread(
            self.enhanced_analyzer.analyze_with_cache_data, sessions, context_path
        )

    async def _analyze_cross_session_correlation(
        self, sessions: List[Any]
    ) -> CorrelationInsights:
        """Analyze cross-session correlations."""
        return await asyncio.to_thread(
            self.correlation_analyzer.analyze_cross_session_patterns, sessions
        )

    async def _generate_enhanced_health_analysis(
        self, context_path: Optional[Path], enhanced_analysis: CacheEnhancedAnalysis
    ) -> HealthScore:
        """Generate traditional health analysis enhanced with cache insights."""
        if context_path and context_path.exists():
            health_report = await asyncio.to_thread(
                self.health_scorer.calculate_health_score, context_data
            )
            # Enhance with cache data
            if enhanced_analysis:
                health_report.focus_score = enhanced_analysis.usage_weighted_focus_score
                health_report.priority_alignment = (
                    enhanced_analysis.priority_alignment_score
                )
            return health_report
        else:
            # Generate synthetic health report from cache data
            return HealthScore(
                overall_score=int(
                    (
                        enhanced_analysis.overall_health_score
                        if enhanced_analysis
                        else 0.5
                    )
                    * 100
                ),
                component_scores={
                    "focus": int(
                        (
                            enhanced_analysis.usage_weighted_focus_score
                            if enhanced_analysis
                            else 0.5
                        )
                        * 100
                    ),
                    "priority_alignment": int(
                        (
                            enhanced_analysis.priority_alignment_score
                            if enhanced_analysis
                            else 0.5
                        )
                        * 100
                    ),
                    "redundancy": 30,
                    "recency": 70,
                    "size_optimization": 40,
                },
                confidence=0.8,
                model_used="cache_enhanced",
                factors={"enhanced_analysis": enhanced_analysis is not None},
                recommendations=["Cache-enhanced analysis completed"],
                timestamp=datetime.now().isoformat(),
            )

    def _calculate_usage_health_metrics(
        self,
        usage_summary: Optional[UsagePatternSummary],
        token_analysis: Optional[TokenAnalysisSummary],
        temporal_insights: Optional[TemporalInsights],
        enhanced_analysis: Optional[CacheEnhancedAnalysis],
        correlation_insights: Optional[CorrelationInsights],
    ) -> UsageBasedHealthMetrics:
        """Calculate comprehensive usage-based health metrics."""

        # Usage-weighted focus score (primary metric)
        focus_score = (
            enhanced_analysis.usage_weighted_focus_score if enhanced_analysis else 0.5
        )

        # Token efficiency score
        efficiency_score = (
            1.0 - (token_analysis.waste_percentage / 100.0) if token_analysis else 0.6
        )

        # Temporal coherence score
        coherence_score = (
            temporal_insights.coherence_score if temporal_insights else 0.5
        )

        # Cross-session consistency
        consistency_score = (
            correlation_insights.correlation_strength if correlation_insights else 0.5
        )

        # Optimization potential (inverse of current efficiency)
        optimization_potential = (
            1.0 - efficiency_score if efficiency_score < 0.8 else 0.2
        )

        # Waste reduction score
        waste_score = efficiency_score  # Same as efficiency for now

        # Workflow alignment score
        workflow_score = usage_summary.workflow_efficiency if usage_summary else 0.6

        return UsageBasedHealthMetrics(
            usage_weighted_focus_score=focus_score,
            efficiency_score=efficiency_score,
            temporal_coherence_score=coherence_score,
            cross_session_consistency=consistency_score,
            optimization_potential=optimization_potential,
            waste_reduction_score=waste_score,
            workflow_alignment=workflow_score,
        )

    def _generate_usage_insights(
        self,
        usage_summary: Optional[UsagePatternSummary],
        token_analysis: Optional[TokenAnalysisSummary],
        temporal_insights: Optional[TemporalInsights],
        enhanced_analysis: Optional[CacheEnhancedAnalysis],
        correlation_insights: Optional[CorrelationInsights],
    ) -> List[UsageInsight]:
        """Generate actionable usage-based insights."""
        insights = []

        # Token waste insights
        if token_analysis and token_analysis.waste_percentage > 20:
            insights.append(
                UsageInsight(
                    type="token_efficiency",
                    title="High Token Waste Detected",
                    description=f"Analysis shows {token_analysis.waste_percentage:.1f}% token waste in recent sessions",
                    impact_score=0.8,
                    recommendation="Consider removing redundant context or consolidating similar files",
                    file_patterns=[
                        pattern.pattern for pattern in token_analysis.waste_patterns[:3]
                    ],
                    session_correlation=0.7,
                )
            )

        # Usage pattern insights
        if usage_summary and usage_summary.workflow_efficiency < 0.6:
            insights.append(
                UsageInsight(
                    type="workflow_efficiency",
                    title="Low Workflow Efficiency",
                    description=f"Current workflow efficiency is {usage_summary.workflow_efficiency:.1%}",
                    impact_score=0.7,
                    recommendation="Focus context on frequently accessed files and current work patterns",
                    file_patterns=[
                        pattern.file_path for pattern in usage_summary.file_patterns[:3]
                    ],
                    session_correlation=0.8,
                )
            )

        # Temporal coherence insights
        if temporal_insights and temporal_insights.coherence_score < 0.5:
            insights.append(
                UsageInsight(
                    type="temporal_coherence",
                    title="Poor Temporal Context Coherence",
                    description="Context jumps between topics frequently without clear transitions",
                    impact_score=0.6,
                    recommendation="Consider reorganizing context by topic or time-based relevance",
                    file_patterns=[],
                    session_correlation=temporal_insights.coherence_score,
                )
            )

        # Cross-session insights
        if correlation_insights and correlation_insights.correlation_strength > 0.8:
            insights.append(
                UsageInsight(
                    type="cross_session_opportunity",
                    title="Strong Cross-Session Patterns Found",
                    description=f"Found {len(correlation_insights.cross_session_patterns)} repeating patterns",
                    impact_score=0.5,
                    recommendation="Consider creating templates or shortcuts for common workflows",
                    file_patterns=[],
                    session_correlation=correlation_insights.correlation_strength,
                )
            )

        return sorted(insights, key=lambda i: i.impact_score, reverse=True)[:5]

    def _generate_optimization_recommendations(
        self,
        health_metrics: UsageBasedHealthMetrics,
        insights: List[UsageInsight],
        enhanced_analysis: Optional[CacheEnhancedAnalysis],
    ) -> List[Dict[str, Any]]:
        """Generate specific optimization recommendations."""
        recommendations = []

        # Based on overall health level
        health_level = health_metrics.health_level

        if health_level in [HealthLevel.POOR, HealthLevel.CRITICAL]:
            recommendations.append(
                {
                    "priority": "high",
                    "title": "Immediate Optimization Required",
                    "description": f"Context health is {health_level.value} - immediate action recommended",
                    "actions": [
                        "Run aggressive optimization to remove redundant content",
                        "Focus on most recently and frequently accessed files",
                        "Remove stale context older than 7 days",
                    ],
                    "estimated_impact": "30-50% size reduction",
                }
            )

        # Based on specific metrics
        if health_metrics.efficiency_score < 0.5:
            recommendations.append(
                {
                    "priority": "high",
                    "title": "Improve Token Efficiency",
                    "description": "High token waste detected in current context",
                    "actions": [
                        "Remove duplicate file reads and redundant context",
                        "Consolidate similar conversations",
                        "Use summarization for verbose sections",
                    ],
                    "estimated_impact": "20-35% efficiency improvement",
                }
            )

        if health_metrics.temporal_coherence_score < 0.6:
            recommendations.append(
                {
                    "priority": "medium",
                    "title": "Improve Context Organization",
                    "description": "Context lacks clear topical organization",
                    "actions": [
                        "Group related files and conversations",
                        "Remove context that doesn't relate to current work",
                        "Maintain chronological order within topics",
                    ],
                    "estimated_impact": "Better focus and comprehension",
                }
            )

        # Usage-specific recommendations
        for insight in insights:
            if insight.impact_score > 0.7:
                recommendations.append(
                    {
                        "priority": "medium" if insight.impact_score < 0.8 else "high",
                        "title": f"Address {insight.title}",
                        "description": insight.description,
                        "actions": [insight.recommendation],
                        "estimated_impact": f"{insight.impact_score:.0%} improvement potential",
                    }
                )

        return recommendations[:6]  # Limit to top 6 recommendations

    def _calculate_trends(
        self,
        sessions: List[Any],
        usage_summary: Optional[UsagePatternSummary],
        token_analysis: Optional[TokenAnalysisSummary],
    ) -> Tuple[Dict[str, List[float]], Dict[str, List[float]]]:
        """Calculate trending data for visualization."""
        # Group sessions by day and calculate metrics
        daily_sessions: Dict[str, List[Any]] = {}

        for session in sessions[-30:]:  # Last 30 sessions
            day_key = session.timestamp.date().isoformat()
            if day_key not in daily_sessions:
                daily_sessions[day_key] = []
            daily_sessions[day_key].append(session)

        usage_trends = {
            "focus_score": [],
            "workflow_efficiency": [],
            "context_size": [],
        }

        efficiency_trends = {
            "token_efficiency": [],
            "waste_percentage": [],
            "cache_hit_rate": [],
        }

        # Calculate daily trends (simplified for demonstration)
        for day_key in sorted(daily_sessions.keys())[-7:]:  # Last 7 days
            day_sessions = daily_sessions[day_key]

            # Simplified trend calculation
            usage_trends["focus_score"].append(0.7)  # Placeholder
            usage_trends["workflow_efficiency"].append(0.6)  # Placeholder
            usage_trends["context_size"].append(len(day_sessions) * 1000)  # Placeholder

            efficiency_trends["token_efficiency"].append(0.75)  # Placeholder
            efficiency_trends["waste_percentage"].append(25.0)  # Placeholder
            efficiency_trends["cache_hit_rate"].append(0.85)  # Placeholder

        return usage_trends, efficiency_trends

    async def _generate_basic_dashboard(
        self, context_path: Optional[Path]
    ) -> CacheEnhancedDashboardData:
        """Generate basic dashboard when cache analysis is unavailable."""
        # Generate traditional health analysis only
        traditional_health = HealthScore(
            overall_score=50,
            component_scores={
                "focus": 50,
                "priority_alignment": 50,
                "context_health": 50,
                "redundancy": 30,
                "recency": 70,
                "size_optimization": 40,
            },
            confidence=0.6,
            model_used="traditional",
            factors={"fallback": True},
            recommendations=["Traditional health analysis completed"],
            timestamp=datetime.now().isoformat(),
        )

        if context_path and context_path.exists():
            try:
                traditional_health = await asyncio.to_thread(
                    self.health_scorer.calculate_health_score, context_data
                )
            except Exception:
                pass

        # Create minimal health metrics
        health_metrics = UsageBasedHealthMetrics(
            usage_weighted_focus_score=traditional_health.component_scores.get(
                "focus", 50
            )
            / 100.0,
            efficiency_score=0.6,
            temporal_coherence_score=0.5,
            cross_session_consistency=0.5,
            optimization_potential=0.4,
            waste_reduction_score=0.6,
            workflow_alignment=0.5,
        )

        return CacheEnhancedDashboardData(
            context_size=0,
            file_count=0,
            session_count=0,
            analysis_timestamp=datetime.now(),
            health_metrics=health_metrics,
            usage_summary=None,
            token_analysis=None,
            temporal_insights=None,
            enhanced_analysis=None,
            correlation_insights=CorrelationInsights(
                session_clusters=[],
                cross_session_patterns=[],
                long_term_trends=[],
                total_sessions_analyzed=0,
                analysis_time_span_days=0,
                file_usage_correlations={},
                tool_usage_correlations={},
                temporal_correlations={},
                session_dependencies=[],
                workflow_continuations=[],
                complexity_evolution=[],
                efficiency_evolution=[],
                focus_evolution=[],
                predicted_next_patterns=[],
                recommended_session_timing=[],
                optimal_workflow_sequences=[],
                analysis_confidence=0.5,
                data_completeness=0.5,
            ),
            traditional_health=traditional_health,
            insights=[],
            optimization_recommendations=[
                {
                    "priority": "medium",
                    "title": "Enable Cache Analysis",
                    "description": "Cache analysis unavailable - limited insights available",
                    "actions": [
                        "Ensure Claude Code cache is accessible",
                        "Run more sessions to build analysis data",
                    ],
                    "estimated_impact": "Enable full optimization capabilities",
                }
            ],
            usage_trends={},
            efficiency_trends={},
        )
