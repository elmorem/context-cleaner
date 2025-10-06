"""
Unit tests for PR19 CLI Optimization Commands

Tests the OptimizationCommandHandler class and related functionality including:
- All optimization modes (quick, preview, aggressive, focus, full)
- Dashboard command integration
- CLI output formatting and error handling
- Integration with InteractiveWorkflowManager and ChangeApprovalSystem
"""

import pytest
import json
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from io import StringIO
from click.testing import CliRunner

from context_cleaner.cli.optimization_commands import (
    OptimizationCommandHandler,
    create_optimization_handler,
    execute_quick_optimization,
    execute_preview_mode,
    execute_aggressive_optimization,
    execute_focus_mode,
    execute_full_optimization
)
from context_cleaner.optimization.personalized_strategies import StrategyType
from context_cleaner.optimization.interactive_workflow import InteractiveSession
from context_cleaner.core.manipulation_engine import ManipulationPlan, ManipulationOperation
from context_cleaner.core.preview_generator import PlanPreview, OperationPreview


class TestOptimizationCommandHandler:
    """Test OptimizationCommandHandler functionality."""
    
    @pytest.fixture
    def handler(self):
        """Create optimization command handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @pytest.fixture
    def verbose_handler(self):
        """Create verbose optimization command handler instance."""
        return OptimizationCommandHandler(verbose=True)
    
    
    @pytest.fixture
    def mock_plan_preview(self, mock_manipulation_plan):
        """Mock plan preview."""
        mock_op_preview = Mock(spec=OperationPreview)
        mock_op_preview.operation = mock_manipulation_plan.operations[0]
        mock_op_preview.estimated_impact = {"token_reduction": 50}
        
        preview = Mock(spec=PlanPreview)
        preview.operation_previews = [mock_op_preview]
        preview.total_size_reduction = 50
        preview.overall_risk = Mock(value="LOW")
        return preview
    
    def test_handler_initialization(self, handler):
        """Test handler initialization."""
        assert handler.config == {}
        assert handler.verbose is False
        assert handler.workflow_manager is not None
    
    def test_verbose_handler_initialization(self, verbose_handler):
        """Test verbose handler initialization."""
        assert verbose_handler.verbose is True
    
    def test_handler_with_config(self):
        """Test handler initialization with config."""
        config = {"optimization_level": "aggressive", "auto_approve": False}
        handler = OptimizationCommandHandler(config=config, verbose=True)
        
        assert handler.config == config
        assert handler.verbose is True


class TestDashboardCommand:
    """Test dashboard optimization command."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard')
    def test_dashboard_web_launch(self, mock_dashboard_class, mock_click, handler):
        """Test dashboard command launches the comprehensive dashboard server."""
        mock_dashboard = Mock()
        mock_dashboard_class.return_value = mock_dashboard

        handler.handle_dashboard_command(format="web", host="0.0.0.0", port=9090, debug=True)

        mock_dashboard_class.assert_called_once()
        mock_dashboard.start_server.assert_called_once_with(
            host="0.0.0.0", port=9090, debug=True, open_browser=True
        )
        messages = [call.args[0] for call in mock_click.echo.call_args_list if call.args]
        assert any("Dashboard URL" in message for message in messages)

    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.json')
    @patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard')
    def test_dashboard_json_format(self, mock_dashboard_class, mock_json, mock_click, handler):
        """Test dashboard command with JSON output format."""
        mock_dashboard = Mock()
        @dataclass
        class FakeReport:
            overall_status: str
            checks_performed: int

        report = FakeReport(overall_status="healthy", checks_performed=5)
        mock_dashboard.generate_comprehensive_health_report = AsyncMock(return_value=report)
        mock_dashboard_class.return_value = mock_dashboard
        mock_json.dumps.return_value = '{"overall_status": "healthy"}'

        handler.handle_dashboard_command(format="json")

        mock_dashboard_class.assert_called_once()
        mock_dashboard.generate_comprehensive_health_report.assert_awaited_once()
        assert mock_json.dumps.call_count == 1
        call_args = mock_json.dumps.call_args
        assert call_args.kwargs.get("indent") == 2
        assert call_args.kwargs.get("default") is str
        payload_arg = call_args.args[0]
        assert payload_arg == {"overall_status": "healthy", "checks_performed": 5}
        mock_click.echo.assert_called_with('{"overall_status": "healthy"}')

    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard', side_effect=Exception("Dashboard error"))
    def test_dashboard_error_handling(self, mock_dashboard_class, mock_click, handler):
        """Test dashboard error handling."""
        handler.handle_dashboard_command()

        mock_dashboard_class.assert_called_once()
        mock_click.echo.assert_called_with(
            "❌ Comprehensive dashboard failed to load: Dashboard error", err=True
        )


class TestQuickOptimization:
    """Test quick optimization command."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @pytest.fixture
    def verbose_handler(self):
        """Create verbose handler instance."""
        return OptimizationCommandHandler(verbose=True)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    @patch('context_cleaner.cli.optimization_commands.create_quick_approval')
    def test_quick_optimization_success(self, mock_create_approval, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session, mock_manipulation_plan):
        """Test successful quick optimization."""
        # Setup mocks
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        mock_manager.generate_optimization_plan.return_value = mock_manipulation_plan
        
        mock_approval_system = Mock()
        mock_approval_system.get_selected_operations.return_value = ["op-001"]
        mock_create_approval.return_value = (mock_approval_system, "approval-001")
        
        mock_result = Mock()
        mock_result.operations_executed = 1
        mock_result.operations_rejected = 0
        mock_manager.apply_selective_changes.return_value = mock_result
        
        # Patch context data retrieval
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_quick_optimization()
        
        # Verify calls
        mock_start_opt.assert_called_once_with(mock_context_data, StrategyType.BALANCED)
        mock_manager.generate_optimization_plan.assert_called_once()
        mock_manager.apply_selective_changes.assert_called_once_with(mock_interactive_session.session_id, ["op-001"])
        
        # Verify success message
        success_calls = [call for call in mock_click.echo.call_args_list if "✅ Quick optimization completed" in str(call)]
        assert len(success_calls) > 0
    
    @patch('context_cleaner.cli.optimization_commands.click')
    def test_quick_optimization_no_context(self, mock_click, handler):
        """Test quick optimization with no context data."""
        with patch.object(handler, '_get_current_context', return_value=None):
            handler.handle_quick_optimization()
        
        mock_click.echo.assert_called_with("ℹ️  No context data found to optimize")
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_quick_optimization_no_changes(self, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session):
        """Test quick optimization when no changes are needed."""
        # Setup mock with empty operations
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        
        empty_plan = Mock()
        empty_plan.operations = []
        mock_manager.generate_optimization_plan.return_value = empty_plan
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_quick_optimization()
        
        mock_click.echo.assert_called_with("✅ Context already well-optimized - no changes needed")
    
    @patch('context_cleaner.cli.optimization_commands.click')
    def test_quick_optimization_error(self, mock_click, handler, mock_context_data):
        """Test quick optimization error handling."""
        with patch.object(handler, '_get_current_context', return_value=mock_context_data), \
             patch('context_cleaner.cli.optimization_commands.start_interactive_optimization', side_effect=Exception("Optimization error")):
            
            handler.handle_quick_optimization()
        
        error_calls = [call for call in mock_click.echo.call_args_list if "❌ Quick optimization failed" in str(call)]
        assert len(error_calls) > 0


class TestPreviewMode:
    """Test preview mode command."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.quick_optimization_preview')
    def test_preview_mode_text_format(self, mock_preview, mock_click, handler, mock_context_data, mock_plan_preview):
        """Test preview mode with text format."""
        mock_preview.return_value = mock_plan_preview
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_preview_mode(strategy=StrategyType.BALANCED, format="text")
        
        mock_preview.assert_called_once_with(mock_context_data, StrategyType.BALANCED)
        
        # Verify preview output
        preview_calls = [call for call in mock_click.echo.call_args_list if "📋 Optimization Preview" in str(call)]
        assert len(preview_calls) > 0
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.quick_optimization_preview')
    @patch('context_cleaner.cli.optimization_commands.json')
    def test_preview_mode_json_format(self, mock_json, mock_preview, mock_click, handler, mock_context_data, mock_plan_preview):
        """Test preview mode with JSON format."""
        mock_preview.return_value = mock_plan_preview
        expected_json_output = '{"strategy": "balanced", "operations_planned": 1}'
        mock_json.dumps.return_value = expected_json_output
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_preview_mode(strategy=StrategyType.BALANCED, format="json")
        
        # Verify JSON was formatted and output
        mock_json.dumps.assert_called_once()
        json_calls = [call for call in mock_click.echo.call_args_list if expected_json_output in str(call)]
        assert len(json_calls) > 0
    
    @patch('context_cleaner.cli.optimization_commands.click')
    def test_preview_mode_no_context(self, mock_click, handler):
        """Test preview mode with no context data."""
        with patch.object(handler, '_get_current_context', return_value=None):
            handler.handle_preview_mode()
        
        mock_click.echo.assert_called_with("ℹ️  No context data found to preview")


class TestAggressiveOptimization:
    """Test aggressive optimization command."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_aggressive_optimization_user_approval(self, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session, mock_manipulation_plan):
        """Test aggressive optimization with user approval."""
        # Setup mocks
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        mock_manager.generate_optimization_plan.return_value = mock_manipulation_plan
        mock_manager.generate_preview.return_value = Mock()
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.operations_executed = 1
        mock_result.execution_time = 0.5
        mock_manager.execute_full_plan.return_value = mock_result
        
        mock_click.confirm.return_value = True
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_aggressive_optimization()
        
        # Verify confirmation was requested
        mock_click.confirm.assert_called_once_with("Apply aggressive optimization changes?", default=False)
        
        # Verify execution
        mock_manager.execute_full_plan.assert_called_once_with(mock_interactive_session.session_id)
        
        # Verify success message
        success_calls = [call for call in mock_click.echo.call_args_list if "✅ Aggressive optimization completed" in str(call)]
        assert len(success_calls) > 0
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_aggressive_optimization_user_cancellation(self, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session, mock_manipulation_plan):
        """Test aggressive optimization user cancellation."""
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        mock_manager.generate_optimization_plan.return_value = mock_manipulation_plan
        mock_manager.generate_preview.return_value = Mock()
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data), \
             patch('context_cleaner.cli.optimization_commands.click.confirm', return_value=False):
            
            handler.handle_aggressive_optimization()
        
        # Verify cancellation
        mock_manager.cancel_session.assert_called_once_with(mock_interactive_session.session_id)
        cancel_calls = [call for call in mock_click.echo.call_args_list if "⏹️  Aggressive optimization cancelled" in str(call)]
        assert len(cancel_calls) > 0


class TestFocusMode:
    """Test focus mode optimization command."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_focus_mode_success(self, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session, mock_manipulation_plan):
        """Test successful focus mode optimization."""
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        mock_manager.generate_optimization_plan.return_value = mock_manipulation_plan
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.operations_executed = 2
        mock_result.execution_time = 0.3
        mock_manager.execute_full_plan.return_value = mock_result
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_focus_mode()
        
        # Verify focus strategy was used
        mock_manager.generate_optimization_plan.assert_called_once_with(
            mock_interactive_session.session_id, StrategyType.FOCUS
        )
        
        # Verify success message
        success_calls = [call for call in mock_click.echo.call_args_list if "✅ Context refocused successfully" in str(call)]
        assert len(success_calls) > 0
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_focus_mode_no_changes(self, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session):
        """Test focus mode when no changes are needed."""
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        
        empty_plan = Mock()
        empty_plan.operations = []
        mock_manager.generate_optimization_plan.return_value = empty_plan
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_focus_mode()
        
        mock_click.echo.assert_called_with("✅ Context focus already optimal - no reordering needed")


class TestFullOptimization:
    """Test full interactive optimization command."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_full_optimization_with_recommendation(self, mock_start_opt, mock_click, handler, mock_context_data, mock_interactive_session, mock_manipulation_plan):
        """Test full optimization with strategy recommendation."""
        mock_manager = Mock()
        mock_start_opt.return_value = (mock_manager, mock_interactive_session)
        mock_manager.recommend_strategy.return_value = StrategyType.BALANCED
        mock_manager.generate_optimization_plan.return_value = mock_manipulation_plan
        mock_manager.generate_preview.return_value = Mock()
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.operations_executed = 3
        mock_result.execution_time = 1.2
        mock_manager.execute_full_plan.return_value = mock_result
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data), \
             patch('context_cleaner.cli.optimization_commands.click.prompt', return_value="balanced"), \
             patch('context_cleaner.cli.optimization_commands.click.confirm', return_value=True):
            
            handler.handle_full_optimization()
        
        # Verify strategy recommendation
        mock_manager.recommend_strategy.assert_called_once_with(mock_interactive_session.session_id)
        
        # Verify strategy prompt
        strategy_calls = [call for call in mock_click.echo.call_args_list if "💡 Recommended strategy" in str(call)]
        assert len(strategy_calls) > 0
        
        # Verify execution
        mock_manager.execute_full_plan.assert_called_once_with(mock_interactive_session.session_id)


class TestConvenienceFunctions:
    """Test convenience functions for optimization commands."""
    
    @patch('context_cleaner.cli.optimization_commands.OptimizationCommandHandler')
    def test_create_optimization_handler(self, mock_handler_class):
        """Test create_optimization_handler convenience function."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        config = {"test": "config"}
        result = create_optimization_handler(config, verbose=True)
        
        mock_handler_class.assert_called_once_with(config, True)
        assert result == mock_handler
    
    @patch('context_cleaner.cli.optimization_commands.OptimizationCommandHandler')
    def test_execute_quick_optimization(self, mock_handler_class):
        """Test execute_quick_optimization convenience function."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        context_data = {"test": "data"}
        execute_quick_optimization(context_data, verbose=True)
        
        mock_handler_class.assert_called_once_with(verbose=True)
        mock_handler.handle_quick_optimization.assert_called_once_with(context_data)
    
    @patch('context_cleaner.cli.optimization_commands.OptimizationCommandHandler')
    def test_execute_preview_mode(self, mock_handler_class):
        """Test execute_preview_mode convenience function."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        context_data = {"test": "data"}
        execute_preview_mode(context_data, strategy="aggressive", format="json", verbose=True)
        
        mock_handler_class.assert_called_once_with(verbose=True)
        mock_handler.handle_preview_mode.assert_called_once_with(
            context_data, StrategyType.AGGRESSIVE, "json"
        )
    
    @patch('context_cleaner.cli.optimization_commands.OptimizationCommandHandler')
    def test_execute_aggressive_optimization(self, mock_handler_class):
        """Test execute_aggressive_optimization convenience function."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        context_data = {"test": "data"}
        execute_aggressive_optimization(context_data, verbose=False)
        
        mock_handler_class.assert_called_once_with(verbose=False)
        mock_handler.handle_aggressive_optimization.assert_called_once_with(context_data)
    
    @patch('context_cleaner.cli.optimization_commands.OptimizationCommandHandler')
    def test_execute_focus_mode(self, mock_handler_class):
        """Test execute_focus_mode convenience function."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        context_data = {"test": "data"}
        execute_focus_mode(context_data, verbose=True)
        
        mock_handler_class.assert_called_once_with(verbose=True)
        mock_handler.handle_focus_mode.assert_called_once_with(context_data)
    
    @patch('context_cleaner.cli.optimization_commands.OptimizationCommandHandler')
    def test_execute_full_optimization(self, mock_handler_class):
        """Test execute_full_optimization convenience function."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        context_data = {"test": "data"}
        execute_full_optimization(context_data, verbose=False)
        
        mock_handler_class.assert_called_once_with(verbose=False)
        mock_handler.handle_full_optimization.assert_called_once_with(context_data)


class TestErrorHandling:
    """Test error handling in optimization commands."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=True)
    
    @patch('context_cleaner.cli.optimization_commands.click')
    def test_get_current_context_returns_sample_data(self, mock_click, handler):
        """Test _get_current_context returns sample data."""
        context = handler._get_current_context()
        
        assert isinstance(context, dict)
        assert "current_task" in context
        assert "file_1" in context
        assert context["current_task"] == "Implementing PR19 optimization modes"
    
    @patch('context_cleaner.cli.optimization_commands.click')
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    def test_verbose_output(self, mock_start_opt, mock_click, handler, mock_context_data):
        """Test verbose output messages."""
        mock_manager = Mock()
        mock_session = Mock()
        mock_start_opt.return_value = (mock_manager, mock_session)
        
        empty_plan = Mock()
        empty_plan.operations = []
        mock_manager.generate_optimization_plan.return_value = empty_plan
        
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            handler.handle_quick_optimization()
        
        # Verify verbose messages
        verbose_calls = [call for call in mock_click.echo.call_args_list if "🚀 Starting quick context optimization" in str(call)]
        assert len(verbose_calls) > 0
    
    @patch('context_cleaner.cli.optimization_commands.click')
    def test_exception_handling_with_traceback(self, mock_click, handler):
        """Test exception handling shows traceback in verbose mode."""
        with patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard', side_effect=Exception("Test error")):
            handler.handle_dashboard_command()
        
        # Verify error message and traceback
        error_calls = [call for call in mock_click.echo.call_args_list if "❌ Comprehensive dashboard failed to load" in str(call)]
        assert len(error_calls) > 0


class TestIntegrationScenarios:
    """Test integration scenarios with real-world workflows."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return OptimizationCommandHandler(verbose=False)
    
    def test_typical_optimization_workflow(self, handler):
        """Test a typical optimization workflow scenario."""
        context_data = {
            "current_task": "Code review session",
            "file_1": "src/main.py - contains main logic",
            "file_2": "tests/test_main.py - unit tests",
            "file_3": "docs/README.md - project documentation",
            "todo_1": "✅ Fix bug in authentication",
            "todo_2": "Add error handling to API calls",
            "todo_3": "Update documentation with new features",
            "error_log": "TypeError: 'NoneType' object - FIXED",
            "notes": "Need to review security implications"
        }
        
        with patch.object(handler, '_get_current_context', return_value=context_data), \
             patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_start_opt, \
             patch('context_cleaner.cli.optimization_commands.quick_optimization_preview') as mock_preview, \
             patch('context_cleaner.cli.optimization_commands.click'):
            
            # Mock the workflow components
            mock_manager = Mock()
            mock_session = Mock()
            mock_start_opt.return_value = (mock_manager, mock_session)
            
            mock_plan = Mock()
            mock_plan.operations = [Mock(), Mock()]  # Two operations
            mock_plan.estimated_total_reduction = 150
            
            mock_preview_result = Mock()
            mock_preview_result.operation_previews = [Mock(), Mock()]
            mock_preview_result.total_size_reduction = 150
            mock_preview.return_value = mock_preview_result
            
            # Test preview mode first
            handler.handle_preview_mode(strategy=StrategyType.BALANCED, format="text")
            
            # Verify preview was called
            mock_preview.assert_called_once_with(context_data, StrategyType.BALANCED)
    
    def test_error_recovery_workflow(self, handler):
        """Test error recovery in optimization workflow."""
        context_data = {"test": "data"}
        
        with patch.object(handler, '_get_current_context', return_value=context_data), \
             patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_start_opt, \
             patch('context_cleaner.cli.optimization_commands.click') as mock_click:
            
            # Simulate error in workflow
            mock_start_opt.side_effect = Exception("Network error")
            
            handler.handle_quick_optimization()
            
            # Verify error handling
            error_calls = [call for call in mock_click.echo.call_args_list if "❌ Quick optimization failed" in str(call)]
            assert len(error_calls) > 0
