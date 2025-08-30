"""
Test suite for Comprehensive Health Dashboard (PR16).
Tests integration with PR15.3 cache intelligence system.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from context_cleaner.dashboard.comprehensive_health_dashboard import (
    ComprehensiveHealthDashboard,
    ComprehensiveHealthReport,
    FocusMetrics,
    RedundancyAnalysis,
    RecencyIndicators,
    SizeOptimizationMetrics,
    HealthColor
)
from context_cleaner.optimization.cache_dashboard import CacheEnhancedDashboardData


class TestComprehensiveHealthDashboard:
    """Test suite for the comprehensive health dashboard."""
    
    @pytest.fixture
    def dashboard(self):
        """Create a dashboard instance for testing."""
        return ComprehensiveHealthDashboard()
    
    @pytest.fixture
    def mock_context_data(self):
        """Mock context data for testing."""
        return {
            "items": [
                {
                    "type": "todo",
                    "content": "Implement comprehensive health dashboard",
                    "status": "in_progress",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "type": "file_read",
                    "file_path": "/src/dashboard/comprehensive_health_dashboard.py",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "type": "todo",
                    "content": "Completed previous feature",
                    "status": "completed",
                    "timestamp": (datetime.now() - timedelta(days=1)).isoformat()
                },
                {
                    "type": "conversation",
                    "content": "Discussion about dashboard implementation",
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "session_info": {
                "start_time": datetime.now().isoformat(),
                "current_task": "Implementing comprehensive health dashboard"
            }
        }
    
    @pytest.mark.asyncio
    async def test_generate_comprehensive_health_report(self, dashboard, mock_context_data):
        """Test generating a comprehensive health report."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        assert isinstance(report, ComprehensiveHealthReport)
        assert isinstance(report.focus_metrics, FocusMetrics)
        assert isinstance(report.redundancy_analysis, RedundancyAnalysis)
        assert isinstance(report.recency_indicators, RecencyIndicators)
        assert isinstance(report.size_optimization, SizeOptimizationMetrics)
        
        # Check that we have a valid health score
        assert 0 <= report.overall_health_score <= 1
        assert report.overall_health_color in HealthColor
        
        # Check that analysis metadata is present
        assert report.analysis_timestamp is not None
        assert report.context_analysis_duration >= 0
        assert 0 <= report.confidence_score <= 1
    
    @pytest.mark.asyncio
    async def test_focus_metrics_calculation(self, dashboard, mock_context_data):
        """Test focus metrics calculation."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        focus = report.focus_metrics
        assert 0 <= focus.focus_score <= 1
        assert 0 <= focus.priority_alignment <= 1
        assert 0 <= focus.current_work_ratio <= 1
        assert 0 <= focus.attention_clarity <= 1
        assert 0 <= focus.usage_weighted_focus <= 1
        assert 0 <= focus.workflow_alignment <= 1
        assert 0 <= focus.task_completion_clarity <= 1
        
        # Test health color determination
        assert focus.overall_focus_health in HealthColor
    
    @pytest.mark.asyncio
    async def test_redundancy_analysis(self, dashboard, mock_context_data):
        """Test redundancy analysis."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        redundancy = report.redundancy_analysis
        assert 0 <= redundancy.duplicate_content_percentage <= 1
        assert 0 <= redundancy.stale_context_percentage <= 1
        assert redundancy.redundant_files_count >= 0
        assert redundancy.obsolete_todos_count >= 0
        assert 0 <= redundancy.usage_redundancy_score <= 1
        assert 0 <= redundancy.elimination_opportunity <= 1
        
        # Test health color determination
        assert redundancy.overall_redundancy_health in HealthColor
    
    @pytest.mark.asyncio
    async def test_recency_indicators(self, dashboard, mock_context_data):
        """Test recency indicators calculation."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        recency = report.recency_indicators
        assert 0 <= recency.fresh_context_percentage <= 1
        assert 0 <= recency.recent_context_percentage <= 1
        assert 0 <= recency.aging_context_percentage <= 1
        assert 0 <= recency.stale_context_percentage <= 1
        assert 0 <= recency.usage_weighted_freshness <= 1
        assert 0 <= recency.session_relevance_score <= 1
        
        # Test that percentages are reasonable (allowing for some overlap between categories)
        total = (recency.fresh_context_percentage + 
                recency.recent_context_percentage + 
                recency.aging_context_percentage + 
                recency.stale_context_percentage)
        assert 0.8 <= total <= 2.0  # Allow more flexibility for overlapping categories
        
        # Test health color determination
        assert recency.overall_recency_health in HealthColor
    
    @pytest.mark.asyncio
    async def test_size_optimization_metrics(self, dashboard, mock_context_data):
        """Test size optimization metrics."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        size = report.size_optimization
        assert size.total_context_size_tokens > 0
        assert 0 <= size.optimization_potential_percentage <= 1
        assert 0 <= size.critical_context_percentage <= 1
        assert size.cleanup_impact_tokens >= 0
        assert 0 <= size.usage_based_optimization_score <= 1
        assert 0 <= size.content_value_density <= 1
        
        # Test that critical + optimization potential <= 1 (roughly)
        assert size.critical_context_percentage + size.optimization_potential_percentage <= 1.1
        
        # Test health color determination
        assert size.overall_size_health in HealthColor
    
    @pytest.mark.asyncio
    async def test_cli_dashboard_formatting(self, dashboard, mock_context_data):
        """Test CLI dashboard formatting."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        cli_output = await dashboard.display_health_dashboard(report, format="cli")
        
        # Check that output contains expected sections
        assert "COMPREHENSIVE CONTEXT HEALTH DASHBOARD" in cli_output
        assert "🎯 FOCUS METRICS" in cli_output
        assert "🧹 REDUNDANCY ANALYSIS" in cli_output
        assert "⏱️ RECENCY INDICATORS" in cli_output
        assert "📈 SIZE OPTIMIZATION" in cli_output
        
        # Check for health color indicators
        assert any(color.value in cli_output for color in HealthColor)
        
        # Check for tree structure indicators
        assert "├─" in cli_output
        assert "└─" in cli_output
    
    @pytest.mark.asyncio
    async def test_json_dashboard_export(self, dashboard, mock_context_data):
        """Test JSON dashboard export."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        json_output = await dashboard.display_health_dashboard(report, format="json")
        
        # Verify it's valid JSON
        data = json.loads(json_output)
        
        # Check required top-level keys
        assert "focus_metrics" in data
        assert "redundancy_analysis" in data
        assert "recency_indicators" in data
        assert "size_optimization" in data
        assert "analysis_timestamp" in data
        assert "confidence_score" in data
    
    @pytest.mark.asyncio
    async def test_web_dashboard_formatting(self, dashboard, mock_context_data):
        """Test web dashboard formatting."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        web_output = await dashboard.display_health_dashboard(report, format="web")
        
        # Check that output contains HTML structure
        assert "<div" in web_output
        assert "</div>" in web_output
        assert "<h2>" in web_output or "<h3>" in web_output
        assert "Overall Score:" in web_output
    
    def test_health_color_determination(self):
        """Test health color determination logic."""
        # Test excellent health
        excellent_metrics = FocusMetrics(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
        assert excellent_metrics.overall_focus_health == HealthColor.EXCELLENT
        
        # Test good health
        good_metrics = FocusMetrics(0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7)
        assert good_metrics.overall_focus_health == HealthColor.GOOD
        
        # Test poor health
        poor_metrics = FocusMetrics(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        assert poor_metrics.overall_focus_health == HealthColor.POOR
        
        # Test critical health
        critical_metrics = FocusMetrics(0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2)
        assert critical_metrics.overall_focus_health == HealthColor.CRITICAL
    
    @pytest.mark.asyncio
    async def test_optimization_recommendations(self, dashboard, mock_context_data):
        """Test optimization recommendations generation."""
        report = await dashboard.generate_comprehensive_health_report(
            context_data=mock_context_data
        )
        
        recommendations = report.optimization_recommendations
        assert isinstance(recommendations, list)
        
        # Check recommendation structure
        for rec in recommendations:
            assert "category" in rec
            assert "priority" in rec
            assert "action" in rec
            assert "estimated_impact" in rec
            assert rec["priority"] in ["high", "medium", "low"]
    
    @pytest.mark.asyncio
    async def test_error_handling(self, dashboard):
        """Test error handling with invalid data."""
        # Test with empty context data
        report = await dashboard.generate_comprehensive_health_report(
            context_data={}
        )
        assert isinstance(report, ComprehensiveHealthReport)
        assert report.confidence_score <= 0.5  # Should have low confidence
        
        # Test with None context data
        report = await dashboard.generate_comprehensive_health_report(
            context_data=None
        )
        assert isinstance(report, ComprehensiveHealthReport)
    
    @pytest.mark.asyncio
    async def test_content_analysis_helpers(self, dashboard):
        """Test content analysis helper methods."""
        # Test current work item detection
        current_work_item = {"content": "TODO: implement feature", "type": "todo"}
        assert dashboard._is_current_work_item(current_work_item)
        
        # Test important item detection
        important_item = {"content": "CRITICAL: fix security issue", "priority": "high"}
        assert dashboard._is_important_item(important_item)
        
        # Test active task detection
        active_task = {"content": "Need to implement dashboard", "status": "pending"}
        assert dashboard._is_active_task(active_task)
        
        completed_task = {"content": "Implement feature - DONE", "status": "completed"}
        assert not dashboard._is_active_task(completed_task)
        
        # Test clear action detection
        clear_action_item = {"content": "Step 1: Create the file structure"}
        assert dashboard._has_clear_action(clear_action_item)
    
    @pytest.mark.asyncio
    async def test_fallback_health_report(self, dashboard):
        """Test fallback health report creation."""
        fallback_report = await dashboard._create_fallback_health_report()
        
        assert isinstance(fallback_report, ComprehensiveHealthReport)
        assert fallback_report.confidence_score <= 0.5
        assert fallback_report.analysis_timestamp is not None
        
        # Check that all metrics are initialized with safe defaults
        assert 0 <= fallback_report.overall_health_score <= 1


class TestHealthColorLogic:
    """Test suite for health color determination logic."""
    
    def test_focus_health_colors(self):
        """Test focus metrics health color determination."""
        # Test boundary conditions
        test_cases = [
            (0.8, HealthColor.EXCELLENT),   # At boundary
            (0.85, HealthColor.EXCELLENT),  # Above boundary
            (0.6, HealthColor.GOOD),        # At boundary
            (0.75, HealthColor.GOOD),       # Above boundary
            (0.3, HealthColor.POOR),        # At boundary
            (0.45, HealthColor.POOR),       # Above boundary
            (0.29, HealthColor.CRITICAL),   # Below boundary
            (0.1, HealthColor.CRITICAL),    # Well below boundary
        ]
        
        for avg_score, expected_color in test_cases:
            metrics = FocusMetrics(
                avg_score, avg_score, avg_score, avg_score, 
                avg_score, avg_score, avg_score
            )
            assert metrics.overall_focus_health == expected_color, f"Score {avg_score} should be {expected_color.name}"
    
    def test_redundancy_health_colors(self):
        """Test redundancy analysis health color determination."""
        test_cases = [
            (0.05, HealthColor.EXCELLENT),   # Low redundancy
            (0.15, HealthColor.GOOD),        # Moderate redundancy
            (0.35, HealthColor.POOR),        # High redundancy
            (0.6, HealthColor.CRITICAL),     # Very high redundancy
        ]
        
        for redundancy_percentage, expected_color in test_cases:
            analysis = RedundancyAnalysis(
                duplicate_content_percentage=redundancy_percentage,
                stale_context_percentage=0.1,
                redundant_files_count=0,
                obsolete_todos_count=0,
                usage_redundancy_score=0.2,
                content_overlap_analysis={},
                elimination_opportunity=0.3
            )
            assert analysis.overall_redundancy_health == expected_color
    
    def test_recency_health_colors(self):
        """Test recency indicators health color determination."""
        test_cases = [
            (0.5, 0.3, HealthColor.EXCELLENT),  # 80% current relevance
            (0.4, 0.3, HealthColor.GOOD),       # 70% current relevance
            (0.3, 0.2, HealthColor.POOR),       # 50% current relevance
            (0.1, 0.1, HealthColor.CRITICAL),   # 20% current relevance
        ]
        
        for fresh_pct, recent_pct, expected_color in test_cases:
            indicators = RecencyIndicators(
                fresh_context_percentage=fresh_pct,
                recent_context_percentage=recent_pct,
                aging_context_percentage=1.0 - fresh_pct - recent_pct - 0.1,
                stale_context_percentage=0.1,
                usage_weighted_freshness=0.5,
                session_relevance_score=0.6,
                content_lifecycle_analysis={}
            )
            assert indicators.overall_recency_health == expected_color
    
    def test_size_optimization_health_colors(self):
        """Test size optimization metrics health color determination."""
        test_cases = [
            (0.1, HealthColor.EXCELLENT),    # Low optimization potential
            (0.2, HealthColor.GOOD),         # Moderate optimization potential
            (0.4, HealthColor.POOR),         # High optimization potential
            (0.6, HealthColor.CRITICAL),     # Very high optimization potential
        ]
        
        for optimization_pct, expected_color in test_cases:
            metrics = SizeOptimizationMetrics(
                total_context_size_tokens=1000,
                optimization_potential_percentage=optimization_pct,
                critical_context_percentage=1.0 - optimization_pct,
                cleanup_impact_tokens=int(1000 * optimization_pct),
                usage_based_optimization_score=0.3,
                content_value_density=0.6,
                optimization_risk_assessment={}
            )
            assert metrics.overall_size_health == expected_color


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__])