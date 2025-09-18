"""
Test Suite for PR20: CLI Integration & Analytics

Tests the enhanced CLI commands, effectiveness tracking,
and analytics integration functionality.
"""

import json
import pytest
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from click.testing import CliRunner

from context_cleaner.cli.analytics_commands import AnalyticsCommandHandler
from context_cleaner.cli.optimization_commands import OptimizationCommandHandler
from context_cleaner.analytics.effectiveness_tracker import (
    EffectivenessTracker,
    OptimizationOutcome,
    EffectivenessMetrics,
    OptimizationSession
)
from context_cleaner.telemetry.context_rot.config import ApplicationConfig


class TestAnalyticsCommandHandler:
    """Test the enhanced analytics CLI command handler."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_config(self, temp_dir):
        """Create mock configuration."""
        config = Mock(spec=ApplicationConfig)
        config.data_directory = str(temp_dir)
        config.dashboard = Mock()
        config.dashboard.port = 8080
        config.dashboard.host = "localhost"
        return config
    
    @pytest.fixture
    def handler(self, mock_config):
        """Create analytics command handler."""
        return AnalyticsCommandHandler(mock_config, verbose=True)
    
    def test_health_check_command_basic(self, handler, capsys):
        """Test basic health check functionality."""
        handler.handle_health_check_command(detailed=False, fix_issues=False, format="text")
        
        captured = capsys.readouterr()
        assert "SYSTEM HEALTH" in captured.out
        assert any(status in captured.out.upper() for status in ["HEALTHY", "WARNING", "UNHEALTHY"])
        assert "Checks performed:" in captured.out
    
    def test_health_check_command_detailed(self, handler, capsys):
        """Test detailed health check functionality."""
        handler.handle_health_check_command(detailed=True, fix_issues=False, format="text")
        
        captured = capsys.readouterr()
        assert "DETAILED RESULTS" in captured.out
        assert "data_directory" in captured.out
        assert "configuration" in captured.out
    
    def test_health_check_command_json_format(self, handler, capsys):
        """Test health check with JSON output format."""
        handler.handle_health_check_command(detailed=False, fix_issues=False, format="json")
        
        captured = capsys.readouterr()
        health_data = json.loads(captured.out)
        
        assert "overall_status" in health_data
        assert "checks_performed" in health_data
        assert "issues_found" in health_data
        assert "checks" in health_data
    
    def test_health_check_with_fixes(self, handler, temp_dir, capsys):
        """Test health check with automatic issue fixes."""
        # Remove data directory to create an issue
        import shutil
        shutil.rmtree(temp_dir)
        
        handler.handle_health_check_command(detailed=False, fix_issues=True, format="text")
        
        captured = capsys.readouterr()
        assert "Fixed" in captured.out or "Failed to fix" in captured.out
    
    @patch('context_cleaner.cli.analytics_commands.AnalyticsCommandHandler._gather_comprehensive_analytics')
    def test_export_analytics_command(self, mock_gather, handler, temp_dir, capsys):
        """Test analytics export functionality."""
        # Mock comprehensive analytics data
        mock_gather.return_value = {
            "export_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_sessions": 5
            },
            "effectiveness_data": {"total_sessions": 5},
            "system_health": {"overall_status": "healthy"}
        }
        
        output_file = temp_dir / "test_export.json"
        handler.handle_export_analytics_command(
            output_path=str(output_file),
            days=30,
            include_sessions=True,
            format="json"
        )
        
        # Verify file was created
        assert output_file.exists()
        
        # Verify content
        with open(output_file, 'r') as f:
            export_data = json.load(f)
        
        assert "export_metadata" in export_data
        assert "effectiveness_data" in export_data
        assert "system_health" in export_data
        
        captured = capsys.readouterr()
        assert "Analytics data exported to:" in captured.out
    
    def test_export_analytics_auto_filename(self, handler, temp_dir, capsys):
        """Test analytics export with automatic filename generation."""
        with patch('context_cleaner.cli.analytics_commands.AnalyticsCommandHandler._gather_comprehensive_analytics') as mock_gather:
            mock_gather.return_value = {"test": "data"}
            
            # Change to temp directory for auto-generated filename
            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                handler.handle_export_analytics_command(
                    output_path=None,
                    days=7,
                    include_sessions=False,
                    format="json"
                )
                
                captured = capsys.readouterr()
                assert "Analytics data exported to:" in captured.out
                
                # Verify a file was created with timestamp pattern
                json_files = list(temp_dir.glob("context_cleaner_analytics_*.json"))
                assert len(json_files) > 0
                
            finally:
                os.chdir(original_cwd)
    
    def test_effectiveness_stats_command(self, handler, capsys):
        """Test effectiveness statistics display."""
        # Mock some effectiveness data
        with patch.object(handler.effectiveness_tracker, 'get_effectiveness_summary') as mock_summary:
            mock_summary.return_value = {
                "total_sessions": 3,
                "period_days": 30,
                "success_rate_percentage": 85.5,
                "average_metrics": {
                    "size_reduction_percentage": 32.5,
                    "health_improvement": 12.3,
                    "focus_improvement": 8.7,
                    "user_satisfaction": 4.2
                },
                "total_impact": {
                    "total_bytes_saved": 150000,
                    "total_duplicates_removed": 25,
                    "total_stale_items_removed": 15,
                    "total_items_consolidated": 8,
                    "total_time_saved_estimate_hours": 2.5
                },
                "strategy_effectiveness": {
                    "BALANCED": {"count": 2, "success_rate": 90.0, "avg_size_reduction": 30.0, "avg_health_improvement": 10.0},
                    "AGGRESSIVE": {"count": 1, "success_rate": 80.0, "avg_size_reduction": 40.0, "avg_health_improvement": 15.0}
                }
            }
            
            handler.handle_effectiveness_stats_command(
                days=30,
                strategy=None,
                detailed=True,
                format="text"
            )
            
            captured = capsys.readouterr()
            assert "OPTIMIZATION EFFECTIVENESS REPORT" in captured.out
            assert "Total sessions: 3" in captured.out
            assert "Success rate: 85.5%" in captured.out
            assert "AVERAGE IMPROVEMENTS" in captured.out
            assert "Context size reduction: 32.5%" in captured.out
            assert "STRATEGY EFFECTIVENESS" in captured.out
    
    def test_effectiveness_stats_no_data(self, handler, capsys):
        """Test effectiveness stats when no data is available."""
        with patch.object(handler.effectiveness_tracker, 'get_effectiveness_summary') as mock_summary:
            mock_summary.return_value = {"total_sessions": 0}
            
            handler.handle_effectiveness_stats_command(days=30, format="text")
            
            captured = capsys.readouterr()
            assert "No optimization sessions found" in captured.out
    
    def test_effectiveness_stats_json_format(self, handler, capsys):
        """Test effectiveness stats with JSON output."""
        mock_data = {
            "total_sessions": 2,
            "success_rate_percentage": 100.0,
            "average_metrics": {"size_reduction_percentage": 25.0}
        }
        
        with patch.object(handler.effectiveness_tracker, 'get_effectiveness_summary') as mock_summary:
            mock_summary.return_value = mock_data
            
            handler.handle_effectiveness_stats_command(days=7, format="json")
            
            captured = capsys.readouterr()
            output_data = json.loads(captured.out)
            assert output_data["total_sessions"] == 2
            assert output_data["success_rate_percentage"] == 100.0
    
    def test_enhanced_dashboard_command(self, handler, capsys):
        """Test enhanced dashboard functionality."""
        with patch.object(handler, '_get_enhanced_dashboard_data') as mock_dashboard:
            mock_dashboard.return_value = {
                "timestamp": datetime.now().isoformat(),
                "system_health": {"overall_status": "healthy"},
                "recent_effectiveness": {
                    "total_sessions": 5, 
                    "success_rate_percentage": 90.0,
                    "average_metrics": {"size_reduction_percentage": 35.0}
                },
                "available_operations": {
                    "quick_optimization": "Fast cleanup",
                    "aggressive_optimization": "Maximum optimization"
                },
                "smart_recommendations": ["Try using Focus mode", "Enable cache integration"]
            }
            
            handler.handle_enhanced_dashboard_command(
                interactive=False,
                operations=True,
                format="text"
            )
            
            captured = capsys.readouterr()
            assert "ENHANCED CONTEXT CLEANER DASHBOARD" in captured.out
            assert "System Status:" in captured.out
            assert "AVAILABLE OPERATIONS" in captured.out
            assert "Recent success rate:" in captured.out


class TestEffectivenessTracker:
    """Test effectiveness tracking functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def tracker(self, temp_dir):
        """Create effectiveness tracker."""
        return EffectivenessTracker(temp_dir)
    
    @pytest.fixture
    def sample_context_data(self):
        """Create sample context data."""
        return {
            "content": "Sample context content for testing",
            "files": ["file1.py", "file2.py"],
            "size": 1000
        }
    
    def test_start_optimization_tracking(self, tracker, sample_context_data):
        """Test starting optimization tracking."""
        session_id = tracker.start_optimization_tracking(
            context_data=sample_context_data,
            strategy_type="BALANCED",
            context_source="test"
        )
        
        assert session_id.startswith("opt_")
        assert len(session_id) > 10  # Should have timestamp
        
        # Verify initial data was stored
        initial_data = tracker._load_initial_metrics(session_id)
        assert initial_data is not None
        assert initial_data["strategy_type"] == "BALANCED"
        assert initial_data["context_source"] == "test"
    
    def test_complete_optimization_tracking(self, tracker, sample_context_data):
        """Test completing optimization tracking."""
        # Start tracking
        session_id = tracker.start_optimization_tracking(
            sample_context_data, "BALANCED", "test"
        )
        
        # Simulate some time passing
        time.sleep(0.1)
        
        # Complete tracking
        optimized_context = {"content": "Optimized content", "size": 800}
        session = tracker.complete_optimization_tracking(
            session_id=session_id,
            optimized_context=optimized_context,
            outcome=OptimizationOutcome.SUCCESS,
            operations_approved=5,
            operations_rejected=2,
            operations_modified=1,
            total_operations=8,
            session_time=1.5,
            user_rating=4,
            user_feedback="Good optimization"
        )
        
        assert isinstance(session, OptimizationSession)
        assert session.session_id == session_id
        assert session.outcome == OptimizationOutcome.SUCCESS
        assert session.operations_approved == 5
        assert session.operations_rejected == 2
        assert session.metrics.user_satisfaction_rating == 4
        assert session.metrics.user_feedback == "Good optimization"
    
    def test_effectiveness_summary_no_data(self, tracker):
        """Test effectiveness summary when no sessions exist."""
        summary = tracker.get_effectiveness_summary(30)
        
        assert summary["total_sessions"] == 0
        assert "message" in summary
        assert "No optimization sessions found" in summary["message"]
    
    def test_effectiveness_summary_with_data(self, tracker, sample_context_data):
        """Test effectiveness summary with session data."""
        # Create a few test sessions
        for i in range(3):
            session_id = tracker.start_optimization_tracking(
                sample_context_data, "BALANCED", "test"
            )
            
            tracker.complete_optimization_tracking(
                session_id=session_id,
                optimized_context={"size": 800},
                outcome=OptimizationOutcome.SUCCESS,
                operations_approved=3 + i,
                operations_rejected=1,
                operations_modified=0,
                total_operations=4 + i,
                session_time=1.0 + i * 0.5,
                user_rating=4 + (i % 2)  # Ratings of 4, 5, 4
            )
        
        summary = tracker.get_effectiveness_summary(30)
        
        assert summary["total_sessions"] == 3
        assert summary["successful_sessions"] == 3
        assert summary["success_rate_percentage"] == 100.0
        assert "average_metrics" in summary
        assert "total_impact" in summary
        assert "strategy_effectiveness" in summary
        
        # Check strategy stats
        balanced_stats = summary["strategy_effectiveness"]["BALANCED"]
        assert balanced_stats["count"] == 3
        assert balanced_stats["success_rate"] == 100.0
    
    def test_session_details_retrieval(self, tracker, sample_context_data):
        """Test retrieving specific session details."""
        # Create a session
        session_id = tracker.start_optimization_tracking(
            sample_context_data, "AGGRESSIVE", "test"
        )
        
        completed_session = tracker.complete_optimization_tracking(
            session_id=session_id,
            optimized_context=sample_context_data,
            outcome=OptimizationOutcome.SUCCESS,
            operations_approved=10,
            operations_rejected=0,
            operations_modified=2,
            total_operations=12,
            session_time=2.5
        )
        
        # Retrieve session details
        retrieved_session = tracker.get_session_details(session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == session_id
        assert retrieved_session.strategy_type == "AGGRESSIVE"
        assert retrieved_session.operations_approved == 10
        assert retrieved_session.total_operations_proposed == 12
    
    def test_export_effectiveness_data(self, tracker, sample_context_data):
        """Test exporting effectiveness data."""
        # Create some test data
        session_id = tracker.start_optimization_tracking(
            sample_context_data, "BALANCED", "export_test"
        )
        
        tracker.complete_optimization_tracking(
            session_id=session_id,
            optimized_context=sample_context_data,
            outcome=OptimizationOutcome.SUCCESS,
            operations_approved=5,
            operations_rejected=1,
            operations_modified=0,
            total_operations=6,
            session_time=1.8
        )
        
        # Export data
        export_data = tracker.export_effectiveness_data(format="json")
        
        assert "export_metadata" in export_data
        assert "effectiveness_summary" in export_data
        assert "all_sessions" in export_data
        
        metadata = export_data["export_metadata"]
        assert metadata["total_sessions"] == 1
        assert metadata["format"] == "json"
        assert "context_cleaner_version" in metadata
        
        # Verify session data is included
        sessions = export_data["all_sessions"]
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id


class TestOptimizationCommandsWithTracking:
    """Test optimization commands with effectiveness tracking integration."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def handler(self):
        """Create optimization command handler."""
        return OptimizationCommandHandler(verbose=True)
    
    @pytest.fixture
    def mock_context_data(self):
        """Mock context data for testing."""
        return {
            "content": "Sample context with TODO items and duplicates",
            "files": ["file1.py", "file2.py"],
            "size": 2000
        }
    
    @patch('context_cleaner.cli.optimization_commands.start_interactive_optimization')
    @patch('context_cleaner.optimization.change_approval.create_quick_approval')
    def test_quick_optimization_with_tracking(self, mock_approval, mock_interactive, handler, mock_context_data, capsys):
        """Test quick optimization with effectiveness tracking."""
        # Mock the interactive optimization
        mock_manager = Mock()
        mock_session = Mock()
        mock_session.session_id = "test_session_123"
        mock_interactive.return_value = (mock_manager, mock_session)
        
        # Mock optimization plan
        mock_plan = Mock()
        mock_operations = [Mock() for _ in range(3)]
        for i, op in enumerate(mock_operations):
            op.operation_id = f"op_{i}"
            op.estimated_token_impact = -100  # Token savings
            op.confidence_score = 0.95  # High confidence for quick approval
            op.requires_confirmation = False  # Safe for auto-approval
        mock_plan.operations = mock_operations
        mock_manager.generate_optimization_plan.return_value = mock_plan
        
        # Mock approval system
        mock_approval_system = Mock()
        mock_approval_id = "approval_123"
        mock_approval.return_value = (mock_approval_system, mock_approval_id)
        mock_approval_system.get_selected_operations.return_value = ["op_0", "op_1"]
        
        # Mock apply changes result
        mock_result = Mock()
        mock_result.operations_executed = 2
        mock_result.operations_rejected = 1
        mock_result.optimized_context = {"optimized": "content"}
        mock_manager.apply_selective_changes.return_value = mock_result
        
        # Mock the context retrieval
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            # Execute quick optimization
            handler.handle_quick_optimization()
            
            captured = capsys.readouterr()
            
            # Verify output includes effectiveness tracking
            assert "Quick optimization completed:" in captured.out
            assert "2 operations applied" in captured.out
            assert "1 operations skipped" in captured.out
            assert "Estimated token reduction:" in captured.out
    
    def test_quick_optimization_no_changes_tracking(self, handler, mock_context_data, capsys):
        """Test tracking when no changes are needed."""
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            with patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_interactive:
                # Mock session with no operations needed
                mock_manager = Mock()
                mock_session = Mock()
                mock_session.session_id = "test_session_no_changes"
                mock_interactive.return_value = (mock_manager, mock_session)
                
                mock_plan = Mock()
                mock_plan.operations = []  # No operations needed
                mock_manager.generate_optimization_plan.return_value = mock_plan
                
                handler.handle_quick_optimization()
                
                captured = capsys.readouterr()
                assert "Context already well-optimized" in captured.out
    
    def test_quick_optimization_error_tracking(self, handler, mock_context_data, capsys):
        """Test effectiveness tracking when optimization fails."""
        with patch.object(handler, '_get_current_context', return_value=mock_context_data):
            with patch('context_cleaner.cli.optimization_commands.start_interactive_optimization') as mock_interactive:
                # Make the optimization raise an exception
                mock_interactive.side_effect = Exception("Optimization failed")
                
                handler.handle_quick_optimization()
                
                captured = capsys.readouterr()
                assert "Quick optimization failed:" in captured.err


class TestCLIIntegration:
    """Integration tests for the new CLI commands."""
    
    def test_cli_help_includes_new_commands(self):
        """Test that new commands appear in CLI help."""
        from context_cleaner.cli.main import main
        
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert 'health-check' in result.output
        assert 'export-analytics' in result.output
        assert 'effectiveness' in result.output
    
    def test_health_check_command_cli(self):
        """Test health-check command through CLI."""
        from context_cleaner.cli.main import main
        
        runner = CliRunner()
        with patch('context_cleaner.cli.analytics_commands.AnalyticsCommandHandler') as mock_handler_class:
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            result = runner.invoke(main, ['health-check', '--detailed'])
            
            assert result.exit_code == 0
            mock_handler.handle_health_check_command.assert_called_once_with(
                detailed=True, fix_issues=False, format='text'
            )
    
    def test_export_analytics_command_cli(self):
        """Test export-analytics command through CLI."""
        from context_cleaner.cli.main import main
        
        runner = CliRunner()
        with patch('context_cleaner.cli.analytics_commands.AnalyticsCommandHandler') as mock_handler_class:
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            result = runner.invoke(main, ['export-analytics', '--days', '7', '--output', 'test.json'])
            
            assert result.exit_code == 0
            mock_handler.handle_export_analytics_command.assert_called_once_with(
                output_path='test.json', days=7, include_sessions=True, format='json'
            )
    
    def test_effectiveness_command_cli(self):
        """Test effectiveness command through CLI."""
        from context_cleaner.cli.main import main
        
        runner = CliRunner()
        with patch('context_cleaner.cli.analytics_commands.AnalyticsCommandHandler') as mock_handler_class:
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            result = runner.invoke(main, ['effectiveness', '--days', '14', '--detailed'])
            
            assert result.exit_code == 0
            mock_handler.handle_effectiveness_stats_command.assert_called_once_with(
                days=14, strategy=None, detailed=True, format='text'
            )
    
    def test_enhanced_dashboard_cli(self):
        """Test enhanced dashboard options through CLI."""
        from context_cleaner.cli.main import main
        
        runner = CliRunner()
        with patch('context_cleaner.cli.analytics_commands.AnalyticsCommandHandler') as mock_handler_class:
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            
            result = runner.invoke(main, ['dashboard', '--interactive', '--operations'])
            
            # Should call enhanced dashboard instead of regular dashboard
            mock_handler.handle_enhanced_dashboard_command.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])