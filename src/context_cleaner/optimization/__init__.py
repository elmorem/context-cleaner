"""
Context Optimization Module - PR15.3: Intelligent Cache-Based Optimization

This module provides comprehensive context optimization capabilities including:
- Cache-enhanced dashboard with usage-based health scoring
- Intelligent recommendations based on usage patterns
- Cross-session analytics for pattern correlation
- Advanced reporting with usage-based insights
- Personalized optimization strategies
"""

from .basic_analyzer import SafeContextAnalyzer
from .cache_dashboard import (
    CacheEnhancedDashboard,
    CacheEnhancedDashboardData,
    UsageBasedHealthMetrics,
    HealthLevel,
    UsageInsight,
)
from .intelligent_recommender import (
    IntelligentRecommendationEngine,
    IntelligentRecommendation,
    PersonalizationProfile,
    OptimizationAction,
    RecommendationPriority,
    OptimizationCategory,
)
from .cross_session_analytics import (
    CrossSessionAnalyticsEngine,
    CrossSessionInsights,
    SessionMetrics,
    PatternEvolution,
    WorkflowTemplate,
)
from .advanced_reports import (
    AdvancedReportingSystem,
    UsageReport,
    ReportSection,
    ReportType,
    ReportFormat,
)
from .personalized_strategies import (
    PersonalizedOptimizationEngine,
    PersonalizedStrategy,
    StrategyRule,
    StrategyType,
    OptimizationMode,
    StrategyRecommendation,
)

# PR19: Interactive Optimization Workflows
from .interactive_workflow import (
    InteractiveWorkflowManager,
    InteractiveSession,
    WorkflowStep,
    WorkflowResult,
    UserAction,
    start_interactive_optimization,
    quick_optimization_preview,
)
from .change_approval import (
    ChangeApprovalSystem,
    ChangeSelection,
    SelectiveApprovalResult,
    ApprovalDecision,
    ChangeCategory,
    create_quick_approval,
    approve_all_operations,
    approve_safe_operations_only,
)

__all__ = [
    # Core optimization
    "SafeContextAnalyzer",
    # Cache-enhanced dashboard
    "CacheEnhancedDashboard",
    "CacheEnhancedDashboardData",
    "UsageBasedHealthMetrics",
    "HealthLevel",
    "UsageInsight",
    # Intelligent recommendations
    "IntelligentRecommendationEngine",
    "IntelligentRecommendation",
    "PersonalizationProfile",
    "OptimizationAction",
    "RecommendationPriority",
    "OptimizationCategory",
    # Cross-session analytics
    "CrossSessionAnalyticsEngine",
    "CrossSessionInsights",
    "SessionMetrics",
    "PatternEvolution",
    "WorkflowTemplate",
    # Advanced reporting
    "AdvancedReportingSystem",
    "UsageReport",
    "ReportSection",
    "ReportType",
    "ReportFormat",
    # Personalized strategies
    "PersonalizedOptimizationEngine",
    "PersonalizedStrategy",
    "StrategyRule",
    "StrategyType",
    "OptimizationMode",
    "StrategyRecommendation",
    # PR19: Interactive workflows
    "InteractiveWorkflowManager",
    "InteractiveSession",
    "WorkflowStep",
    "WorkflowResult",
    "UserAction",
    "start_interactive_optimization",
    "quick_optimization_preview",
    # PR19: Change approval
    "ChangeApprovalSystem",
    "ChangeSelection",
    "SelectiveApprovalResult",
    "ApprovalDecision",
    "ChangeCategory",
    "create_quick_approval",
    "approve_all_operations",
    "approve_safe_operations_only",
]
