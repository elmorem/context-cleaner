"""
Pytest configuration and fixtures for Context Cleaner tests.
"""

import warnings

import pytest
import tempfile
from datetime import datetime, timedelta

warnings.filterwarnings(
    "ignore",
    message=r".*websockets\.server\.serve is deprecated",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*websockets\.legacy is deprecated",
    category=DeprecationWarning,
)

from context_cleaner.telemetry.context_rot.config import ApplicationConfig
from context_cleaner.analytics.productivity_analyzer import ProductivityAnalyzer


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def test_config(temp_data_dir):
    """Create test configuration."""
    config = ApplicationConfig.default()
    config.data_directory = temp_data_dir
    config.tracking.enabled = True
    config.tracking.session_timeout_minutes = 5
    config.analysis.max_context_size = 10000
    return config


@pytest.fixture
def productivity_analyzer(test_config):
    """Create ProductivityAnalyzer instance for testing."""
    return ProductivityAnalyzer(test_config)


@pytest.fixture
def mock_session_data():
    """Generate mock session data for testing."""
    base_time = datetime.now() - timedelta(days=7)

    sessions = []
    for i in range(10):
        session_time = base_time + timedelta(hours=i * 8)
        sessions.append(
            {
                "timestamp": session_time.isoformat(),
                "session_duration": 120 + (i * 15),  # 2-4 hours
                "context_health_score": 70 + (i * 3),  # Improving over time
                "productivity_score": 65 + (i * 4),  # Improving productivity
                "optimization_events": i % 3,  # Variable optimizations
                "session_type": ["coding", "debugging", "testing"][i % 3],
            }
        )

    return sessions


@pytest.fixture
def mock_context_data():
    """Generate mock context data for testing."""
    return {
        "total_tokens": 15000,
        "file_count": 25,
        "conversation_depth": 45,
        "last_optimization": "2024-12-20T10:30:00",
        "tools_used": ["Read", "Write", "Bash", "Edit"],
        "session_start": "2024-12-20T09:00:00",
    }


# ===========================
# Optimization Module Fixtures (from tests/optimization/conftest.py)
# ===========================

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass
import statistics

# Import the modules we're testing (with conditional imports for missing dependencies)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Import project modules
from context_cleaner.optimization.cache_dashboard import (
    CacheEnhancedDashboard, UsageBasedHealthMetrics, HealthLevel,
    CacheEnhancedDashboardData, UsageInsight
)
from context_cleaner.optimization.intelligent_recommender import (
    IntelligentRecommendationEngine, PersonalizationProfile, IntelligentRecommendation
)
from context_cleaner.optimization.cross_session_analytics import (
    CrossSessionAnalyticsEngine, SessionMetrics, CrossSessionInsights
)
from context_cleaner.optimization.advanced_reports import AdvancedReportingSystem
from context_cleaner.optimization.personalized_strategies import PersonalizedOptimizationEngine


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_cache_locations(temp_storage_dir):
    """Create mock cache locations with test data."""
    cache_dirs = []
    for i in range(3):
        cache_dir = temp_storage_dir / f"cache_{i}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock cache files
        cache_file = cache_dir / "conversations.json"
        mock_data = {
            "sessions": [
                {
                    "session_id": f"session_{i}_{j}",
                    "timestamp": (datetime.now() - timedelta(days=j)).isoformat(),
                    "duration_minutes": 60 + j * 15,
                    "files_accessed": [f"file_{j}.py", f"test_{j}.py"],
                    "total_tokens": 1000 + j * 200,
                    "efficiency_score": 0.7 + (j % 5) * 0.05,
                    "focus_score": 0.6 + (j % 4) * 0.1,
                    "workflow_type": ["development", "testing", "debugging"][j % 3],
                    "tools_used": ["read", "edit", "bash"][:(j % 3) + 1],
                    "optimization_actions": ["remove_duplicates", "consolidate"][:(j % 2) + 1]
                }
                for j in range(10)
            ]
        }
        
        with open(cache_file, 'w') as f:
            json.dump(mock_data, f)
        
        cache_dirs.append(cache_dir)
    
    return cache_dirs


@pytest.fixture
def mock_optimization_session_data():
    """Generate comprehensive mock session data for optimization testing."""
    sessions = []
    base_time = datetime.now() - timedelta(days=30)
    
    workflows = ["development", "testing", "debugging", "documentation", "research"]
    tools = [["read", "edit"], ["bash", "read"], ["edit", "bash", "read"], ["read"], ["read", "edit", "bash"]]
    file_types = [[".py"], [".py", ".md"], [".js", ".py"], [".md"], [".py", ".js", ".md"]]
    
    for i in range(50):
        session_time = base_time + timedelta(hours=i * 6 + (i % 24))
        workflow_idx = i % len(workflows)
        
        session = Mock()
        session.session_id = f"session_{i:03d}"
        session.timestamp = session_time
        session.duration_minutes = 45 + (i % 120)  # 45-165 minutes
        session.files_accessed = [f"file_{j}.py" for j in range((i % 5) + 1)]
        session.total_tokens = 800 + i * 50 + (i % 1000)
        session.efficiency_score = 0.5 + (i % 50) / 100.0  # 0.5-1.0
        session.focus_score = 0.4 + (i % 60) / 100.0  # 0.4-1.0
        session.workflow_type = workflows[workflow_idx]
        session.tools_used = tools[workflow_idx]
        session.file_types = file_types[workflow_idx]
        session.optimization_actions = ["remove_duplicates", "consolidate_similar", "reorder_priority"][:(i % 3) + 1]
        
        sessions.append(session)
    
    return sessions


@pytest.fixture
def mock_usage_pattern_summary():
    """Create mock usage pattern summary."""
    from context_cleaner.analysis import UsagePatternSummary, FileAccessPattern
    
    file_patterns = []
    for i in range(10):
        pattern = Mock(spec=FileAccessPattern)
        pattern.file_path = f"src/module_{i}.py"
        pattern.access_frequency = 10 - i  # Decreasing frequency
        pattern.last_access_hours = i * 2
        pattern.pattern = f"*.{['py', 'js', 'md'][i % 3]}"
        file_patterns.append(pattern)
    
    summary = Mock(spec=UsagePatternSummary)
    summary.file_patterns = file_patterns
    summary.workflow_efficiency = 0.75
    summary.total_files = len(file_patterns)
    summary.frequent_patterns = file_patterns[:3]
    
    return summary


@pytest.fixture
def mock_token_analysis_summary():
    """Create mock token analysis summary."""
    from context_cleaner.analysis import TokenAnalysisSummary, TokenWastePattern
    
    waste_patterns = []
    for i in range(5):
        pattern = Mock(spec=TokenWastePattern)
        pattern.pattern = f"duplicate_content_{i}"
        pattern.waste_tokens = 100 + i * 50
        pattern.frequency = 5 - i
        waste_patterns.append(pattern)
    
    summary = Mock(spec=TokenAnalysisSummary)
    summary.total_tokens = 10000
    summary.efficient_tokens = 7500
    summary.waste_tokens = 2500
    summary.waste_percentage = 25.0
    summary.waste_patterns = waste_patterns
    summary.efficiency_score = 0.75
    
    return summary


@pytest.fixture
def mock_temporal_insights():
    """Create mock temporal insights."""
    from context_cleaner.analysis import TemporalInsights
    
    insights = Mock(spec=TemporalInsights)
    insights.coherence_score = 0.6
    insights.temporal_patterns = ["morning_focus", "afternoon_debugging"]
    insights.session_transitions = {"development": ["testing", "debugging"], "testing": ["development"]}
    insights.peak_efficiency_hours = [9, 10, 11, 14, 15]
    
    return insights


@pytest.fixture
def mock_enhanced_analysis():
    """Create mock enhanced analysis."""
    from context_cleaner.analysis import CacheEnhancedAnalysis
    
    analysis = Mock(spec=CacheEnhancedAnalysis)
    analysis.usage_weighted_focus_score = 0.72
    analysis.priority_alignment_score = 0.68
    analysis.overall_health_score = 0.70
    analysis.weighted_context_size = 8500
    analysis.optimization_opportunities = ["remove_stale", "consolidate_similar"]
    
    return analysis


@pytest.fixture
def mock_correlation_insights():
    """Create mock correlation insights."""
    from context_cleaner.analysis import CorrelationInsights, CrossSessionPattern
    
    patterns = []
    for i in range(3):
        pattern = Mock(spec=CrossSessionPattern)
        pattern.pattern_id = f"pattern_{i}"
        pattern.pattern_type = ["file_sequence", "tool_usage", "workflow"][i]
        pattern.frequency = 0.8 - i * 0.1
        pattern.sessions = [f"session_{j}" for j in range(5)]
        patterns.append(pattern)
    
    insights = Mock(spec=CorrelationInsights)
    insights.session_clusters = []
    insights.cross_session_patterns = patterns
    insights.long_term_trends = ["increasing_efficiency", "workflow_stabilization"]
    insights.correlation_strength = 0.75
    
    return insights


@pytest.fixture
def mock_health_metrics():
    """Create mock usage-based health metrics."""
    return UsageBasedHealthMetrics(
        usage_weighted_focus_score=0.75,
        efficiency_score=0.80,
        temporal_coherence_score=0.65,
        cross_session_consistency=0.70,
        optimization_potential=0.25,
        waste_reduction_score=0.80,
        workflow_alignment=0.72
    )


@pytest.fixture
def mock_personalization_profile():
    """Create mock personalization profile."""
    return PersonalizationProfile(
        user_id="test_user",
        preferred_optimization_modes=["balanced", "efficiency"],
        typical_session_length=timedelta(hours=2),
        common_file_types=[".py", ".js", ".md"],
        frequent_workflows=["development", "testing"],
        confirmation_preferences={
            "high_risk": True,
            "automation": False,
            "bulk_delete": True
        },
        automation_comfort_level=0.6,
        optimization_frequency="weekly",
        successful_recommendations=["rec_001", "rec_002"],
        rejected_recommendations=["rec_003"],
        optimization_outcomes={"token_efficiency": 0.8, "workflow_alignment": 0.7},
        profile_confidence=0.75,
        last_updated=datetime.now(),
        session_count=25
    )


@pytest.fixture
def mock_dashboard_data(
    mock_health_metrics, 
    mock_usage_pattern_summary,
    mock_token_analysis_summary,
    mock_temporal_insights,
    mock_enhanced_analysis,
    mock_correlation_insights
):
    """Create comprehensive mock dashboard data."""
    return CacheEnhancedDashboardData(
        context_size=10000,
        file_count=25,
        session_count=20,
        analysis_timestamp=datetime.now(),
        health_metrics=mock_health_metrics,
        usage_summary=mock_usage_pattern_summary,
        token_analysis=mock_token_analysis_summary,
        temporal_insights=mock_temporal_insights,
        enhanced_analysis=mock_enhanced_analysis,
        correlation_insights=mock_correlation_insights,
        traditional_health=Mock(focus_score=0.75, priority_alignment=0.70, context_health_score=0.72),
        insights=[
            UsageInsight(
                type="token_efficiency",
                title="High Token Waste Detected",
                description="25% token waste identified",
                impact_score=0.8,
                recommendation="Remove redundant content",
                file_patterns=["*.py", "*.md"],
                session_correlation=0.7
            )
        ],
        optimization_recommendations=[{
            "priority": "high",
            "title": "Optimize Token Usage",
            "description": "Remove duplicate content",
            "actions": ["remove_duplicates", "consolidate_similar"],
            "estimated_impact": "25% efficiency improvement"
        }],
        usage_trends={"focus_score": [0.6, 0.65, 0.7, 0.75], "efficiency": [0.7, 0.72, 0.75, 0.78]},
        efficiency_trends={"token_efficiency": [0.7, 0.73, 0.75, 0.78], "waste_reduction": [0.3, 0.25, 0.22, 0.20]}
    )


@pytest.fixture
def mock_cross_session_insights(mock_correlation_insights):
    """Create comprehensive mock cross-session insights."""
    return CrossSessionInsights(
        analysis_timestamp=datetime.now(),
        sessions_analyzed=30,
        time_span_days=30,
        correlation_insights=mock_correlation_insights,
        pattern_evolution=[],
        workflow_templates=[],
        efficiency_trends={
            "overall_efficiency": [0.65, 0.70, 0.72, 0.75, 0.78],
            "focus_improvement": [0.60, 0.62, 0.65, 0.68, 0.70],
            "session_productivity": [2.0, 2.2, 2.5, 2.8, 3.0],
            "optimization_impact": [0.3, 0.35, 0.4, 0.45, 0.5]
        },
        optimization_effectiveness={"remove_duplicates": 0.8, "consolidate_similar": 0.7},
        user_adaptation_score=0.75,
        predicted_patterns=["Increasing efficiency trend", "Stable workflow patterns"],
        optimization_recommendations=[{
            "type": "workflow_optimization",
            "title": "Optimize Development Workflow",
            "description": "Create template for development workflows",
            "impact": "Medium",
            "effort": "Low",
            "potential_improvement": "20% efficiency gain"
        }],
        automation_opportunities=[{
            "type": "workflow_automation",
            "name": "Automate Duplicate Removal",
            "description": "Used frequently with high success rate",
            "automation_potential": 0.8,
            "confidence": 0.85
        }],
        session_clusters=[],
        cluster_characteristics={}
    )


# ML Mocking Fixtures
@pytest.fixture
def mock_sklearn_unavailable():
    """Mock sklearn as unavailable for testing fallback behavior."""
    with patch.dict('sys.modules', {'sklearn': None, 'sklearn.cluster': None, 'sklearn.preprocessing': None}):
        yield


@pytest.fixture  
def mock_sklearn_kmeans():
    """Mock sklearn KMeans for clustering tests."""
    mock_kmeans = Mock()
    mock_kmeans.fit_predict.return_value = [0, 1, 0, 1, 2, 2, 0, 1]  # Mock cluster labels
    mock_kmeans.cluster_centers_ = [[0.5, 0.5], [0.8, 0.3], [0.2, 0.9]]  # Mock centers
    
    with patch('context_cleaner.optimization.cross_session_analytics.KMeans', return_value=mock_kmeans):
        yield mock_kmeans


@pytest.fixture
def mock_numpy_unavailable():
    """Mock numpy as unavailable for testing fallback behavior."""
    with patch.dict('sys.modules', {'numpy': None}):
        yield


# Async Testing Utilities
@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_session():
    """Create async session context for testing."""
    # Mock async context that can be used in tests
    return AsyncMock()


# File System Mocking
@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.mkdir'), \
         patch('builtins.open', mock_open_factory()):
        yield


def mock_open_factory():
    """Factory for creating mock file operations."""
    def mock_open_func(*args, **kwargs):
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.read.return_value = '{"test": "data"}'
        mock_file.write = Mock()
        return mock_file
    return mock_open_func


# Error Injection Fixtures
@pytest.fixture
def inject_file_system_errors():
    """Inject file system errors for testing error handling."""
    def _inject_error(error_type=OSError, error_msg="File system error"):
        return patch('builtins.open', side_effect=error_type(error_msg))
    return _inject_error


@pytest.fixture
def inject_json_errors():
    """Inject JSON parsing errors for testing error handling."""
    def _inject_error():
        return patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "test", 0))
    return _inject_error


@pytest.fixture
def inject_async_errors():
    """Inject async operation errors for testing error handling."""
    def _inject_error(error_type=asyncio.TimeoutError, error_msg="Async operation failed"):
        async def failing_coroutine(*args, **kwargs):
            raise error_type(error_msg)
        return failing_coroutine
    return _inject_error


# Performance Testing Fixtures
@pytest.fixture
def large_dataset():
    """Generate large dataset for performance testing."""
    def _generate_data(size=1000):
        sessions = []
        for i in range(size):
            session = Mock()
            session.session_id = f"perf_session_{i:05d}"
            session.timestamp = datetime.now() - timedelta(hours=i)
            session.duration_minutes = 60 + (i % 180)
            session.files_accessed = [f"file_{j}.py" for j in range((i % 20) + 1)]
            session.total_tokens = 1000 + i * 10
            session.efficiency_score = 0.5 + (i % 500) / 1000.0
            session.focus_score = 0.4 + (i % 600) / 1000.0
            session.workflow_type = ["development", "testing", "debugging", "research"][i % 4]
            session.tools_used = ["read", "edit", "bash"]
            session.optimization_actions = ["remove_duplicates", "consolidate_similar"]
            sessions.append(session)
        return sessions
    return _generate_data


# Integration Testing Fixtures
@pytest.fixture
def integrated_system_components(temp_storage_dir):
    """Create integrated system with all components for integration testing."""
    dashboard = CacheEnhancedDashboard()
    recommender = IntelligentRecommendationEngine(temp_storage_dir / "recommendations")
    analytics = CrossSessionAnalyticsEngine(temp_storage_dir / "analytics")
    reports = AdvancedReportingSystem(temp_storage_dir / "reports")
    strategies = PersonalizedOptimizationEngine(temp_storage_dir / "strategies")
    
    return {
        "dashboard": dashboard,
        "recommender": recommender,
        "analytics": analytics,
        "reports": reports,
        "strategies": strategies,
        "storage_dir": temp_storage_dir
    }


# PR19 Interactive Workflow Fixtures
@pytest.fixture
def mock_context_data():
    """Mock context data for testing."""
    return {
        "current_task": "Testing optimization",
        "file_1": "Main implementation file", 
        "file_2": "Test file content",
        "todo_1": "✅ Completed task",
        "todo_2": "Pending task", 
        "notes": "Implementation notes"
    }


@pytest.fixture
def mock_interactive_session(mock_context_data):
    """Mock interactive session."""
    from unittest.mock import Mock
    from context_cleaner.optimization.interactive_workflow import InteractiveSession
    from context_cleaner.optimization.personalized_strategies import StrategyType
    
    session = Mock(spec=InteractiveSession)
    session.session_id = "test-session-001"
    session.context_data = mock_context_data
    session.selected_strategy = StrategyType.BALANCED
    return session


@pytest.fixture
def mock_manipulation_plan():
    """Mock manipulation plan."""
    from unittest.mock import Mock
    from context_cleaner.core.manipulation_engine import ManipulationPlan, ManipulationOperation
    
    mock_op = Mock(spec=ManipulationOperation)
    mock_op.operation_id = "op-001"
    mock_op.operation_type = "remove"
    mock_op.reasoning = "Remove obsolete content"
    
    plan = Mock(spec=ManipulationPlan)
    plan.plan_id = "test-plan-001"
    plan.operations = [mock_op]
    plan.total_operations = 1
    plan.estimated_total_reduction = 50
    return plan


@pytest.fixture
def mock_plan_preview():
    """Mock plan preview."""
    from unittest.mock import Mock
    from context_cleaner.core.preview_generator import PlanPreview, OperationPreview
    
    mock_op_preview = Mock(spec=OperationPreview)
    mock_op_preview.operation_id = "op-001"
    mock_op_preview.estimated_impact = {"token_reduction": 50}
    mock_op_preview.preview_text = "Remove obsolete content: 'old data'"
    
    preview = Mock(spec=PlanPreview)
    preview.operation_previews = [mock_op_preview]
    preview.total_size_reduction = 50
    preview.confidence_score = 0.85
    return preview


# Pytest markers and configuration
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def cleanup_async_tasks():
    """Clean up async tasks after each test."""
    yield
    # Cancel any remaining tasks
    try:
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        for task in tasks:
            task.cancel()
    except RuntimeError:
        # No event loop running - nothing to clean up
        pass
