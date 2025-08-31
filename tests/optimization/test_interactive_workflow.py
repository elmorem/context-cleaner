"""
Unit tests for PR19 Interactive Workflow Manager

Tests the InteractiveWorkflowManager class and related functionality including:
- Session management and lifecycle
- Strategy-specific plan generation
- Preview generation and workflow control
- Integration with manipulation engine and safety framework
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from context_cleaner.optimization.interactive_workflow import (
    InteractiveWorkflowManager,
    InteractiveSession,
    WorkflowStep,
    WorkflowResult,
    UserAction,
    start_interactive_optimization,
    quick_optimization_preview
)
from context_cleaner.optimization.personalized_strategies import StrategyType
from context_cleaner.core.manipulation_engine import ManipulationPlan, ManipulationOperation


class TestInteractiveSession:
    """Test InteractiveSession data class."""
    
    def test_session_creation(self):
        """Test creating an interactive session."""
        context_data = {"file_1": "content", "todo_1": "task"}
        
        session = InteractiveSession(
            session_id="test-session-001",
            context_data=context_data,
            selected_strategy=StrategyType.BALANCED,
            manipulation_plan=None,
            preview=None,
            user_selections={},
            current_step=WorkflowStep.ANALYSIS,
            started_at=datetime.now().isoformat(),
            metadata={"verbose": True}
        )
        
        assert session.session_id == "test-session-001"
        assert session.context_data == context_data
        assert session.selected_strategy == StrategyType.BALANCED
        assert session.current_step == WorkflowStep.ANALYSIS
        assert session.metadata["verbose"] is True
        assert session.manipulation_plan is None
        assert session.preview is None
        assert session.user_selections == {}


class TestInteractiveWorkflowManager:
    """Test InteractiveWorkflowManager functionality."""
    
    @pytest.fixture
    def workflow_manager(self):
        """Create a workflow manager instance."""
        return InteractiveWorkflowManager()
    
    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for testing."""
        return {
            "current_task": "Implementing PR19",
            "file_1": "Working on workflow manager",
            "file_2": "Creating test suite",
            "todo_1": "✅ Create workflow system",
            "todo_2": "Add user confirmation",
            "error_log": "Fixed import issues",
            "notes": "Testing optimization strategies"
        }
    
    def test_manager_initialization(self, workflow_manager):
        """Test workflow manager initialization."""
        assert workflow_manager.active_sessions == {}
        assert workflow_manager.manipulation_engine is not None
        assert workflow_manager.preview_generator is not None
        assert workflow_manager.confirmation_manager is not None
        assert workflow_manager.transaction_manager is not None
    
    def test_start_interactive_optimization(self, workflow_manager, sample_context_data):
        """Test starting an interactive optimization session."""
        session = workflow_manager.start_interactive_optimization(
            sample_context_data, 
            StrategyType.BALANCED
        )
        
        assert isinstance(session, InteractiveSession)
        assert session.session_id.startswith("opt-")
        assert session.context_data == sample_context_data
        assert session.selected_strategy == StrategyType.BALANCED
        assert session.current_step == WorkflowStep.ANALYSIS
        assert session.session_id in workflow_manager.active_sessions
    
    def test_start_optimization_without_strategy(self, workflow_manager, sample_context_data):
        """Test starting optimization without specifying strategy."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        assert session.selected_strategy is None
        assert session.current_step == WorkflowStep.ANALYSIS
    
    def test_recommend_strategy(self, workflow_manager, sample_context_data):
        """Test strategy recommendation based on context."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Mock the personalization engine to return a simple strategy
        mock_strategy = Mock()
        mock_strategy.strategy_type = StrategyType.BALANCED
        
        # Mock the async method to return the strategy directly instead of a coroutine
        with patch.object(workflow_manager.personalization_engine, 'create_personalized_strategy') as mock_create:
            mock_create.return_value = mock_strategy
            
            recommended = workflow_manager.recommend_strategy(session.session_id)
        
        assert isinstance(recommended, StrategyType)
        # Should recommend based on context analysis
        assert recommended in [StrategyType.CONSERVATIVE, StrategyType.BALANCED, StrategyType.AGGRESSIVE, StrategyType.FOCUS]
    
    def test_generate_optimization_plan(self, workflow_manager, sample_context_data):
        """Test generating optimization plan."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create:
            # Mock the manipulation plan
            mock_plan = Mock(spec=ManipulationPlan)
            mock_plan.plan_id = "test-plan"
            mock_plan.operations = [Mock(spec=ManipulationOperation)]
            mock_plan.estimated_total_reduction = 100
            mock_create.return_value = mock_plan
            
            plan = workflow_manager.generate_optimization_plan(session.session_id, StrategyType.BALANCED)
            
            assert plan == mock_plan
            assert workflow_manager.active_sessions[session.session_id].manipulation_plan == mock_plan
            assert workflow_manager.active_sessions[session.session_id].current_step == WorkflowStep.PREVIEW_GENERATION
    
    def test_generate_preview(self, workflow_manager, sample_context_data):
        """Test generating optimization preview."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Create a mock manipulation plan
        mock_plan = Mock(spec=ManipulationPlan)
        mock_plan.operations = [Mock(spec=ManipulationOperation)]
        workflow_manager.active_sessions[session.session_id].manipulation_plan = mock_plan
        
        with patch.object(workflow_manager.preview_generator, 'preview_plan') as mock_preview:
            mock_preview_result = Mock()
            mock_preview_result.operation_previews = []
            mock_preview_result.total_size_reduction = 50
            mock_preview.return_value = mock_preview_result
            
            preview = workflow_manager.generate_preview(session.session_id)
            
            assert preview == mock_preview_result
            assert workflow_manager.active_sessions[session.session_id].preview == mock_preview_result
            assert workflow_manager.active_sessions[session.session_id].current_step == WorkflowStep.USER_CONFIRMATION
    
    def test_generate_preview_without_plan_fails(self, workflow_manager, sample_context_data):
        """Test that generating preview without plan raises error."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        with pytest.raises(ValueError, match="No manipulation plan available"):
            workflow_manager.generate_preview(session.session_id)
    
    def test_execute_full_plan(self, workflow_manager, sample_context_data):
        """Test executing full optimization plan."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Setup mock plan
        mock_operation = Mock(spec=ManipulationOperation)
        mock_operation.operation_id = "op-001"
        mock_plan = Mock(spec=ManipulationPlan)
        mock_plan.plan_id = "test-plan-001"
        mock_plan.operations = [mock_operation]
        workflow_manager.active_sessions[session.session_id].manipulation_plan = mock_plan
        
        with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                operations_executed=1,
                execution_time=0.5,
                error_messages=[]
            )
            
            result = workflow_manager.execute_full_plan(session.session_id)
            
            assert result.success is True
            assert result.operations_executed == 1
            assert workflow_manager.active_sessions[session.session_id].current_step == WorkflowStep.VERIFICATION
    
    def test_apply_selective_changes(self, workflow_manager, sample_context_data):
        """Test applying selective changes from user selection."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Setup mock plan with multiple operations
        mock_ops = [Mock(spec=ManipulationOperation) for _ in range(3)]
        for i, op in enumerate(mock_ops):
            op.operation_id = f"op-{i:03d}"
            op.estimated_token_impact = -10  # Negative means reduction
        
        mock_plan = Mock(spec=ManipulationPlan)
        mock_plan.plan_id = "test-plan-001"
        mock_plan.operations = mock_ops
        mock_plan.estimated_execution_time = 0.5
        mock_plan.safety_level = "SAFE"
        workflow_manager.active_sessions[session.session_id].manipulation_plan = mock_plan
        
        # Select only first two operations
        selected_ops = ["op-000", "op-001"]
        
        with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                operations_executed=2,
                operations_rejected=1,
                execution_time=0.3
            )
            
            result = workflow_manager.apply_selective_changes(session.session_id, selected_ops)
            
            assert result.success is True
            assert result.operations_executed == 2
            assert result.operations_rejected == 1
    
    def test_cancel_session(self, workflow_manager, sample_context_data):
        """Test canceling an optimization session."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        session_id = session.session_id
        
        workflow_manager.cancel_session(session_id)
        
        assert session_id not in workflow_manager.active_sessions
    
    def test_get_session_status(self, workflow_manager, sample_context_data):
        """Test getting session status."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        status = workflow_manager.get_session_status(session.session_id)
        
        assert status["session_id"] == session.session_id
        assert status["current_step"] == WorkflowStep.ANALYSIS.value
        assert status["started_at"] == session.started_at
        assert "operations_planned" in status
        assert "preview_available" in status
    
    def test_session_not_found_error(self, workflow_manager):
        """Test error handling for non-existent session."""
        with pytest.raises(ValueError, match="Session .* not found or expired"):
            workflow_manager.recommend_strategy("non-existent-session")
    
    def test_strategy_specific_plan_generation(self, workflow_manager, sample_context_data):
        """Test that different strategies generate appropriate plans."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Test balanced strategy
        with patch.object(workflow_manager, '_generate_balanced_plan') as mock_balanced:
            mock_balanced.return_value = Mock(operations=[Mock()])
            workflow_manager.generate_optimization_plan(session.session_id, StrategyType.BALANCED)
            mock_balanced.assert_called_once_with(sample_context_data)
        
        # Test aggressive strategy
        with patch.object(workflow_manager, '_generate_aggressive_plan') as mock_aggressive:
            mock_aggressive.return_value = Mock(operations=[Mock()])
            workflow_manager.generate_optimization_plan(session.session_id, StrategyType.AGGRESSIVE)
            mock_aggressive.assert_called_once_with(sample_context_data)
        
        # Test focus strategy
        with patch.object(workflow_manager, '_generate_focus_plan') as mock_focus:
            mock_focus.return_value = Mock(operations=[Mock()])
            workflow_manager.generate_optimization_plan(session.session_id, StrategyType.FOCUS)
            mock_focus.assert_called_once_with(sample_context_data)


class TestConvenienceFunctions:
    """Test convenience functions for interactive optimization."""
    
    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for testing."""
        return {
            "task": "Testing convenience functions",
            "file_1": "test_file.py",
            "todo_1": "Create tests"
        }
    
    def test_start_interactive_optimization_function(self, sample_context_data):
        """Test start_interactive_optimization convenience function."""
        manager, session = start_interactive_optimization(
            sample_context_data, 
            StrategyType.BALANCED
        )
        
        assert isinstance(manager, InteractiveWorkflowManager)
        assert isinstance(session, InteractiveSession)
        assert session.selected_strategy == StrategyType.BALANCED
        assert session.context_data == sample_context_data
    
    def test_quick_optimization_preview_function(self, sample_context_data):
        """Test quick_optimization_preview convenience function."""
        with patch('context_cleaner.optimization.interactive_workflow.InteractiveWorkflowManager') as mock_manager_class:
            # Setup mock manager and session
            mock_manager = Mock()
            mock_session = Mock()
            mock_session.session_id = "test-session"
            mock_manager.start_interactive_optimization.return_value = mock_session
            mock_manager.generate_optimization_plan.return_value = Mock(operations=[])
            mock_manager.generate_preview.return_value = Mock(operation_previews=[])
            mock_manager_class.return_value = mock_manager
            
            preview = quick_optimization_preview(sample_context_data, StrategyType.BALANCED)
            
            mock_manager.start_interactive_optimization.assert_called_once_with(
                sample_context_data, StrategyType.BALANCED
            )
            mock_manager.generate_optimization_plan.assert_called_once_with(
                mock_session.session_id, StrategyType.BALANCED
            )
            mock_manager.generate_preview.assert_called_once_with(mock_session.session_id)
            mock_manager.cancel_session.assert_called_once_with(mock_session.session_id)


class TestWorkflowSteps:
    """Test workflow step management and transitions."""
    
    def test_workflow_step_enum(self):
        """Test workflow step enumeration."""
        assert WorkflowStep.ANALYSIS.value == "analysis"
        assert WorkflowStep.STRATEGY_SELECTION.value == "strategy_selection"
        assert WorkflowStep.PREVIEW_GENERATION.value == "preview_generation"
        assert WorkflowStep.USER_CONFIRMATION.value == "user_confirmation"
        assert WorkflowStep.CHANGE_SELECTION.value == "change_selection"
        assert WorkflowStep.EXECUTION.value == "execution"
        assert WorkflowStep.VERIFICATION.value == "verification"
    
    def test_user_action_enum(self):
        """Test user action enumeration."""
        assert UserAction.APPROVE_ALL.value == "approve_all"
        assert UserAction.SELECTIVE_APPROVE.value == "selective_approve"
        assert UserAction.REJECT_ALL.value == "reject_all"
        assert UserAction.MODIFY_STRATEGY.value == "modify_strategy"
        assert UserAction.REQUEST_PREVIEW.value == "request_preview"
        assert UserAction.CANCEL.value == "cancel"


class TestErrorHandling:
    """Test error handling in interactive workflows."""
    
    @pytest.fixture
    def workflow_manager(self):
        """Create a workflow manager instance."""
        return InteractiveWorkflowManager()
    
    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for testing."""
        return {"test": "data"}
    
    def test_plan_generation_error_handling(self, workflow_manager, sample_context_data):
        """Test error handling during plan generation."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create:
            mock_create.side_effect = Exception("Plan generation failed")
            
            with pytest.raises(Exception, match="Plan generation failed"):
                workflow_manager.generate_optimization_plan(session.session_id, StrategyType.BALANCED)
    
    def test_preview_generation_error_handling(self, workflow_manager, sample_context_data):
        """Test error handling during preview generation."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Add mock plan
        mock_plan = Mock(spec=ManipulationPlan)
        workflow_manager.active_sessions[session.session_id].manipulation_plan = mock_plan
        
        with patch.object(workflow_manager.preview_generator, 'preview_plan') as mock_preview:
            mock_preview.side_effect = Exception("Preview generation failed")
            
            with pytest.raises(Exception, match="Preview generation failed"):
                workflow_manager.generate_preview(session.session_id)
    
    def test_execution_error_handling(self, workflow_manager, sample_context_data):
        """Test error handling during plan execution."""
        session = workflow_manager.start_interactive_optimization(sample_context_data)
        
        # Setup mock plan
        mock_plan = Mock(spec=ManipulationPlan)
        mock_plan.operations = [Mock()]
        workflow_manager.active_sessions[session.session_id].manipulation_plan = mock_plan
        
        with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
            mock_execute.return_value = Mock(
                success=False,
                error_messages=["Execution failed", "Rollback completed"]
            )
            
            result = workflow_manager.execute_full_plan(session.session_id)
            
            assert result.success is False
            assert len(result.error_messages) >= 1


class TestPerformance:
    """Test performance aspects of interactive workflows."""
    
    @pytest.fixture
    def workflow_manager(self):
        """Create a workflow manager instance."""
        return InteractiveWorkflowManager()
    
    def test_concurrent_sessions(self, workflow_manager):
        """Test handling multiple concurrent sessions."""
        context_data_list = [{"test": f"data_{i}"} for i in range(10)]
        
        sessions = []
        for i, context_data in enumerate(context_data_list):
            session = workflow_manager.start_interactive_optimization(
                context_data, 
                StrategyType.BALANCED
            )
            sessions.append(session)
        
        # All sessions should be tracked
        assert len(workflow_manager.active_sessions) == 10
        
        # Each session should be independent
        for session in sessions:
            assert session.session_id in workflow_manager.active_sessions
            status = workflow_manager.get_session_status(session.session_id)
            assert status["current_step"] == WorkflowStep.ANALYSIS.value
        
        # Clean up sessions
        for session in sessions:
            workflow_manager.cancel_session(session.session_id)
        
        assert len(workflow_manager.active_sessions) == 0
    
    def test_large_context_handling(self, workflow_manager):
        """Test handling large context data efficiently."""
        # Create large context data
        large_context = {}
        for i in range(1000):
            large_context[f"file_{i}"] = f"Content for file {i}" * 100
        
        session = workflow_manager.start_interactive_optimization(large_context)
        
        # Should handle large context without issues
        assert session.context_data == large_context
        assert len(session.context_data) == 1000
        
        # Status should still work efficiently
        status = workflow_manager.get_session_status(session.session_id)
        assert status["session_id"] == session.session_id