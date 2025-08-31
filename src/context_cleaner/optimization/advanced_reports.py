"""
Advanced Reporting System with Usage-Based Insights

This module provides comprehensive reporting capabilities that leverage
cache analysis and cross-session data for detailed optimization insights.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import statistics
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64

from .cache_dashboard import (
    CacheEnhancedDashboardData,
    UsageBasedHealthMetrics,
    HealthLevel,
)
from .cross_session_analytics import (
    CrossSessionInsights,
    PatternEvolution,
    WorkflowTemplate,
)
from .intelligent_recommender import IntelligentRecommendation, PersonalizationProfile


class ReportFormat(Enum):
    """Available report output formats."""

    JSON = "json"
    HTML = "html"
    MARKDOWN = "markdown"
    PDF = "pdf"


class ReportType(Enum):
    """Types of reports available."""

    EXECUTIVE_SUMMARY = "executive_summary"
    DETAILED_ANALYSIS = "detailed_analysis"
    TREND_REPORT = "trend_report"
    OPTIMIZATION_REPORT = "optimization_report"
    PERSONALIZATION_REPORT = "personalization_report"
    COMPARATIVE_ANALYSIS = "comparative_analysis"


@dataclass
class ReportSection:
    """A section within a report."""

    title: str
    content: str
    charts: List[Dict[str, Any]]
    insights: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any]


@dataclass
class UsageReport:
    """Comprehensive usage-based optimization report."""

    report_id: str
    report_type: ReportType
    generated_at: datetime
    time_period: Dict[str, datetime]

    # Report content
    executive_summary: str
    sections: List[ReportSection]

    # Key metrics
    key_metrics: Dict[str, Any]
    performance_indicators: Dict[str, float]
    trend_analysis: Dict[str, List[float]]

    # Insights and recommendations
    critical_insights: List[str]
    optimization_recommendations: List[Dict[str, Any]]
    automation_opportunities: List[Dict[str, Any]]

    # Supporting data
    charts_data: List[Dict[str, Any]]
    raw_data: Dict[str, Any]

    # Metadata
    confidence_score: float
    data_completeness: float
    next_analysis_date: datetime


class AdvancedReportingSystem:
    """
    Advanced reporting system that generates comprehensive reports
    with usage-based insights and actionable recommendations.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the advanced reporting system."""
        self.storage_path = storage_path or Path.home() / ".context_cleaner" / "reports"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._report_templates: Dict[ReportType, Dict[str, Any]] = {}
        self._report_cache: Dict[str, UsageReport] = {}
        self._visualization_cache: Dict[str, str] = {}

    async def generate_comprehensive_report(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
        personalization_profile: Optional[PersonalizationProfile] = None,
        report_type: ReportType = ReportType.DETAILED_ANALYSIS,
        output_format: ReportFormat = ReportFormat.HTML,
        time_period_days: int = 30,
    ) -> UsageReport:
        """
        Generate a comprehensive usage-based optimization report.

        Args:
            dashboard_data: Cache-enhanced dashboard data
            cross_session_insights: Cross-session analysis results
            recommendations: Intelligent recommendations
            personalization_profile: User personalization profile
            report_type: Type of report to generate
            output_format: Output format for the report
            time_period_days: Time period for analysis

        Returns:
            Comprehensive usage report
        """
        report_id = f"{report_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Calculate time period
        end_date = datetime.now()
        start_date = end_date - timedelta(days=time_period_days)
        time_period = {"start": start_date, "end": end_date}

        # Generate executive summary
        executive_summary = await self._generate_executive_summary(
            dashboard_data, cross_session_insights, recommendations
        )

        # Generate report sections based on type
        sections = await self._generate_report_sections(
            report_type,
            dashboard_data,
            cross_session_insights,
            recommendations,
            personalization_profile,
        )

        # Extract key metrics
        key_metrics = self._extract_key_metrics(dashboard_data, cross_session_insights)

        # Calculate performance indicators
        performance_indicators = self._calculate_performance_indicators(
            dashboard_data, cross_session_insights
        )

        # Generate trend analysis
        trend_analysis = self._generate_trend_analysis(
            dashboard_data, cross_session_insights
        )

        # Extract critical insights
        critical_insights = self._extract_critical_insights(
            dashboard_data, cross_session_insights, recommendations
        )

        # Format optimization recommendations
        optimization_recommendations = self._format_optimization_recommendations(
            recommendations
        )

        # Extract automation opportunities
        automation_opportunities = cross_session_insights.automation_opportunities

        # Generate charts and visualizations
        charts_data = await self._generate_charts_data(
            dashboard_data, cross_session_insights, trend_analysis
        )

        # Prepare raw data
        raw_data = {
            "dashboard_data": asdict(dashboard_data),
            "cross_session_insights": asdict(cross_session_insights),
            "recommendations": [asdict(r) for r in recommendations],
        }

        # Calculate confidence and completeness scores
        confidence_score = self._calculate_confidence_score(
            dashboard_data, cross_session_insights
        )
        data_completeness = self._calculate_data_completeness(
            dashboard_data, cross_session_insights
        )

        # Calculate next analysis date
        next_analysis_date = end_date + timedelta(days=7)  # Weekly analysis

        report = UsageReport(
            report_id=report_id,
            report_type=report_type,
            generated_at=datetime.now(),
            time_period=time_period,
            executive_summary=executive_summary,
            sections=sections,
            key_metrics=key_metrics,
            performance_indicators=performance_indicators,
            trend_analysis=trend_analysis,
            critical_insights=critical_insights,
            optimization_recommendations=optimization_recommendations,
            automation_opportunities=automation_opportunities,
            charts_data=charts_data,
            raw_data=raw_data,
            confidence_score=confidence_score,
            data_completeness=data_completeness,
            next_analysis_date=next_analysis_date,
        )

        # Cache report
        self._report_cache[report_id] = report

        # Persist report
        await self._persist_report(report, output_format)

        return report

    async def _generate_executive_summary(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
    ) -> str:
        """Generate executive summary of key findings."""
        health_level = dashboard_data.health_metrics.health_level
        overall_score = dashboard_data.health_metrics.overall_health_score
        sessions_analyzed = cross_session_insights.sessions_analyzed

        critical_recs = [
            r for r in recommendations if r.priority.value in ["critical", "high"]
        ]

        summary_parts = []

        # Health status
        summary_parts.append(
            f"**Context Health Status**: {health_level.value.title()} "
            f"(Score: {overall_score:.1%})"
        )

        # Analysis scope
        summary_parts.append(
            f"**Analysis Coverage**: {sessions_analyzed} sessions analyzed "
            f"over {cross_session_insights.time_span_days} days"
        )

        # Key findings
        if health_level in [HealthLevel.POOR, HealthLevel.CRITICAL]:
            summary_parts.append(
                "**Key Finding**: Context health requires immediate attention. "
                f"{len(critical_recs)} high-priority optimizations identified."
            )
        elif health_level == HealthLevel.EXCELLENT:
            summary_parts.append(
                "**Key Finding**: Context is well-optimized. Focus on maintaining "
                "current performance and leveraging automation opportunities."
            )
        else:
            summary_parts.append(
                f"**Key Finding**: Context shows {health_level.value} performance "
                f"with {len(critical_recs)} optimization opportunities identified."
            )

        # Efficiency insights
        if dashboard_data.token_analysis:
            waste_pct = dashboard_data.token_analysis.waste_percentage
            summary_parts.append(
                f"**Token Efficiency**: {100-waste_pct:.1f}% efficient "
                f"({waste_pct:.1f}% waste identified)"
            )

        # Usage patterns
        if dashboard_data.usage_summary:
            workflow_eff = dashboard_data.usage_summary.workflow_efficiency
            summary_parts.append(
                f"**Workflow Alignment**: {workflow_eff:.1%} efficiency "
                "based on actual usage patterns"
            )

        # Automation potential
        automation_count = len(cross_session_insights.automation_opportunities)
        if automation_count > 0:
            summary_parts.append(
                f"**Automation Potential**: {automation_count} processes "
                "identified for potential automation"
            )

        return "\n\n".join(summary_parts)

    async def _generate_report_sections(
        self,
        report_type: ReportType,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
        personalization_profile: Optional[PersonalizationProfile],
    ) -> List[ReportSection]:
        """Generate report sections based on report type."""
        sections = []

        if report_type == ReportType.EXECUTIVE_SUMMARY:
            sections.extend(
                await self._generate_executive_sections(
                    dashboard_data, cross_session_insights, recommendations
                )
            )
        elif report_type == ReportType.DETAILED_ANALYSIS:
            sections.extend(
                await self._generate_detailed_sections(
                    dashboard_data, cross_session_insights, recommendations
                )
            )
        elif report_type == ReportType.TREND_REPORT:
            sections.extend(
                await self._generate_trend_sections(
                    dashboard_data, cross_session_insights
                )
            )
        elif report_type == ReportType.OPTIMIZATION_REPORT:
            sections.extend(
                await self._generate_optimization_sections(
                    recommendations, cross_session_insights
                )
            )
        elif report_type == ReportType.PERSONALIZATION_REPORT:
            sections.extend(
                await self._generate_personalization_sections(
                    personalization_profile, recommendations
                )
            )
        elif report_type == ReportType.COMPARATIVE_ANALYSIS:
            sections.extend(
                await self._generate_comparative_sections(
                    dashboard_data, cross_session_insights
                )
            )

        return sections

    async def _generate_executive_sections(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
    ) -> List[ReportSection]:
        """Generate executive-level sections."""
        sections = []

        # Health Overview
        health_content = self._format_health_overview(dashboard_data.health_metrics)
        sections.append(
            ReportSection(
                title="Context Health Overview",
                content=health_content,
                charts=[
                    {
                        "type": "health_gauge",
                        "data": asdict(dashboard_data.health_metrics),
                    }
                ],
                insights=[
                    f"Overall health score: {dashboard_data.health_metrics.overall_health_score:.1%}",
                    f"Usage-weighted focus: {dashboard_data.health_metrics.usage_weighted_focus_score:.1%}",
                    f"Token efficiency: {dashboard_data.health_metrics.efficiency_score:.1%}",
                ],
                recommendations=[r.title for r in recommendations[:3]],
                metadata={"importance": "high", "audience": "executive"},
            )
        )

        # Key Performance Indicators
        kpi_content = self._format_kpi_summary(cross_session_insights)
        sections.append(
            ReportSection(
                title="Key Performance Indicators",
                content=kpi_content,
                charts=[
                    {
                        "type": "kpi_dashboard",
                        "data": cross_session_insights.efficiency_trends,
                    }
                ],
                insights=[
                    f"User adaptation score: {cross_session_insights.user_adaptation_score:.1%}",
                    f"Sessions analyzed: {cross_session_insights.sessions_analyzed}",
                    f"Workflow templates identified: {len(cross_session_insights.workflow_templates)}",
                ],
                recommendations=[],
                metadata={"importance": "medium", "audience": "executive"},
            )
        )

        return sections

    async def _generate_detailed_sections(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
    ) -> List[ReportSection]:
        """Generate detailed analysis sections."""
        sections = []

        # Usage Pattern Analysis
        if dashboard_data.usage_summary:
            usage_content = self._format_usage_analysis(dashboard_data.usage_summary)
            sections.append(
                ReportSection(
                    title="Usage Pattern Analysis",
                    content=usage_content,
                    charts=[
                        {"type": "usage_heatmap", "data": dashboard_data.usage_trends}
                    ],
                    insights=[
                        f"Workflow efficiency: {dashboard_data.usage_summary.workflow_efficiency:.1%}",
                        f"File patterns identified: {len(dashboard_data.usage_summary.file_patterns)}",
                        f"Most accessed files show clear usage patterns",
                    ],
                    recommendations=[
                        r.title
                        for r in recommendations
                        if r.category.value == "workflow_alignment"
                    ],
                    metadata={"importance": "high", "technical_level": "detailed"},
                )
            )

        # Token Efficiency Deep Dive
        if dashboard_data.token_analysis:
            token_content = self._format_token_analysis(dashboard_data.token_analysis)
            sections.append(
                ReportSection(
                    title="Token Efficiency Analysis",
                    content=token_content,
                    charts=[
                        {
                            "type": "waste_breakdown",
                            "data": dashboard_data.efficiency_trends,
                        }
                    ],
                    insights=[
                        f"Token waste: {dashboard_data.token_analysis.waste_percentage:.1f}%",
                        f"Efficiency opportunities: {len(dashboard_data.token_analysis.waste_patterns)}",
                        f"Cache optimization potential identified",
                    ],
                    recommendations=[
                        r.title
                        for r in recommendations
                        if r.category.value == "token_efficiency"
                    ],
                    metadata={"importance": "high", "technical_level": "detailed"},
                )
            )

        # Cross-Session Patterns
        pattern_content = self._format_pattern_analysis(cross_session_insights)
        sections.append(
            ReportSection(
                title="Cross-Session Pattern Analysis",
                content=pattern_content,
                charts=[
                    {
                        "type": "pattern_evolution",
                        "data": cross_session_insights.pattern_evolution,
                    }
                ],
                insights=[
                    f"Patterns tracked: {len(cross_session_insights.pattern_evolution)}",
                    f"Session clusters: {len(cross_session_insights.session_clusters)}",
                    f"Automation opportunities: {len(cross_session_insights.automation_opportunities)}",
                ],
                recommendations=cross_session_insights.optimization_recommendations,
                metadata={"importance": "medium", "technical_level": "detailed"},
            )
        )

        return sections

    async def _generate_trend_sections(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> List[ReportSection]:
        """Generate trend analysis sections."""
        sections = []

        # Efficiency Trends
        trend_content = self._format_trend_analysis(
            cross_session_insights.efficiency_trends
        )
        sections.append(
            ReportSection(
                title="Efficiency Trends Over Time",
                content=trend_content,
                charts=[
                    {
                        "type": "line_chart",
                        "data": cross_session_insights.efficiency_trends,
                    }
                ],
                insights=[
                    "Overall efficiency shows positive trend",
                    "Focus improvement correlates with optimization actions",
                    "Session productivity varies with context size",
                ],
                recommendations=[
                    "Continue current optimization strategy",
                    "Monitor for trend reversals",
                ],
                metadata={"importance": "medium", "time_series": True},
            )
        )

        # Pattern Evolution
        evolution_content = self._format_pattern_evolution(
            cross_session_insights.pattern_evolution
        )
        sections.append(
            ReportSection(
                title="Pattern Evolution Analysis",
                content=evolution_content,
                charts=[
                    {
                        "type": "evolution_chart",
                        "data": cross_session_insights.pattern_evolution,
                    }
                ],
                insights=[
                    "Workflow patterns show increasing stability",
                    "User adaptation to optimization suggestions is positive",
                    "Some patterns could benefit from automation",
                ],
                recommendations=[
                    "Implement automation for stable patterns",
                    "Continue monitoring adaptation",
                ],
                metadata={"importance": "low", "predictive": True},
            )
        )

        return sections

    async def _generate_optimization_sections(
        self,
        recommendations: List[IntelligentRecommendation],
        cross_session_insights: CrossSessionInsights,
    ) -> List[ReportSection]:
        """Generate optimization-focused sections."""
        sections = []

        # Priority Recommendations
        high_priority = [
            r for r in recommendations if r.priority.value in ["critical", "high"]
        ]
        rec_content = self._format_recommendations(high_priority)
        sections.append(
            ReportSection(
                title="High Priority Optimizations",
                content=rec_content,
                charts=[
                    {
                        "type": "priority_matrix",
                        "data": [asdict(r) for r in high_priority],
                    }
                ],
                insights=[
                    f"{len(high_priority)} high-priority items identified",
                    "Estimated significant efficiency gains possible",
                    "Implementation can be largely automated",
                ],
                recommendations=[r.title for r in high_priority],
                metadata={"importance": "critical", "actionable": True},
            )
        )

        # Automation Opportunities
        automation_content = self._format_automation_opportunities(
            cross_session_insights.automation_opportunities
        )
        sections.append(
            ReportSection(
                title="Automation Opportunities",
                content=automation_content,
                charts=[
                    {
                        "type": "automation_potential",
                        "data": cross_session_insights.automation_opportunities,
                    }
                ],
                insights=[
                    f"Found {len(cross_session_insights.automation_opportunities)} automation candidates",
                    "High-frequency patterns are prime for automation",
                    "Estimated time savings significant",
                ],
                recommendations=[
                    "Implement automated workflows",
                    "Monitor automation effectiveness",
                ],
                metadata={"importance": "medium", "automation_focused": True},
            )
        )

        return sections

    async def _generate_personalization_sections(
        self,
        personalization_profile: Optional[PersonalizationProfile],
        recommendations: List[IntelligentRecommendation],
    ) -> List[ReportSection]:
        """Generate personalization-focused sections."""
        sections = []

        if personalization_profile:
            # User Profile Analysis
            profile_content = self._format_profile_analysis(personalization_profile)
            sections.append(
                ReportSection(
                    title="User Profile Analysis",
                    content=profile_content,
                    charts=[
                        {
                            "type": "profile_radar",
                            "data": asdict(personalization_profile),
                        }
                    ],
                    insights=[
                        f"Profile confidence: {personalization_profile.profile_confidence:.1%}",
                        f"Sessions tracked: {personalization_profile.session_count}",
                        f"Automation comfort: {personalization_profile.automation_comfort_level:.1%}",
                    ],
                    recommendations=[
                        "Continue building profile data",
                        "Adjust automation based on comfort level",
                    ],
                    metadata={"importance": "medium", "personalized": True},
                )
            )

            # Personalized Recommendations
            personalized_recs = [
                r for r in recommendations if r.user_preference_alignment > 0.7
            ]
            pers_rec_content = self._format_personalized_recommendations(
                personalized_recs
            )
            sections.append(
                ReportSection(
                    title="Personalized Optimization Strategy",
                    content=pers_rec_content,
                    charts=[
                        {
                            "type": "personalization_fit",
                            "data": [asdict(r) for r in personalized_recs],
                        }
                    ],
                    insights=[
                        f"{len(personalized_recs)} recommendations highly aligned with preferences",
                        "Personalization improves recommendation acceptance",
                        "Historical effectiveness guides future suggestions",
                    ],
                    recommendations=[r.title for r in personalized_recs[:5]],
                    metadata={"importance": "high", "personalized": True},
                )
            )

        return sections

    async def _generate_comparative_sections(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> List[ReportSection]:
        """Generate comparative analysis sections."""
        sections = []

        # Historical Comparison
        comparison_content = self._format_historical_comparison(cross_session_insights)
        sections.append(
            ReportSection(
                title="Historical Performance Comparison",
                content=comparison_content,
                charts=[
                    {
                        "type": "comparison_chart",
                        "data": cross_session_insights.efficiency_trends,
                    }
                ],
                insights=[
                    "Performance improvement over time period",
                    "Optimization effectiveness varies by category",
                    "User adaptation shows positive trend",
                ],
                recommendations=[
                    "Continue successful optimization patterns",
                    "Address declining areas",
                ],
                metadata={"importance": "medium", "comparative": True},
            )
        )

        return sections

    def _extract_key_metrics(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> Dict[str, Any]:
        """Extract key metrics from analysis data."""
        return {
            "overall_health_score": dashboard_data.health_metrics.overall_health_score,
            "efficiency_score": dashboard_data.health_metrics.efficiency_score,
            "focus_score": dashboard_data.health_metrics.usage_weighted_focus_score,
            "workflow_efficiency": (
                dashboard_data.usage_summary.workflow_efficiency
                if dashboard_data.usage_summary
                else 0
            ),
            "token_waste_percentage": (
                dashboard_data.token_analysis.waste_percentage
                if dashboard_data.token_analysis
                else 0
            ),
            "sessions_analyzed": cross_session_insights.sessions_analyzed,
            "user_adaptation_score": cross_session_insights.user_adaptation_score,
            "automation_opportunities": len(
                cross_session_insights.automation_opportunities
            ),
            "pattern_count": len(cross_session_insights.pattern_evolution),
            "cluster_count": len(cross_session_insights.session_clusters),
        }

    def _calculate_performance_indicators(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> Dict[str, float]:
        """Calculate key performance indicators."""
        indicators = {
            "health_trend": 0.0,
            "efficiency_improvement": 0.0,
            "optimization_effectiveness": 0.0,
            "pattern_stability": 0.0,
            "automation_readiness": 0.0,
        }

        # Health trend (simplified)
        health_score = dashboard_data.health_metrics.overall_health_score
        indicators["health_trend"] = health_score

        # Efficiency improvement (from trends)
        efficiency_trends = cross_session_insights.efficiency_trends.get(
            "overall_efficiency", []
        )
        if len(efficiency_trends) > 1:
            indicators["efficiency_improvement"] = (
                efficiency_trends[-1] - efficiency_trends[0]
            )

        # Optimization effectiveness (average from cross-session analysis)
        if cross_session_insights.optimization_effectiveness:
            indicators["optimization_effectiveness"] = statistics.mean(
                cross_session_insights.optimization_effectiveness.values()
            )

        # Pattern stability (from pattern evolution)
        if cross_session_insights.pattern_evolution:
            stability_scores = [
                p.stability_score for p in cross_session_insights.pattern_evolution
            ]
            indicators["pattern_stability"] = statistics.mean(stability_scores)

        # Automation readiness
        automation_count = len(cross_session_insights.automation_opportunities)
        indicators["automation_readiness"] = min(
            1.0, automation_count / 5.0
        )  # Normalize to 0-1

        return indicators

    def _generate_trend_analysis(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> Dict[str, List[float]]:
        """Generate trend analysis data."""
        trends = cross_session_insights.efficiency_trends.copy()

        # Add dashboard trends if available
        if dashboard_data.usage_trends:
            trends.update(dashboard_data.usage_trends)
        if dashboard_data.efficiency_trends:
            trends.update(dashboard_data.efficiency_trends)

        return trends

    def _extract_critical_insights(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
    ) -> List[str]:
        """Extract the most critical insights."""
        insights = []

        # Health-based insights
        health_level = dashboard_data.health_metrics.health_level
        if health_level == HealthLevel.CRITICAL:
            insights.append("🚨 Critical: Context health requires immediate attention")
        elif health_level == HealthLevel.POOR:
            insights.append("⚠️ Poor context health detected - optimization needed")
        elif health_level == HealthLevel.EXCELLENT:
            insights.append(
                "✅ Excellent context health - focus on maintaining performance"
            )

        # Token efficiency insights
        if (
            dashboard_data.token_analysis
            and dashboard_data.token_analysis.waste_percentage > 30
        ):
            insights.append(
                f"💰 High token waste: {dashboard_data.token_analysis.waste_percentage:.1f}% - significant cost savings possible"
            )

        # Usage pattern insights
        if (
            dashboard_data.usage_summary
            and dashboard_data.usage_summary.workflow_efficiency < 0.5
        ):
            insights.append(
                f"🔄 Low workflow efficiency: {dashboard_data.usage_summary.workflow_efficiency:.1%} - context misaligned with usage"
            )

        # Cross-session insights
        if cross_session_insights.user_adaptation_score > 0.8:
            insights.append(
                "📈 Excellent user adaptation - optimizations are working well"
            )
        elif cross_session_insights.user_adaptation_score < 0.3:
            insights.append(
                "📉 Poor adaptation - current optimizations may not be effective"
            )

        # Automation insights
        automation_count = len(cross_session_insights.automation_opportunities)
        if automation_count > 3:
            insights.append(
                f"🤖 High automation potential: {automation_count} processes identified"
            )

        # Critical recommendations
        critical_recs = [r for r in recommendations if r.priority.value == "critical"]
        if critical_recs:
            insights.append(
                f"⚡ {len(critical_recs)} critical optimizations require immediate action"
            )

        return insights[:7]  # Top 7 insights

    def _format_optimization_recommendations(
        self, recommendations: List[IntelligentRecommendation]
    ) -> List[Dict[str, Any]]:
        """Format recommendations for report output."""
        formatted = []

        for rec in recommendations:
            formatted.append(
                {
                    "title": rec.title,
                    "description": rec.description,
                    "category": rec.category.value,
                    "priority": rec.priority.value,
                    "estimated_impact": {
                        "token_savings": rec.estimated_token_savings,
                        "efficiency_gain": rec.estimated_efficiency_gain,
                        "focus_improvement": rec.estimated_focus_improvement,
                    },
                    "implementation": {
                        "can_be_automated": rec.can_be_automated,
                        "requires_confirmation": rec.requires_confirmation,
                        "estimated_time_savings": rec.estimated_time_savings,
                    },
                    "confidence": rec.learning_confidence,
                }
            )

        return formatted

    async def _generate_charts_data(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        trend_analysis: Dict[str, List[float]],
    ) -> List[Dict[str, Any]]:
        """Generate data for charts and visualizations."""
        charts = []

        # Health gauge chart
        charts.append(
            {
                "type": "gauge",
                "title": "Context Health Score",
                "data": {
                    "score": dashboard_data.health_metrics.overall_health_score,
                    "level": dashboard_data.health_metrics.health_level.value,
                    "components": {
                        "Focus": dashboard_data.health_metrics.usage_weighted_focus_score,
                        "Efficiency": dashboard_data.health_metrics.efficiency_score,
                        "Coherence": dashboard_data.health_metrics.temporal_coherence_score,
                        "Consistency": dashboard_data.health_metrics.cross_session_consistency,
                    },
                },
            }
        )

        # Trend line chart
        if trend_analysis:
            charts.append(
                {"type": "line", "title": "Performance Trends", "data": trend_analysis}
            )

        # Token waste breakdown
        if dashboard_data.token_analysis:
            charts.append(
                {
                    "type": "pie",
                    "title": "Token Usage Breakdown",
                    "data": {
                        "Efficient Usage": 100
                        - dashboard_data.token_analysis.waste_percentage,
                        "Waste/Redundancy": dashboard_data.token_analysis.waste_percentage,
                    },
                }
            )

        # Workflow efficiency heatmap
        if dashboard_data.usage_summary:
            charts.append(
                {
                    "type": "heatmap",
                    "title": "File Access Patterns",
                    "data": {
                        "patterns": [
                            {
                                "file": pattern.file_path,
                                "frequency": pattern.access_frequency,
                                "recency": pattern.last_access_hours,
                            }
                            for pattern in dashboard_data.usage_summary.file_patterns[
                                :10
                            ]
                        ]
                    },
                }
            )

        # Automation opportunities
        charts.append(
            {
                "type": "bar",
                "title": "Automation Opportunities",
                "data": {
                    "opportunities": [
                        {
                            "name": opp.get("name", "Unknown"),
                            "potential": opp.get("automation_potential", 0),
                            "confidence": opp.get("confidence", 0),
                        }
                        for opp in cross_session_insights.automation_opportunities[:5]
                    ]
                },
            }
        )

        return charts

    def _calculate_confidence_score(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> float:
        """Calculate overall confidence score for the analysis."""
        factors = []

        # Sessions analyzed
        session_factor = min(1.0, cross_session_insights.sessions_analyzed / 20.0)
        factors.append(session_factor)

        # Time span
        time_factor = min(1.0, cross_session_insights.time_span_days / 30.0)
        factors.append(time_factor)

        # Data availability
        data_factor = 1.0
        if not dashboard_data.usage_summary:
            data_factor -= 0.2
        if not dashboard_data.token_analysis:
            data_factor -= 0.2
        if not dashboard_data.enhanced_analysis:
            data_factor -= 0.2
        factors.append(max(0, data_factor))

        # Pattern consistency
        if cross_session_insights.pattern_evolution:
            stability_scores = [
                p.stability_score for p in cross_session_insights.pattern_evolution
            ]
            pattern_factor = statistics.mean(stability_scores)
            factors.append(pattern_factor)

        return statistics.mean(factors) if factors else 0.5

    def _calculate_data_completeness(
        self,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> float:
        """Calculate data completeness score."""
        completeness = 0.0
        total_components = 7

        # Dashboard components
        if dashboard_data.usage_summary:
            completeness += 1
        if dashboard_data.token_analysis:
            completeness += 1
        if dashboard_data.temporal_insights:
            completeness += 1
        if dashboard_data.enhanced_analysis:
            completeness += 1
        if dashboard_data.correlation_insights:
            completeness += 1

        # Cross-session components
        if cross_session_insights.pattern_evolution:
            completeness += 1
        if cross_session_insights.session_clusters:
            completeness += 1

        return completeness / total_components

    # Formatting helper methods
    def _format_health_overview(self, health_metrics: UsageBasedHealthMetrics) -> str:
        """Format health overview section."""
        return f"""
**Overall Health Score**: {health_metrics.overall_health_score:.1%} ({health_metrics.health_level.value.title()})

**Component Scores**:
- Usage-Weighted Focus: {health_metrics.usage_weighted_focus_score:.1%}
- Token Efficiency: {health_metrics.efficiency_score:.1%}
- Temporal Coherence: {health_metrics.temporal_coherence_score:.1%}
- Cross-Session Consistency: {health_metrics.cross_session_consistency:.1%}
- Workflow Alignment: {health_metrics.workflow_alignment:.1%}

**Optimization Potential**: {health_metrics.optimization_potential:.1%}
"""

    def _format_kpi_summary(self, insights: CrossSessionInsights) -> str:
        """Format KPI summary section."""
        return f"""
**Analysis Coverage**:
- Sessions Analyzed: {insights.sessions_analyzed}
- Time Span: {insights.time_span_days} days
- Data Confidence: High

**Performance Indicators**:
- User Adaptation Score: {insights.user_adaptation_score:.1%}
- Pattern Stability: {statistics.mean([p.stability_score for p in insights.pattern_evolution]):.1% if insights.pattern_evolution else "N/A"}
- Workflow Templates: {len(insights.workflow_templates)}
- Automation Opportunities: {len(insights.automation_opportunities)}
"""

    def _format_usage_analysis(self, usage_summary) -> str:
        """Format usage analysis section."""
        return f"""
**Workflow Efficiency**: {usage_summary.workflow_efficiency:.1%}

**File Access Patterns**:
- Total Files Tracked: {len(usage_summary.file_patterns)}
- Most Frequently Accessed: {usage_summary.file_patterns[0].file_path if usage_summary.file_patterns else "N/A"}
- Average Access Frequency: {statistics.mean([p.access_frequency for p in usage_summary.file_patterns]) if usage_summary.file_patterns else 0:.1f}

**Workflow Insights**:
Based on actual usage patterns, context alignment with user behavior can be significantly improved.
"""

    def _format_token_analysis(self, token_analysis) -> str:
        """Format token analysis section."""
        return f"""
**Token Efficiency**: {100 - token_analysis.waste_percentage:.1f}%
**Waste Percentage**: {token_analysis.waste_percentage:.1f}%

**Waste Patterns Identified**:
{chr(10).join([f"- {pattern.pattern}" for pattern in token_analysis.waste_patterns[:5]])}

**Optimization Impact**:
Addressing identified waste patterns could improve efficiency by {token_analysis.waste_percentage * 0.8:.1f}%.
"""

    def _format_pattern_analysis(self, insights: CrossSessionInsights) -> str:
        """Format pattern analysis section."""
        return f"""
**Pattern Evolution**:
- Patterns Tracked: {len(insights.pattern_evolution)}
- Average Stability: {statistics.mean([p.stability_score for p in insights.pattern_evolution]):.1% if insights.pattern_evolution else "N/A"}
- Adaptation Trends: {"Positive" if insights.user_adaptation_score > 0.6 else "Needs Improvement"}

**Session Clustering**:
- Clusters Identified: {len(insights.session_clusters)}
- Common Workflows: {", ".join([template.name for template in insights.workflow_templates[:3]])}

**Predictive Insights**:
{chr(10).join([f"- {prediction}" for prediction in insights.predicted_patterns[:3]])}
"""

    # Additional formatting methods would go here...
    def _format_trend_analysis(self, trends: Dict[str, List[float]]) -> str:
        return "Trend analysis content..."

    def _format_pattern_evolution(self, patterns: List[PatternEvolution]) -> str:
        return "Pattern evolution content..."

    def _format_recommendations(
        self, recommendations: List[IntelligentRecommendation]
    ) -> str:
        return "Recommendations content..."

    def _format_automation_opportunities(
        self, opportunities: List[Dict[str, Any]]
    ) -> str:
        return "Automation opportunities content..."

    def _format_profile_analysis(self, profile: PersonalizationProfile) -> str:
        return "Profile analysis content..."

    def _format_personalized_recommendations(
        self, recommendations: List[IntelligentRecommendation]
    ) -> str:
        return "Personalized recommendations content..."

    def _format_historical_comparison(self, insights: CrossSessionInsights) -> str:
        return "Historical comparison content..."

    async def _persist_report(
        self, report: UsageReport, output_format: ReportFormat
    ) -> None:
        """Persist report to storage."""
        try:
            report_path = (
                self.storage_path / f"{report.report_id}.{output_format.value}"
            )

            if output_format == ReportFormat.JSON:
                with open(report_path, "w") as f:
                    json.dump(asdict(report), f, default=str, indent=2)
            elif output_format == ReportFormat.HTML:
                html_content = self._generate_html_report(report)
                with open(report_path, "w") as f:
                    f.write(html_content)
            elif output_format == ReportFormat.MARKDOWN:
                md_content = self._generate_markdown_report(report)
                with open(report_path, "w") as f:
                    f.write(md_content)

        except Exception:
            pass  # Silent fail for persistence

    def _generate_html_report(self, report: UsageReport) -> str:
        """Generate HTML version of report."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{report.report_type.value.title()} Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .metric {{ background: #f5f5f5; padding: 10px; margin: 10px 0; }}
        .insight {{ background: #e8f4fd; padding: 10px; margin: 10px 0; }}
        .recommendation {{ background: #fff3cd; padding: 10px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>Context Cleaner Optimization Report</h1>
    <p>Generated: {report.generated_at}</p>
    
    <h2>Executive Summary</h2>
    <p>{report.executive_summary}</p>
    
    <h2>Key Metrics</h2>
    <div class="metric">
        <strong>Overall Health Score:</strong> {report.key_metrics.get('overall_health_score', 0):.1%}
    </div>
    
    <h2>Critical Insights</h2>
    {chr(10).join([f'<div class="insight">{insight}</div>' for insight in report.critical_insights])}
    
    <h2>Recommendations</h2>
    {chr(10).join([f'<div class="recommendation">{rec.get("title", "Unknown")}</div>' for rec in report.optimization_recommendations[:5]])}
</body>
</html>
"""

    def _generate_markdown_report(self, report: UsageReport) -> str:
        """Generate Markdown version of report."""
        return f"""# Context Cleaner Optimization Report

**Generated:** {report.generated_at}
**Report Type:** {report.report_type.value.title()}
**Time Period:** {report.time_period['start']} to {report.time_period['end']}

## Executive Summary

{report.executive_summary}

## Key Metrics

- **Overall Health Score:** {report.key_metrics.get('overall_health_score', 0):.1%}
- **Efficiency Score:** {report.key_metrics.get('efficiency_score', 0):.1%}
- **Sessions Analyzed:** {report.key_metrics.get('sessions_analyzed', 0)}

## Critical Insights

{chr(10).join([f'- {insight}' for insight in report.critical_insights])}

## Optimization Recommendations

{chr(10).join([f'### {rec.get("title", "Unknown")}\\n{rec.get("description", "")}\\n' for rec in report.optimization_recommendations[:5]])}

---
*Report generated by Context Cleaner Advanced Analytics*
"""
