"""Cost optimization engine for intelligent model selection and budget management."""

import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ..clients.base import TelemetryClient
from .models import (
    BudgetConfig, 
    ModelRecommendation, 
    ModelType, 
    TaskComplexity, 
    TaskAnalysis,
    CostAnalysis,
    OptimizationSuggestion,
    UsagePattern
)
from .budget_manager import BudgetManager

logger = logging.getLogger(__name__)


class CostOptimizationEngine:
    """Main engine for cost optimization and intelligent model selection."""
    
    def __init__(self, telemetry_client: TelemetryClient, budget_config: Optional[BudgetConfig] = None):
        self.telemetry = telemetry_client
        self.budget_config = budget_config or BudgetConfig()
        self.budget_manager = BudgetManager(telemetry_client, self.budget_config)
        
        # Model cost data (approximate, based on telemetry analysis)
        self.model_costs = {
            ModelType.SONNET_4: {
                "input_cost_per_1k_tokens": 0.015,  # $0.015 per 1k input tokens
                "output_cost_per_1k_tokens": 0.075,  # $0.075 per 1k output tokens
                "avg_duration_ms": 5000
            },
            ModelType.HAIKU: {
                "input_cost_per_1k_tokens": 0.00025,  # $0.00025 per 1k input tokens  
                "output_cost_per_1k_tokens": 0.00125,  # $0.00125 per 1k output tokens
                "avg_duration_ms": 1500
            }
        }
        
        # Task complexity keywords for automatic classification
        self.complexity_keywords = {
            TaskComplexity.SIMPLE: [
                "read", "show", "display", "list", "what is", "explain", "help",
                "find", "search", "check", "status", "version"
            ],
            TaskComplexity.MODERATE: [
                "analyze", "edit", "modify", "update", "fix", "implement", "create",
                "write", "documentation", "test", "debug", "refactor"
            ],
            TaskComplexity.COMPLEX: [
                "architecture", "design", "optimize", "performance", "security",
                "migrate", "integration", "algorithm", "system", "complex"
            ],
            TaskComplexity.CREATIVE: [
                "generate", "brainstorm", "creative", "invent", "compose",
                "story", "ideas", "innovative", "artistic"
            ]
        }
    
    async def should_use_haiku(self, task_description: str, session_id: str) -> bool:
        """Determine if Haiku should be used based on task analysis and budget."""
        try:
            # Check budget constraints first
            if await self.budget_manager.should_force_cost_optimization(session_id):
                logger.info("Forcing Haiku due to budget constraints")
                return True
            
            # Analyze task complexity
            task_analysis = await self.analyze_task_complexity(task_description)
            
            # Simple tasks are good candidates for Haiku
            if task_analysis.complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE] and task_analysis.is_routine:
                return True
            
            # Check current session costs
            current_costs = await self.budget_manager.get_current_costs(session_id)
            session_percentage = current_costs["session"] / self.budget_config.session_limit
            
            # Use Haiku if approaching budget limits
            if session_percentage > self.budget_config.warning_threshold:
                return True
            
            # Check token count - large contexts work well with Haiku for analysis tasks
            if task_analysis.estimated_tokens > 2000 and not task_analysis.requires_precision:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error determining model choice: {e}")
            # Default to conservative choice (Haiku) on error
            return True
    
    async def get_model_recommendation(self, task_description: str, session_id: str) -> ModelRecommendation:
        """Get comprehensive model recommendation based on task analysis and budget."""
        try:
            task_analysis = await self.analyze_task_complexity(task_description)
            should_use_haiku = await self.should_use_haiku(task_description, session_id)
            
            if should_use_haiku:
                model = ModelType.HAIKU
                confidence = 0.9 if task_analysis.is_routine else 0.7
                reasoning = self._generate_haiku_reasoning(task_analysis, session_id)
            else:
                model = ModelType.SONNET_4
                confidence = 0.8 if task_analysis.requires_precision else 0.6
                reasoning = self._generate_sonnet_reasoning(task_analysis)
            
            # Calculate expected costs
            expected_cost = self._estimate_cost(model, task_analysis.estimated_tokens)
            expected_duration = self.model_costs[model]["avg_duration_ms"]
            
            # Calculate savings if recommending Haiku over Sonnet
            cost_savings = None
            if model == ModelType.HAIKU:
                sonnet_cost = self._estimate_cost(ModelType.SONNET_4, task_analysis.estimated_tokens)
                cost_savings = sonnet_cost - expected_cost
            
            return ModelRecommendation(
                model=model,
                confidence=confidence,
                reasoning=reasoning,
                expected_cost=expected_cost,
                expected_duration_ms=expected_duration,
                cost_savings=cost_savings
            )
            
        except Exception as e:
            logger.error(f"Error generating model recommendation: {e}")
            # Return safe default
            return ModelRecommendation(
                model=ModelType.HAIKU,
                confidence=0.5,
                reasoning="Default recommendation due to error",
                expected_cost=0.01
            )
    
    async def analyze_task_complexity(self, task_description: str) -> TaskAnalysis:
        """Analyze task complexity and characteristics."""
        desc_lower = task_description.lower()
        
        # Determine complexity based on keywords
        complexity_scores = {}
        for complexity, keywords in self.complexity_keywords.items():
            score = sum(1 for keyword in keywords if keyword in desc_lower)
            if score > 0:
                complexity_scores[complexity] = score
        
        # Get the complexity with highest score, default to MODERATE
        complexity = TaskComplexity.MODERATE
        if complexity_scores:
            complexity = max(complexity_scores.items(), key=lambda x: x[1])[0]
        
        # Estimate tokens using enhanced token counting system
        estimated_tokens = self._get_accurate_token_count(task_description)
        
        # Determine if precision is required
        precision_keywords = ["exact", "precise", "accurate", "correct", "specific", "detailed"]
        requires_precision = any(keyword in desc_lower for keyword in precision_keywords)
        
        # Determine if routine
        routine_keywords = ["read", "list", "show", "check", "status", "find", "search"]
        is_routine = any(keyword in desc_lower for keyword in routine_keywords)
        
        return TaskAnalysis(
            task_description=task_description,
            complexity=complexity,
            estimated_tokens=estimated_tokens,
            requires_precision=requires_precision,
            is_routine=is_routine,
            similar_tasks_history=[]  # Could be populated from telemetry data
        )
    
    def _get_accurate_token_count(self, text: str) -> int:
        """Get accurate token count using enhanced token counting system."""
        try:
            # Try to use enhanced token counter if available
            import asyncio
            try:
                from ...analysis.enhanced_token_counter import AnthropicTokenCounter
                import os
                
                # Get API key
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.debug("No ANTHROPIC_API_KEY found, using fallback estimation")
                    raise ValueError("No API key available")
                
                # Use Anthropic's count-tokens API to get accurate count
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Create messages in the format expected by the API
                    messages = [{"role": "user", "content": text}]
                    
                    # Use the API to count tokens
                    async def count_tokens():
                        async with AnthropicTokenCounter(api_key) as counter:
                            return await counter.count_tokens_for_messages(messages)
                    
                    tokens = loop.run_until_complete(count_tokens())
                    if tokens > 0:
                        return tokens
                except Exception as api_error:
                    logger.debug(f"Anthropic API token counting failed: {api_error}")
                finally:
                    loop.close()
            except ImportError:
                logger.debug("Enhanced token counter not available, using fallback")
            
        except Exception as e:
            logger.debug(f"Enhanced token counting failed: {e}")
        
        # Fallback to improved approximation (better than simple word count)
        estimated_tokens = len(text.split()) * 1.3  # Approximate token count
        estimated_tokens = max(100, min(4000, int(estimated_tokens)))  # Reasonable bounds
        return estimated_tokens
    
    def _estimate_cost(self, model: ModelType, estimated_tokens: int) -> float:
        """Estimate cost for a request with given model and token count."""
        cost_data = self.model_costs[model]
        
        # Assume input:output ratio of 4:1 (typical for most tasks)
        input_tokens = estimated_tokens
        output_tokens = estimated_tokens // 4
        
        input_cost = (input_tokens / 1000) * cost_data["input_cost_per_1k_tokens"]
        output_cost = (output_tokens / 1000) * cost_data["output_cost_per_1k_tokens"]
        
        return input_cost + output_cost
    
    def _generate_haiku_reasoning(self, task_analysis: TaskAnalysis, session_id: str) -> str:
        """Generate reasoning for why Haiku is recommended."""
        reasons = []
        
        if task_analysis.is_routine:
            reasons.append("routine task suitable for efficient processing")
        
        if task_analysis.complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]:
            reasons.append(f"{task_analysis.complexity.value} complexity level")
        
        if task_analysis.estimated_tokens > 2000:
            reasons.append("large context size - Haiku handles efficiently")
        
        # Could add budget-related reasoning here
        reasons.append("cost-effective choice with 60-80% savings vs Sonnet")
        
        return "Haiku recommended: " + ", ".join(reasons)
    
    def _generate_sonnet_reasoning(self, task_analysis: TaskAnalysis) -> str:
        """Generate reasoning for why Sonnet is recommended.""" 
        reasons = []
        
        if task_analysis.requires_precision:
            reasons.append("high precision required")
        
        if task_analysis.complexity in [TaskComplexity.COMPLEX, TaskComplexity.CREATIVE]:
            reasons.append(f"{task_analysis.complexity.value} task benefits from advanced reasoning")
        
        if not task_analysis.is_routine:
            reasons.append("non-routine task requiring sophisticated analysis")
        
        return "Sonnet 4 recommended: " + ", ".join(reasons)
    
    async def get_session_analysis(self, session_id: str) -> CostAnalysis:
        """Get comprehensive cost analysis for the current session."""
        try:
            current_costs = await self.budget_manager.get_current_costs(session_id)
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            model_stats = await self.telemetry.get_model_usage_stats(days=7)
            
            # Calculate averages for comparison
            daily_avg = 1.50  # Default average, could be calculated from historical data
            session_avg = 1.00
            
            # Calculate vs averages
            vs_daily_avg = ((current_costs["daily"] - daily_avg) / daily_avg) * 100 if daily_avg > 0 else 0
            vs_session_avg = ((current_costs["session"] - session_avg) / session_avg) * 100 if session_avg > 0 else 0
            
            # Model cost breakdown
            sonnet_cost = 0
            haiku_cost = 0
            for model, stats in model_stats.items():
                if "sonnet" in model.lower():
                    sonnet_cost += stats.get("total_cost", 0)
                elif "haiku" in model.lower():
                    haiku_cost += stats.get("total_cost", 0)
            
            # Efficiency metrics
            cost_per_token = 0
            cost_per_minute = 0
            if session_metrics:
                cost_per_token = current_costs["session"] / max(session_metrics.total_input_tokens, 1)
                session_duration = 60  # Default 60 minutes
                if session_metrics.start_time and session_metrics.end_time:
                    duration_delta = session_metrics.end_time - session_metrics.start_time
                    session_duration = duration_delta.total_seconds() / 60
                cost_per_minute = current_costs["session"] / max(session_duration, 1)
            
            # Projections
            projections = await self.budget_manager.get_budget_projections(session_id)
            
            return CostAnalysis(
                session_cost=current_costs["session"],
                daily_cost=current_costs["daily"],
                weekly_cost=current_costs["weekly"],
                vs_daily_avg=vs_daily_avg,
                vs_session_avg=vs_session_avg,
                sonnet_cost=sonnet_cost,
                haiku_cost=haiku_cost,
                cost_per_token=cost_per_token,
                cost_per_minute=cost_per_minute,
                projected_daily_cost=projections.get("projected_daily_total"),
                budget_remaining=max(0, self.budget_config.session_limit - current_costs["session"])
            )
            
        except Exception as e:
            logger.error(f"Error generating session analysis: {e}")
            return CostAnalysis(
                session_cost=0, daily_cost=0, weekly_cost=0,
                vs_daily_avg=0, vs_session_avg=0,
                sonnet_cost=0, haiku_cost=0,
                cost_per_token=0, cost_per_minute=0
            )
    
    async def get_optimization_suggestions(self, session_id: str) -> List[OptimizationSuggestion]:
        """Get personalized optimization suggestions for the current session."""
        suggestions = []
        
        try:
            # Get budget-related suggestions
            budget_suggestions = await self.budget_manager.check_budget_status(session_id)
            suggestions.extend(budget_suggestions)
            
            # Get session metrics for analysis
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            if session_metrics:
                # High API call frequency suggestion
                if session_metrics.api_calls > 20:
                    suggestions.append(OptimizationSuggestion(
                        type="efficiency",
                        priority="medium",
                        title="High API Usage Detected",
                        description=f"Session has {session_metrics.api_calls} API calls. Consider batching requests or using more efficient workflows.",
                        expected_savings_percent=25.0
                    ))
                
                # Large context suggestion
                avg_tokens = session_metrics.total_input_tokens / max(session_metrics.api_calls, 1)
                if avg_tokens > 2000:
                    suggestions.append(OptimizationSuggestion(
                        type="context_optimization",
                        priority="medium",
                        title="Large Context Size",
                        description=f"Average request size is {avg_tokens:.0f} tokens. Consider breaking down large contexts for better efficiency.",
                        expected_savings_percent=30.0,
                        auto_applicable=self.budget_config.auto_context_optimization
                    ))
            
            # Model usage optimization
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            sonnet_requests = 0
            total_requests = 0
            for model, stats in model_stats.items():
                total_requests += stats["request_count"]
                if "sonnet" in model.lower():
                    sonnet_requests += stats["request_count"]
            
            if total_requests > 0:
                sonnet_percentage = sonnet_requests / total_requests
                if sonnet_percentage > 0.7:  # More than 70% Sonnet usage
                    suggestions.append(OptimizationSuggestion(
                        type="model_optimization",
                        priority="high",
                        title="High Sonnet Usage",
                        description=f"{sonnet_percentage:.0%} of requests use Sonnet. Many tasks could use Haiku for significant savings.",
                        expected_savings_percent=65.0,
                        auto_applicable=self.budget_config.auto_switch_haiku
                    ))
            
        except Exception as e:
            logger.error(f"Error generating optimization suggestions: {e}")
        
        return suggestions
    
    async def get_usage_patterns(self, session_id: str) -> UsagePattern:
        """Analyze user usage patterns for personalized recommendations."""
        try:
            model_stats = await self.telemetry.get_model_usage_stats(days=7)
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            
            # Calculate model preferences
            preferred_models = {}
            total_requests = sum(stats["request_count"] for stats in model_stats.values())
            
            for model, stats in model_stats.items():
                if "sonnet" in model.lower():
                    model_type = ModelType.SONNET_4
                else:
                    model_type = ModelType.HAIKU
                    
                if model_type not in preferred_models:
                    preferred_models[model_type] = 0
                preferred_models[model_type] += stats["request_count"] / max(total_requests, 1)
            
            # Default values
            average_session_duration = 30.0  # minutes
            if session_metrics and session_metrics.start_time and session_metrics.end_time:
                duration_delta = session_metrics.end_time - session_metrics.start_time
                average_session_duration = duration_delta.total_seconds() / 60
            
            # Estimate cost sensitivity based on usage patterns
            cost_sensitivity = 0.5  # Default medium sensitivity
            if preferred_models.get(ModelType.HAIKU, 0) > 0.6:
                cost_sensitivity = 0.8  # High cost sensitivity
            elif preferred_models.get(ModelType.SONNET_4, 0) > 0.8:
                cost_sensitivity = 0.2  # Low cost sensitivity
            
            return UsagePattern(
                preferred_models=preferred_models,
                peak_hours=[10, 11, 14, 15],  # Based on telemetry analysis
                average_session_duration_minutes=average_session_duration,
                common_task_types=["analysis", "coding", "debugging"],  # Could be derived from data
                cost_sensitivity=cost_sensitivity
            )
            
        except Exception as e:
            logger.error(f"Error analyzing usage patterns: {e}")
            return UsagePattern(
                preferred_models={ModelType.HAIKU: 0.6, ModelType.SONNET_4: 0.4},
                peak_hours=[10, 14],
                average_session_duration_minutes=30.0,
                common_task_types=["general"],
                cost_sensitivity=0.5
            )