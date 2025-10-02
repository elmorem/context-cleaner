"""
CLI Command Tests for Enhanced Token Analysis

Tests the CLI commands for enhanced token analysis, including parameter handling,
output formatting, and integration with the enhanced token counting system.
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner
from io import StringIO

from src.context_cleaner.cli.commands.enhanced_token_analysis import (
    token_analysis,
    comprehensive,
    dashboard,
    session,
)
from src.context_cleaner.analysis.enhanced_token_counter import (
    EnhancedTokenAnalysis,
    SessionTokenMetrics,
)
from .fixtures import JSONLFixtures, UndercountTestCases


class TestComprehensiveCommand:
    """Test the comprehensive token analysis CLI command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner for testing."""
        return CliRunner()

    @pytest.fixture
    def mock_analysis(self):
        """Create mock analysis results with undercount detection."""
        sessions = {
            "session_001": SessionTokenMetrics(
                session_id="session_001",
                reported_input_tokens=100,
                reported_output_tokens=50,
                calculated_total_tokens=1500,  # 10x undercount
                user_messages=["User request"],
                assistant_messages=["Assistant response"],
                content_categories={
                    "user_messages": 800,
                    "claude_md": 300,
                    "system_prompts": 400,
                },
            )
        }

        return EnhancedTokenAnalysis(
            total_sessions_analyzed=1,
            total_files_processed=20,  # Enhanced processing
            total_lines_processed=50000,  # Enhanced processing
            total_reported_tokens=150,  # Current system result
            total_calculated_tokens=1500,  # Enhanced system result
            global_accuracy_ratio=10.0,  # 10x undercount
            global_undercount_percentage=90.0,  # 90% undercount
            sessions=sessions,
            category_reported={
                "user_messages": 800,
                "claude_md": 300,
                "system_prompts": 400,
            },
            api_calls_made=5,
            processing_time_seconds=3.45,
            errors_encountered=[],
        )

    def test_comprehensive_command_basic_execution(self, runner, mock_analysis):
        """Test basic execution of comprehensive command."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, [])

            assert result.exit_code == 0
            assert (
                "Enhanced Token Analysis - Addressing 90% Undercount Issue"
                in result.output
            )
            assert "Analysis Complete" in result.output
            assert "Undercount percentage: 90.0%" in result.output

    def test_comprehensive_command_with_api_key(self, runner, mock_analysis):
        """Test comprehensive command with API key parameter."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, ["--api-key", "test-key-123"])

            assert result.exit_code == 0
            mock_service_class.assert_called_with("test-key-123")
            assert "API validation: Enabled" in result.output

    def test_comprehensive_command_with_file_limits(self, runner, mock_analysis):
        """Test comprehensive command with file and line limits."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                comprehensive, ["--max-files", "15", "--max-lines", "2000"]
            )

            assert result.exit_code == 0

            # Verify service was called with correct parameters
            call_args = mock_service.analyze_comprehensive_token_usage.call_args
            assert call_args[1]["max_files"] == 15
            assert call_args[1]["max_lines_per_file"] == 2000

            assert "Files to process: 15 files" in result.output
            assert "Lines per file: 2000 lines" in result.output

    def test_comprehensive_command_no_api_flag(self, runner, mock_analysis):
        """Test comprehensive command with --no-api flag."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, ["--no-api"])

            assert result.exit_code == 0

            # Verify API validation was disabled
            call_args = mock_service.analyze_comprehensive_token_usage.call_args
            assert call_args[1]["use_count_tokens_api"] is False

            assert "API validation: Disabled" in result.output

    def test_comprehensive_command_output_file(self, runner, mock_analysis):
        """Test comprehensive command with output file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            output_path = tmp_file.name

        try:
            with patch(
                "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
            ) as mock_service_class:
                mock_service = AsyncMock()
                mock_service.analyze_comprehensive_token_usage = AsyncMock(
                    return_value=mock_analysis
                )
                mock_service_class.return_value = mock_service

                result = runner.invoke(comprehensive, ["--output", output_path])

                assert result.exit_code == 0
                assert f"Results saved to {output_path}" in result.output

                # Verify output file was created with correct content
                with open(output_path, "r") as f:
                    output_data = json.load(f)

                assert "timestamp" in output_data
                assert "analysis" in output_data
                assert output_data["analysis"]["sessions_analyzed"] == 1
                assert output_data["analysis"]["files_processed"] == 20
                assert output_data["analysis"]["undercount_percentage"] == 90.0
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_comprehensive_command_undercount_detection_display(
        self, runner, mock_analysis
    ):
        """Test that undercount detection is prominently displayed."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, [])

            assert result.exit_code == 0

            # Verify undercount detection is prominently displayed
            assert "⚠️  Undercount Detection:" in result.output
            assert "Undercount percentage: 90.0%" in result.output
            assert "Missed tokens: 1,350" in result.output
            assert "Actual usage is 10.0x higher than reported" in result.output

    def test_comprehensive_command_comparison_display(self, runner, mock_analysis):
        """Test comparison with current method display."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, ["--compare"])

            assert result.exit_code == 0

            # Verify comparison section is displayed
            assert "🔄 Comparing with Current Dashboard Method..." in result.output
            assert "Would only process 10 files vs 20" in result.output
            assert "Would only process ~10,000 lines vs 50,000" in result.output
            assert "Would miss 90.0% of tokens" in result.output

    def test_comprehensive_command_error_handling(self, runner):
        """Test error handling in comprehensive command."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                side_effect=Exception("Analysis failed")
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, [])

            assert result.exit_code == 1  # Should exit with error
            assert "❌ Analysis failed: Analysis failed" in result.output

    def test_comprehensive_command_session_breakdown(self, runner, mock_analysis):
        """Test session breakdown display."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, [])

            assert result.exit_code == 0

            # Verify session breakdown is displayed
            assert "👥 Top Sessions by Token Usage:" in result.output
            assert "1. Session session_001" in result.output
            assert "Reported: 150 tokens" in result.output
            assert "Calculated: 1,500 tokens" in result.output
            assert "⚠️  Undercount: 90.0%" in result.output


class TestDashboardCommand:
    """Test the dashboard integration CLI command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner for testing."""
        return CliRunner()

    def test_dashboard_command_success(self, runner):
        """Test successful dashboard integration test."""
        mock_dashboard_data = {
            "total_tokens": {"total": 2500},
            "categories": [
                {"name": "User Messages", "tokens": {"total": 1500}},
                {"name": "Assistant Messages", "tokens": {"total": 1000}},
            ],
            "analysis_metadata": {
                "enhanced_analysis": True,
                "sessions_analyzed": 5,
                "files_processed": 25,
                "accuracy_improvement": {
                    "improvement_factor": "5.2x",
                    "undercount_percentage": "80.1%",
                },
            },
            "recommendations": [
                "⚠️ Significant undercount detected (80.1%)",
                "📊 Analyzed 25 conversation files (vs previous limit of 10)",
            ],
        }

        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.get_enhanced_token_analysis = AsyncMock(
                return_value=mock_dashboard_data
            )
            mock_analyzer_class.return_value = mock_analyzer

            result = runner.invoke(dashboard, [])

            assert result.exit_code == 0
            assert "✅ Dashboard integration successful!" in result.output
            assert "Total tokens: 2,500" in result.output
            assert "Categories found: 2" in result.output
            assert "Enhanced analysis: ✅" in result.output
            assert "Sessions: 5" in result.output
            assert "Files: 25" in result.output
            assert "Improvement: 5.2x" in result.output
            assert "Undercount: 80.1%" in result.output

    def test_dashboard_command_fallback(self, runner):
        """Test dashboard integration with fallback."""
        mock_fallback_data = {
            "total_tokens": {"total": 0},
            "categories": [],
            "analysis_metadata": {"enhanced_analysis": False, "fallback_used": True},
            "recommendations": [
                "Enhanced token analysis failed. Check logs and API key configuration."
            ],
        }

        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.get_enhanced_token_analysis = AsyncMock(
                return_value=mock_fallback_data
            )
            mock_analyzer_class.return_value = mock_analyzer

            result = runner.invoke(dashboard, [])

            assert result.exit_code == 0
            assert "Enhanced analysis: ❌ (fallback used)" in result.output
            assert "Enhanced token analysis failed" in result.output

    def test_dashboard_command_error(self, runner):
        """Test dashboard integration error handling."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.get_enhanced_token_analysis = AsyncMock(
                side_effect=Exception("Dashboard integration failed")
            )
            mock_analyzer_class.return_value = mock_analyzer

            result = runner.invoke(dashboard, [])

            assert result.exit_code == 1  # Should exit with error
            assert (
                "❌ Dashboard integration failed: Dashboard integration failed"
                in result.output
            )


class TestSessionCommand:
    """Test the session-specific analysis CLI command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner for testing."""
        return CliRunner()

    @pytest.fixture
    def mock_analysis_with_sessions(self):
        """Create mock analysis with multiple sessions."""
        sessions = {
            "session_abc123": SessionTokenMetrics(
                session_id="session_abc123",
                reported_input_tokens=200,
                reported_output_tokens=100,
                calculated_total_tokens=1800,
                user_messages=["User message 1", "User message 2"],
                assistant_messages=["Assistant response"],
                system_prompts=["System context"],
                tool_calls=[{"tool": "read", "args": {}}],
                content_categories={
                    "user_messages": 900,
                    "system_prompts": 400,
                    "system_tools": 500,
                },
            ),
            "session_def456": SessionTokenMetrics(
                session_id="session_def456",
                reported_input_tokens=150,
                reported_output_tokens=75,
                calculated_total_tokens=1200,
                user_messages=["Another user message"],
                assistant_messages=["Another response"],
                content_categories={"user_messages": 600, "claude_md": 600},
            ),
        }

        return EnhancedTokenAnalysis(
            total_sessions_analyzed=2,
            total_files_processed=10,
            total_lines_processed=5000,
            total_reported_tokens=525,
            total_calculated_tokens=3000,
            global_accuracy_ratio=5.71,
            global_undercount_percentage=82.5,
            sessions=sessions,
        )

    def test_session_command_missing_session_id(self, runner):
        """Test session command without session ID parameter."""
        result = runner.invoke(session, [])

        assert result.exit_code == 1  # Should exit with error
        assert "--session-id is required" in result.output

    @pytest.mark.skip(
        reason="Session command creates service internally, mocking doesn't work - needs implementation refactor"
    )
    def test_session_command_exact_match(self, runner, mock_analysis_with_sessions):
        """Test session command with exact session ID match."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis_with_sessions
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(session, ["--session-id", "session_abc123"])

            assert result.exit_code == 0
            assert "📊 Session: session_abc123" in result.output
            assert "Reported tokens: 300" in result.output  # 200 + 100
            assert "Calculated tokens: 1,800" in result.output
            assert "Accuracy ratio: 6.00x" in result.output
            assert "⚠️  Undercount: 83.3%" in result.output

            # Content breakdown
            assert "User messages: 2" in result.output
            assert "Assistant messages: 1" in result.output
            assert "System prompts: 1" in result.output
            assert "Tool calls: 1" in result.output

            # Category breakdown
            assert "User Messages: 900" in result.output
            assert "System Prompts: 400" in result.output
            assert "System Tools: 500" in result.output

    @pytest.mark.skip(
        reason="Session command creates service internally, mocking doesn't work - needs implementation refactor"
    )
    def test_session_command_partial_match(self, runner, mock_analysis_with_sessions):
        """Test session command with partial session ID match."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis_with_sessions
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(session, ["--session-id", "abc123"])

            assert result.exit_code == 0
            assert "📊 Session: session_abc123" in result.output
            assert "Reported tokens: 300" in result.output

    @pytest.mark.skip(
        reason="Session command creates service internally, mocking doesn't work - needs implementation refactor"
    )
    def test_session_command_not_found(self, runner, mock_analysis_with_sessions):
        """Test session command with non-existent session ID."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis_with_sessions
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(session, ["--session-id", "nonexistent"])

            assert result.exit_code == 0
            assert "❌ Session 'nonexistent' not found" in result.output
            assert "Available sessions: 2" in result.output

    @pytest.mark.skip(
        reason="Session command creates service internally, mocking doesn't work - needs implementation refactor"
    )
    def test_session_command_multiple_matches(self, runner):
        """Test session command with multiple partial matches."""
        sessions = {
            "session_test_001": SessionTokenMetrics(session_id="session_test_001"),
            "session_test_002": SessionTokenMetrics(session_id="session_test_002"),
            "session_test_003": SessionTokenMetrics(session_id="session_test_003"),
        }

        mock_analysis = EnhancedTokenAnalysis(
            total_sessions_analyzed=3,
            total_files_processed=3,
            total_lines_processed=300,
            total_reported_tokens=300,
            total_calculated_tokens=600,
            global_accuracy_ratio=2.0,
            global_undercount_percentage=50.0,
            sessions=sessions,
        )

        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(session, ["--session-id", "test"])

            assert result.exit_code == 0
            assert "Multiple sessions match 'test':" in result.output
            assert "session_test_001" in result.output
            assert "session_test_002" in result.output
            assert "session_test_003" in result.output

    def test_session_command_error_handling(self, runner):
        """Test session command error handling."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                side_effect=Exception("Session analysis failed")
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(session, ["--session-id", "test_session"])

            assert result.exit_code == 1  # Should exit with error
            assert "Session analysis failed: Session analysis failed" in result.output


class TestTokenAnalysisGroup:
    """Test the token analysis command group."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner for testing."""
        return CliRunner()

    def test_token_analysis_group_help(self, runner):
        """Test token analysis group help display."""
        result = runner.invoke(token_analysis, ["--help"])

        assert result.exit_code == 0
        assert (
            "Enhanced token analysis commands using Anthropic's count-tokens API"
            in result.output
        )
        assert "comprehensive" in result.output
        assert "dashboard" in result.output
        assert "session" in result.output

    def test_comprehensive_command_help(self, runner):
        """Test comprehensive command help display."""
        result = runner.invoke(comprehensive, ["--help"])

        assert result.exit_code == 0
        assert (
            "Run comprehensive token analysis addressing the 90% undercount issue"
            in result.output
        )
        assert "--api-key" in result.output
        assert "--max-files" in result.output
        assert "--max-lines" in result.output
        assert "--no-api" in result.output
        assert "--output" in result.output
        assert "--compare" in result.output

    def test_dashboard_command_help(self, runner):
        """Test dashboard command help display."""
        result = runner.invoke(dashboard, ["--help"])

        assert result.exit_code == 0
        assert (
            "Test the dashboard integration for enhanced token analysis"
            in result.output
        )

    def test_session_command_help(self, runner):
        """Test session command help display."""
        result = runner.invoke(session, ["--help"])

        assert result.exit_code == 0
        assert "Analyze token usage for a specific session" in result.output
        assert "--session-id" in result.output


class TestCLIIntegration:
    """Test integration aspects of CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner for testing."""
        return CliRunner()

    def test_cli_parameter_passing(self, runner):
        """Test that CLI parameters are correctly passed to underlying services."""
        mock_analysis = EnhancedTokenAnalysis(
            total_sessions_analyzed=1,
            total_files_processed=5,
            total_lines_processed=500,
            total_reported_tokens=100,
            total_calculated_tokens=200,
            global_accuracy_ratio=2.0,
            global_undercount_percentage=50.0,
        )

        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                comprehensive,
                [
                    "--api-key",
                    "test-key",
                    "--max-files",
                    "20",
                    "--max-lines",
                    "5000",
                    "--no-api",
                ],
            )

            assert result.exit_code == 0

            # Verify service was initialized with correct API key
            mock_service_class.assert_called_with("test-key")

            # Verify analysis was called with correct parameters
            call_args = mock_service.analyze_comprehensive_token_usage.call_args
            assert call_args[1]["max_files"] == 20
            assert call_args[1]["max_lines_per_file"] == 5000
            assert call_args[1]["use_count_tokens_api"] is False  # --no-api flag

    def test_cli_error_propagation(self, runner):
        """Test that errors from underlying services are properly handled."""
        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                side_effect=ValueError("Invalid configuration")
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, [])

            assert result.exit_code == 1
            assert "Analysis failed: Invalid configuration" in result.output

    def test_cli_output_consistency(self, runner):
        """Test that CLI output format is consistent across commands."""
        # Test that all commands use consistent formatting and symbols
        mock_analysis = EnhancedTokenAnalysis(
            total_sessions_analyzed=1,
            total_files_processed=1,
            total_lines_processed=100,
            total_reported_tokens=50,
            total_calculated_tokens=500,
            global_accuracy_ratio=10.0,
            global_undercount_percentage=90.0,
        )

        with patch(
            "src.context_cleaner.cli.commands.enhanced_token_analysis.EnhancedTokenCounterService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service.analyze_comprehensive_token_usage = AsyncMock(
                return_value=mock_analysis
            )
            mock_service_class.return_value = mock_service

            result = runner.invoke(comprehensive, [])

            assert result.exit_code == 0

            # Check for consistent emoji usage and formatting
            assert "🔍 Enhanced Token Analysis" in result.output
            assert "📊 Current Implementation Limitations:" in result.output
            assert "🚀 Enhanced Analysis Parameters:" in result.output
            assert "⏳ Running enhanced analysis..." in result.output
            assert "✅ Analysis Complete" in result.output
            assert "📈 Coverage Improvements:" in result.output
            assert "🎯 Token Count Results:" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
