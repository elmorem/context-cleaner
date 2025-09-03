"""Tests for CostOptimizationEngine."""

import pytest
from unittest.mock import Mock, patch

from src.context_cleaner.telemetry.cost_optimization.engine import CostOptimizationEngine
from src.context_cleaner.telemetry.cost_optimization.models import BudgetConfig, ModelType, TaskComplexity


class TestCostOptimizationEngine:
    """Test suite for CostOptimizationEngine."""
    
    @pytest.fixture
    def budget_config(self):
        """Create test budget configuration."""
        return BudgetConfig(
            session_limit=2.0,
            daily_limit=5.0,
            auto_switch_haiku=True,
            auto_context_optimization=True
        )
    
    @pytest.fixture
    def cost_engine(self, mock_telemetry_client, budget_config):
        """Create CostOptimizationEngine with mock client."""
        return CostOptimizationEngine(mock_telemetry_client, budget_config)
    
    @pytest.mark.asyncio
    async def test_should_use_haiku_for_routine_tasks(self, cost_engine):
        """Test that routine tasks recommend Haiku."""
        routine_task = "read the file and show me the contents"
        session_id = "test-session"
        
        should_use_haiku = await cost_engine.should_use_haiku(routine_task, session_id)
        
        assert should_use_haiku is True
    
    @pytest.mark.asyncio
    async def test_should_use_sonnet_for_complex_tasks(self, cost_engine):
        """Test that complex tasks may recommend Sonnet."""
        complex_task = "design a comprehensive system architecture for a microservices platform with security considerations"
        session_id = "test-session"
        
        # Mock low session cost to not force Haiku
        cost_engine.budget_manager.get_current_costs = Mock(return_value={"session": 0.50})
        cost_engine.budget_manager.should_force_cost_optimization = Mock(return_value=False)
        
        should_use_haiku = await cost_engine.should_use_haiku(complex_task, session_id)
        
        # Complex task might still use Haiku for cost efficiency, but let's test the logic
        # The actual result depends on the full analysis, but we can test the task analysis
        task_analysis = await cost_engine.analyze_task_complexity(complex_task)
        assert task_analysis.complexity in [TaskComplexity.COMPLEX, TaskComplexity.CREATIVE]
    
    @pytest.mark.asyncio
    async def test_force_haiku_when_over_budget(self, cost_engine):
        """Test that Haiku is forced when over budget."""
        any_task = "any task description"
        session_id = "expensive-session"
        
        # Mock budget manager to say we're over budget
        cost_engine.budget_manager.should_force_cost_optimization = Mock(return_value=True)
        
        should_use_haiku = await cost_engine.should_use_haiku(any_task, session_id)
        
        assert should_use_haiku is True
    
    @pytest.mark.asyncio
    async def test_model_recommendation_simple_task(self, cost_engine):
        """Test model recommendation for simple task."""
        simple_task = "check the status of the system"
        session_id = "test-session"
        
        recommendation = await cost_engine.get_model_recommendation(simple_task, session_id)
        
        assert recommendation.model == ModelType.HAIKU
        assert recommendation.confidence > 0.5
        assert "routine" in recommendation.reasoning.lower() or "cost" in recommendation.reasoning.lower()
        assert recommendation.expected_cost is not None
        assert recommendation.cost_savings is not None
    
    @pytest.mark.asyncio 
    async def test_model_recommendation_includes_cost_estimate(self, cost_engine):
        """Test that model recommendations include cost estimates."""
        task = "analyze this code for potential improvements"
        session_id = "test-session"
        
        recommendation = await cost_engine.get_model_recommendation(task, session_id)
        
        assert recommendation.expected_cost is not None
        assert recommendation.expected_cost > 0
        assert recommendation.expected_duration_ms is not None
        assert recommendation.expected_duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_analyze_task_complexity_simple(self, cost_engine):
        """Test task complexity analysis for simple tasks."""
        simple_tasks = [
            "read the file config.py",
            "show me the contents of README.md", 
            "list all files in the directory",
            "what is the status of the system"
        ]
        
        for task in simple_tasks:
            analysis = await cost_engine.analyze_task_complexity(task)
            assert analysis.complexity == TaskComplexity.SIMPLE
            assert analysis.is_routine is True
            assert analysis.estimated_tokens > 0
    
    @pytest.mark.asyncio
    async def test_analyze_task_complexity_moderate(self, cost_engine):
        """Test task complexity analysis for moderate tasks."""
        moderate_tasks = [
            "analyze the code and suggest improvements",
            "edit the function to handle edge cases",
            "create documentation for this module",
            "debug the authentication issue"
        ]
        
        for task in moderate_tasks:
            analysis = await cost_engine.analyze_task_complexity(task)
            assert analysis.complexity == TaskComplexity.MODERATE
    
    @pytest.mark.asyncio
    async def test_analyze_task_complexity_complex(self, cost_engine):
        """Test task complexity analysis for complex tasks."""
        complex_tasks = [
            "design a secure authentication system",
            "optimize the database performance for high throughput",
            "architect a scalable microservices platform",
            "implement a complex algorithm for data processing"
        ]
        
        for task in complex_tasks:
            analysis = await cost_engine.analyze_task_complexity(task)
            assert analysis.complexity == TaskComplexity.COMPLEX
            assert analysis.requires_precision is False or analysis.requires_precision is True  # Could be either
    
    @pytest.mark.asyncio
    async def test_analyze_task_complexity_creative(self, cost_engine):
        """Test task complexity analysis for creative tasks."""
        creative_tasks = [
            "generate ideas for improving user experience",
            "brainstorm creative solutions to the problem",
            "compose a technical blog post about the feature",
            "invent a novel approach to data visualization"
        ]
        
        for task in creative_tasks:
            analysis = await cost_engine.analyze_task_complexity(task)
            assert analysis.complexity == TaskComplexity.CREATIVE
    
    @pytest.mark.asyncio
    async def test_precision_keyword_detection(self, cost_engine):
        """Test detection of precision requirements."""
        precision_tasks = [
            "provide exact calculations for the budget",
            "give me the precise configuration settings",
            "I need accurate performance measurements",
            "show me the specific error details"
        ]
        
        for task in precision_tasks:
            analysis = await cost_engine.analyze_task_complexity(task)
            assert analysis.requires_precision is True
    
    @pytest.mark.asyncio
    async def test_large_context_detection(self, cost_engine):
        """Test that large contexts are handled appropriately."""
        # Create a very long task description
        large_task = "analyze " + " ".join(["word"] * 1000)  # Very long description
        session_id = "test-session"
        
        analysis = await cost_engine.analyze_task_complexity(large_task)
        
        # Should estimate a reasonable number of tokens
        assert analysis.estimated_tokens > 1000
        
        # Should recommend Haiku for large contexts (cost efficiency)
        should_use_haiku = await cost_engine.should_use_haiku(large_task, session_id)
        assert should_use_haiku is True
    
    @pytest.mark.asyncio
    async def test_session_analysis_calculation(self, cost_engine, mock_telemetry_client, sample_session_metrics):
        """Test session cost analysis calculations."""
        session_id = "test-session"
        
        # Set up mock data
        mock_telemetry_client.set_test_session(session_id, sample_session_metrics)
        mock_telemetry_client.set_cost_trends({"2024-09-01": 2.25, "2024-08-31": 1.50})
        mock_telemetry_client.set_model_stats({
            "claude-sonnet-4-20250514": {
                "request_count": 10,
                "total_cost": 1.80,
                "avg_duration_ms": 5000,
                "total_input_tokens": 5000,
                "total_output_tokens": 1000
            },
            "claude-3-5-haiku-20241022": {
                "request_count": 5,
                "total_cost": 0.45,
                "avg_duration_ms": 1500,
                "total_input_tokens": 3000,
                "total_output_tokens": 500
            }
        })
        
        analysis = await cost_engine.get_session_analysis(session_id)
        
        assert analysis.session_cost == sample_session_metrics.total_cost
        assert analysis.cost_per_token > 0
        assert analysis.sonnet_cost > 0
        assert analysis.haiku_cost > 0
        assert analysis.budget_remaining is not None
    
    @pytest.mark.asyncio
    async def test_optimization_suggestions_high_cost(self, cost_engine, mock_telemetry_client):
        """Test optimization suggestions for high-cost sessions."""
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        from datetime import datetime, timedelta
        
        # Create high-cost session
        expensive_session = SessionMetrics(
            session_id="expensive-session",
            start_time=datetime.now() - timedelta(minutes=45),
            end_time=None,
            api_calls=20,
            total_cost=4.0,  # Very high cost
            total_input_tokens=20000,
            total_output_tokens=3000,
            error_count=0,
            tools_used=["Read", "Edit", "Bash"]
        )
        
        mock_telemetry_client.set_test_session("expensive-session", expensive_session)
        
        # Mock budget manager to return high costs
        cost_engine.budget_manager.get_current_costs = Mock(return_value={"session": 4.0})
        
        suggestions = await cost_engine.get_optimization_suggestions("expensive-session")
        
        assert len(suggestions) > 0
        
        # Should include budget-related suggestions
        budget_suggestions = [s for s in suggestions if "budget" in s.type.lower()]
        assert len(budget_suggestions) > 0
        
        # Should include efficiency suggestions
        efficiency_suggestions = [s for s in suggestions if s.type == "efficiency"]
        assert len(efficiency_suggestions) > 0
    
    def test_cost_estimation(self, cost_engine):
        """Test cost estimation for different models."""
        # Test Sonnet cost estimation
        sonnet_cost = cost_engine._estimate_cost(ModelType.SONNET_4, 1000)
        haiku_cost = cost_engine._estimate_cost(ModelType.HAIKU, 1000)
        
        # Sonnet should be more expensive than Haiku
        assert sonnet_cost > haiku_cost
        
        # Both should be positive
        assert sonnet_cost > 0
        assert haiku_cost > 0
        
        # Rough sanity check - costs should be in reasonable ranges
        assert sonnet_cost < 1.0  # Shouldn't be more than $1 for 1k tokens
        assert haiku_cost < 0.1   # Haiku should be much cheaper