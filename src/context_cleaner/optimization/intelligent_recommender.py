"""
Intelligent Optimization Recommendation Engine

This module provides intelligent, usage-pattern-based recommendations for
context optimization leveraging cache analysis and historical patterns.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import math

from ..cache import (
    UsagePatternSummary,
    TokenAnalysisSummary,
    TemporalInsights,
    CacheEnhancedAnalysis,
    CorrelationInsights,
    FileAccessPattern,
    WorkflowPattern,
    TokenWastePattern,
    CrossSessionPattern,
)
from .cache_dashboard import UsageBasedHealthMetrics, HealthLevel


class RecommendationPriority(Enum):
    """Priority levels for optimization recommendations."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OptimizationCategory(Enum):
    """Categories of optimization recommendations."""

    TOKEN_EFFICIENCY = "token_efficiency"
    WORKFLOW_ALIGNMENT = "workflow_alignment"
    TEMPORAL_ORGANIZATION = "temporal_organization"
    CROSS_SESSION_LEARNING = "cross_session_learning"
    REDUNDANCY_REMOVAL = "redundancy_removal"
    FOCUS_IMPROVEMENT = "focus_improvement"
    PERSONALIZATION = "personalization"


@dataclass
class OptimizationAction:
    """Specific action within a recommendation."""

    action_type: str
    description: str
    target_files: List[str]
    expected_impact: str
    confidence_score: float
    automation_possible: bool


@dataclass
class IntelligentRecommendation:
    """Smart recommendation with usage-pattern analysis."""

    id: str
    category: OptimizationCategory
    priority: RecommendationPriority
    title: str
    description: str
    rationale: str

    # Usage pattern analysis
    usage_patterns_analyzed: List[str]
    historical_effectiveness: float
    user_preference_alignment: float
    context_specificity: float

    # Specific actions
    actions: List[OptimizationAction]

    # Impact estimates
    estimated_token_savings: int
    estimated_efficiency_gain: float
    estimated_focus_improvement: float
    risk_level: str

    # Implementation details
    requires_confirmation: bool
    can_be_automated: bool
    estimated_time_savings: str
    learning_confidence: float

    # Metadata
    generated_at: datetime
    expires_at: datetime
    session_context: Dict[str, Any]


@dataclass
class PersonalizationProfile:
    """User personalization profile based on usage patterns."""

    user_id: str

    # Preference patterns
    preferred_optimization_modes: List[str]
    typical_session_length: timedelta
    common_file_types: List[str]
    frequent_workflows: List[str]

    # Behavioral patterns
    confirmation_preferences: Dict[str, bool]
    automation_comfort_level: float
    optimization_frequency: str

    # Historical effectiveness
    successful_recommendations: List[str]
    rejected_recommendations: List[str]
    optimization_outcomes: Dict[str, float]

    # Learning metadata
    profile_confidence: float
    last_updated: datetime
    session_count: int


class IntelligentRecommendationEngine:
    """
    Advanced recommendation engine that leverages cache analysis,
    usage patterns, and machine learning for personalized optimization.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the intelligent recommendation engine."""
        self.storage_path = (
            storage_path or Path.home() / ".context_cleaner" / "recommendations"
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._profiles_cache: Dict[str, PersonalizationProfile] = {}
        self._recommendation_history: Dict[str, List[IntelligentRecommendation]] = {}
        self._effectiveness_tracker: Dict[str, Dict[str, float]] = {}

    async def generate_intelligent_recommendations(
        self,
        health_metrics: UsageBasedHealthMetrics,
        usage_summary: Optional[UsagePatternSummary],
        token_analysis: Optional[TokenAnalysisSummary],
        temporal_insights: Optional[TemporalInsights],
        enhanced_analysis: Optional[CacheEnhancedAnalysis],
        correlation_insights: Optional[CorrelationInsights],
        user_id: str = "default",
        context_size: int = 0,
        max_recommendations: int = 10,
    ) -> List[IntelligentRecommendation]:
        """
        Generate intelligent, personalized optimization recommendations.

        Args:
            health_metrics: Current usage-based health metrics
            usage_summary: Usage pattern analysis results
            token_analysis: Token efficiency analysis results
            temporal_insights: Temporal pattern insights
            enhanced_analysis: Cache-enhanced context analysis
            correlation_insights: Cross-session correlation analysis
            user_id: User identifier for personalization
            context_size: Current context size in tokens
            max_recommendations: Maximum recommendations to generate

        Returns:
            List of prioritized intelligent recommendations
        """
        # Load or create personalization profile
        profile = await self._load_personalization_profile(user_id)

        # Generate base recommendations from all analysis sources
        recommendations = []

        # Token efficiency recommendations
        if token_analysis:
            token_recs = await self._generate_token_efficiency_recommendations(
                token_analysis, health_metrics, profile, context_size
            )
            recommendations.extend(token_recs)

        # Workflow alignment recommendations
        if usage_summary:
            workflow_recs = await self._generate_workflow_recommendations(
                usage_summary, health_metrics, profile
            )
            recommendations.extend(workflow_recs)

        # Temporal organization recommendations
        if temporal_insights:
            temporal_recs = await self._generate_temporal_recommendations(
                temporal_insights, health_metrics, profile
            )
            recommendations.extend(temporal_recs)

        # Cross-session learning recommendations
        if correlation_insights:
            learning_recs = await self._generate_learning_recommendations(
                correlation_insights, health_metrics, profile
            )
            recommendations.extend(learning_recs)

        # Focus improvement recommendations
        if enhanced_analysis:
            focus_recs = await self._generate_focus_recommendations(
                enhanced_analysis, health_metrics, profile
            )
            recommendations.extend(focus_recs)

        # Health-based emergency recommendations
        if health_metrics.health_level in [HealthLevel.POOR, HealthLevel.CRITICAL]:
            emergency_recs = await self._generate_emergency_recommendations(
                health_metrics, profile, context_size
            )
            recommendations.extend(emergency_recs)

        # Apply personalization and prioritization
        personalized_recs = await self._apply_personalization(recommendations, profile)

        # Sort by priority and effectiveness
        sorted_recs = self._prioritize_recommendations(personalized_recs, profile)

        # Update personalization profile
        await self._update_personalization_profile(user_id, profile, sorted_recs)

        return sorted_recs[:max_recommendations]

    async def _load_personalization_profile(
        self, user_id: str
    ) -> PersonalizationProfile:
        """Load or create user personalization profile."""
        if user_id in self._profiles_cache:
            return self._profiles_cache[user_id]

        profile_path = self.storage_path / f"profile_{user_id}.json"

        if profile_path.exists():
            try:
                with open(profile_path, "r") as f:
                    data = json.load(f)
                profile = PersonalizationProfile(**data)
                self._profiles_cache[user_id] = profile
                return profile
            except Exception:
                pass

        # Create default profile
        profile = PersonalizationProfile(
            user_id=user_id,
            preferred_optimization_modes=["balanced"],
            typical_session_length=timedelta(hours=2),
            common_file_types=[".py", ".js", ".md"],
            frequent_workflows=["development", "debugging"],
            confirmation_preferences={
                "high_risk": True,
                "automation": False,
                "bulk_delete": True,
            },
            automation_comfort_level=0.5,
            optimization_frequency="weekly",
            successful_recommendations=[],
            rejected_recommendations=[],
            optimization_outcomes={},
            profile_confidence=0.1,
            last_updated=datetime.now(),
            session_count=0,
        )

        self._profiles_cache[user_id] = profile
        return profile

    async def _generate_token_efficiency_recommendations(
        self,
        token_analysis: TokenAnalysisSummary,
        health_metrics: UsageBasedHealthMetrics,
        profile: PersonalizationProfile,
        context_size: int,
    ) -> List[IntelligentRecommendation]:
        """Generate token efficiency optimization recommendations."""
        recommendations = []

        if token_analysis.waste_percentage > 30:
            # High waste - aggressive cleanup needed
            actions = [
                OptimizationAction(
                    action_type="remove_duplicates",
                    description="Remove duplicate file reads and redundant context",
                    target_files=[p.pattern for p in token_analysis.waste_patterns[:5]],
                    expected_impact=f"{token_analysis.waste_percentage * 0.6:.1f}% token reduction",
                    confidence_score=0.85,
                    automation_possible=True,
                ),
                OptimizationAction(
                    action_type="consolidate_similar",
                    description="Consolidate similar conversations and code blocks",
                    target_files=[],
                    expected_impact="15-25% efficiency improvement",
                    confidence_score=0.7,
                    automation_possible=False,
                ),
            ]

            rec = IntelligentRecommendation(
                id=f"token_efficiency_{datetime.now().timestamp()}",
                category=OptimizationCategory.TOKEN_EFFICIENCY,
                priority=RecommendationPriority.HIGH,
                title="Significant Token Waste Detected",
                description=f"Analysis shows {token_analysis.waste_percentage:.1f}% token waste",
                rationale="High token waste reduces efficiency and increases costs",
                usage_patterns_analyzed=["token_usage", "file_access_frequency"],
                historical_effectiveness=self._get_historical_effectiveness(
                    "token_efficiency", profile
                ),
                user_preference_alignment=self._calculate_preference_alignment(
                    OptimizationCategory.TOKEN_EFFICIENCY, profile
                ),
                context_specificity=0.8,
                actions=actions,
                estimated_token_savings=int(
                    context_size * token_analysis.waste_percentage / 100 * 0.7
                ),
                estimated_efficiency_gain=token_analysis.waste_percentage * 0.6 / 100,
                estimated_focus_improvement=0.3,
                risk_level="low",
                requires_confirmation=profile.confirmation_preferences.get(
                    "automation", True
                ),
                can_be_automated=True,
                estimated_time_savings="5-10 minutes per session",
                learning_confidence=0.8,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=7),
                session_context={"waste_percentage": token_analysis.waste_percentage},
            )

            recommendations.append(rec)

        elif token_analysis.waste_percentage > 15:
            # Moderate waste - targeted optimization
            actions = [
                OptimizationAction(
                    action_type="optimize_frequent_files",
                    description="Optimize frequently accessed files with high token waste",
                    target_files=[p.pattern for p in token_analysis.waste_patterns[:3]],
                    expected_impact=f"{token_analysis.waste_percentage * 0.4:.1f}% token reduction",
                    confidence_score=0.75,
                    automation_possible=True,
                )
            ]

            rec = IntelligentRecommendation(
                id=f"token_moderate_{datetime.now().timestamp()}",
                category=OptimizationCategory.TOKEN_EFFICIENCY,
                priority=RecommendationPriority.MEDIUM,
                title="Moderate Token Optimization Opportunity",
                description="Targeted optimization can improve token efficiency",
                rationale="Focused optimization on high-impact areas",
                usage_patterns_analyzed=["token_waste_patterns"],
                historical_effectiveness=self._get_historical_effectiveness(
                    "token_moderate", profile
                ),
                user_preference_alignment=self._calculate_preference_alignment(
                    OptimizationCategory.TOKEN_EFFICIENCY, profile
                ),
                context_specificity=0.6,
                actions=actions,
                estimated_token_savings=int(
                    context_size * token_analysis.waste_percentage / 100 * 0.4
                ),
                estimated_efficiency_gain=token_analysis.waste_percentage * 0.3 / 100,
                estimated_focus_improvement=0.2,
                risk_level="very_low",
                requires_confirmation=False,
                can_be_automated=True,
                estimated_time_savings="2-5 minutes per session",
                learning_confidence=0.7,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=5),
                session_context={"waste_percentage": token_analysis.waste_percentage},
            )

            recommendations.append(rec)

        return recommendations

    async def _generate_workflow_recommendations(
        self,
        usage_summary: UsagePatternSummary,
        health_metrics: UsageBasedHealthMetrics,
        profile: PersonalizationProfile,
    ) -> List[IntelligentRecommendation]:
        """Generate workflow alignment recommendations."""
        recommendations = []

        if usage_summary.workflow_efficiency < 0.5:
            # Poor workflow efficiency
            top_patterns = sorted(
                usage_summary.file_patterns,
                key=lambda p: p.access_frequency,
                reverse=True,
            )[:5]

            actions = [
                OptimizationAction(
                    action_type="prioritize_frequent_files",
                    description="Move frequently accessed files to top of context",
                    target_files=[p.file_path for p in top_patterns],
                    expected_impact="30-45% workflow efficiency improvement",
                    confidence_score=0.8,
                    automation_possible=True,
                ),
                OptimizationAction(
                    action_type="remove_stale_context",
                    description="Remove files not accessed in recent sessions",
                    target_files=[],
                    expected_impact="Improved focus and reduced cognitive load",
                    confidence_score=0.7,
                    automation_possible=False,
                ),
            ]

            rec = IntelligentRecommendation(
                id=f"workflow_efficiency_{datetime.now().timestamp()}",
                category=OptimizationCategory.WORKFLOW_ALIGNMENT,
                priority=RecommendationPriority.HIGH,
                title="Improve Workflow Efficiency",
                description=f"Current workflow efficiency is {usage_summary.workflow_efficiency:.1%}",
                rationale="Aligning context with actual usage patterns improves productivity",
                usage_patterns_analyzed=["file_access_frequency", "workflow_patterns"],
                historical_effectiveness=self._get_historical_effectiveness(
                    "workflow_efficiency", profile
                ),
                user_preference_alignment=self._calculate_preference_alignment(
                    OptimizationCategory.WORKFLOW_ALIGNMENT, profile
                ),
                context_specificity=0.9,
                actions=actions,
                estimated_token_savings=0,
                estimated_efficiency_gain=0.4,
                estimated_focus_improvement=0.5,
                risk_level="low",
                requires_confirmation=profile.confirmation_preferences.get(
                    "high_risk", True
                ),
                can_be_automated=True,
                estimated_time_savings="10-15 minutes per session",
                learning_confidence=0.85,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=3),
                session_context={
                    "workflow_efficiency": usage_summary.workflow_efficiency
                },
            )

            recommendations.append(rec)

        return recommendations

    async def _generate_temporal_recommendations(
        self,
        temporal_insights: TemporalInsights,
        health_metrics: UsageBasedHealthMetrics,
        profile: PersonalizationProfile,
    ) -> List[IntelligentRecommendation]:
        """Generate temporal organization recommendations."""
        recommendations = []

        if temporal_insights.coherence_score < 0.6:
            actions = [
                OptimizationAction(
                    action_type="reorganize_chronologically",
                    description="Group related context by time and topic",
                    target_files=[],
                    expected_impact="Improved context flow and comprehension",
                    confidence_score=0.6,
                    automation_possible=True,
                ),
                OptimizationAction(
                    action_type="add_topic_boundaries",
                    description="Add clear separators between different topics",
                    target_files=[],
                    expected_impact="Better mental model organization",
                    confidence_score=0.7,
                    automation_possible=False,
                ),
            ]

            rec = IntelligentRecommendation(
                id=f"temporal_organization_{datetime.now().timestamp()}",
                category=OptimizationCategory.TEMPORAL_ORGANIZATION,
                priority=RecommendationPriority.MEDIUM,
                title="Improve Context Organization",
                description="Context lacks clear temporal and topical structure",
                rationale="Well-organized context improves comprehension and efficiency",
                usage_patterns_analyzed=["temporal_patterns", "topic_transitions"],
                historical_effectiveness=self._get_historical_effectiveness(
                    "temporal_organization", profile
                ),
                user_preference_alignment=self._calculate_preference_alignment(
                    OptimizationCategory.TEMPORAL_ORGANIZATION, profile
                ),
                context_specificity=0.5,
                actions=actions,
                estimated_token_savings=0,
                estimated_efficiency_gain=0.2,
                estimated_focus_improvement=0.4,
                risk_level="very_low",
                requires_confirmation=False,
                can_be_automated=True,
                estimated_time_savings="Better comprehension, less re-reading",
                learning_confidence=0.6,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=7),
                session_context={"coherence_score": temporal_insights.coherence_score},
            )

            recommendations.append(rec)

        return recommendations

    async def _generate_learning_recommendations(
        self,
        correlation_insights: CorrelationInsights,
        health_metrics: UsageBasedHealthMetrics,
        profile: PersonalizationProfile,
    ) -> List[IntelligentRecommendation]:
        """Generate cross-session learning recommendations."""
        recommendations = []

        if len(correlation_insights.cross_session_patterns) > 2:
            # Strong patterns found - suggest optimizations
            patterns = correlation_insights.cross_session_patterns[:3]

            actions = [
                OptimizationAction(
                    action_type="create_workflow_templates",
                    description="Create templates for common workflow patterns",
                    target_files=[],
                    expected_impact="Faster session startup, consistent context",
                    confidence_score=correlation_insights.correlation_strength,
                    automation_possible=True,
                ),
                OptimizationAction(
                    action_type="pre_load_common_context",
                    description="Automatically include frequently co-occurring files",
                    target_files=[],
                    expected_impact="Reduced setup time for common workflows",
                    confidence_score=0.7,
                    automation_possible=True,
                ),
            ]

            rec = IntelligentRecommendation(
                id=f"cross_session_learning_{datetime.now().timestamp()}",
                category=OptimizationCategory.CROSS_SESSION_LEARNING,
                priority=RecommendationPriority.MEDIUM,
                title="Leverage Cross-Session Patterns",
                description=f"Found {len(patterns)} strong workflow patterns",
                rationale="Learning from patterns can automate and optimize future sessions",
                usage_patterns_analyzed=[
                    "cross_session_correlation",
                    "workflow_repetition",
                ],
                historical_effectiveness=self._get_historical_effectiveness(
                    "cross_session_learning", profile
                ),
                user_preference_alignment=self._calculate_preference_alignment(
                    OptimizationCategory.CROSS_SESSION_LEARNING, profile
                ),
                context_specificity=correlation_insights.correlation_strength,
                actions=actions,
                estimated_token_savings=0,
                estimated_efficiency_gain=0.3,
                estimated_focus_improvement=0.2,
                risk_level="low",
                requires_confirmation=profile.confirmation_preferences.get(
                    "automation", True
                ),
                can_be_automated=True,
                estimated_time_savings="5-10 minutes per session setup",
                learning_confidence=correlation_insights.correlation_strength,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=14),
                session_context={
                    "pattern_count": len(patterns),
                    "correlation_strength": correlation_insights.correlation_strength,
                },
            )

            recommendations.append(rec)

        return recommendations

    async def _generate_focus_recommendations(
        self,
        enhanced_analysis: CacheEnhancedAnalysis,
        health_metrics: UsageBasedHealthMetrics,
        profile: PersonalizationProfile,
    ) -> List[IntelligentRecommendation]:
        """Generate focus improvement recommendations."""
        recommendations = []

        if enhanced_analysis.usage_weighted_focus_score < 0.6:
            actions = [
                OptimizationAction(
                    action_type="remove_low_relevance_content",
                    description="Remove content with low relevance to current work",
                    target_files=[],
                    expected_impact=f"Focus improvement: {(0.8 - enhanced_analysis.usage_weighted_focus_score) * 100:.1f}%",
                    confidence_score=0.8,
                    automation_possible=True,
                ),
                OptimizationAction(
                    action_type="prioritize_current_work",
                    description="Move current work context to prominent position",
                    target_files=[],
                    expected_impact="Improved attention and task alignment",
                    confidence_score=0.9,
                    automation_possible=True,
                ),
            ]

            rec = IntelligentRecommendation(
                id=f"focus_improvement_{datetime.now().timestamp()}",
                category=OptimizationCategory.FOCUS_IMPROVEMENT,
                priority=RecommendationPriority.HIGH,
                title="Improve Context Focus",
                description=f"Focus score: {enhanced_analysis.usage_weighted_focus_score:.1%}",
                rationale="Better focused context reduces distractions and improves productivity",
                usage_patterns_analyzed=["relevance_scoring", "current_work_alignment"],
                historical_effectiveness=self._get_historical_effectiveness(
                    "focus_improvement", profile
                ),
                user_preference_alignment=self._calculate_preference_alignment(
                    OptimizationCategory.FOCUS_IMPROVEMENT, profile
                ),
                context_specificity=0.9,
                actions=actions,
                estimated_token_savings=0,
                estimated_efficiency_gain=0.3,
                estimated_focus_improvement=0.8
                - enhanced_analysis.usage_weighted_focus_score,
                risk_level="low",
                requires_confirmation=profile.confirmation_preferences.get(
                    "high_risk", False
                ),
                can_be_automated=True,
                estimated_time_savings="Reduced context switching time",
                learning_confidence=0.8,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=3),
                session_context={
                    "current_focus_score": enhanced_analysis.usage_weighted_focus_score,
                    "target_focus_score": 0.8,
                },
            )

            recommendations.append(rec)

        return recommendations

    async def _generate_emergency_recommendations(
        self,
        health_metrics: UsageBasedHealthMetrics,
        profile: PersonalizationProfile,
        context_size: int,
    ) -> List[IntelligentRecommendation]:
        """Generate emergency recommendations for critical health situations."""
        recommendations = []

        if health_metrics.health_level == HealthLevel.CRITICAL:
            actions = [
                OptimizationAction(
                    action_type="emergency_cleanup",
                    description="Aggressive cleanup to restore context health",
                    target_files=[],
                    expected_impact="50-70% size reduction, major efficiency improvement",
                    confidence_score=0.9,
                    automation_possible=True,
                ),
                OptimizationAction(
                    action_type="reset_to_essentials",
                    description="Keep only essential, recently used context",
                    target_files=[],
                    expected_impact="Immediate productivity restoration",
                    confidence_score=0.95,
                    automation_possible=False,
                ),
            ]

            rec = IntelligentRecommendation(
                id=f"emergency_cleanup_{datetime.now().timestamp()}",
                category=OptimizationCategory.FOCUS_IMPROVEMENT,
                priority=RecommendationPriority.CRITICAL,
                title="Emergency Context Cleanup Required",
                description="Context health is critical - immediate action needed",
                rationale="Critical context degradation severely impacts productivity",
                usage_patterns_analyzed=["overall_health", "emergency_patterns"],
                historical_effectiveness=0.9,  # Emergency actions are usually effective
                user_preference_alignment=1.0,  # Override preferences for emergency
                context_specificity=1.0,
                actions=actions,
                estimated_token_savings=int(context_size * 0.6),
                estimated_efficiency_gain=0.7,
                estimated_focus_improvement=0.8,
                risk_level="medium",
                requires_confirmation=True,  # Always confirm emergency actions
                can_be_automated=False,  # Emergency should be manual
                estimated_time_savings="Immediate productivity restoration",
                learning_confidence=0.9,
                generated_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=6),  # Urgent
                session_context={
                    "health_level": health_metrics.health_level.value,
                    "overall_score": health_metrics.overall_health_score,
                },
            )

            recommendations.append(rec)

        return recommendations

    async def _apply_personalization(
        self,
        recommendations: List[IntelligentRecommendation],
        profile: PersonalizationProfile,
    ) -> List[IntelligentRecommendation]:
        """Apply personalization to recommendations based on user profile."""
        personalized = []

        for rec in recommendations:
            # Adjust based on user preferences
            if rec.category.value in profile.preferred_optimization_modes:
                rec.user_preference_alignment = min(
                    1.0, rec.user_preference_alignment + 0.2
                )

            # Adjust automation based on comfort level
            if rec.can_be_automated and profile.automation_comfort_level < 0.5:
                rec.requires_confirmation = True

            # Adjust priority based on historical effectiveness
            historical_eff = self._get_historical_effectiveness(
                rec.category.value, profile
            )
            if historical_eff < 0.3 and rec.priority != RecommendationPriority.CRITICAL:
                # Downgrade priority if historically ineffective
                priorities = list(RecommendationPriority)
                current_idx = priorities.index(rec.priority)
                if current_idx < len(priorities) - 1:
                    rec.priority = priorities[current_idx + 1]

            personalized.append(rec)

        return personalized

    def _prioritize_recommendations(
        self,
        recommendations: List[IntelligentRecommendation],
        profile: PersonalizationProfile,
    ) -> List[IntelligentRecommendation]:
        """Sort recommendations by priority and effectiveness."""

        def priority_score(rec: IntelligentRecommendation) -> float:
            # Priority weight
            priority_weights = {
                RecommendationPriority.CRITICAL: 1000,
                RecommendationPriority.HIGH: 100,
                RecommendationPriority.MEDIUM: 10,
                RecommendationPriority.LOW: 1,
            }

            score = priority_weights[rec.priority]

            # Add effectiveness factors
            score += rec.historical_effectiveness * 50
            score += rec.user_preference_alignment * 30
            score += rec.learning_confidence * 20
            score += rec.estimated_efficiency_gain * 100

            # Penalty for requiring confirmation if user prefers automation
            if rec.requires_confirmation and profile.automation_comfort_level > 0.7:
                score *= 0.8

            return score

        return sorted(recommendations, key=priority_score, reverse=True)

    def _get_historical_effectiveness(
        self, category: str, profile: PersonalizationProfile
    ) -> float:
        """Get historical effectiveness for a recommendation category."""
        if category in profile.optimization_outcomes:
            return profile.optimization_outcomes[category]
        return 0.6  # Default moderate effectiveness

    def _calculate_preference_alignment(
        self, category: OptimizationCategory, profile: PersonalizationProfile
    ) -> float:
        """Calculate how well this recommendation aligns with user preferences."""
        if category.value in profile.preferred_optimization_modes:
            return 0.9

        # Check for related preferences
        related_preferences = {
            OptimizationCategory.TOKEN_EFFICIENCY: ["efficiency", "performance"],
            OptimizationCategory.WORKFLOW_ALIGNMENT: ["workflow", "productivity"],
            OptimizationCategory.FOCUS_IMPROVEMENT: ["focus", "clarity"],
        }

        if category in related_preferences:
            for pref in related_preferences[category]:
                if pref in profile.preferred_optimization_modes:
                    return 0.7

        return 0.5  # Neutral alignment

    async def _update_personalization_profile(
        self,
        user_id: str,
        profile: PersonalizationProfile,
        recommendations: List[IntelligentRecommendation],
    ) -> None:
        """Update personalization profile with new session data."""
        profile.last_updated = datetime.now()
        profile.session_count += 1

        # Update confidence based on more data
        profile.profile_confidence = min(1.0, profile.profile_confidence + 0.1)

        # Save profile
        profile_path = self.storage_path / f"profile_{user_id}.json"
        try:
            with open(profile_path, "w") as f:
                json.dump(asdict(profile), f, default=str, indent=2)
        except Exception:
            pass  # Silent fail for profile saving

        # Cache updated profile
        self._profiles_cache[user_id] = profile

    async def record_recommendation_outcome(
        self,
        recommendation_id: str,
        outcome: str,
        effectiveness_score: float,
        user_id: str = "default",
    ) -> None:
        """Record the outcome of a recommendation for learning purposes."""
        profile = await self._load_personalization_profile(user_id)

        # Find the recommendation category
        # This would typically be stored with the recommendation
        # For now, we'll update based on the outcome

        if outcome == "accepted":
            # This recommendation was successful
            if recommendation_id not in profile.successful_recommendations:
                profile.successful_recommendations.append(recommendation_id)
        elif outcome == "rejected":
            # This recommendation was rejected
            if recommendation_id not in profile.rejected_recommendations:
                profile.rejected_recommendations.append(recommendation_id)

        # Update profile
        await self._update_personalization_profile(user_id, profile, [])
