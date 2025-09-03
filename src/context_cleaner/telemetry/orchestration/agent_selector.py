"""
Advanced Agent Selection System for Phase 3 Advanced Automation

Implements intelligent agent selection using telemetry patterns, performance analytics,
and context-aware optimization to choose the optimal agent for each task.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import statistics

from ..clients.clickhouse_client import ClickHouseClient
from ..analytics.session_analysis import SessionAnalyticsEngine
from .task_orchestrator import AgentType, TaskComplexity
from .workflow_learner import WorkflowLearner, AgentPerformanceProfile

logger = logging.getLogger(__name__)


class SelectionCriteria(Enum):
    """Criteria for agent selection"""
    EXPERTISE = "expertise"           # Domain knowledge and specialization
    PERFORMANCE = "performance"       # Historical success rates and efficiency
    COST = "cost"                    # Cost-effectiveness and budget constraints
    SPEED = "speed"                  # Response time and execution speed
    AVAILABILITY = "availability"     # Current workload and availability
    CONTEXT = "context"              # Context-specific suitability


class SelectionStrategy(Enum):
    """Agent selection strategies"""
    PERFORMANCE_FIRST = "performance_first"       # Prioritize success rate
    COST_OPTIMIZED = "cost_optimized"            # Prioritize cost efficiency
    BALANCED = "balanced"                        # Balance all factors
    SPEED_OPTIMIZED = "speed_optimized"          # Prioritize response time
    EXPERTISE_MATCHED = "expertise_matched"      # Match domain expertise
    ADAPTIVE = "adaptive"                        # Learn and adapt based on context


@dataclass
class TaskContext:
    """Context information for task analysis"""
    description: str
    complexity: TaskComplexity
    domain_keywords: List[str]
    technical_requirements: List[str]
    time_constraints: Optional[timedelta]
    budget_constraints: Optional[float]
    quality_requirements: List[str]
    dependencies: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapability:
    """Detailed capability information for an agent"""
    agent_type: AgentType
    primary_domains: List[str]
    secondary_domains: List[str]
    technical_skills: List[str]
    strength_keywords: List[str]
    weakness_keywords: List[str]
    typical_response_time_ms: float
    cost_per_hour: float
    max_concurrent_tasks: int
    learning_curve_factor: float  # How quickly agent improves with experience


@dataclass
class SelectionScore:
    """Score for agent selection with breakdown"""
    agent_type: AgentType
    total_score: float
    expertise_score: float
    performance_score: float
    cost_score: float
    speed_score: float
    availability_score: float
    context_score: float
    confidence: float
    reasoning: List[str] = field(default_factory=list)


@dataclass
class SelectionRecommendation:
    """Final agent selection recommendation"""
    primary_agent: AgentType
    backup_agents: List[AgentType]
    selection_reasoning: str
    expected_performance: Dict[str, float]
    risk_factors: List[str]
    optimization_suggestions: List[str]
    confidence: float


class AgentSelector:
    """Advanced agent selection system with telemetry-driven intelligence"""
    
    def __init__(self, telemetry_client: ClickHouseClient, workflow_learner: WorkflowLearner):
        self.telemetry = telemetry_client
        self.analytics = SessionAnalyticsEngine(telemetry_client)
        self.learner = workflow_learner
        
        # Agent capability definitions
        self.agent_capabilities = self._initialize_agent_capabilities()
        
        # Selection configuration
        self.default_strategy = SelectionStrategy.BALANCED
        self.score_weights = {
            SelectionCriteria.EXPERTISE: 0.25,
            SelectionCriteria.PERFORMANCE: 0.25,
            SelectionCriteria.COST: 0.20,
            SelectionCriteria.SPEED: 0.15,
            SelectionCriteria.AVAILABILITY: 0.10,
            SelectionCriteria.CONTEXT: 0.05
        }
        
        # Performance tracking
        self.selection_history: List[Dict[str, Any]] = []
        self.agent_workloads: Dict[AgentType, int] = {}
        self.context_patterns: Dict[str, List[AgentType]] = {}
        
        # Caching for performance
        self._capability_cache: Dict[str, List[AgentType]] = {}
        self._performance_cache: Dict[AgentType, Dict[str, float]] = {}
        self._cache_ttl = timedelta(minutes=30)
        self._last_cache_update: Optional[datetime] = None
    
    def _initialize_agent_capabilities(self) -> Dict[AgentType, AgentCapability]:
        """Initialize detailed capability information for each agent type"""
        return {
            AgentType.GENERAL_PURPOSE: AgentCapability(
                agent_type=AgentType.GENERAL_PURPOSE,
                primary_domains=["research", "analysis", "coordination", "general_tasks"],
                secondary_domains=["documentation", "planning", "communication"],
                technical_skills=["file_operations", "data_analysis", "project_coordination"],
                strength_keywords=["research", "analyze", "coordinate", "plan", "overview"],
                weakness_keywords=["specialized", "expert", "advanced", "complex_algorithm"],
                typical_response_time_ms=5000,
                cost_per_hour=2.0,
                max_concurrent_tasks=5,
                learning_curve_factor=1.2
            ),
            
            AgentType.CODEBASE_ARCHITECT: AgentCapability(
                agent_type=AgentType.CODEBASE_ARCHITECT,
                primary_domains=["architecture", "scalability", "performance", "system_design"],
                secondary_domains=["security", "best_practices", "technology_stack"],
                technical_skills=["architecture_patterns", "performance_optimization", "security_analysis"],
                strength_keywords=["architecture", "design", "scalability", "performance", "system", "structure"],
                weakness_keywords=["ui", "frontend", "styling", "visual", "quick_fix"],
                typical_response_time_ms=8000,
                cost_per_hour=3.5,
                max_concurrent_tasks=2,
                learning_curve_factor=0.9
            ),
            
            AgentType.FRONTEND_EXPERT: AgentCapability(
                agent_type=AgentType.FRONTEND_EXPERT,
                primary_domains=["react", "typescript", "frontend", "ui", "user_experience"],
                secondary_domains=["javascript", "css", "html", "responsive_design"],
                technical_skills=["react_development", "typescript", "ui_components", "state_management"],
                strength_keywords=["react", "typescript", "frontend", "ui", "component", "interface", "user"],
                weakness_keywords=["backend", "database", "server", "api_design", "infrastructure"],
                typical_response_time_ms=6000,
                cost_per_hour=3.0,
                max_concurrent_tasks=3,
                learning_curve_factor=1.1
            ),
            
            AgentType.BACKEND_ENGINEER: AgentCapability(
                agent_type=AgentType.BACKEND_ENGINEER,
                primary_domains=["python", "api", "backend", "database", "server"],
                secondary_domains=["microservices", "integration", "data_processing"],
                technical_skills=["api_development", "database_design", "python", "server_architecture"],
                strength_keywords=["python", "api", "backend", "database", "server", "endpoint", "service"],
                weakness_keywords=["frontend", "ui", "react", "styling", "visual", "user_interface"],
                typical_response_time_ms=6500,
                cost_per_hour=3.2,
                max_concurrent_tasks=3,
                learning_curve_factor=1.0
            ),
            
            AgentType.SENIOR_REVIEWER: AgentCapability(
                agent_type=AgentType.SENIOR_REVIEWER,
                primary_domains=["code_review", "quality_assurance", "best_practices", "security"],
                secondary_domains=["architecture_review", "mentoring", "standards"],
                technical_skills=["code_analysis", "security_review", "best_practices", "quality_assessment"],
                strength_keywords=["review", "quality", "security", "best_practices", "audit", "analyze", "improve"],
                weakness_keywords=["implement", "create", "build", "develop", "new_feature"],
                typical_response_time_ms=7000,
                cost_per_hour=4.0,
                max_concurrent_tasks=4,
                learning_curve_factor=0.8
            ),
            
            AgentType.TEST_ENGINEER: AgentCapability(
                agent_type=AgentType.TEST_ENGINEER,
                primary_domains=["testing", "quality_assurance", "automation", "verification"],
                secondary_domains=["test_strategy", "coverage_analysis", "performance_testing"],
                technical_skills=["test_development", "automation", "quality_assurance", "test_strategy"],
                strength_keywords=["test", "testing", "quality", "verify", "validation", "coverage", "automation"],
                weakness_keywords=["design", "architecture", "business_logic", "ui_design"],
                typical_response_time_ms=5500,
                cost_per_hour=2.8,
                max_concurrent_tasks=4,
                learning_curve_factor=1.1
            ),
            
            AgentType.CI_LOG_ANALYZER: AgentCapability(
                agent_type=AgentType.CI_LOG_ANALYZER,
                primary_domains=["log_analysis", "debugging", "ci_cd", "troubleshooting"],
                secondary_domains=["monitoring", "error_analysis", "performance_debugging"],
                technical_skills=["log_analysis", "debugging", "ci_cd_troubleshooting", "error_investigation"],
                strength_keywords=["log", "error", "debug", "failure", "ci", "build", "pipeline", "troubleshoot"],
                weakness_keywords=["create", "implement", "design", "new_feature", "ui"],
                typical_response_time_ms=4500,
                cost_per_hour=2.5,
                max_concurrent_tasks=6,
                learning_curve_factor=1.3
            ),
            
            AgentType.DOCKER_EXPERT: AgentCapability(
                agent_type=AgentType.DOCKER_EXPERT,
                primary_domains=["docker", "containerization", "deployment", "orchestration"],
                secondary_domains=["kubernetes", "devops", "infrastructure"],
                technical_skills=["containerization", "docker_compose", "deployment", "orchestration"],
                strength_keywords=["docker", "container", "deployment", "orchestration", "kubernetes", "devops"],
                weakness_keywords=["frontend", "ui", "design", "business_logic"],
                typical_response_time_ms=6000,
                cost_per_hour=3.5,
                max_concurrent_tasks=2,
                learning_curve_factor=0.9
            ),
            
            AgentType.DATABASE_EXPERT: AgentCapability(
                agent_type=AgentType.DATABASE_EXPERT,
                primary_domains=["database", "sql", "postgresql", "performance", "optimization"],
                secondary_domains=["data_modeling", "migration", "backup"],
                technical_skills=["database_design", "query_optimization", "migration", "performance_tuning"],
                strength_keywords=["database", "sql", "postgresql", "query", "optimization", "migration", "data"],
                weakness_keywords=["frontend", "ui", "react", "styling"],
                typical_response_time_ms=7000,
                cost_per_hour=3.8,
                max_concurrent_tasks=2,
                learning_curve_factor=0.8
            ),
            
            AgentType.UI_ENGINEER: AgentCapability(
                agent_type=AgentType.UI_ENGINEER,
                primary_domains=["ui_design", "user_experience", "frontend", "styling"],
                secondary_domains=["accessibility", "responsive_design", "user_testing"],
                technical_skills=["ui_components", "styling", "user_experience", "design_systems"],
                strength_keywords=["ui", "design", "user", "interface", "styling", "component", "visual"],
                weakness_keywords=["backend", "database", "server", "api", "algorithm"],
                typical_response_time_ms=5500,
                cost_per_hour=2.9,
                max_concurrent_tasks=3,
                learning_curve_factor=1.2
            )
        }
    
    async def select_optimal_agent(self, task_context: TaskContext, 
                                 strategy: SelectionStrategy = None) -> SelectionRecommendation:
        """
        Select the optimal agent for a given task context
        
        This is the main entry point for agent selection
        """
        try:
            strategy = strategy or self.default_strategy
            logger.info(f"Selecting agent for task: {task_context.description[:50]}... using {strategy.value} strategy")
            
            # Step 1: Get candidate agents based on capabilities
            candidates = await self._get_candidate_agents(task_context)
            logger.debug(f"Found {len(candidates)} candidate agents")
            
            # Step 2: Score each candidate against all criteria
            scored_agents = await self._score_agents(candidates, task_context, strategy)
            
            # Step 3: Apply strategy-specific optimizations
            optimized_scores = await self._apply_selection_strategy(scored_agents, strategy, task_context)
            
            # Step 4: Generate final recommendation
            recommendation = await self._generate_recommendation(optimized_scores, task_context)
            
            # Step 5: Track selection for learning
            await self._track_selection(task_context, recommendation)
            
            logger.info(f"Selected agent: {recommendation.primary_agent.value} (confidence: {recommendation.confidence:.2f})")
            return recommendation
            
        except Exception as e:
            logger.error(f"Error in agent selection: {e}")
            # Fallback to general purpose agent
            return SelectionRecommendation(
                primary_agent=AgentType.GENERAL_PURPOSE,
                backup_agents=[AgentType.SENIOR_REVIEWER],
                selection_reasoning=f"Fallback selection due to error: {e}",
                expected_performance={"success_rate": 0.7},
                risk_factors=["Error in selection process"],
                optimization_suggestions=["Review selection criteria"],
                confidence=0.3
            )
    
    async def batch_select_agents(self, task_contexts: List[TaskContext],
                                strategy: SelectionStrategy = None) -> List[SelectionRecommendation]:
        """Select agents for multiple tasks with optimization for workflow coherence"""
        recommendations = []
        
        try:
            # Consider agent workload distribution for batch selection
            temp_workloads = self.agent_workloads.copy()
            
            for task_context in task_contexts:
                # Adjust availability scores based on temporary workload
                recommendation = await self.select_optimal_agent(task_context, strategy)
                
                # Update temporary workload
                temp_workloads[recommendation.primary_agent] = temp_workloads.get(
                    recommendation.primary_agent, 0) + 1
                
                recommendations.append(recommendation)
            
            # Optimize for workflow coherence if needed
            optimized_recommendations = await self._optimize_batch_coherence(recommendations, task_contexts)
            
            return optimized_recommendations
            
        except Exception as e:
            logger.error(f"Error in batch agent selection: {e}")
            return recommendations
    
    async def _get_candidate_agents(self, task_context: TaskContext) -> List[AgentType]:
        """Get candidate agents based on task context and capabilities"""
        candidates = set()
        
        # Keyword-based matching
        task_keywords = set(task_context.description.lower().split())
        domain_keywords = set(kw.lower() for kw in task_context.domain_keywords)
        all_keywords = task_keywords | domain_keywords
        
        for agent_type, capability in self.agent_capabilities.items():
            # Check strength keywords
            strength_matches = len(all_keywords & set(capability.strength_keywords))
            weakness_matches = len(all_keywords & set(capability.weakness_keywords))
            
            # Add agent if it has strength matches and few weakness matches
            if strength_matches > 0 and weakness_matches < strength_matches:
                candidates.add(agent_type)
            
            # Also add agents based on primary domain matching
            for domain in capability.primary_domains:
                if any(domain in keyword or keyword in domain for keyword in all_keywords):
                    candidates.add(agent_type)
        
        # Always include general purpose as fallback
        candidates.add(AgentType.GENERAL_PURPOSE)
        
        # Filter based on technical requirements if specified
        if task_context.technical_requirements:
            filtered_candidates = set()
            for agent_type in candidates:
                capability = self.agent_capabilities[agent_type]
                if any(req.lower() in skill.lower() for req in task_context.technical_requirements 
                       for skill in capability.technical_skills):
                    filtered_candidates.add(agent_type)
            
            if filtered_candidates:
                candidates = filtered_candidates
            
        return list(candidates)
    
    async def _score_agents(self, candidates: List[AgentType], task_context: TaskContext,
                          strategy: SelectionStrategy) -> List[SelectionScore]:
        """Score each candidate agent across all selection criteria"""
        scored_agents = []
        
        for agent_type in candidates:
            try:
                capability = self.agent_capabilities[agent_type]
                
                # Calculate individual criterion scores
                expertise_score = await self._calculate_expertise_score(agent_type, task_context)
                performance_score = await self._calculate_performance_score(agent_type, task_context)
                cost_score = await self._calculate_cost_score(agent_type, task_context)
                speed_score = await self._calculate_speed_score(agent_type, task_context)
                availability_score = await self._calculate_availability_score(agent_type, task_context)
                context_score = await self._calculate_context_score(agent_type, task_context)
                
                # Calculate weighted total score
                total_score = (
                    expertise_score * self.score_weights[SelectionCriteria.EXPERTISE] +
                    performance_score * self.score_weights[SelectionCriteria.PERFORMANCE] +
                    cost_score * self.score_weights[SelectionCriteria.COST] +
                    speed_score * self.score_weights[SelectionCriteria.SPEED] +
                    availability_score * self.score_weights[SelectionCriteria.AVAILABILITY] +
                    context_score * self.score_weights[SelectionCriteria.CONTEXT]
                )
                
                # Calculate confidence based on data availability
                confidence = await self._calculate_selection_confidence(agent_type, task_context)
                
                # Generate reasoning
                reasoning = self._generate_score_reasoning(
                    agent_type, expertise_score, performance_score, cost_score, 
                    speed_score, availability_score, context_score
                )
                
                score = SelectionScore(
                    agent_type=agent_type,
                    total_score=total_score,
                    expertise_score=expertise_score,
                    performance_score=performance_score,
                    cost_score=cost_score,
                    speed_score=speed_score,
                    availability_score=availability_score,
                    context_score=context_score,
                    confidence=confidence,
                    reasoning=reasoning
                )
                
                scored_agents.append(score)
                
            except Exception as e:
                logger.error(f"Error scoring agent {agent_type.value}: {e}")
                continue
        
        # Sort by total score
        scored_agents.sort(key=lambda x: x.total_score, reverse=True)
        return scored_agents
    
    async def _calculate_expertise_score(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate expertise score based on domain knowledge and specialization"""
        capability = self.agent_capabilities[agent_type]
        score = 0.0
        
        task_keywords = set(task_context.description.lower().split())
        domain_keywords = set(kw.lower() for kw in task_context.domain_keywords)
        all_keywords = task_keywords | domain_keywords
        
        # Primary domain matching (higher weight)
        primary_matches = sum(1 for domain in capability.primary_domains 
                            if any(domain in keyword or keyword in domain for keyword in all_keywords))
        score += primary_matches * 0.4
        
        # Secondary domain matching
        secondary_matches = sum(1 for domain in capability.secondary_domains
                              if any(domain in keyword or keyword in domain for keyword in all_keywords))
        score += secondary_matches * 0.2
        
        # Strength keyword matching
        strength_matches = len(all_keywords & set(capability.strength_keywords))
        score += strength_matches * 0.3
        
        # Penalty for weakness keyword matching
        weakness_matches = len(all_keywords & set(capability.weakness_keywords))
        score -= weakness_matches * 0.15
        
        # Technical requirements matching
        if task_context.technical_requirements:
            tech_matches = sum(1 for req in task_context.technical_requirements
                             if any(req.lower() in skill.lower() for skill in capability.technical_skills))
            score += (tech_matches / len(task_context.technical_requirements)) * 0.3
        
        # Complexity appropriateness
        if task_context.complexity == TaskComplexity.ENTERPRISE and agent_type in [
            AgentType.CODEBASE_ARCHITECT, AgentType.SENIOR_REVIEWER
        ]:
            score += 0.2
        elif task_context.complexity == TaskComplexity.SIMPLE and agent_type == AgentType.GENERAL_PURPOSE:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_performance_score(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate performance score based on historical success rates and efficiency"""
        try:
            # Get performance data from workflow learner
            agent_insights = await self.learner.get_agent_performance_insights(agent_type)
            
            if "error" not in agent_insights:
                performance_data = agent_insights["performance"]
                success_rate = performance_data["success_rate"]
                
                # Base score from success rate
                score = success_rate
                
                # Adjust based on trend
                trend = performance_data["efficiency_trend"]
                if trend == "improving":
                    score += 0.1
                elif trend == "declining":
                    score -= 0.1
                
                # Adjust based on sample size (more data = more reliable)
                sample_count = agent_insights.get("sample_size", 0)
                reliability_factor = min(sample_count / 20, 1.0)  # Full reliability at 20+ samples
                score = score * reliability_factor + 0.5 * (1 - reliability_factor)  # Fallback to 0.5
                
                return max(0.0, min(1.0, score))
            else:
                # Fallback to capability-based estimation
                return self._estimate_performance_from_capability(agent_type, task_context)
                
        except Exception as e:
            logger.error(f"Error calculating performance score for {agent_type.value}: {e}")
            return 0.5
    
    async def _calculate_cost_score(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate cost efficiency score"""
        capability = self.agent_capabilities[agent_type]
        
        # Inverse relationship - lower cost = higher score
        max_cost = 5.0  # Maximum expected cost per hour
        base_score = 1.0 - (capability.cost_per_hour / max_cost)
        
        # Apply budget constraints if specified
        if task_context.budget_constraints:
            estimated_task_duration = 1.0  # Assume 1 hour default
            estimated_cost = capability.cost_per_hour * estimated_task_duration
            
            if estimated_cost > task_context.budget_constraints:
                base_score *= 0.3  # Heavy penalty for budget violation
            elif estimated_cost > task_context.budget_constraints * 0.8:
                base_score *= 0.7  # Moderate penalty for near budget limit
        
        # Adjust based on task complexity (more complex tasks justify higher costs)
        if task_context.complexity == TaskComplexity.ENTERPRISE and capability.cost_per_hour > 3.0:
            base_score += 0.1  # Bonus for high-end agents on complex tasks
        elif task_context.complexity == TaskComplexity.SIMPLE and capability.cost_per_hour < 2.5:
            base_score += 0.1  # Bonus for cost-effective agents on simple tasks
        
        return max(0.0, min(1.0, base_score))
    
    async def _calculate_speed_score(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate speed/responsiveness score"""
        capability = self.agent_capabilities[agent_type]
        
        # Inverse relationship - lower response time = higher score
        max_response_time = 10000  # 10 seconds
        base_score = 1.0 - (capability.typical_response_time_ms / max_response_time)
        
        # Apply time constraints if specified
        if task_context.time_constraints:
            urgency_factor = 1.0
            if task_context.time_constraints < timedelta(hours=1):
                urgency_factor = 1.3  # Boost speed importance for urgent tasks
            elif task_context.time_constraints > timedelta(days=1):
                urgency_factor = 0.7  # Reduce speed importance for long-term tasks
            
            base_score *= urgency_factor
        
        # Learning curve factor (agents that improve quickly are valuable for speed)
        base_score *= capability.learning_curve_factor
        
        return max(0.0, min(1.0, base_score))
    
    async def _calculate_availability_score(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate availability score based on current workload"""
        capability = self.agent_capabilities[agent_type]
        current_workload = self.agent_workloads.get(agent_type, 0)
        
        # Calculate availability ratio
        availability_ratio = max(0, capability.max_concurrent_tasks - current_workload) / capability.max_concurrent_tasks
        
        # Time-based availability adjustment
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 17:  # Business hours
            availability_ratio *= 1.0  # Full availability
        elif 6 <= current_hour <= 21:  # Extended hours
            availability_ratio *= 0.8  # Slightly reduced
        else:  # Off hours
            availability_ratio *= 0.6  # Reduced availability
        
        return availability_ratio
    
    async def _calculate_context_score(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate context-specific suitability score"""
        score = 0.5  # Base neutral score
        
        # Quality requirements matching
        capability = self.agent_capabilities[agent_type]
        if "high_quality" in task_context.quality_requirements:
            if agent_type in [AgentType.SENIOR_REVIEWER, AgentType.CODEBASE_ARCHITECT]:
                score += 0.3
        
        if "fast_delivery" in task_context.quality_requirements:
            if capability.typical_response_time_ms < 6000:
                score += 0.2
        
        # User preferences
        preferred_agent = task_context.user_preferences.get("preferred_agent")
        if preferred_agent == agent_type.value:
            score += 0.3
        
        avoided_agent = task_context.user_preferences.get("avoid_agent")
        if avoided_agent == agent_type.value:
            score -= 0.4
        
        # Context pattern matching from history
        context_key = self._generate_context_key(task_context)
        if context_key in self.context_patterns:
            successful_agents = self.context_patterns[context_key]
            if agent_type in successful_agents:
                score += 0.2
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_selection_confidence(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Calculate confidence in the selection decision"""
        confidence_factors = []
        
        # Performance data availability
        try:
            agent_insights = await self.learner.get_agent_performance_insights(agent_type)
            if "error" not in agent_insights:
                sample_size = agent_insights.get("sample_size", 0)
                confidence_factors.append(min(sample_size / 20, 1.0))
            else:
                confidence_factors.append(0.3)  # Low confidence without performance data
        except:
            confidence_factors.append(0.3)
        
        # Capability matching strength
        capability = self.agent_capabilities[agent_type]
        task_keywords = set(task_context.description.lower().split())
        strength_matches = len(task_keywords & set(capability.strength_keywords))
        total_keywords = len(task_keywords)
        match_ratio = strength_matches / max(total_keywords, 1)
        confidence_factors.append(match_ratio)
        
        # Historical context success
        context_key = self._generate_context_key(task_context)
        if context_key in self.context_patterns:
            successful_count = len(self.context_patterns[context_key])
            confidence_factors.append(min(successful_count / 5, 1.0))
        else:
            confidence_factors.append(0.4)
        
        # Average confidence across factors
        return statistics.mean(confidence_factors)
    
    def _generate_score_reasoning(self, agent_type: AgentType, expertise: float, performance: float,
                                cost: float, speed: float, availability: float, context: float) -> List[str]:
        """Generate human-readable reasoning for the selection score"""
        reasoning = []
        capability = self.agent_capabilities[agent_type]
        
        if expertise > 0.7:
            reasoning.append(f"Strong expertise match - specializes in {', '.join(capability.primary_domains)}")
        elif expertise < 0.3:
            reasoning.append(f"Limited expertise match for this task type")
        
        if performance > 0.8:
            reasoning.append("Excellent historical performance and success rate")
        elif performance < 0.5:
            reasoning.append("Below-average historical performance")
        
        if cost > 0.7:
            reasoning.append("Cost-effective option for this task")
        elif cost < 0.3:
            reasoning.append("Higher cost option - may exceed budget constraints")
        
        if speed > 0.7:
            reasoning.append("Fast response time and quick execution")
        elif speed < 0.4:
            reasoning.append("Slower response time - may not be suitable for urgent tasks")
        
        if availability < 0.3:
            reasoning.append("Currently heavily loaded - may experience delays")
        elif availability > 0.8:
            reasoning.append("Good availability - can start immediately")
        
        return reasoning
    
    def _estimate_performance_from_capability(self, agent_type: AgentType, task_context: TaskContext) -> float:
        """Estimate performance when no historical data is available"""
        capability = self.agent_capabilities[agent_type]
        
        # Base estimation from capability design
        base_performance = {
            AgentType.GENERAL_PURPOSE: 0.75,
            AgentType.CODEBASE_ARCHITECT: 0.85,
            AgentType.FRONTEND_EXPERT: 0.80,
            AgentType.BACKEND_ENGINEER: 0.82,
            AgentType.SENIOR_REVIEWER: 0.88,
            AgentType.TEST_ENGINEER: 0.78,
            AgentType.CI_LOG_ANALYZER: 0.76,
            AgentType.DOCKER_EXPERT: 0.83,
            AgentType.DATABASE_EXPERT: 0.85,
            AgentType.UI_ENGINEER: 0.77
        }.get(agent_type, 0.70)
        
        # Adjust based on task complexity match
        if task_context.complexity == TaskComplexity.ENTERPRISE:
            if agent_type in [AgentType.CODEBASE_ARCHITECT, AgentType.SENIOR_REVIEWER]:
                base_performance += 0.1
            elif agent_type == AgentType.GENERAL_PURPOSE:
                base_performance -= 0.1
        
        return max(0.0, min(1.0, base_performance))
    
    def _generate_context_key(self, task_context: TaskContext) -> str:
        """Generate a key for context pattern tracking"""
        # Simplified context key based on main keywords and complexity
        keywords = sorted(task_context.domain_keywords[:3])  # Top 3 keywords
        return f"{task_context.complexity.value}_{'-'.join(keywords)}"
    
    async def _apply_selection_strategy(self, scored_agents: List[SelectionScore],
                                      strategy: SelectionStrategy,
                                      task_context: TaskContext) -> List[SelectionScore]:
        """Apply strategy-specific optimizations to agent scores"""
        if strategy == SelectionStrategy.PERFORMANCE_FIRST:
            # Heavily weight performance
            for score in scored_agents:
                score.total_score = score.performance_score * 0.6 + score.total_score * 0.4
                
        elif strategy == SelectionStrategy.COST_OPTIMIZED:
            # Heavily weight cost efficiency
            for score in scored_agents:
                score.total_score = score.cost_score * 0.5 + score.total_score * 0.5
                
        elif strategy == SelectionStrategy.SPEED_OPTIMIZED:
            # Heavily weight speed
            for score in scored_agents:
                score.total_score = score.speed_score * 0.5 + score.total_score * 0.5
                
        elif strategy == SelectionStrategy.EXPERTISE_MATCHED:
            # Heavily weight domain expertise
            for score in scored_agents:
                score.total_score = score.expertise_score * 0.6 + score.total_score * 0.4
                
        elif strategy == SelectionStrategy.ADAPTIVE:
            # Learn from past successes to adjust weights
            optimized_scores = await self._apply_adaptive_optimization(scored_agents, task_context)
            return optimized_scores
        
        # Re-sort after strategy application
        scored_agents.sort(key=lambda x: x.total_score, reverse=True)
        return scored_agents
    
    async def _apply_adaptive_optimization(self, scored_agents: List[SelectionScore],
                                         task_context: TaskContext) -> List[SelectionScore]:
        """Apply adaptive optimization based on learned patterns"""
        # This would implement more sophisticated learning-based optimization
        # For now, implement a simplified version
        
        context_key = self._generate_context_key(task_context)
        if context_key in self.context_patterns:
            # Boost scores for agents that have been successful in similar contexts
            successful_agents = set(self.context_patterns[context_key])
            
            for score in scored_agents:
                if score.agent_type in successful_agents:
                    score.total_score *= 1.2  # 20% boost for historically successful agents
                    score.reasoning.append("Historically successful in similar contexts")
        
        scored_agents.sort(key=lambda x: x.total_score, reverse=True)
        return scored_agents
    
    async def _generate_recommendation(self, scored_agents: List[SelectionScore],
                                     task_context: TaskContext) -> SelectionRecommendation:
        """Generate final selection recommendation"""
        if not scored_agents:
            # Fallback recommendation
            return SelectionRecommendation(
                primary_agent=AgentType.GENERAL_PURPOSE,
                backup_agents=[],
                selection_reasoning="No suitable agents found - using fallback",
                expected_performance={"success_rate": 0.5},
                risk_factors=["Fallback selection with unknown performance"],
                optimization_suggestions=["Review task requirements and agent capabilities"],
                confidence=0.2
            )
        
        primary = scored_agents[0]
        backups = [score.agent_type for score in scored_agents[1:4]]  # Top 3 backups
        
        # Generate comprehensive reasoning
        reasoning_parts = [
            f"Selected {primary.agent_type.value} with score {primary.total_score:.2f}",
            f"Key strengths: {', '.join(primary.reasoning[:2])}"
        ]
        
        if primary.confidence < 0.5:
            reasoning_parts.append("Note: Low confidence due to limited historical data")
        
        reasoning = ". ".join(reasoning_parts)
        
        # Expected performance metrics
        expected_performance = {
            "success_rate": max(0.1, primary.performance_score),
            "cost_efficiency": primary.cost_score,
            "speed_rating": primary.speed_score,
            "expertise_match": primary.expertise_score
        }
        
        # Risk factors
        risk_factors = []
        if primary.availability_score < 0.3:
            risk_factors.append("Agent may be overloaded - potential delays")
        if primary.cost_score < 0.4:
            risk_factors.append("Higher cost option - monitor budget")
        if primary.confidence < 0.5:
            risk_factors.append("Limited historical performance data")
        
        # Optimization suggestions
        optimization_suggestions = []
        if len(backups) > 0:
            optimization_suggestions.append(f"Consider backup options: {backups[0].value}")
        if primary.performance_score < 0.6:
            optimization_suggestions.append("Monitor performance closely and be ready to switch agents")
        
        return SelectionRecommendation(
            primary_agent=primary.agent_type,
            backup_agents=backups,
            selection_reasoning=reasoning,
            expected_performance=expected_performance,
            risk_factors=risk_factors,
            optimization_suggestions=optimization_suggestions,
            confidence=primary.confidence
        )
    
    async def _optimize_batch_coherence(self, recommendations: List[SelectionRecommendation],
                                      task_contexts: List[TaskContext]) -> List[SelectionRecommendation]:
        """Optimize batch recommendations for workflow coherence"""
        # Implement workflow coherence optimization
        # For now, just return the original recommendations
        return recommendations
    
    async def _track_selection(self, task_context: TaskContext, recommendation: SelectionRecommendation):
        """Track agent selection for learning and optimization"""
        selection_record = {
            "timestamp": datetime.now(),
            "task_description": task_context.description,
            "complexity": task_context.complexity.value,
            "selected_agent": recommendation.primary_agent.value,
            "confidence": recommendation.confidence,
            "expected_performance": recommendation.expected_performance
        }
        
        self.selection_history.append(selection_record)
        
        # Update context patterns
        context_key = self._generate_context_key(task_context)
        if context_key not in self.context_patterns:
            self.context_patterns[context_key] = []
        self.context_patterns[context_key].append(recommendation.primary_agent)
        
        # Update agent workload
        self.agent_workloads[recommendation.primary_agent] = self.agent_workloads.get(
            recommendation.primary_agent, 0) + 1
    
    def update_agent_workload(self, agent_type: AgentType, change: int):
        """Update agent workload (call when tasks start/complete)"""
        current_workload = self.agent_workloads.get(agent_type, 0)
        self.agent_workloads[agent_type] = max(0, current_workload + change)
    
    async def get_selection_analytics(self) -> Dict[str, Any]:
        """Get analytics about agent selection patterns"""
        if not self.selection_history:
            return {"message": "No selection history available"}
        
        total_selections = len(self.selection_history)
        
        # Agent usage distribution
        agent_usage = {}
        for record in self.selection_history:
            agent = record["selected_agent"]
            agent_usage[agent] = agent_usage.get(agent, 0) + 1
        
        # Average confidence
        avg_confidence = statistics.mean([r["confidence"] for r in self.selection_history])
        
        # Complexity distribution
        complexity_dist = {}
        for record in self.selection_history:
            complexity = record["complexity"]
            complexity_dist[complexity] = complexity_dist.get(complexity, 0) + 1
        
        return {
            "total_selections": total_selections,
            "agent_usage_distribution": agent_usage,
            "average_confidence": avg_confidence,
            "complexity_distribution": complexity_dist,
            "context_patterns_learned": len(self.context_patterns),
            "most_selected_agent": max(agent_usage.items(), key=lambda x: x[1])[0] if agent_usage else None
        }
    
    # Dashboard widget support methods
    
    async def get_agent_utilization(self) -> Dict[str, Any]:
        """Get agent utilization data for dashboard widgets"""
        # Calculate utilization percentages based on workload and capacity
        agent_utilization = {}
        total_workload = sum(self.agent_workloads.values())
        
        for agent_type in AgentType:
            current_workload = self.agent_workloads.get(agent_type, 0)
            # Assume each agent has a capacity of 10 concurrent tasks
            max_capacity = 10
            utilization = min(100.0, (current_workload / max_capacity) * 100)
            agent_utilization[agent_type.value] = round(utilization, 1)
        
        return {
            "utilization": agent_utilization,
            "total_active_tasks": total_workload,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics for dashboard widgets"""
        agent_performance = {}
        
        # Calculate performance metrics from selection history
        for agent_type in AgentType:
            agent_selections = [
                record for record in self.selection_history 
                if record["selected_agent"] == agent_type.value
            ]
            
            if agent_selections:
                # Calculate average metrics
                avg_confidence = statistics.mean([s["confidence"] for s in agent_selections])
                
                # Mock some additional performance data (would come from actual execution tracking)
                success_rate = min(100.0, 75.0 + avg_confidence * 25)  # Scale confidence to success rate
                avg_duration = 5.0 + (1.0 - avg_confidence) * 10.0    # Lower confidence = longer duration
                cost_efficiency = 0.6 + avg_confidence * 0.3           # Higher confidence = better efficiency
                
                agent_performance[agent_type.value] = {
                    "success_rate": round(success_rate, 1),
                    "avg_duration": round(avg_duration, 1),
                    "cost_efficiency": round(cost_efficiency, 2),
                    "selection_count": len(agent_selections),
                    "avg_confidence": round(avg_confidence, 2)
                }
            else:
                # Default metrics for agents with no history
                agent_performance[agent_type.value] = {
                    "success_rate": 85.0,
                    "avg_duration": 6.0,
                    "cost_efficiency": 0.75,
                    "selection_count": 0,
                    "avg_confidence": 0.7
                }
        
        return {
            "performance": agent_performance,
            "timestamp": datetime.now().isoformat()
        }