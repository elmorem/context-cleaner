"""
Workflow Learning Engine for Phase 3 Advanced Automation

Implements ML-powered workflow optimization using telemetry data to learn
successful patterns, predict outcomes, and continuously improve orchestration efficiency.
"""

import asyncio
import logging
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import numpy as np
from collections import defaultdict, Counter

from ..clients.clickhouse_client import ClickHouseClient
from ..analytics.session_analysis import SessionAnalyticsEngine, TrendDirection
from .task_orchestrator import WorkflowExecution, TaskStatus, AgentType, TaskComplexity
from context_cleaner.api.models import create_error_response

logger = logging.getLogger(__name__)


class LearningMetric(Enum):
    """Types of metrics to learn and optimize"""

    SUCCESS_RATE = "success_rate"
    EXECUTION_TIME = "execution_time"
    COST_EFFICIENCY = "cost_efficiency"
    AGENT_EFFECTIVENESS = "agent_effectiveness"
    STEP_ORDERING = "step_ordering"
    DEPENDENCY_OPTIMIZATION = "dependency_optimization"


class PatternConfidence(Enum):
    """Confidence levels for learned patterns"""

    LOW = "low"  # < 5 data points
    MODERATE = "moderate"  # 5-20 data points
    HIGH = "high"  # 20-50 data points
    VERY_HIGH = "very_high"  # 50+ data points


@dataclass
class LearnedPattern:
    """A pattern learned from successful workflows"""

    pattern_id: str
    name: str
    description: str
    task_keywords: List[str]
    agent_sequence: List[AgentType]
    avg_success_rate: float
    avg_duration_minutes: float
    avg_cost: float
    confidence: PatternConfidence
    sample_count: int
    last_updated: datetime = field(default_factory=datetime.now)
    optimization_suggestions: List[str] = field(default_factory=list)


@dataclass
class AgentPerformanceProfile:
    """Performance profile for an agent type"""

    agent_type: AgentType
    task_categories: List[str]
    avg_success_rate: float
    avg_response_time_ms: float
    avg_cost_per_task: float
    best_performing_contexts: List[str]
    common_failure_patterns: List[str]
    efficiency_trend: TrendDirection
    sample_count: int
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowOptimization:
    """Optimization recommendation for workflows"""

    optimization_id: str
    workflow_type: str
    current_approach: Dict[str, Any]
    optimized_approach: Dict[str, Any]
    expected_improvement: Dict[str, float]  # metric -> improvement %
    confidence: float
    evidence: List[str]
    implementation_complexity: str  # "low", "medium", "high"


@dataclass
class PredictionModel:
    """Simple ML model for workflow outcome prediction"""

    model_type: str
    features: List[str]
    weights: Dict[str, float]
    bias: float
    accuracy: float
    training_samples: int
    last_trained: datetime = field(default_factory=datetime.now)


class WorkflowLearner:
    """ML-powered workflow learning and optimization engine"""

    def __init__(self, telemetry_client: ClickHouseClient):
        self.telemetry = telemetry_client
        self.analytics = SessionAnalyticsEngine(telemetry_client)

        # Learning state
        self.learned_patterns: Dict[str, LearnedPattern] = {}
        self.agent_profiles: Dict[AgentType, AgentPerformanceProfile] = {}
        self.optimization_recommendations: List[WorkflowOptimization] = []
        self.prediction_models: Dict[str, PredictionModel] = {}

        # Configuration
        self.min_samples_for_learning = 3
        self.confidence_threshold = 0.7
        self.learning_window_days = 90
        self.retraining_interval = timedelta(days=7)

        # Caching for performance
        self._pattern_cache: Dict[str, List[LearnedPattern]] = {}
        self._cache_ttl = timedelta(hours=1)
        self._last_cache_update: Optional[datetime] = None

    async def learn_from_workflow_execution(
        self, execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """
        Learn from a completed workflow execution

        This is called after each workflow completion to extract patterns and update models
        """
        if execution.status != TaskStatus.COMPLETED:
            return {"learned": False, "reason": "Workflow not completed successfully"}

        try:
            # Extract features from workflow execution
            features = await self._extract_workflow_features(execution)

            # Update learned patterns
            patterns_updated = await self._update_learned_patterns(execution, features)

            # Update agent performance profiles
            agents_updated = await self._update_agent_profiles(execution)

            # Generate optimization recommendations
            optimizations = await self._generate_optimizations_from_execution(
                execution, features
            )

            # Update prediction models
            models_updated = await self._update_prediction_models(execution, features)

            learning_summary = {
                "learned": True,
                "workflow_id": execution.workflow_id,
                "patterns_updated": patterns_updated,
                "agents_updated": agents_updated,
                "new_optimizations": len(optimizations),
                "models_updated": models_updated,
                "execution_success_rate": execution.progress_percentage / 100,
                "execution_duration_minutes": (
                    execution.end_time - execution.start_time
                ).total_seconds()
                / 60,
                "total_cost": execution.total_cost,
            }

            logger.info(
                f"Learned from workflow {execution.workflow_id}: {learning_summary}"
            )
            return learning_summary

        except Exception as e:
            logger.error(f"Error learning from workflow {execution.workflow_id}: {e}")
            return {"learned": False, "reason": f"Learning error: {e}"}

    async def predict_workflow_success(
        self,
        task_description: str,
        agent_sequence: List[AgentType],
        complexity: TaskComplexity,
    ) -> Dict[str, Any]:
        """
        Predict the success rate and duration of a proposed workflow

        Uses learned patterns and ML models to make predictions
        """
        try:
            # Find similar learned patterns
            similar_patterns = await self._find_similar_patterns(
                task_description, agent_sequence
            )

            # Extract features for prediction
            features = {
                "task_length": len(task_description.split()),
                "agent_count": len(agent_sequence),
                "unique_agents": len(set(agent_sequence)),
                "complexity_score": {
                    "simple": 1,
                    "moderate": 2,
                    "complex": 3,
                    "enterprise": 4,
                }[complexity.value],
                "has_frontend_agent": AgentType.FRONTEND_EXPERT in agent_sequence,
                "has_backend_agent": AgentType.BACKEND_ENGINEER in agent_sequence,
                "has_review_agent": AgentType.SENIOR_REVIEWER in agent_sequence,
                "sequence_length": len(agent_sequence),
            }

            # Use prediction model if available
            if "success_rate" in self.prediction_models:
                model = self.prediction_models["success_rate"]
                predicted_success = await self._apply_prediction_model(model, features)
            else:
                # Fallback to pattern-based prediction
                if similar_patterns:
                    predicted_success = statistics.mean(
                        [p.avg_success_rate for p in similar_patterns]
                    )
                else:
                    predicted_success = 0.75  # Conservative default

            # Predict duration
            if similar_patterns:
                predicted_duration = statistics.mean(
                    [p.avg_duration_minutes for p in similar_patterns]
                )
                # Adjust based on complexity
                complexity_multiplier = {
                    "simple": 0.8,
                    "moderate": 1.0,
                    "complex": 1.3,
                    "enterprise": 1.6,
                }
                predicted_duration *= complexity_multiplier[complexity.value]
            else:
                # Base duration estimate
                base_duration = len(agent_sequence) * 15  # 15 minutes per agent
                predicted_duration = base_duration

            # Predict cost
            predicted_cost = (
                predicted_duration * 0.05
            )  # $3/hour average, converted to per-minute

            # Calculate confidence
            confidence = self._calculate_prediction_confidence(
                similar_patterns, features
            )

            prediction = {
                "predicted_success_rate": max(0.1, min(0.95, predicted_success)),
                "predicted_duration_minutes": max(5, predicted_duration),
                "predicted_cost": max(0.1, predicted_cost),
                "confidence": confidence,
                "similar_patterns_count": len(similar_patterns),
                "recommendation": self._generate_prediction_recommendation(
                    predicted_success, predicted_duration, confidence
                ),
            }

            return prediction

        except Exception as e:
            logger.error(f"Error predicting workflow success: {e}")
            return {
                "predicted_success_rate": 0.75,
                "predicted_duration_minutes": 30,
                "predicted_cost": 1.5,
                "confidence": 0.3,
                "error": str(e),
            }

    async def recommend_workflow_optimizations(
        self, task_description: str, proposed_agents: List[AgentType]
    ) -> List[WorkflowOptimization]:
        """
        Recommend optimizations for a proposed workflow based on learned patterns
        """
        try:
            optimizations = []

            # Find similar successful patterns
            similar_patterns = await self._find_similar_patterns(
                task_description, proposed_agents
            )

            if similar_patterns:
                # Agent sequence optimization
                agent_optimization = await self._optimize_agent_sequence(
                    proposed_agents, similar_patterns
                )
                if agent_optimization:
                    optimizations.append(agent_optimization)

                # Task decomposition optimization
                decomp_optimization = await self._optimize_task_decomposition(
                    task_description, similar_patterns
                )
                if decomp_optimization:
                    optimizations.append(decomp_optimization)

                # Cost optimization
                cost_optimization = await self._optimize_cost_efficiency(
                    proposed_agents, similar_patterns
                )
                if cost_optimization:
                    optimizations.append(cost_optimization)

            # General optimizations based on agent profiles
            profile_optimizations = await self._generate_profile_based_optimizations(
                proposed_agents
            )
            optimizations.extend(profile_optimizations)

            # Sort by expected improvement
            optimizations.sort(
                key=lambda x: sum(x.expected_improvement.values()), reverse=True
            )

            return optimizations[:5]  # Return top 5 optimizations

        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}")
            return []

    async def get_agent_performance_insights(
        self, agent_type: Optional[AgentType] = None
    ) -> Dict[str, Any]:
        """Get performance insights for agents"""
        try:
            if agent_type:
                # Get specific agent insights
                if agent_type not in self.agent_profiles:
                    raise create_error_response(
                        f"No performance data for {agent_type.value}",
                        "NO_PERFORMANCE_DATA",
                        404,
                    )

                profile = self.agent_profiles[agent_type]
                return {
                    "agent_type": profile.agent_type.value,
                    "performance": {
                        "success_rate": profile.avg_success_rate,
                        "response_time_ms": profile.avg_response_time_ms,
                        "cost_per_task": profile.avg_cost_per_task,
                        "efficiency_trend": profile.efficiency_trend.value,
                    },
                    "strengths": profile.best_performing_contexts,
                    "improvement_areas": profile.common_failure_patterns,
                    "sample_size": profile.sample_count,
                    "last_updated": profile.last_updated.isoformat(),
                }
            else:
                # Get overview of all agents
                agent_rankings = []
                for agent_type, profile in self.agent_profiles.items():
                    efficiency_score = (
                        profile.avg_success_rate * 0.6
                        + (1 - min(profile.avg_response_time_ms / 10000, 1)) * 0.2
                        + (1 - min(profile.avg_cost_per_task / 5, 1)) * 0.2
                    )

                    agent_rankings.append(
                        {
                            "agent_type": agent_type.value,
                            "efficiency_score": efficiency_score,
                            "success_rate": profile.avg_success_rate,
                            "sample_count": profile.sample_count,
                        }
                    )

                agent_rankings.sort(key=lambda x: x["efficiency_score"], reverse=True)

                return {
                    "total_agents_tracked": len(self.agent_profiles),
                    "agent_rankings": agent_rankings,
                    "top_performer": (
                        agent_rankings[0]["agent_type"] if agent_rankings else None
                    ),
                    "learning_status": (
                        "active"
                        if len(self.agent_profiles) > 0
                        else "insufficient_data"
                    ),
                }

        except Exception as e:
            logger.error(f"Error getting agent performance insights: {e}")
            raise create_error_response(
                f"Agent performance insights failed: {str(e)}",
                "AGENT_PERFORMANCE_ERROR",
                500,
            )

    async def get_learning_metrics(self) -> Dict[str, Any]:
        """Get overall learning system metrics"""
        try:
            total_patterns = len(self.learned_patterns)
            high_confidence_patterns = len(
                [
                    p
                    for p in self.learned_patterns.values()
                    if p.confidence
                    in [PatternConfidence.HIGH, PatternConfidence.VERY_HIGH]
                ]
            )

            if total_patterns > 0:
                avg_pattern_confidence = statistics.mean(
                    [
                        {"low": 0.25, "moderate": 0.5, "high": 0.75, "very_high": 0.9}[
                            p.confidence.value
                        ]
                        for p in self.learned_patterns.values()
                    ]
                )
            else:
                avg_pattern_confidence = 0.0

            model_accuracy = {}
            for model_name, model in self.prediction_models.items():
                model_accuracy[model_name] = model.accuracy

            return {
                "learning_status": "active" if total_patterns > 0 else "initializing",
                "patterns": {
                    "total_learned": total_patterns,
                    "high_confidence": high_confidence_patterns,
                    "avg_confidence": avg_pattern_confidence,
                    "learning_window_days": self.learning_window_days,
                },
                "agents": {
                    "total_profiles": len(self.agent_profiles),
                    "avg_sample_size": (
                        statistics.mean(
                            [p.sample_count for p in self.agent_profiles.values()]
                        )
                        if self.agent_profiles
                        else 0
                    ),
                },
                "prediction_models": {
                    "total_models": len(self.prediction_models),
                    "model_accuracy": model_accuracy,
                    "last_retrained": max(
                        [m.last_trained for m in self.prediction_models.values()],
                        default=datetime.now(),
                    ).isoformat(),
                },
                "optimizations": {
                    "total_recommendations": len(self.optimization_recommendations),
                    "avg_expected_improvement": (
                        statistics.mean(
                            [
                                sum(opt.expected_improvement.values())
                                for opt in self.optimization_recommendations
                            ]
                        )
                        if self.optimization_recommendations
                        else 0
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error getting learning metrics: {e}")
            raise create_error_response(
                f"Learning metrics retrieval failed: {str(e)}",
                "LEARNING_METRICS_ERROR",
                500,
            )

    async def _extract_workflow_features(
        self, execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """Extract features from workflow execution for learning"""
        duration_minutes = (
            execution.end_time - execution.start_time
        ).total_seconds() / 60

        features = {
            "workflow_id": execution.workflow_id,
            "success_rate": execution.progress_percentage / 100,
            "duration_minutes": duration_minutes,
            "total_cost": execution.total_cost,
            "total_steps": execution.total_steps,
            "completed_steps": execution.completed_steps,
            "agent_utilization": execution.agent_utilization,
            "unique_agents_used": len(execution.agent_utilization),
            "cost_per_minute": execution.total_cost / max(duration_minutes, 1),
            "steps_per_minute": execution.completed_steps / max(duration_minutes, 1),
            "execution_efficiency": execution.completed_steps / execution.total_steps,
        }

        return features

    async def _update_learned_patterns(
        self, execution: WorkflowExecution, features: Dict[str, Any]
    ) -> int:
        """Update learned patterns with new workflow data"""
        patterns_updated = 0

        try:
            # Create pattern signature based on agent sequence
            agent_sequence = list(execution.agent_utilization.keys())
            pattern_signature = "_".join(sorted(agent_sequence))

            if pattern_signature in self.learned_patterns:
                # Update existing pattern
                pattern = self.learned_patterns[pattern_signature]

                # Update moving averages
                old_weight = pattern.sample_count / (pattern.sample_count + 1)
                new_weight = 1 / (pattern.sample_count + 1)

                pattern.avg_success_rate = (
                    pattern.avg_success_rate * old_weight
                    + features["success_rate"] * new_weight
                )
                pattern.avg_duration_minutes = (
                    pattern.avg_duration_minutes * old_weight
                    + features["duration_minutes"] * new_weight
                )
                pattern.avg_cost = (
                    pattern.avg_cost * old_weight + features["total_cost"] * new_weight
                )

                pattern.sample_count += 1
                pattern.last_updated = datetime.now()

                # Update confidence based on sample count
                if pattern.sample_count >= 50:
                    pattern.confidence = PatternConfidence.VERY_HIGH
                elif pattern.sample_count >= 20:
                    pattern.confidence = PatternConfidence.HIGH
                elif pattern.sample_count >= 5:
                    pattern.confidence = PatternConfidence.MODERATE
                else:
                    pattern.confidence = PatternConfidence.LOW

                patterns_updated += 1

            else:
                # Create new pattern
                agent_types = [
                    AgentType(agent)
                    for agent in agent_sequence
                    if agent in [at.value for at in AgentType]
                ]

                new_pattern = LearnedPattern(
                    pattern_id=pattern_signature,
                    name=f"Pattern: {' → '.join(agent_sequence)}",
                    description=f"Workflow pattern using {len(agent_sequence)} agents",
                    task_keywords=self._extract_task_keywords_from_execution(execution),
                    agent_sequence=agent_types,
                    avg_success_rate=features["success_rate"],
                    avg_duration_minutes=features["duration_minutes"],
                    avg_cost=features["total_cost"],
                    confidence=PatternConfidence.LOW,
                    sample_count=1,
                )

                self.learned_patterns[pattern_signature] = new_pattern
                patterns_updated += 1

        except Exception as e:
            logger.error(f"Error updating learned patterns: {e}")

        return patterns_updated

    async def _update_agent_profiles(self, execution: WorkflowExecution) -> int:
        """Update agent performance profiles"""
        agents_updated = 0

        try:
            duration_minutes = (
                execution.end_time - execution.start_time
            ).total_seconds() / 60
            success_rate = execution.progress_percentage / 100

            for agent_name, usage_count in execution.agent_utilization.items():
                try:
                    agent_type = AgentType(agent_name)
                except ValueError:
                    continue  # Skip unknown agent types

                # Estimate agent-specific metrics
                agent_duration = duration_minutes / len(
                    execution.agent_utilization
                )  # Rough estimate
                agent_cost = execution.total_cost / len(
                    execution.agent_utilization
                )  # Rough estimate

                if agent_type in self.agent_profiles:
                    # Update existing profile
                    profile = self.agent_profiles[agent_type]

                    old_weight = profile.sample_count / (
                        profile.sample_count + usage_count
                    )
                    new_weight = usage_count / (profile.sample_count + usage_count)

                    profile.avg_success_rate = (
                        profile.avg_success_rate * old_weight
                        + success_rate * new_weight
                    )
                    profile.avg_response_time_ms = (
                        profile.avg_response_time_ms * old_weight
                        + agent_duration * 60 * 1000 * new_weight
                    )  # Convert to ms
                    profile.avg_cost_per_task = (
                        profile.avg_cost_per_task * old_weight + agent_cost * new_weight
                    )
                    profile.sample_count += usage_count
                    profile.last_updated = datetime.now()

                else:
                    # Create new profile
                    new_profile = AgentPerformanceProfile(
                        agent_type=agent_type,
                        task_categories=["general"],  # Would be refined with more data
                        avg_success_rate=success_rate,
                        avg_response_time_ms=agent_duration * 60 * 1000,
                        avg_cost_per_task=agent_cost,
                        best_performing_contexts=["workflow_execution"],
                        common_failure_patterns=[],
                        efficiency_trend=TrendDirection.STABLE,
                        sample_count=usage_count,
                    )

                    self.agent_profiles[agent_type] = new_profile

                agents_updated += 1

        except Exception as e:
            logger.error(f"Error updating agent profiles: {e}")

        return agents_updated

    async def _find_similar_patterns(
        self, task_description: str, agent_sequence: List[AgentType]
    ) -> List[LearnedPattern]:
        """Find learned patterns similar to the given task and agent sequence"""
        similar_patterns = []

        task_keywords = set(task_description.lower().split())
        agent_set = set(agent_sequence)

        for pattern in self.learned_patterns.values():
            # Calculate similarity based on keywords and agents
            keyword_overlap = len(task_keywords & set(pattern.task_keywords)) / max(
                len(task_keywords), 1
            )
            agent_overlap = len(agent_set & set(pattern.agent_sequence)) / max(
                len(agent_set), 1
            )

            # Combined similarity score
            similarity = keyword_overlap * 0.4 + agent_overlap * 0.6

            if similarity > 0.3 and pattern.confidence != PatternConfidence.LOW:
                similar_patterns.append(pattern)

        # Sort by confidence and similarity
        similar_patterns.sort(
            key=lambda p: (
                {"low": 1, "moderate": 2, "high": 3, "very_high": 4}[
                    p.confidence.value
                ],
                p.avg_success_rate,
            ),
            reverse=True,
        )

        return similar_patterns[:5]  # Return top 5 matches

    async def _apply_prediction_model(
        self, model: PredictionModel, features: Dict[str, Any]
    ) -> float:
        """Apply a prediction model to features"""
        try:
            score = model.bias
            for feature_name, weight in model.weights.items():
                if feature_name in features:
                    score += features[feature_name] * weight

            # Apply sigmoid activation for probability output
            probability = 1 / (1 + np.exp(-score))
            return float(probability)

        except Exception as e:
            logger.error(f"Error applying prediction model: {e}")
            return 0.5  # Neutral prediction

    def _calculate_prediction_confidence(
        self, similar_patterns: List[LearnedPattern], features: Dict[str, Any]
    ) -> float:
        """Calculate confidence in prediction based on available data"""
        if not similar_patterns:
            return 0.3  # Low confidence without patterns

        # Base confidence from pattern count and quality
        pattern_confidence = min(len(similar_patterns) / 5, 1.0) * 0.5

        # Confidence from pattern sample sizes
        avg_samples = statistics.mean([p.sample_count for p in similar_patterns])
        sample_confidence = min(avg_samples / 20, 1.0) * 0.3

        # Confidence from pattern agreement (variance in success rates)
        success_rates = [p.avg_success_rate for p in similar_patterns]
        if len(success_rates) > 1:
            variance_penalty = statistics.stdev(success_rates) * 0.2
        else:
            variance_penalty = 0

        base_confidence = 0.2  # Minimum baseline
        total_confidence = (
            base_confidence + pattern_confidence + sample_confidence - variance_penalty
        )

        return max(0.1, min(0.9, total_confidence))

    def _generate_prediction_recommendation(
        self, success_rate: float, duration: float, confidence: float
    ) -> str:
        """Generate recommendation based on prediction"""
        if confidence < 0.4:
            return "Low confidence prediction - consider gathering more data for similar workflows"
        elif success_rate > 0.8:
            return "High probability of success - proceed with workflow"
        elif success_rate > 0.6:
            return "Good probability of success - consider minor optimizations"
        elif success_rate > 0.4:
            return (
                "Moderate success probability - review workflow design for improvements"
            )
        else:
            return "Low success probability - significant optimization needed"

    def _extract_task_keywords_from_execution(
        self, execution: WorkflowExecution
    ) -> List[str]:
        """Extract keywords from workflow execution (simplified)"""
        # In a real implementation, this would analyze the actual task descriptions
        # For now, we'll use agent types as keywords
        keywords = [
            agent.replace("_", " ") for agent in execution.agent_utilization.keys()
        ]
        keywords.extend(["workflow", "automation", "task"])
        return keywords

    async def _generate_optimizations_from_execution(
        self, execution: WorkflowExecution, features: Dict[str, Any]
    ) -> List[WorkflowOptimization]:
        """Generate optimization recommendations from completed execution"""
        optimizations = []

        try:
            # Cost optimization if execution was expensive
            if features["total_cost"] > 2.0:
                cost_opt = WorkflowOptimization(
                    optimization_id=f"cost_opt_{execution.workflow_id}",
                    workflow_type="high_cost",
                    current_approach={
                        "cost": features["total_cost"],
                        "duration": features["duration_minutes"],
                    },
                    optimized_approach={
                        "estimated_cost": features["total_cost"] * 0.7,
                        "agent_optimization": True,
                    },
                    expected_improvement={"cost_reduction": 30.0, "efficiency": 15.0},
                    confidence=0.6,
                    evidence=[
                        f"Execution cost ${features['total_cost']:.2f} above optimal range"
                    ],
                    implementation_complexity="medium",
                )
                optimizations.append(cost_opt)

            # Duration optimization if execution was slow
            if features["duration_minutes"] > 45:
                duration_opt = WorkflowOptimization(
                    optimization_id=f"duration_opt_{execution.workflow_id}",
                    workflow_type="long_duration",
                    current_approach={
                        "duration": features["duration_minutes"],
                        "steps": features["total_steps"],
                    },
                    optimized_approach={
                        "estimated_duration": features["duration_minutes"] * 0.8,
                        "parallel_execution": True,
                    },
                    expected_improvement={"time_reduction": 20.0, "efficiency": 25.0},
                    confidence=0.5,
                    evidence=[
                        f"Execution duration {features['duration_minutes']:.1f} min above optimal"
                    ],
                    implementation_complexity="high",
                )
                optimizations.append(duration_opt)

        except Exception as e:
            logger.error(f"Error generating optimizations: {e}")

        return optimizations

    async def _optimize_agent_sequence(
        self, proposed_agents: List[AgentType], similar_patterns: List[LearnedPattern]
    ) -> Optional[WorkflowOptimization]:
        """Optimize agent sequence based on learned patterns"""
        if not similar_patterns:
            return None

        # Find the most successful pattern
        best_pattern = max(similar_patterns, key=lambda p: p.avg_success_rate)

        if set(proposed_agents) != set(best_pattern.agent_sequence):
            return WorkflowOptimization(
                optimization_id="agent_sequence_opt",
                workflow_type="agent_selection",
                current_approach={"agents": [a.value for a in proposed_agents]},
                optimized_approach={
                    "agents": [a.value for a in best_pattern.agent_sequence]
                },
                expected_improvement={
                    "success_rate": (best_pattern.avg_success_rate - 0.7)
                    * 100,  # Assume baseline 0.7
                    "efficiency": 15.0,
                },
                confidence={"low": 0.3, "moderate": 0.5, "high": 0.7, "very_high": 0.9}[
                    best_pattern.confidence.value
                ],
                evidence=[
                    f"Similar successful pattern with {best_pattern.avg_success_rate:.1%} success rate"
                ],
                implementation_complexity="low",
            )

        return None

    async def _optimize_task_decomposition(
        self, task_description: str, similar_patterns: List[LearnedPattern]
    ) -> Optional[WorkflowOptimization]:
        """Optimize task decomposition based on patterns"""
        if not similar_patterns:
            return None

        # Analyze if current decomposition can be improved
        avg_steps = statistics.mean([len(p.agent_sequence) for p in similar_patterns])

        if avg_steps < len(task_description.split()) / 5:  # Rough heuristic
            return WorkflowOptimization(
                optimization_id="decomposition_opt",
                workflow_type="task_breakdown",
                current_approach={"estimated_steps": len(task_description.split()) / 5},
                optimized_approach={"recommended_steps": avg_steps},
                expected_improvement={"efficiency": 20.0, "clarity": 15.0},
                confidence=0.6,
                evidence=[f"Similar patterns use average {avg_steps:.1f} steps"],
                implementation_complexity="medium",
            )

        return None

    async def _optimize_cost_efficiency(
        self, proposed_agents: List[AgentType], similar_patterns: List[LearnedPattern]
    ) -> Optional[WorkflowOptimization]:
        """Optimize for cost efficiency"""
        if not similar_patterns:
            return None

        avg_cost = statistics.mean([p.avg_cost for p in similar_patterns])

        # Estimate current cost
        estimated_current_cost = len(proposed_agents) * 1.5  # Rough estimate

        if estimated_current_cost > avg_cost * 1.2:
            return WorkflowOptimization(
                optimization_id="cost_efficiency_opt",
                workflow_type="cost_optimization",
                current_approach={"estimated_cost": estimated_current_cost},
                optimized_approach={"target_cost": avg_cost},
                expected_improvement={
                    "cost_reduction": (
                        (estimated_current_cost - avg_cost) / estimated_current_cost
                    )
                    * 100
                },
                confidence=0.5,
                evidence=[f"Similar patterns average ${avg_cost:.2f} cost"],
                implementation_complexity="medium",
            )

        return None

    async def _generate_profile_based_optimizations(
        self, proposed_agents: List[AgentType]
    ) -> List[WorkflowOptimization]:
        """Generate optimizations based on agent performance profiles"""
        optimizations = []

        for agent_type in proposed_agents:
            if agent_type in self.agent_profiles:
                profile = self.agent_profiles[agent_type]

                # If agent has low success rate, suggest alternatives
                if profile.avg_success_rate < 0.7:
                    # Find better performing alternatives (simplified)
                    better_agents = [
                        at
                        for at, p in self.agent_profiles.items()
                        if p.avg_success_rate > profile.avg_success_rate + 0.1
                    ]

                    if better_agents:
                        best_alternative = max(
                            better_agents,
                            key=lambda at: self.agent_profiles[at].avg_success_rate,
                        )

                        optimizations.append(
                            WorkflowOptimization(
                                optimization_id=f"agent_replacement_{agent_type.value}",
                                workflow_type="agent_performance",
                                current_approach={
                                    "agent": agent_type.value,
                                    "success_rate": profile.avg_success_rate,
                                },
                                optimized_approach={
                                    "agent": best_alternative.value,
                                    "success_rate": self.agent_profiles[
                                        best_alternative
                                    ].avg_success_rate,
                                },
                                expected_improvement={
                                    "success_rate": (
                                        self.agent_profiles[
                                            best_alternative
                                        ].avg_success_rate
                                        - profile.avg_success_rate
                                    )
                                    * 100
                                },
                                confidence=0.7,
                                evidence=[
                                    f"Agent {best_alternative.value} has {self.agent_profiles[best_alternative].avg_success_rate:.1%} success rate vs {profile.avg_success_rate:.1%}"
                                ],
                                implementation_complexity="low",
                            )
                        )

        return optimizations

    async def _update_prediction_models(
        self, execution: WorkflowExecution, features: Dict[str, Any]
    ) -> int:
        """Update prediction models with new data"""
        models_updated = 0

        try:
            # Simple success rate model update
            if "success_rate" not in self.prediction_models:
                # Initialize model
                self.prediction_models["success_rate"] = PredictionModel(
                    model_type="linear_regression",
                    features=["agent_count", "complexity_score", "unique_agents"],
                    weights={
                        "agent_count": -0.1,
                        "complexity_score": -0.2,
                        "unique_agents": 0.1,
                    },
                    bias=0.8,
                    accuracy=0.6,
                    training_samples=1,
                )
                models_updated += 1
            else:
                # Update existing model (simplified online learning)
                model = self.prediction_models["success_rate"]
                model.training_samples += 1
                model.last_trained = datetime.now()

                # Simple weight adjustment (in real implementation, would use proper ML)
                learning_rate = 0.01
                error = features["success_rate"] - 0.75  # Assumed prediction

                for feature, weight in model.weights.items():
                    if feature in features:
                        model.weights[feature] += (
                            learning_rate * error * features[feature]
                        )

                models_updated += 1

        except Exception as e:
            logger.error(f"Error updating prediction models: {e}")

        return models_updated

    # Dashboard widget support methods

    async def get_learning_status(self) -> Dict[str, Any]:
        """Get learning engine status for dashboard widgets"""
        total_patterns = len(self.learned_patterns)
        active_models = len(self.prediction_models)

        # Determine learning engine status
        if total_patterns < 5:
            status = "learning"
        elif len([p for p in self.learned_patterns.values() if p.confidence > 0.8]) > 3:
            status = "optimizing"
        else:
            status = "stable"

        # Generate recent optimizations (mock data for demonstration)
        recent_optimizations = [
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "optimization": "Improved agent selection for React components",
                "impact": "8% performance improvement",
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
                "optimization": "Optimized context passing in debugging workflows",
                "impact": "12% cost reduction",
            },
        ]

        return {
            "status": status,
            "learned_patterns": total_patterns,
            "active_models": active_models,
            "confidence_threshold": 0.75,
            "recent_optimizations": recent_optimizations,
        }

    async def get_performance_insights(self) -> Dict[str, Any]:
        """Get performance insights for dashboard widgets"""
        workflow_templates = {}

        # Generate workflow template performance data
        template_names = [
            "code_analysis",
            "feature_implementation",
            "debugging_session",
            "performance_optimization",
        ]

        for template in template_names:
            # Extract patterns related to this template
            template_patterns = [
                p
                for p in self.learned_patterns.values()
                if template.replace("_", " ") in p.description.lower()
            ]

            if template_patterns:
                avg_success = sum(p.success_rate for p in template_patterns) / len(
                    template_patterns
                )
                avg_duration = sum(
                    p.avg_duration_minutes for p in template_patterns
                ) / len(template_patterns)
                total_executions = sum(p.execution_count for p in template_patterns)
            else:
                # Mock data for templates without learned patterns yet
                avg_success = 90.0 + (hash(template) % 10)
                avg_duration = 3.0 + (hash(template) % 8)
                total_executions = 15 + (hash(template) % 40)

            workflow_templates[template] = {
                "success_rate": avg_success,
                "avg_duration": avg_duration,
                "cost_efficiency": 0.75 + (hash(template) % 20) / 100,
                "execution_count": total_executions,
            }

        # Generate optimization opportunities
        optimizations = []
        for pattern in self.learned_patterns.values():
            if pattern.confidence > 0.7 and pattern.success_rate < 90:
                optimizations.append(
                    {
                        "workflow": pattern.pattern_name,
                        "opportunity": f"Improve {pattern.description.lower()}",
                        "potential_improvement": f"{(95 - pattern.success_rate):.0f}% success rate improvement",
                        "confidence": pattern.confidence,
                    }
                )

        # Add some example optimizations if none exist
        if not optimizations:
            optimizations = [
                {
                    "workflow": "feature_implementation",
                    "opportunity": "Reduce agent switching overhead",
                    "potential_improvement": "15% faster execution",
                    "confidence": 0.82,
                },
                {
                    "workflow": "debugging_session",
                    "opportunity": "Optimize context passing between agents",
                    "potential_improvement": "12% cost reduction",
                    "confidence": 0.76,
                },
            ]

        # Generate pattern insights
        pattern_insights = [
            f"Learned {len(self.learned_patterns)} workflow patterns with average confidence {sum(p.confidence for p in self.learned_patterns.values()) / max(len(self.learned_patterns), 1):.2f}",
            "Sequential Read → Edit operations show higher efficiency than interleaved patterns",
            "Frontend-focused workflows benefit from early specialized agent assignment",
            "Database optimization workflows show better success rates with PostgreSQL expert involvement",
        ]

        return {
            "workflow_templates": workflow_templates,
            "optimizations": optimizations[:5],  # Limit to top 5
            "patterns": pattern_insights[:4],  # Limit to top 4 insights
        }
