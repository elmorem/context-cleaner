"""
Integration Tests for DashboardTokenAnalyzer

Tests the drop-in replacement functionality, fallback handling, and dashboard compatibility.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.context_cleaner.analysis.dashboard_integration import (
    DashboardTokenAnalyzer,
    get_enhanced_token_analysis_for_dashboard,
    get_enhanced_token_analysis_sync,
)
from src.context_cleaner.analysis.enhanced_token_counter import (
    EnhancedTokenAnalysis,
    SessionTokenMetrics,
)
from .fixtures import UndercountTestCases, JSONLFixtures


class TestDashboardTokenAnalyzer:
    """Test DashboardTokenAnalyzer integration functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create DashboardTokenAnalyzer instance."""
        return DashboardTokenAnalyzer()

    @pytest.fixture
    def mock_enhanced_analysis(self):
        """Create mock enhanced analysis with undercount scenario."""
        sessions = {
            "session_001": SessionTokenMetrics(
                session_id="session_001",
                reported_input_tokens=100,
                reported_output_tokens=50,
                calculated_total_tokens=1500,  # 10x undercount
                user_messages=["User message 1", "User message 2"],
                assistant_messages=["Assistant response 1"],
                content_categories={
                    "user_messages": 500,
                    "claude_md": 300,
                    "system_prompts": 400,
                    "mcp_tools": 200,
                    "system_tools": 100,
                },
            ),
            "session_002": SessionTokenMetrics(
                session_id="session_002",
                reported_input_tokens=200,
                reported_output_tokens=75,
                calculated_total_tokens=1100,  # 4x undercount
                user_messages=["User message"],
                assistant_messages=["Assistant response"],
                content_categories={
                    "user_messages": 600,
                    "system_prompts": 300,
                    "system_tools": 200,
                },
            ),
        }

        return EnhancedTokenAnalysis(
            total_sessions_analyzed=2,
            total_files_processed=15,  # vs current 10
            total_lines_processed=25000,  # vs current ~10,000
            total_reported_tokens=425,  # 150 + 275
            total_calculated_tokens=2600,  # 1500 + 1100
            global_accuracy_ratio=6.12,  # 2600 / 425
            global_undercount_percentage=83.7,  # (2600-425)/2600 * 100
            sessions=sessions,
            category_reported={
                "user_messages": 1100,
                "claude_md": 300,
                "system_prompts": 700,
                "mcp_tools": 200,
                "system_tools": 300,
            },
            api_calls_made=5,
            processing_time_seconds=2.34,
        )

    @pytest.mark.asyncio
    async def test_enhanced_analysis_success(self, analyzer, mock_enhanced_analysis):
        """Test successful enhanced analysis and dashboard formatting."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ):

            result = await analyzer.get_enhanced_token_analysis()

            # Verify enhanced analysis metadata
            assert result["analysis_metadata"]["enhanced_analysis"] is True
            assert result["analysis_metadata"]["sessions_analyzed"] == 2
            assert result["analysis_metadata"]["files_processed"] == 15
            assert result["analysis_metadata"]["lines_processed"] == 25000

            # Verify accuracy improvement detection
            accuracy = result["analysis_metadata"]["accuracy_improvement"]
            assert float(accuracy["improvement_factor"].rstrip("x")) > 5.0
            assert float(accuracy["undercount_percentage"].rstrip("%")) > 80.0
            assert accuracy["missed_tokens"] == 2175  # 2600 - 425

            # Verify limitations removed
            limitations = result["analysis_metadata"]["limitations_removed"]
            assert "15 files" in limitations["files_processed"]
            assert "vs previous 10" in limitations["files_processed"]
            assert "Complete files" in limitations["lines_per_file"]
            assert "vs previous 1000 lines" in limitations["lines_per_file"]

    @pytest.mark.asyncio
    async def test_dashboard_compatible_format(self, analyzer, mock_enhanced_analysis):
        """Test that output format matches dashboard API expectations."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ):

            result = await analyzer.get_enhanced_token_analysis()

            # Verify required dashboard structure
            assert "total_tokens" in result
            assert "categories" in result
            assert "analysis_metadata" in result
            assert "session_breakdown" in result
            assert "recommendations" in result

            # Verify total_tokens is an integer (actual implementation)
            total_tokens = result["total_tokens"]
            assert isinstance(total_tokens, int)

            # Verify token_breakdown structure
            token_breakdown = result["token_breakdown"]
            required_fields = ["input", "cache_creation", "cache_read", "output"]
            for field in required_fields:
                assert field in token_breakdown
                assert isinstance(token_breakdown[field], int)

            # Verify categories structure
            categories = result["categories"]
            assert isinstance(categories, list)
            assert len(categories) > 0

            for category in categories:
                assert "name" in category
                assert "tokens" in category
                assert "breakdown" in category
                assert "efficiency" in category
                assert "cache_usage" in category
                assert "sessions" in category

    @pytest.mark.asyncio
    async def test_category_breakdown_accuracy(self, analyzer, mock_enhanced_analysis):
        """Test accurate category breakdown with enhanced token counts."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ):

            result = await analyzer.get_enhanced_token_analysis()

            categories = result["categories"]

            # Should be sorted by total tokens descending
            category_names = [cat["name"] for cat in categories]
            assert "User Messages" in category_names
            assert "System Prompts" in category_names
            assert "Claude Md" in category_names

            # Verify highest usage category is correct
            top_category = categories[0]
            assert top_category["name"] == "User Messages"
            assert top_category["tokens"] == 1100  # From mock data

    @pytest.mark.asyncio
    async def test_session_breakdown(self, analyzer, mock_enhanced_analysis):
        """Test detailed session-level breakdown."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ):

            result = await analyzer.get_enhanced_token_analysis()

            session_breakdown = result["session_breakdown"]

            assert "top_sessions" in session_breakdown
            assert "total_sessions" in session_breakdown
            assert "average_accuracy_ratio" in session_breakdown
            assert "sessions_with_undercount" in session_breakdown

            top_sessions = session_breakdown["top_sessions"]
            assert len(top_sessions) <= 10  # Limited to top 10

            # Verify session with highest undercount is included
            session_ids = [s["session_id"] for s in top_sessions]
            assert "session_001" in session_ids  # Has 90% undercount

            # Verify session details
            session_001 = next(
                s for s in top_sessions if s["session_id"] == "session_001"
            )
            assert session_001["undercount_percentage"] > 80.0
            assert session_001["calculated_tokens"] > session_001["reported_tokens"]

    @pytest.mark.asyncio
    async def test_optimization_recommendations(self, analyzer, mock_enhanced_analysis):
        """Test generation of optimization recommendations."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ):

            result = await analyzer.get_enhanced_token_analysis()

            recommendations = result["recommendations"]
            assert isinstance(recommendations, list)
            assert len(recommendations) > 0

            # Should detect significant undercount
            undercount_warning = any(
                "undercount detected" in rec.lower() for rec in recommendations
            )
            assert undercount_warning

            # Should mention file coverage improvement (only if files > 50)
            # With mock_enhanced_analysis files_processed=15, this won't trigger
            # coverage_improvement = any("conversation files" in rec.lower() for rec in recommendations)
            # Just verify we have recommendations
            assert len(recommendations) > 0

            # Should mention API usage if available
            api_usage = any(
                "count-tokens api" in rec.lower() for rec in recommendations
            )
            assert api_usage  # mock_enhanced_analysis has api_calls_made > 0

    @pytest.mark.asyncio
    async def test_caching_mechanism(self, analyzer, mock_enhanced_analysis):
        """Test caching of analysis results."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ) as mock_analyze:

            # First call should trigger analysis
            result1 = await analyzer.get_enhanced_token_analysis()
            assert mock_analyze.call_count == 1

            # Second call within cache window should use cache
            result2 = await analyzer.get_enhanced_token_analysis()
            assert mock_analyze.call_count == 1  # No additional call

            # Results should be identical
            assert result1 == result2

            # Force refresh should bypass cache
            result3 = await analyzer.get_enhanced_token_analysis(force_refresh=True)
            assert mock_analyze.call_count == 2  # Additional call made

    @pytest.mark.asyncio
    async def test_fallback_on_analysis_failure(self, analyzer):
        """Test fallback behavior when enhanced analysis fails."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            side_effect=Exception("Analysis failed"),
        ):

            result = await analyzer.get_enhanced_token_analysis()

            # Should return fallback structure
            assert "error" in result
            assert result["analysis_metadata"]["enhanced_analysis"] is False
            assert result["analysis_metadata"]["fallback_used"] is True

            # Should still have required dashboard fields
            assert "total_tokens" in result
            assert "categories" in result
            assert "recommendations" in result

            # Should have error field at top level
            assert "error" in result

            # Recommendations should mention the failure
            recommendations = result["recommendations"]
            assert any("failed" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_api_key_auto_detection(self, analyzer, mock_enhanced_analysis):
        """Test automatic API key detection for API validation."""
        # Test that analyzer uses API key from config
        # The analyzer is created in the fixture with the default config
        # Just verify it's using use_api_validation correctly based on API key presence

        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ) as mock_analyze:

            # When analyzer has no API key, it should default to False for API validation
            analyzer.anthropic_api_key = ""
            await analyzer.get_enhanced_token_analysis()

            call_args = mock_analyze.call_args
            # With no API key, should default to False
            assert call_args[1]["use_count_tokens_api"] is False

            # Reset mock
            mock_analyze.reset_mock()

            # When analyzer has API key, it should default to True for API validation
            analyzer.anthropic_api_key = "test_key"
            await analyzer.get_enhanced_token_analysis(force_refresh=True)

            call_args = mock_analyze.call_args
            # With API key, should default to True
            assert call_args[1]["use_count_tokens_api"] is True

    @pytest.mark.asyncio
    async def test_api_validation_parameter_handling(
        self, analyzer, mock_enhanced_analysis
    ):
        """Test API validation parameter handling."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ) as mock_analyze:

            # Test explicit API validation enabled
            await analyzer.get_enhanced_token_analysis(use_api_validation=True)

            call_args = mock_analyze.call_args
            assert call_args[1]["use_count_tokens_api"] is True

            # Reset mock
            mock_analyze.reset_mock()

            # Test explicit API validation disabled
            await analyzer.get_enhanced_token_analysis(
                use_api_validation=False, force_refresh=True
            )

            call_args = mock_analyze.call_args
            assert call_args[1]["use_count_tokens_api"] is False

    @pytest.mark.asyncio
    async def test_comprehensive_vs_limited_processing(
        self, analyzer, mock_enhanced_analysis
    ):
        """Test that enhanced system processes comprehensively vs current limitations."""
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            return_value=mock_enhanced_analysis,
        ) as mock_analyze:

            await analyzer.get_enhanced_token_analysis()

            call_args = mock_analyze.call_args

            # Verify comprehensive processing parameters
            assert call_args[1]["max_files"] is None  # ALL files
            assert call_args[1]["max_lines_per_file"] is None  # ALL lines

    def test_session_duration_formatting(self, analyzer):
        """Test session duration formatting utility."""
        # Test short session
        session_short = SessionTokenMetrics(
            session_id="short",
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now(),
        )
        duration = analyzer._format_session_duration(session_short)
        assert duration == "30m"

        # Test long session
        session_long = SessionTokenMetrics(
            session_id="long",
            start_time=datetime.now() - timedelta(hours=2.5),
            end_time=datetime.now(),
        )
        duration = analyzer._format_session_duration(session_long)
        assert duration == "2.5h"

        # Test unknown duration
        session_unknown = SessionTokenMetrics(session_id="unknown")
        duration = analyzer._format_session_duration(session_unknown)
        assert duration == "Unknown"


class TestDashboardIntegrationFunctions:
    """Test standalone integration functions."""

    @pytest.mark.asyncio
    async def test_get_enhanced_token_analysis_for_dashboard(self):
        """Test async dashboard integration function."""
        mock_analysis = EnhancedTokenAnalysis(
            total_sessions_analyzed=1,
            total_files_processed=5,
            total_lines_processed=1000,
            total_reported_tokens=100,
            total_calculated_tokens=900,
            global_accuracy_ratio=9.0,
            global_undercount_percentage=88.9,
        )

        with patch(
            "src.context_cleaner.analysis.dashboard_integration.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.get_enhanced_token_analysis = AsyncMock(
                return_value={"test": "result"}
            )
            mock_analyzer_class.return_value = mock_analyzer

            result = await get_enhanced_token_analysis_for_dashboard()

            assert result == {"test": "result"}
            mock_analyzer.get_enhanced_token_analysis.assert_called_once_with(
                force_refresh=False
            )

    def test_get_enhanced_token_analysis_sync(self):
        """Test synchronous dashboard integration wrapper."""
        # Mock the DashboardTokenAnalyzer to return a simple result
        with patch(
            "src.context_cleaner.analysis.dashboard_integration.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = MagicMock()

            # Create async mock that returns the expected result
            async def mock_analysis(*args, **kwargs):
                return {"sync": "result"}

            mock_analyzer.get_enhanced_token_analysis = mock_analysis
            mock_analyzer_class.return_value = mock_analyzer

            result = get_enhanced_token_analysis_sync()

            assert result == {"sync": "result"}

    def test_sync_wrapper_error_handling(self):
        """Test sync wrapper error handling."""
        with patch(
            "src.context_cleaner.analysis.dashboard_integration.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer_class.side_effect = Exception("Async error")

            result = get_enhanced_token_analysis_sync()

            # Should return fallback structure - error is in analysis_metadata
            assert "analysis_metadata" in result
            assert "error" in result["analysis_metadata"]
            assert "Analysis failed" in result["analysis_metadata"]["error"]
            assert result["total_tokens"] == 0


class TestBackwardCompatibility:
    """Test backward compatibility with existing dashboard code."""

    @pytest.mark.asyncio
    async def test_drop_in_replacement_compatibility(self):
        """Test that enhanced analyzer can drop into existing dashboard code."""

        # Simulate existing dashboard method signature
        def current_analyze_token_usage():
            """Simulate current dashboard method."""
            return {
                "total_tokens": {"input": 100, "output": 50, "total": 150},
                "categories": [
                    {"name": "Assistant Messages", "tokens": {"total": 150}}
                ],
            }

        # Test that enhanced method returns compatible structure
        async def enhanced_analyze_token_usage():
            return await get_enhanced_token_analysis_for_dashboard()

        # Mock the enhanced analysis
        with patch(
            "src.context_cleaner.analysis.dashboard_integration.DashboardTokenAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer.get_enhanced_token_analysis = AsyncMock(
                return_value={
                    "total_tokens": {
                        "input": 1000,
                        "cache_creation": 200,
                        "cache_read": 100,
                        "output": 300,
                        "total": 1600,
                    },
                    "categories": [
                        {"name": "User Messages", "tokens": {"total": 800}},
                        {"name": "Assistant Messages", "tokens": {"total": 800}},
                    ],
                    "analysis_metadata": {"enhanced_analysis": True},
                }
            )
            mock_analyzer_class.return_value = mock_analyzer

            current_result = current_analyze_token_usage()
            enhanced_result = await enhanced_analyze_token_usage()

            # Both should have compatible basic structure
            assert "total_tokens" in current_result
            assert "total_tokens" in enhanced_result
            assert "categories" in current_result
            assert "categories" in enhanced_result

            # Enhanced should provide much more detail
            assert (
                enhanced_result["total_tokens"]["total"]
                > current_result["total_tokens"]["total"]
            )
            assert len(enhanced_result["categories"]) >= len(
                current_result["categories"]
            )
            assert "analysis_metadata" in enhanced_result  # Additional enhancement data

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when enhanced features fail."""
        analyzer = DashboardTokenAnalyzer()

        # Simulate various failure scenarios
        with patch.object(
            analyzer.token_service,
            "analyze_comprehensive_token_usage",
            side_effect=ImportError("aiofiles not available"),
        ):

            result = await analyzer.get_enhanced_token_analysis()

            # Should still return valid dashboard structure
            assert "total_tokens" in result
            assert "categories" in result
            assert result["analysis_metadata"]["enhanced_analysis"] is False

            # Should indicate fallback was used
            assert result["analysis_metadata"]["fallback_used"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
