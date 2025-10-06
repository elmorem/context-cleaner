"""
Integration tests for PR19 Optimization Modes & Interactive Workflow

Tests the complete end-to-end workflow including:
- Integration between InteractiveWorkflowManager and ChangeApprovalSystem
- CLI commands integration with optimization components
- Full optimization workflow from analysis to execution
- Integration with PR17 (ManipulationEngine) and PR18 (Safety Framework)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from context_cleaner.cli.main import main
from context_cleaner.cli.optimization_commands import OptimizationCommandHandler
from context_cleaner.optimization.interactive_workflow import (
    InteractiveWorkflowManager,
    WorkflowResult,
    start_interactive_optimization,
    quick_optimization_preview,
)
from context_cleaner.optimization.change_approval import (
    ChangeApprovalSystem,
    create_quick_approval,
    ApprovalDecision
)
from context_cleaner.optimization.personalized_strategies import StrategyType
from context_cleaner.core.manipulation_engine import ManipulationEngine, ManipulationOperation
from context_cleaner.core.preview_generator import PreviewGenerator
from context_cleaner.core.manipulation_validator import ManipulationValidator


class TestCompleteOptimizationWorkflow:
    """Test complete optimization workflow integration."""
    
    @pytest.fixture
    def real_context_data(self):
        """Realistic context data for integration testing."""
        return {
            "current_task": "Refactoring user authentication system",
            "file_1": "src/auth/login.py - Main login logic with session handling",
            "file_2": "src/auth/validators.py - Input validation functions",
            "file_3": "tests/test_auth.py - Authentication test suite",
            "file_4": "docs/auth_flow.md - Authentication flow documentation",
            "todo_1": "✅ Fix password hashing vulnerability",
            "todo_2": "Add multi-factor authentication support",
            "todo_3": "Update session timeout handling",
            "todo_4": "✅ Implement rate limiting for login attempts",
            "error_log_1": "ValueError: Invalid password format - RESOLVED",
            "error_log_2": "KeyError: 'csrf_token' - FIXED in commit abc123",
            "notes_1": "Security review completed - all issues addressed",
            "notes_2": "Performance testing shows 15% improvement",
            "old_file_1": "legacy/auth_v1.py - Deprecated authentication module",
            "old_file_2": "legacy/session_v1.py - Old session management",
            "duplicate_content": "Same authentication logic appears in multiple files",
            "conversation_1": "Discussion about security best practices",
            "conversation_2": "Code review feedback and implementation notes"
        }
    
    @pytest.fixture
    def workflow_manager(self):
        """Create workflow manager for integration testing."""
        manager = InteractiveWorkflowManager()
        # Ensure configuration attributes exist even if implementation defers initialization
        manager.max_active_sessions = getattr(manager, "max_active_sessions", 10)
        manager.auto_cleanup_sessions = False
        return manager
    
    @pytest.fixture
    def approval_system(self):
        """Create approval system for integration testing."""
        return ChangeApprovalSystem()
    
    def test_end_to_end_workflow_balanced_strategy(self, workflow_manager, real_context_data):
        """Test complete workflow with balanced strategy."""
        # Start interactive optimization
        session = workflow_manager.start_interactive_optimization(
            real_context_data,
            StrategyType.BALANCED
        )
        
        assert session is not None
        assert session.context_data == real_context_data
        assert session.selected_strategy == StrategyType.BALANCED
        
        # Get strategy recommendation
        recommended_strategy = workflow_manager.recommend_strategy(session.session_id)
        assert recommended_strategy in [StrategyType.CONSERVATIVE, StrategyType.BALANCED, StrategyType.AGGRESSIVE, StrategyType.FOCUS]
        
        # Generate optimization plan (will create mocked components)
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create_plan:
            # Create realistic mock operations
            mock_operations = [
                ManipulationOperation(
                    operation_id="op-001",
                    operation_type="remove",
                    target_keys=["old_file_1", "old_file_2"],
                    operation_data={"reason": "legacy clean-up"},
                    estimated_token_impact=-200,
                    confidence_score=0.9,
                    reasoning="Remove deprecated legacy files",
                    requires_confirmation=False,
                ),
                ManipulationOperation(
                    operation_id="op-002",
                    operation_type="consolidate",
                    target_keys=["duplicate_content"],
                    operation_data={"merge_target": "file_1"},
                    estimated_token_impact=-150,
                    confidence_score=0.8,
                    reasoning="Consolidate duplicate authentication logic",
                    requires_confirmation=True,
                ),
                ManipulationOperation(
                    operation_id="op-003",
                    operation_type="reorder",
                    target_keys=["todo_2", "todo_3"],
                    operation_data={"priority": "high"},
                    estimated_token_impact=-50,
                    confidence_score=0.95,
                    reasoning="Prioritize current authentication tasks",
                    requires_confirmation=False,
                ),
            ]
            
            mock_plan = Mock()
            mock_plan.operations = mock_operations
            mock_plan.estimated_total_reduction = 400
            mock_plan.plan_id = "plan-balanced"
            mock_plan.estimated_execution_time = 1.0
            mock_plan.safety_level = "medium"
            mock_create_plan.return_value = mock_plan
            
            plan = workflow_manager.generate_optimization_plan(session.session_id, StrategyType.BALANCED)
            
            assert plan == mock_plan
            assert len(plan.operations) == 3
            assert workflow_manager.active_sessions[session.session_id].manipulation_plan == mock_plan
        
        # Generate preview
        with patch.object(workflow_manager.preview_generator, 'preview_plan') as mock_preview:
            mock_preview_result = Mock()
            mock_preview_result.operation_previews = [
                Mock(operation=op, estimated_impact={"token_reduction": abs(op.estimated_token_impact)})
                for op in mock_operations
            ]
            mock_preview_result.total_size_reduction = 400
            mock_preview_result.overall_risk = Mock(value="MEDIUM")
            mock_preview.return_value = mock_preview_result
            
            preview = workflow_manager.generate_preview(session.session_id)
            
            assert preview == mock_preview_result
            assert len(preview.operation_previews) == 3
        
        # Test selective approval integration
        approval_system = ChangeApprovalSystem()
        approval_id = approval_system.create_approval_session(plan)
        
        # User approves high-confidence operations only
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE, "Safe removal")
        approval_system.select_operation(approval_id, "op-002", ApprovalDecision.DEFER, "Need more review")
        approval_system.select_operation(approval_id, "op-003", ApprovalDecision.APPROVE, "Safe reordering")
        
        selected_operations = approval_system.get_selected_operations(approval_id)
        assert len(selected_operations) == 2
        assert "op-001" in selected_operations
        assert "op-003" in selected_operations
        
        # Execute selected changes
        with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
            with patch.object(
                workflow_manager,
                '_execute_plan_with_transaction',
                return_value=WorkflowResult(
                    workflow_id="wf-123",
                    success=True,
                    strategy_used=StrategyType.BALANCED,
                    operations_planned=len(selected_operations),
                    operations_executed=len(selected_operations),
                    operations_rejected=0,
                    execution_time=0.5,
                    user_satisfaction=None,
                    changes_applied=selected_operations,
                    error_messages=[],
                    created_at=datetime.now().isoformat(),
                ),
            ):
                mock_execute.return_value = Mock(
                    success=True,
                    operations_executed=2,
                    operations_rejected=1,
                    execution_time=0.8
                )

                result = workflow_manager.apply_selective_changes(session.session_id, selected_operations)

                assert result.success is True
                assert result.operations_executed == 2
                assert result.operations_rejected == 1
    
    def test_aggressive_optimization_workflow(self, workflow_manager, real_context_data):
        """Test aggressive optimization workflow with full execution."""
        session = workflow_manager.start_interactive_optimization(
            real_context_data,
            StrategyType.AGGRESSIVE
        )
        
        # Mock aggressive plan with more operations
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create_plan:
            aggressive_operations = [
                ManipulationOperation(
                    operation_id=f"aggressive-op-{i:03d}",
                    operation_type=["remove", "consolidate", "summarize"][i % 3],
                    target_keys=[f"target-{i}"] ,
                    operation_data={"detail": f"op-{i}"},
                    estimated_token_impact=-(50 + i * 20),
                    confidence_score=0.7 + (i % 3) * 0.1,
                    reasoning=f"Aggressive optimization operation {i}",
                    requires_confirmation=i % 2 == 0,
                )
                for i in range(8)
            ]
            
            mock_plan = Mock()
            mock_plan.operations = aggressive_operations
            mock_plan.estimated_total_reduction = 1000
            mock_plan.plan_id = "plan-aggressive"
            mock_plan.estimated_execution_time = 2.0
            mock_plan.safety_level = "high"
            mock_create_plan.return_value = mock_plan
            
            plan = workflow_manager.generate_optimization_plan(session.session_id, StrategyType.AGGRESSIVE)
            
            assert len(plan.operations) == 8
            
            # Test full plan execution
            with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
                with patch.object(
                    workflow_manager,
                    '_execute_plan_with_transaction',
                    return_value=WorkflowResult(
                        workflow_id="wf-aggressive",
                        success=True,
                        strategy_used=StrategyType.AGGRESSIVE,
                        operations_planned=len(aggressive_operations),
                        operations_executed=len(aggressive_operations),
                        operations_rejected=0,
                        execution_time=2.5,
                        user_satisfaction=None,
                        changes_applied=[op.operation_id for op in aggressive_operations],
                        error_messages=[],
                        created_at=datetime.now().isoformat(),
                    ),
                ):
                    mock_execute.return_value = Mock(
                        success=True,
                        operations_executed=8,
                        operations_rejected=0,
                        execution_time=2.5,
                        error_messages=[]
                    )

                    result = workflow_manager.execute_full_plan(session.session_id)
                    
                    assert result.success is True
                    assert result.operations_executed == 8
    
    def test_focus_mode_workflow(self, workflow_manager, real_context_data):
        """Test focus mode workflow that only reorders without removing content."""
        session = workflow_manager.start_interactive_optimization(
            real_context_data,
            StrategyType.FOCUS
        )
        
        # Focus mode should generate only reordering operations
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create_plan:
            focus_operations = [
                Mock(operation_id="focus-op-001",
                     operation_type="reorder",
                     reasoning="Move current tasks to top priority",
                     confidence_score=0.95,
                     requires_confirmation=False,
                     estimated_token_impact=0),  # No content removal
                Mock(operation_id="focus-op-002", 
                     operation_type="reorder",
                     reasoning="Group authentication-related items",
                     confidence_score=0.9,
                     requires_confirmation=False,
                     estimated_token_impact=0)
            ]
            
            mock_plan = Mock()
            mock_plan.operations = focus_operations
            mock_plan.estimated_total_reduction = 0  # Focus mode preserves content
            mock_create_plan.return_value = mock_plan
            
            plan = workflow_manager.generate_optimization_plan(session.session_id, StrategyType.FOCUS)
            
            # Verify focus mode characteristics
            assert all(op.operation_type == "reorder" for op in plan.operations)
            assert all(op.estimated_token_impact == 0 for op in plan.operations)
            assert plan.estimated_total_reduction == 0
            
            # Focus mode should execute automatically (low risk)
            with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
                mock_execute.return_value = Mock(
                    success=True,
                    operations_executed=2,
                    operations_rejected=0,
                    execution_time=0.3
                )
                
                result = workflow_manager.execute_full_plan(session.session_id)
                
                assert result.success is True
                assert result.operations_executed == 2
    
    def test_error_handling_and_rollback(self, workflow_manager, real_context_data):
        """Test error handling and rollback functionality."""
        session = workflow_manager.start_interactive_optimization(
            real_context_data,
            StrategyType.BALANCED
        )
        
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create_plan:
            mock_operations = [
                Mock(operation_id="error-op-001", operation_type="remove",
                     reasoning="This will fail", confidence_score=0.5)
            ]
            
            mock_plan = Mock()
            mock_plan.operations = mock_operations
            mock_create_plan.return_value = mock_plan
            
            workflow_manager.generate_optimization_plan(session.session_id)
            
            # Simulate execution failure
            with patch.object(workflow_manager.manipulation_engine, 'execute_plan') as mock_execute:
                mock_execute.return_value = Mock(
                    success=False,
                    operations_executed=0,
                    operations_rejected=1,
                    error_messages=["Operation failed validation", "Rollback completed successfully"]
                )
                
                result = workflow_manager.execute_full_plan(session.session_id)
                
                assert result.success is False
                assert len(result.error_messages) == 2
                assert "Rollback completed" in result.error_messages[1]


class TestCLIIntegration:
    """Test CLI integration with optimization workflow."""
    
    @pytest.fixture
    def cli_runner(self):
        """Create CLI test runner."""
        return CliRunner()
    
    def test_preview_command_integration(self, cli_runner):
        """Test CLI preview command integration."""
        with patch('context_cleaner.cli.optimization_commands.quick_optimization_preview') as mock_preview:
            # Mock preview result
            mock_operation = Mock()
            mock_operation.operation_id = "cli-op-001"
            mock_operation.operation_type = "remove"
            mock_operation.reasoning = "Remove outdated documentation"
            mock_operation.confidence_score = 0.85
            
            mock_op_preview = Mock()
            mock_op_preview.operation = mock_operation
            mock_op_preview.estimated_impact = {"token_reduction": 100}
            
            mock_preview_result = Mock()
            mock_preview_result.operation_previews = [mock_op_preview]
            mock_preview_result.total_size_reduction = 100
            mock_preview_result.overall_risk = Mock(value="LOW")
            
            mock_preview.return_value = mock_preview_result
            
            result = cli_runner.invoke(main, ['optimize', '--preview'])
            
            assert result.exit_code == 0
            assert "📋 Optimization Preview" in result.output
            assert "Operations Planned: 1" in result.output
            assert "REMOVE: Remove outdated documentation" in result.output
    
    def test_quick_command_integration(self, cli_runner):
        """Test CLI quick command integration."""
        with patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_start_opt, \
             patch('context_cleaner.cli.optimization_commands.create_quick_approval') as mock_create_approval:
            
            # Setup mocks
            mock_manager = Mock()
            mock_session = Mock(session_id="cli-session-001")
            mock_start_opt.return_value = (mock_manager, mock_session)
            
            mock_plan = Mock()
            mock_plan.operations = []  # No operations found
            mock_manager.generate_optimization_plan.return_value = mock_plan
            
            result = cli_runner.invoke(main, ['optimize', '--quick'])
            
            assert result.exit_code == 0
            assert "✅ Context already well-optimized - no changes needed" in result.output
    
    def test_dashboard_command_integration(self, cli_runner):
        """Test CLI dashboard command integration."""
        with patch('context_cleaner.cli.optimization_commands.BasicDashboard') as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.get_formatted_output.return_value = """
🎯 CONTEXT HEALTH DASHBOARD
========================================
🟢 Health: Good (75/100)
➡️ Trend: Improving

💡 RECOMMENDATIONS
--------------------
  ✅ Context is well-organized
  📋 Consider minor cleanup
            """.strip()
            
            mock_dashboard_class.return_value = mock_dashboard
            
            result = cli_runner.invoke(main, ['optimize', '--dashboard'])
            
            assert result.exit_code == 0
            assert "🎯 CONTEXT HEALTH DASHBOARD" in result.output
            assert "Health: Good (75/100)" in result.output
    
    def test_focus_command_integration(self, cli_runner):
        """Test CLI focus command integration."""
        with patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_start_opt:
            mock_manager = Mock()
            mock_session = Mock(session_id="focus-session-001")
            mock_start_opt.return_value = (mock_manager, mock_session)
            
            mock_plan = Mock()
            mock_plan.operations = [Mock()]  # One reordering operation
            mock_manager.generate_optimization_plan.return_value = mock_plan
            
            mock_result = Mock()
            mock_result.success = True
            mock_result.operations_executed = 1
            mock_result.execution_time = 0.2
            mock_manager.execute_full_plan.return_value = mock_result
            
            result = cli_runner.invoke(main, ['optimize', '--focus'])
            
            assert result.exit_code == 0
            assert "✅ Context refocused successfully" in result.output
            assert "1 reordering operations applied" in result.output
            assert "No content removed (focus mode)" in result.output


class TestAdvancedIntegrationScenarios:
    """Test advanced integration scenarios and edge cases."""
    
    def test_concurrent_optimization_sessions(self):
        """Test handling multiple concurrent optimization sessions."""
        workflow_manager = InteractiveWorkflowManager()
        
        # Create multiple concurrent sessions
        sessions = []
        context_datasets = [
            {"task": f"Task {i}", "file": f"file_{i}.py", "priority": "high" if i % 2 == 0 else "low"}
            for i in range(5)
        ]
        
        for i, context_data in enumerate(context_datasets):
            session = workflow_manager.start_interactive_optimization(
                context_data,
                [StrategyType.CONSERVATIVE, StrategyType.BALANCED, StrategyType.AGGRESSIVE][i % 3]
            )
            sessions.append(session)
        
        # All sessions should be independent
        assert len(workflow_manager.active_sessions) == 5
        
        for i, session in enumerate(sessions):
            status = workflow_manager.get_session_status(session.session_id)
            assert status["session_id"] == session.session_id
            assert "task" in session.context_data
            assert session.context_data["task"] == f"Task {i}"
        
        # Clean up
        for session in sessions:
            workflow_manager.cancel_session(session.session_id)
        
        assert len(workflow_manager.active_sessions) == 0
    
    def test_large_context_optimization(self):
        """Test optimization with very large context data."""
        workflow_manager = InteractiveWorkflowManager()
        
        # Create large context data
        large_context = {}
        for i in range(500):  # 500 context items
            large_context[f"file_{i:03d}"] = f"Content for file {i}" + " data" * 50
            if i % 10 == 0:
                large_context[f"todo_{i//10}"] = f"Task {i//10}: Complete implementation"
            if i % 20 == 0:
                large_context[f"error_{i//20}"] = f"Error {i//20}: Fixed in recent commit"
        
        session = workflow_manager.start_interactive_optimization(
            large_context,
            StrategyType.AGGRESSIVE
        )
        
        assert len(session.context_data) == 500 + 50 + 25  # Files + todos + errors
        
        # Should handle large context efficiently
        status = workflow_manager.get_session_status(session.session_id)
        assert status["session_id"] == session.session_id
        assert "has_plan" in status
        assert "has_preview" in status
    
    def test_cross_component_integration(self):
        """Test integration across all PR19 components."""
        # Test the complete pipeline: CLI -> WorkflowManager -> ApprovalSystem -> Execution
        
        handler = OptimizationCommandHandler(verbose=False)
        context_data = {
            "main_file": "src/integration_test.py",
            "test_file": "tests/test_integration.py", 
            "todo_1": "✅ Implement cross-component integration",
            "todo_2": "Add comprehensive error handling",
            "old_notes": "Legacy implementation notes - can be removed",
            "duplicate_config": "Configuration appears in multiple places"
        }
        
        with patch.object(handler, '_get_current_context', return_value=context_data), \
             patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_start_opt, \
             patch('context_cleaner.cli.optimization_commands.create_quick_approval') as mock_create_approval:
            
            # Setup complete workflow mocks
            mock_manager = Mock()
            mock_session = Mock(session_id="integration-test-001")
            mock_start_opt.return_value = (mock_manager, mock_session)
            
            # Create realistic operations
            operations = [
                Mock(operation_id="int-op-001", operation_type="remove",
                     confidence_score=0.9, requires_confirmation=False,
                     estimated_token_impact=-100),
                Mock(operation_id="int-op-002", operation_type="consolidate", 
                     confidence_score=0.8, requires_confirmation=True,
                     estimated_token_impact=-150)
            ]
            
            mock_plan = Mock()
            mock_plan.operations = operations
            mock_manager.generate_optimization_plan.return_value = mock_plan
            
            # Setup approval system
            mock_approval_system = Mock()
            mock_approval_system.get_selected_operations.return_value = ["int-op-001"]  # Only safe operation
            mock_create_approval.return_value = (mock_approval_system, "approval-int-001")
            
            # Setup execution result
            mock_result = Mock()
            mock_result.operations_executed = 1
            mock_result.operations_rejected = 1
            mock_manager.apply_selective_changes.return_value = mock_result
            
            # Execute quick optimization
            handler.handle_quick_optimization(context_data)
            
            # Verify complete workflow was executed
            mock_start_opt.assert_called_once_with(context_data, StrategyType.BALANCED)
            mock_manager.generate_optimization_plan.assert_called_once()
            mock_create_approval.assert_called_once_with(operations, auto_approve_safe=True)
            mock_manager.apply_selective_changes.assert_called_once_with(
                mock_session.session_id, ["int-op-001"]
            )
    
    def test_error_propagation_across_components(self):
        """Test error propagation across integrated components."""
        handler = OptimizationCommandHandler(verbose=True)
        
        with patch.object(handler, '_get_current_context', return_value={"test": "data"}), \
             patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_start_opt:
            
            # Simulate error in workflow manager
            mock_start_opt.side_effect = ValueError("Integration error: Component unavailable")
            
            with patch('context_cleaner.cli.optimization_commands.click') as mock_click:
                handler.handle_quick_optimization()
                
                # Verify error was caught and reported properly
                error_calls = [call for call in mock_click.echo.call_args_list 
                             if "❌ Quick optimization failed" in str(call)]
                assert len(error_calls) > 0
                
                # In verbose mode, should also show traceback
                traceback_calls = [call for call in mock_click.echo.call_args_list 
                                 if "Integration error" in str(call)]
                assert len(traceback_calls) > 0


class TestPerformanceIntegration:
    """Test performance aspects of integrated workflow."""
    
    def test_optimization_performance_with_real_data(self):
        """Test optimization performance with realistic data volumes."""
        import time
        
        workflow_manager = InteractiveWorkflowManager()
        
        # Create realistic context size (similar to actual usage)
        context_data = {}
        
        # Add various types of content
        for i in range(100):
            context_data[f"file_{i:03d}"] = f"File content {i}" + " line" * 20
        
        for i in range(50):
            context_data[f"todo_{i:02d}"] = f"Task {i}: {'✅' if i % 3 == 0 else ''} Task description"
        
        for i in range(25):
            context_data[f"error_{i:02d}"] = f"Error {i}: {'FIXED' if i % 2 == 0 else 'PENDING'} - Details"
        
        for i in range(10):
            context_data[f"conversation_{i}"] = f"Discussion about feature {i}" + " detail" * 30
        
        # Measure session creation performance
        start_time = time.time()
        session = workflow_manager.start_interactive_optimization(context_data, StrategyType.BALANCED)
        session_time = time.time() - start_time
        
        # Session creation should be fast (< 0.1 seconds)
        assert session_time < 0.1
        assert len(session.context_data) == 185  # 100 + 50 + 25 + 10
        
        # Measure status retrieval performance
        start_time = time.time()
        status = workflow_manager.get_session_status(session.session_id)
        status_time = time.time() - start_time
        
        # Status retrieval should be very fast (< 0.01 seconds)
        assert status_time < 0.01
        assert status["session_id"] == session.session_id
    
    def test_approval_system_performance(self):
        """Test approval system performance with many operations."""
        approval_system = ChangeApprovalSystem()
        
        # Create large number of mock operations
        operations = []
        for i in range(200):
            op = Mock()
            op.operation_id = f"perf-op-{i:03d}"
            op.operation_type = ["remove", "consolidate", "reorder", "summarize"][i % 4]
            op.confidence_score = 0.5 + (i % 50) / 100.0
            op.requires_confirmation = i % 5 == 0
            operations.append(op)
        
        # Create mock plan
        plan = Mock()
        plan.operations = operations
        plan.total_operations = len(operations)
        
        import time
        
        # Measure approval session creation
        start_time = time.time()
        approval_id = approval_system.create_approval_session(plan)
        creation_time = time.time() - start_time
        
        # Should handle large operation sets efficiently (< 0.05 seconds)
        assert creation_time < 0.05
        
        # Measure categorization performance
        start_time = time.time()
        categorized = approval_system.categorize_operations(operations)
        categorization_time = time.time() - start_time
        
        # Categorization should be fast (< 0.02 seconds)
        assert categorization_time < 0.02
        
        # Verify all operations were categorized
        total_categorized = sum(len(ops) for ops in categorized.values())
        assert total_categorized == 200
        
        # Measure batch approval performance
        removal_ops = [op.operation_id for op in operations if op.operation_type == "remove"]
        
        start_time = time.time()
        approval_system.select_by_category(
            approval_id, 
            ChangeApprovalSystem()._get_operation_category(operations[0]),
            ApprovalDecision.APPROVE,
            removal_ops
        )
        batch_approval_time = time.time() - start_time
        
        # Batch approval should be efficient (< 0.1 seconds)
        assert batch_approval_time < 0.1


class TestBackwardCompatibility:
    """Test backward compatibility with existing systems."""
    
    def test_integration_with_existing_analyzers(self):
        """Test integration with existing context analysis components."""
        # Verify that PR19 components work with existing analysis results
        from context_cleaner.core.context_analyzer import ContextAnalysisResult
        from context_cleaner.core.focus_scorer import FocusMetrics
        from context_cleaner.core.redundancy_detector import RedundancyReport
        from context_cleaner.core.recency_analyzer import RecencyReport  
        from context_cleaner.core.priority_analyzer import PriorityReport
        
        workflow_manager = InteractiveWorkflowManager()
        
        # Create analysis result using existing components
        focus_metrics = Mock(spec=FocusMetrics)
        redundancy_report = Mock(spec=RedundancyReport)
        recency_report = Mock(spec=RecencyReport)
        priority_report = Mock(spec=PriorityReport)
        
        analysis_result = Mock(spec=ContextAnalysisResult)
        analysis_result.focus_metrics = focus_metrics
        analysis_result.redundancy_report = redundancy_report
        analysis_result.recency_report = recency_report
        analysis_result.priority_report = priority_report
        analysis_result.health_score = 75
        
        context_data = {"integration": "test"}
        
        # Should work with existing analysis results
        session = workflow_manager.start_interactive_optimization(context_data)
        
        with patch.object(workflow_manager.manipulation_engine, 'create_manipulation_plan') as mock_create:
            mock_create.return_value = Mock(operations=[], estimated_total_reduction=0)
            
            # Should accept existing analysis results
            plan = workflow_manager.generate_optimization_plan(session.session_id)
            
            # Verify the manipulation engine was called with proper analysis
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert len(call_args[0]) >= 2  # context_data and analysis_result
    
    def test_cli_backward_compatibility(self):
        """Test that CLI changes don't break existing functionality."""
        runner = CliRunner()
        
        # Existing CLI commands should still work
        with patch('context_cleaner.cli.optimization_commands.BasicDashboard') as mock_dashboard:
            mock_dashboard.return_value.get_formatted_output.return_value = "Dashboard OK"
            
            # Test existing dashboard functionality still works
            result = runner.invoke(main, ['optimize', '--dashboard'])
            assert result.exit_code == 0
        
        # Test that new commands are additive, not replacing existing ones
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'optimize' in result.output
        
        # Test optimize command help
        result = runner.invoke(main, ['optimize', '--help'])
        assert result.exit_code == 0
        assert '--quick' in result.output
        assert '--preview' in result.output
        assert '--aggressive' in result.output
        assert '--focus' in result.output
        assert '--dashboard' in result.output
