"""
Personalized Optimization Strategies

This module provides personalized optimization strategies that adapt to
individual user workflows, preferences, and effectiveness patterns.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
import statistics
from collections import defaultdict

from .intelligent_recommender import PersonalizationProfile, IntelligentRecommendation
from .cross_session_analytics import CrossSessionInsights
from .cache_dashboard import CacheEnhancedDashboardData


class StrategyType(Enum):
    """Types of personalized strategies."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    FOCUS = "focus"  # PR19: Priority-based reordering without content removal
    WORKFLOW_SPECIFIC = "workflow_specific"
    LEARNING_ADAPTIVE = "learning_adaptive"


class OptimizationMode(Enum):
    """Optimization execution modes."""

    MANUAL = "manual"
    SEMI_AUTOMATIC = "semi_automatic"
    AUTOMATIC = "automatic"
    PREDICTIVE = "predictive"


@dataclass
class StrategyRule:
    """Individual rule within a strategy."""

    rule_id: str
    name: str
    description: str
    condition: str
    action: str
    parameters: Dict[str, Any]
    effectiveness_score: float
    confidence_level: float
    last_applied: Optional[datetime] = None


@dataclass
class PersonalizedStrategy:
    """Complete personalized optimization strategy."""

    strategy_id: str
    user_id: str
    name: str
    description: str
    strategy_type: StrategyType
    optimization_mode: OptimizationMode

    # Strategy rules and logic
    rules: List[StrategyRule]
    workflow_preferences: Dict[str, Any]
    automation_settings: Dict[str, bool]

    # Performance tracking
    effectiveness_history: List[float]
    success_rate: float
    adaptation_speed: float
    user_satisfaction: float

    # Metadata
    created_at: datetime
    last_updated: datetime
    usage_count: int
    learning_iterations: int
    confidence_score: float


@dataclass
class StrategyRecommendation:
    """Recommendation for strategy adoption or modification."""

    recommendation_id: str
    strategy_type: StrategyType
    title: str
    description: str
    rationale: str
    expected_benefits: List[str]
    implementation_effort: str
    confidence: float
    personalization_fit: float


class PersonalizedOptimizationEngine:
    """
    Engine that creates and manages personalized optimization strategies
    based on user behavior, preferences, and effectiveness patterns.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the personalized optimization engine."""
        self.storage_path = (
            storage_path or Path.home() / ".context_cleaner" / "strategies"
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._user_strategies: Dict[str, List[PersonalizedStrategy]] = {}
        self._strategy_templates: Dict[StrategyType, PersonalizedStrategy] = {}
        self._effectiveness_tracker: Dict[str, List[float]] = defaultdict(list)

        # Initialize default strategy templates (lazy initialization when needed)
        self._templates_initialized = False
        self._initialize_default_templates()

    async def create_personalized_strategy(
        self,
        user_id: str,
        profile: PersonalizationProfile,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
        preferred_type: Optional[StrategyType] = None,
    ) -> PersonalizedStrategy:
        """
        Create a personalized optimization strategy for a user.

        Args:
            user_id: User identifier
            profile: User's personalization profile
            dashboard_data: Current dashboard analysis
            cross_session_insights: Cross-session analysis results
            recommendations: Current intelligent recommendations
            preferred_type: User's preferred strategy type

        Returns:
            Personalized optimization strategy
        """
        # Determine optimal strategy type
        strategy_type = preferred_type or await self._determine_optimal_strategy_type(
            profile, dashboard_data, cross_session_insights
        )

        # Determine optimization mode based on user comfort level
        optimization_mode = self._determine_optimization_mode(profile)

        # Generate strategy rules
        rules = await self._generate_strategy_rules(
            strategy_type,
            profile,
            dashboard_data,
            cross_session_insights,
            recommendations,
        )

        # Create workflow preferences
        workflow_preferences = self._create_workflow_preferences(
            profile, cross_session_insights
        )

        # Configure automation settings
        automation_settings = self._configure_automation_settings(
            profile, optimization_mode
        )

        # Create strategy
        strategy_id = f"{user_id}_{strategy_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        strategy = PersonalizedStrategy(
            strategy_id=strategy_id,
            user_id=user_id,
            name=f"{strategy_type.value.title()} Optimization Strategy",
            description=f"Personalized {strategy_type.value} strategy based on usage patterns and preferences",
            strategy_type=strategy_type,
            optimization_mode=optimization_mode,
            rules=rules,
            workflow_preferences=workflow_preferences,
            automation_settings=automation_settings,
            effectiveness_history=[],
            success_rate=0.0,
            adaptation_speed=1.0,
            user_satisfaction=0.8,  # Start optimistic
            created_at=datetime.now(),
            last_updated=datetime.now(),
            usage_count=0,
            learning_iterations=0,
            confidence_score=0.6,  # Initial confidence
        )

        # Store strategy
        if user_id not in self._user_strategies:
            self._user_strategies[user_id] = []
        self._user_strategies[user_id].append(strategy)

        # Persist strategy
        await self._persist_strategy(strategy)

        return strategy

    async def adapt_strategy(
        self,
        strategy: PersonalizedStrategy,
        effectiveness_feedback: float,
        user_feedback: Optional[str] = None,
        new_data: Optional[Dict[str, Any]] = None,
    ) -> PersonalizedStrategy:
        """
        Adapt strategy based on effectiveness feedback and new data.

        Args:
            strategy: Strategy to adapt
            effectiveness_feedback: Effectiveness score (0-1)
            user_feedback: Optional user feedback
            new_data: Additional data for adaptation

        Returns:
            Updated strategy
        """
        # Update effectiveness history
        strategy.effectiveness_history.append(effectiveness_feedback)

        # Recalculate success rate
        strategy.success_rate = statistics.mean(strategy.effectiveness_history)

        # Adapt rules based on effectiveness
        if effectiveness_feedback < 0.5:
            # Poor effectiveness - adjust strategy
            await self._adjust_strategy_for_poor_performance(strategy)
        elif effectiveness_feedback > 0.8:
            # Good effectiveness - reinforce successful patterns
            await self._reinforce_successful_patterns(strategy)

        # Update adaptation speed
        recent_effectiveness = strategy.effectiveness_history[
            -5:
        ]  # Last 5 applications
        if len(recent_effectiveness) > 1:
            trend = recent_effectiveness[-1] - recent_effectiveness[0]
            strategy.adaptation_speed = max(
                0.1, min(2.0, strategy.adaptation_speed + trend)
            )

        # Update user satisfaction based on feedback
        if user_feedback:
            satisfaction_adjustment = self._parse_user_feedback(user_feedback)
            strategy.user_satisfaction = max(
                0.0, min(1.0, strategy.user_satisfaction + satisfaction_adjustment)
            )

        # Increment counters
        strategy.usage_count += 1
        strategy.learning_iterations += 1
        strategy.last_updated = datetime.now()

        # Recalculate confidence
        strategy.confidence_score = self._calculate_strategy_confidence(strategy)

        # Persist updated strategy
        await self._persist_strategy(strategy)

        return strategy

    async def recommend_strategy_changes(
        self,
        strategy: PersonalizedStrategy,
        recent_performance: List[float],
        current_context: Dict[str, Any],
    ) -> List[StrategyRecommendation]:
        """
        Recommend changes to improve strategy effectiveness.

        Args:
            strategy: Current strategy
            recent_performance: Recent effectiveness scores
            current_context: Current optimization context

        Returns:
            List of strategy recommendations
        """
        recommendations = []

        # Analyze performance trends
        if len(recent_performance) > 3:
            trend = statistics.mean(recent_performance[-3:]) - statistics.mean(
                recent_performance[:-3]
            )

            if trend < -0.2:  # Declining performance
                recommendations.append(
                    StrategyRecommendation(
                        recommendation_id=f"decline_{datetime.now().timestamp()}",
                        strategy_type=StrategyType.LEARNING_ADAPTIVE,
                        title="Address Declining Performance",
                        description="Switch to adaptive learning strategy to address performance decline",
                        rationale="Recent effectiveness scores show declining trend",
                        expected_benefits=[
                            "Improved learning from recent patterns",
                            "Better adaptation to changing workflows",
                            "Recovery of optimization effectiveness",
                        ],
                        implementation_effort="Medium",
                        confidence=0.8,
                        personalization_fit=0.9,
                    )
                )

        # Check if strategy type is still optimal
        if strategy.success_rate < 0.6:
            if strategy.strategy_type == StrategyType.AGGRESSIVE:
                recommendations.append(
                    StrategyRecommendation(
                        recommendation_id=f"moderate_{datetime.now().timestamp()}",
                        strategy_type=StrategyType.BALANCED,
                        title="Moderate Optimization Approach",
                        description="Switch to balanced approach for better user acceptance",
                        rationale="Aggressive strategy showing poor success rate",
                        expected_benefits=[
                            "Higher user acceptance rate",
                            "More sustainable optimization",
                            "Better long-term effectiveness",
                        ],
                        implementation_effort="Low",
                        confidence=0.7,
                        personalization_fit=0.8,
                    )
                )
            elif strategy.strategy_type == StrategyType.CONSERVATIVE:
                recommendations.append(
                    StrategyRecommendation(
                        recommendation_id=f"enhance_{datetime.now().timestamp()}",
                        strategy_type=StrategyType.BALANCED,
                        title="Enhance Optimization Impact",
                        description="Increase optimization impact while maintaining safety",
                        rationale="Conservative approach may be too cautious",
                        expected_benefits=[
                            "Greater optimization impact",
                            "Improved efficiency gains",
                            "Better resource utilization",
                        ],
                        implementation_effort="Medium",
                        confidence=0.6,
                        personalization_fit=0.7,
                    )
                )

        # Check automation opportunities
        if (
            strategy.optimization_mode == OptimizationMode.MANUAL
            and strategy.success_rate > 0.8
        ):
            recommendations.append(
                StrategyRecommendation(
                    recommendation_id=f"automate_{datetime.now().timestamp()}",
                    strategy_type=strategy.strategy_type,  # Keep same type
                    title="Enable Semi-Automatic Mode",
                    description="Enable automation for proven optimization patterns",
                    rationale="High success rate indicates reliable patterns suitable for automation",
                    expected_benefits=[
                        "Reduced manual intervention",
                        "Faster optimization cycles",
                        "Consistent application of proven patterns",
                    ],
                    implementation_effort="Low",
                    confidence=0.9,
                    personalization_fit=0.8,
                )
            )

        # Workflow-specific recommendations
        workflow_performance = self._analyze_workflow_performance(
            strategy, current_context
        )
        for workflow, performance in workflow_performance.items():
            if performance < 0.5:
                recommendations.append(
                    StrategyRecommendation(
                        recommendation_id=f"workflow_{workflow}_{datetime.now().timestamp()}",
                        strategy_type=StrategyType.WORKFLOW_SPECIFIC,
                        title=f"Optimize {workflow} Workflow",
                        description=f"Create specialized optimization for {workflow} workflow",
                        rationale=f"{workflow} workflow showing poor optimization effectiveness",
                        expected_benefits=[
                            f"Improved {workflow} workflow efficiency",
                            "Specialized optimization patterns",
                            "Better context alignment",
                        ],
                        implementation_effort="Medium",
                        confidence=0.7,
                        personalization_fit=0.9,
                    )
                )

        return sorted(
            recommendations,
            key=lambda r: r.confidence * r.personalization_fit,
            reverse=True,
        )

    async def apply_strategy(
        self, strategy: PersonalizedStrategy, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply a personalized strategy to optimize context.

        Args:
            strategy: Strategy to apply
            context: Current context to optimize

        Returns:
            Optimization results and applied actions
        """
        applied_actions = []
        optimization_results = {
            "actions_applied": [],
            "estimated_improvements": {},
            "confidence_scores": {},
            "next_actions": [],
        }

        # Apply rules in order of effectiveness
        sorted_rules = sorted(
            strategy.rules, key=lambda r: r.effectiveness_score, reverse=True
        )

        for rule in sorted_rules:
            if await self._should_apply_rule(rule, context, strategy.optimization_mode):
                try:
                    result = await self._apply_optimization_rule(rule, context)
                    applied_actions.append(
                        {
                            "rule_id": rule.rule_id,
                            "rule_name": rule.name,
                            "action": rule.action,
                            "result": result,
                            "confidence": rule.confidence_level,
                        }
                    )
                    rule.last_applied = datetime.now()
                except Exception as e:
                    # Log failure but continue
                    applied_actions.append(
                        {
                            "rule_id": rule.rule_id,
                            "rule_name": rule.name,
                            "action": rule.action,
                            "result": f"Failed: {str(e)}",
                            "confidence": 0.0,
                        }
                    )

        optimization_results["actions_applied"] = applied_actions

        # Calculate estimated improvements
        optimization_results["estimated_improvements"] = {
            "token_savings": sum(
                [
                    action.get("result", {}).get("token_savings", 0)
                    for action in applied_actions
                ]
            ),
            "efficiency_gain": sum(
                [
                    action.get("result", {}).get("efficiency_gain", 0)
                    for action in applied_actions
                ]
            ),
            "focus_improvement": max(
                [
                    action.get("result", {}).get("focus_improvement", 0)
                    for action in applied_actions
                ]
            ),
        }

        # Calculate confidence scores
        optimization_results["confidence_scores"] = {
            "overall_confidence": strategy.confidence_score,
            "application_confidence": (
                statistics.mean(
                    [action.get("confidence", 0) for action in applied_actions]
                )
                if applied_actions
                else 0
            ),
            "strategy_effectiveness": strategy.success_rate,
        }

        # Suggest next actions
        optimization_results["next_actions"] = await self._suggest_next_actions(
            strategy, context, applied_actions
        )

        return optimization_results

    async def _determine_optimal_strategy_type(
        self,
        profile: PersonalizationProfile,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
    ) -> StrategyType:
        """Determine optimal strategy type for user."""

        # Check user preferences first
        if "conservative" in profile.preferred_optimization_modes:
            return StrategyType.CONSERVATIVE
        elif "aggressive" in profile.preferred_optimization_modes:
            return StrategyType.AGGRESSIVE
        elif "balanced" in profile.preferred_optimization_modes:
            return StrategyType.BALANCED

        # Analyze context health and user adaptation
        health_score = dashboard_data.health_metrics.overall_health_score
        adaptation_score = cross_session_insights.user_adaptation_score
        automation_comfort = profile.automation_comfort_level

        # Decision logic based on analysis
        if health_score < 0.4:  # Poor health - need aggressive action
            return StrategyType.AGGRESSIVE
        elif (
            health_score > 0.8 and adaptation_score > 0.7
        ):  # Good health and adaptation - use learning
            return StrategyType.LEARNING_ADAPTIVE
        elif (
            automation_comfort > 0.7
        ):  # Comfortable with automation - balanced approach
            return StrategyType.BALANCED
        else:  # Default to conservative
            return StrategyType.CONSERVATIVE

    def _determine_optimization_mode(
        self, profile: PersonalizationProfile
    ) -> OptimizationMode:
        """Determine optimization mode based on user preferences."""
        comfort_level = profile.automation_comfort_level

        if comfort_level < 0.3:
            return OptimizationMode.MANUAL
        elif comfort_level < 0.7:
            return OptimizationMode.SEMI_AUTOMATIC
        else:
            return OptimizationMode.AUTOMATIC

    async def _generate_strategy_rules(
        self,
        strategy_type: StrategyType,
        profile: PersonalizationProfile,
        dashboard_data: CacheEnhancedDashboardData,
        cross_session_insights: CrossSessionInsights,
        recommendations: List[IntelligentRecommendation],
    ) -> List[StrategyRule]:
        """Generate strategy rules based on analysis and preferences."""
        rules = []

        # Base rules from strategy type template
        if strategy_type == StrategyType.CONSERVATIVE:
            rules.extend(self._get_conservative_rules())
        elif strategy_type == StrategyType.AGGRESSIVE:
            rules.extend(self._get_aggressive_rules())
        elif strategy_type == StrategyType.BALANCED:
            rules.extend(self._get_balanced_rules())
        elif strategy_type == StrategyType.LEARNING_ADAPTIVE:
            rules.extend(self._get_adaptive_rules())
        elif strategy_type == StrategyType.WORKFLOW_SPECIFIC:
            rules.extend(self._get_workflow_specific_rules(cross_session_insights))

        # Customize rules based on recommendations
        for rec in recommendations:
            if rec.priority.value in ["critical", "high"]:
                custom_rule = self._create_rule_from_recommendation(rec)
                rules.append(custom_rule)

        # Add usage-pattern-specific rules
        if dashboard_data.usage_summary:
            usage_rules = self._create_usage_pattern_rules(dashboard_data.usage_summary)
            rules.extend(usage_rules)

        # Add token efficiency rules
        if dashboard_data.token_analysis:
            token_rules = self._create_token_efficiency_rules(
                dashboard_data.token_analysis
            )
            rules.extend(token_rules)

        return rules[:15]  # Limit to 15 rules for performance

    def _create_workflow_preferences(
        self,
        profile: PersonalizationProfile,
        cross_session_insights: CrossSessionInsights,
    ) -> Dict[str, Any]:
        """Create workflow preferences based on user data."""
        preferences = {
            "preferred_workflows": profile.frequent_workflows,
            "session_length_preference": profile.typical_session_length.total_seconds()
            / 3600,  # hours
            "file_type_preferences": profile.common_file_types,
            "optimization_frequency": profile.optimization_frequency,
            "confirmation_requirements": profile.confirmation_preferences,
        }

        # Add insights from cross-session analysis
        if cross_session_insights.workflow_templates:
            template_prefs = {}
            for template in cross_session_insights.workflow_templates:
                template_prefs[template.template_id] = {
                    "usage_frequency": template.usage_frequency,
                    "success_rate": template.success_rate,
                    "optimization_strategy": template.optimization_strategy,
                }
            preferences["workflow_templates"] = template_prefs

        return preferences

    def _configure_automation_settings(
        self, profile: PersonalizationProfile, optimization_mode: OptimizationMode
    ) -> Dict[str, bool]:
        """Configure automation settings based on user preferences."""
        base_settings = {
            "auto_remove_duplicates": False,
            "auto_consolidate_similar": False,
            "auto_reorder_priority": False,
            "auto_summarize_verbose": False,
            "auto_remove_stale": False,
            "require_confirmation_high_risk": True,
            "require_confirmation_bulk_delete": True,
            "enable_predictive_optimization": False,
        }

        # Adjust based on optimization mode
        if optimization_mode == OptimizationMode.AUTOMATIC:
            base_settings.update(
                {
                    "auto_remove_duplicates": True,
                    "auto_consolidate_similar": True,
                    "auto_reorder_priority": True,
                    "require_confirmation_high_risk": False,
                }
            )
        elif optimization_mode == OptimizationMode.SEMI_AUTOMATIC:
            base_settings.update(
                {"auto_remove_duplicates": True, "auto_reorder_priority": True}
            )

        # Apply user preferences
        base_settings.update(profile.confirmation_preferences)

        return base_settings

    # Rule generation methods
    def _get_conservative_rules(self) -> List[StrategyRule]:
        """Get conservative optimization rules."""
        return [
            StrategyRule(
                rule_id="conservative_duplicate_removal",
                name="Safe Duplicate Removal",
                description="Remove only obvious duplicates with confirmation",
                condition="duplicate_confidence > 0.9",
                action="remove_duplicates",
                parameters={"confirmation_required": True, "confidence_threshold": 0.9},
                effectiveness_score=0.7,
                confidence_level=0.9,
            ),
            StrategyRule(
                rule_id="conservative_stale_removal",
                name="Remove Very Old Content",
                description="Remove content older than 30 days with confirmation",
                condition="content_age_days > 30",
                action="remove_stale",
                parameters={"age_threshold_days": 30, "confirmation_required": True},
                effectiveness_score=0.6,
                confidence_level=0.8,
            ),
        ]

    def _get_aggressive_rules(self) -> List[StrategyRule]:
        """Get aggressive optimization rules."""
        return [
            StrategyRule(
                rule_id="aggressive_duplicate_removal",
                name="Aggressive Duplicate Removal",
                description="Remove duplicates with lower confidence threshold",
                condition="duplicate_confidence > 0.7",
                action="remove_duplicates",
                parameters={
                    "confirmation_required": False,
                    "confidence_threshold": 0.7,
                },
                effectiveness_score=0.8,
                confidence_level=0.7,
            ),
            StrategyRule(
                rule_id="aggressive_consolidation",
                name="Aggressive Content Consolidation",
                description="Consolidate similar content automatically",
                condition="similarity_score > 0.8",
                action="consolidate_similar",
                parameters={"similarity_threshold": 0.8, "auto_apply": True},
                effectiveness_score=0.9,
                confidence_level=0.8,
            ),
            StrategyRule(
                rule_id="aggressive_stale_removal",
                name="Remove Recent Stale Content",
                description="Remove content older than 7 days",
                condition="content_age_days > 7",
                action="remove_stale",
                parameters={"age_threshold_days": 7, "confirmation_required": False},
                effectiveness_score=0.7,
                confidence_level=0.6,
            ),
        ]

    def _get_balanced_rules(self) -> List[StrategyRule]:
        """Get balanced optimization rules."""
        return [
            StrategyRule(
                rule_id="balanced_duplicate_removal",
                name="Balanced Duplicate Removal",
                description="Remove duplicates with moderate confidence",
                condition="duplicate_confidence > 0.8",
                action="remove_duplicates",
                parameters={"confirmation_required": True, "confidence_threshold": 0.8},
                effectiveness_score=0.8,
                confidence_level=0.8,
            ),
            StrategyRule(
                rule_id="balanced_priority_reorder",
                name="Priority-Based Reordering",
                description="Reorder content based on usage patterns",
                condition="usage_frequency_available",
                action="reorder_priority",
                parameters={"usage_weight": 0.7, "recency_weight": 0.3},
                effectiveness_score=0.7,
                confidence_level=0.9,
            ),
        ]

    def _get_adaptive_rules(self) -> List[StrategyRule]:
        """Get adaptive learning rules."""
        return [
            StrategyRule(
                rule_id="adaptive_pattern_learning",
                name="Learn from User Patterns",
                description="Adapt optimization based on user behavior",
                condition="sufficient_usage_data",
                action="learn_and_adapt",
                parameters={"learning_rate": 0.1, "adaptation_threshold": 0.05},
                effectiveness_score=0.9,
                confidence_level=0.7,
            ),
            StrategyRule(
                rule_id="adaptive_feedback_integration",
                name="Integrate User Feedback",
                description="Adjust strategies based on user feedback",
                condition="user_feedback_available",
                action="adapt_from_feedback",
                parameters={"feedback_weight": 0.8, "historical_weight": 0.2},
                effectiveness_score=0.8,
                confidence_level=0.8,
            ),
        ]

    def _get_workflow_specific_rules(
        self, insights: CrossSessionInsights
    ) -> List[StrategyRule]:
        """Get workflow-specific rules based on insights."""
        rules = []

        for template in insights.workflow_templates:
            rule = StrategyRule(
                rule_id=f"workflow_{template.template_id}",
                name=f"Optimize for {template.name}",
                description=f"Apply {template.name} specific optimizations",
                condition=f"workflow_type == '{template.name}'",
                action="apply_workflow_template",
                parameters={
                    "template_id": template.template_id,
                    "strategy": template.optimization_strategy,
                },
                effectiveness_score=template.success_rate,
                confidence_level=min(0.9, template.success_rate + 0.1),
            )
            rules.append(rule)

        return rules

    def _create_rule_from_recommendation(
        self, recommendation: IntelligentRecommendation
    ) -> StrategyRule:
        """Create a strategy rule from an intelligent recommendation."""
        return StrategyRule(
            rule_id=f"rec_{recommendation.id}",
            name=recommendation.title,
            description=recommendation.description,
            condition=f"category == '{recommendation.category.value}'",
            action="apply_recommendation",
            parameters={
                "recommendation_id": recommendation.id,
                "actions": [asdict(action) for action in recommendation.actions],
            },
            effectiveness_score=recommendation.historical_effectiveness,
            confidence_level=recommendation.learning_confidence,
        )

    def _create_usage_pattern_rules(self, usage_summary) -> List[StrategyRule]:
        """Create rules based on usage patterns."""
        rules = []

        # High-frequency file prioritization
        rules.append(
            StrategyRule(
                rule_id="prioritize_frequent_files",
                name="Prioritize Frequently Accessed Files",
                description="Move frequently accessed files to top of context",
                condition="file_access_frequency > average",
                action="prioritize_files",
                parameters={"frequency_threshold": "top_20_percent"},
                effectiveness_score=0.8,
                confidence_level=0.9,
            )
        )

        return rules

    def _create_token_efficiency_rules(self, token_analysis) -> List[StrategyRule]:
        """Create rules based on token analysis."""
        rules = []

        if token_analysis.waste_percentage > 20:
            rules.append(
                StrategyRule(
                    rule_id="reduce_token_waste",
                    name="Reduce Token Waste",
                    description="Remove high-waste patterns to improve efficiency",
                    condition="waste_percentage > 20",
                    action="remove_waste_patterns",
                    parameters={
                        "waste_patterns": [
                            p.pattern for p in token_analysis.waste_patterns[:3]
                        ]
                    },
                    effectiveness_score=0.9,
                    confidence_level=0.8,
                )
            )

        return rules

    async def _should_apply_rule(
        self,
        rule: StrategyRule,
        context: Dict[str, Any],
        optimization_mode: OptimizationMode,
    ) -> bool:
        """Determine if a rule should be applied given current context."""

        # Check if rule was recently applied
        if rule.last_applied:
            time_since_last = datetime.now() - rule.last_applied
            if time_since_last < timedelta(
                minutes=30
            ):  # Minimum 30 minutes between applications
                return False

        # Check optimization mode permissions
        if optimization_mode == OptimizationMode.MANUAL:
            return False  # Manual mode requires explicit user action

        # Check confidence threshold
        if rule.confidence_level < 0.6:
            return False  # Don't apply low-confidence rules automatically

        # Evaluate condition (simplified - would use more sophisticated condition parsing)
        return self._evaluate_rule_condition(rule.condition, context)

    def _evaluate_rule_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate rule condition against current context."""
        # Simplified condition evaluation
        # In production, would use a proper condition parser/evaluator

        if "duplicate_confidence" in condition:
            return context.get("duplicate_confidence", 0) > 0.8
        elif "content_age_days" in condition:
            return context.get("content_age_days", 0) > 7
        elif "usage_frequency_available" in condition:
            return "usage_patterns" in context
        elif "sufficient_usage_data" in condition:
            return context.get("session_count", 0) > 5

        return True  # Default to True for unknown conditions

    async def _apply_optimization_rule(
        self, rule: StrategyRule, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply an optimization rule to the context."""
        result = {
            "token_savings": 0,
            "efficiency_gain": 0.0,
            "focus_improvement": 0.0,
            "changes_made": [],
        }

        # Simplified rule application - in production would have full implementation
        if rule.action == "remove_duplicates":
            result.update(
                {
                    "token_savings": 500,
                    "efficiency_gain": 0.1,
                    "changes_made": ["Removed duplicate content"],
                }
            )
        elif rule.action == "consolidate_similar":
            result.update(
                {
                    "token_savings": 300,
                    "efficiency_gain": 0.15,
                    "changes_made": ["Consolidated similar content blocks"],
                }
            )
        elif rule.action == "reorder_priority":
            result.update(
                {
                    "focus_improvement": 0.2,
                    "changes_made": ["Reordered content by priority"],
                }
            )
        elif rule.action == "remove_stale":
            result.update(
                {
                    "token_savings": 800,
                    "efficiency_gain": 0.05,
                    "changes_made": ["Removed stale content"],
                }
            )

        return result

    async def _suggest_next_actions(
        self,
        strategy: PersonalizedStrategy,
        context: Dict[str, Any],
        applied_actions: List[Dict[str, Any]],
    ) -> List[str]:
        """Suggest next optimization actions."""
        suggestions = []

        # Based on what was applied
        if not applied_actions:
            suggestions.append("Consider running manual optimization first")

        # Based on strategy effectiveness
        if strategy.success_rate < 0.6:
            suggestions.append("Review and adjust strategy parameters")

        # Based on context analysis
        if context.get("health_score", 0.5) < 0.6:
            suggestions.append("Consider more aggressive optimization")

        suggestions.append("Monitor effectiveness and provide feedback")

        return suggestions

    def _adjust_strategy_for_poor_performance(
        self, strategy: PersonalizedStrategy
    ) -> None:
        """Adjust strategy rules for poor performance."""
        # Lower confidence thresholds for rules
        for rule in strategy.rules:
            rule.confidence_level = max(0.3, rule.confidence_level - 0.1)

        # Adjust automation settings to be more conservative
        strategy.automation_settings["require_confirmation_high_risk"] = True
        strategy.automation_settings["auto_remove_stale"] = False

    def _reinforce_successful_patterns(self, strategy: PersonalizedStrategy) -> None:
        """Reinforce successful patterns in strategy."""
        # Increase confidence for effective rules
        recent_effectiveness = strategy.effectiveness_history[-3:]
        if statistics.mean(recent_effectiveness) > 0.8:
            for rule in strategy.rules:
                rule.effectiveness_score = min(1.0, rule.effectiveness_score + 0.05)

    def _parse_user_feedback(self, feedback: str) -> float:
        """Parse user feedback into satisfaction adjustment."""
        feedback_lower = feedback.lower()

        if any(
            word in feedback_lower for word in ["great", "excellent", "perfect", "love"]
        ):
            return 0.1
        elif any(word in feedback_lower for word in ["good", "helpful", "nice"]):
            return 0.05
        elif any(
            word in feedback_lower for word in ["bad", "terrible", "hate", "awful"]
        ):
            return -0.2
        elif any(word in feedback_lower for word in ["okay", "fine", "average"]):
            return 0.0
        else:
            return 0.0

    def _calculate_strategy_confidence(self, strategy: PersonalizedStrategy) -> float:
        """Calculate overall confidence score for strategy."""
        factors = []

        # Usage count factor
        usage_factor = min(1.0, strategy.usage_count / 20.0)
        factors.append(usage_factor)

        # Success rate factor
        factors.append(strategy.success_rate)

        # User satisfaction factor
        factors.append(strategy.user_satisfaction)

        # Rule confidence factor
        rule_confidences = [rule.confidence_level for rule in strategy.rules]
        if rule_confidences:
            factors.append(statistics.mean(rule_confidences))

        return statistics.mean(factors) if factors else 0.5

    def _analyze_workflow_performance(
        self, strategy: PersonalizedStrategy, context: Dict[str, Any]
    ) -> Dict[str, float]:
        """Analyze performance by workflow type."""
        # Simplified analysis - would track actual performance by workflow
        workflow_performance = {}

        for workflow in strategy.workflow_preferences.get("preferred_workflows", []):
            # Mock performance data
            workflow_performance[workflow] = max(
                0.1, strategy.success_rate + (hash(workflow) % 100) / 500.0
            )

        return workflow_performance

    def _initialize_default_templates(self) -> None:
        """Initialize default strategy templates."""
        # This would load/create default templates for each strategy type
        if self._templates_initialized:
            return
        self._templates_initialized = True

    async def _persist_strategy(self, strategy: PersonalizedStrategy) -> None:
        """Persist strategy to storage."""
        try:
            strategy_path = self.storage_path / f"strategy_{strategy.strategy_id}.json"

            with open(strategy_path, "w") as f:
                json.dump(asdict(strategy), f, default=str, indent=2)

        except Exception:
            pass  # Silent fail for persistence

    async def load_user_strategies(self, user_id: str) -> List[PersonalizedStrategy]:
        """Load all strategies for a user."""
        strategies = []

        try:
            for strategy_file in self.storage_path.glob(f"strategy_{user_id}_*.json"):
                with open(strategy_file, "r") as f:
                    data = json.load(f)
                    # Note: This would need proper deserialization in production
                    strategies.append(data)
        except Exception:
            pass

        return strategies
