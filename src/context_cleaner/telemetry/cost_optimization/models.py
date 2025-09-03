"""Data models for cost optimization system."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ModelType(Enum):
    """Available Claude models."""
    SONNET_4 = "claude-sonnet-4-20250514"
    HAIKU = "claude-3-5-haiku-20241022"


class TaskComplexity(Enum):
    """Task complexity levels for model selection."""
    SIMPLE = "simple"          # File reading, basic questions
    MODERATE = "moderate"      # Analysis, editing, documentation
    COMPLEX = "complex"        # Architecture design, complex debugging
    CREATIVE = "creative"      # Creative writing, brainstorming


@dataclass
class BudgetConfig:
    """Configuration for budget limits and thresholds."""
    daily_limit: float = 5.0      # Default $5/day
    session_limit: float = 2.0    # Default $2/session
    request_limit: float = 0.05   # Default $0.05/request
    
    # Alert thresholds (percentages)
    warning_threshold: float = 0.8    # 80%
    critical_threshold: float = 0.95  # 95%
    
    # Auto-optimization settings
    auto_switch_haiku: bool = True
    auto_context_optimization: bool = True


@dataclass
class ModelRecommendation:
    """Recommendation for which model to use."""
    model: ModelType
    confidence: float  # 0.0 to 1.0
    reasoning: str
    expected_cost: Optional[float] = None
    expected_duration_ms: Optional[float] = None
    cost_savings: Optional[float] = None


@dataclass 
class CostAnalysis:
    """Analysis of current costs and trends."""
    session_cost: float
    daily_cost: float
    weekly_cost: float
    
    # Comparisons to averages
    vs_daily_avg: float  # Percentage difference
    vs_session_avg: float
    
    # Model breakdown
    sonnet_cost: float
    haiku_cost: float
    
    # Efficiency metrics
    cost_per_token: float
    cost_per_minute: float
    
    # Projections
    projected_daily_cost: Optional[float] = None
    budget_remaining: Optional[float] = None


@dataclass
class OptimizationSuggestion:
    """Suggestion for cost optimization."""
    type: str  # "model_switch", "context_reduction", "budget_alert", etc.
    priority: str  # "low", "medium", "high", "critical"
    title: str
    description: str
    expected_savings: Optional[float] = None  # Dollar amount
    expected_savings_percent: Optional[float] = None  # Percentage
    action_required: bool = False
    auto_applicable: bool = False


@dataclass
class TaskAnalysis:
    """Analysis of a task to determine complexity and optimal model."""
    task_description: str
    complexity: TaskComplexity
    estimated_tokens: int
    requires_precision: bool
    is_routine: bool
    similar_tasks_history: List[Dict[str, Any]]
    
    
@dataclass
class UsagePattern:
    """Pattern analysis of user behavior."""
    preferred_models: Dict[ModelType, float]  # Usage percentages
    peak_hours: List[int]
    average_session_duration_minutes: float
    common_task_types: List[str]
    cost_sensitivity: float  # 0.0 to 1.0, how cost-conscious user is