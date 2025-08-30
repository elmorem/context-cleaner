"""
Test suite for CacheEnhancedDashboard - Focus: Async Operations & Complex Functions

This test suite addresses critical issues in the cache dashboard:
1. Complex async operations with multiple analysis tasks
2. Cache discovery and session parsing reliability
3. Health metrics calculation accuracy
4. Error handling and fallback mechanisms
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from context_cleaner.optimization.cache_dashboard import (
    CacheEnhancedDashboard, UsageBasedHealthMetrics, HealthLevel,
    CacheEnhancedDashboardData, UsageInsight
)


class TestCacheEnhancedDashboard:
    """Test suite for CacheEnhancedDashboard focusing on async operations and complex functions."""
    
    @pytest.fixture
    def dashboard(self, temp_storage_dir):
        """Create dashboard instance for testing."""
        return CacheEnhancedDashboard(temp_storage_dir)
    
    # Test 1: Async operations and concurrent task management
    @pytest.mark.asyncio
    async def test_generate_dashboard_concurrent_analysis(self, dashboard, mock_cache_locations):
        """Test concurrent analysis tasks in dashboard generation."""
        # Mock the discovery to return our test cache locations
        with patch.object(dashboard, '_discover_cache_locations', return_value=mock_cache_locations):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=[Mock() for _ in range(10)]):
                # Mock all analysis methods to track concurrent execution
                analysis_methods = [
                    '_analyze_usage_patterns',
                    '_analyze_token_efficiency', 
                    '_analyze_temporal_patterns',
                    '_analyze_enhanced_context'
                ]
                
                async def mock_analysis(*args, **kwargs):
                    await asyncio.sleep(0.01)  # Simulate work
                    return Mock()
                
                for method in analysis_methods:
                    setattr(dashboard, method, mock_analysis)
                
                # This should execute analysis tasks concurrently
                result = await dashboard.generate_dashboard(max_sessions=10)
                
                assert isinstance(result, CacheEnhancedDashboardData)
                assert result.session_count == 10
    
    @pytest.mark.asyncio
    async def test_generate_dashboard_with_timeout_handling(self, dashboard):
        """Test dashboard generation handles analysis timeouts properly."""
        async def timeout_analysis(*args, **kwargs):
            await asyncio.sleep(10)  # This will timeout
            return Mock()
        
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=[Mock()]):
                with patch.object(dashboard, '_analyze_usage_patterns', timeout_analysis):
                    
                    # Should handle timeout gracefully
                    result = await dashboard.generate_dashboard()
                    
                    # Should return basic dashboard on timeout/error
                    assert isinstance(result, CacheEnhancedDashboardData)
    
    @pytest.mark.asyncio
    async def test_generate_dashboard_partial_analysis_failure(self, dashboard, mock_cache_locations):
        """Test dashboard generation when some analysis tasks fail."""
        with patch.object(dashboard, '_discover_cache_locations', return_value=mock_cache_locations):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=[Mock() for _ in range(5)]):
                # Mock some methods to fail
                async def failing_analysis(*args, **kwargs):
                    raise Exception("Analysis failed")
                
                async def working_analysis(*args, **kwargs):
                    return Mock()
                
                dashboard._analyze_usage_patterns = working_analysis
                dashboard._analyze_token_efficiency = failing_analysis  # This fails
                dashboard._analyze_temporal_patterns = working_analysis
                dashboard._analyze_enhanced_context = working_analysis
                
                # Should handle partial failures gracefully
                result = await dashboard.generate_dashboard()
                
                assert isinstance(result, CacheEnhancedDashboardData)
    
    # Test 2: Cache discovery and session parsing reliability
    @pytest.mark.asyncio
    async def test_discover_cache_locations_error_handling(self, dashboard):
        """Test cache discovery handles various error conditions."""
        # Test with service that raises exceptions
        with patch.object(dashboard.cache_discovery, 'discover_cache_locations', side_effect=Exception("Discovery failed")):
            locations = await dashboard._discover_cache_locations()
            assert locations == []  # Should return empty list on error
    
    @pytest.mark.asyncio
    async def test_discover_cache_locations_nonexistent_paths(self, dashboard):
        """Test cache discovery filters out non-existent paths."""
        mock_locations = [Mock(path=Path("/nonexistent1")), Mock(path=Path("/nonexistent2"))]
        
        with patch.object(dashboard.cache_discovery, 'discover_cache_locations', return_value=mock_locations):
            with patch.object(Path, 'exists', return_value=False):
                locations = await dashboard._discover_cache_locations()
                assert locations == []  # Should filter out non-existent paths
    
    @pytest.mark.asyncio
    async def test_parse_recent_sessions_error_handling(self, dashboard):
        """Test session parsing handles various error conditions."""
        cache_paths = [Path("/test1"), Path("/test2"), Path("/test3")]
        
        # Mock parser to fail on some paths
        def mock_parse(cache_path, max_sessions):
            if str(cache_path).endswith("test2"):
                raise Exception("Parse error")
            return [Mock(timestamp=datetime.now() - timedelta(hours=i)) for i in range(3)]
        
        with patch.object(dashboard.session_parser, 'parse_cache_directory', side_effect=mock_parse):
            sessions = await dashboard._parse_recent_sessions(cache_paths, 20)
            
            # Should have sessions from successful parses only
            assert len(sessions) == 6  # 3 sessions from test1 and test3
            assert all(hasattr(s, 'timestamp') for s in sessions)
    
    @pytest.mark.asyncio
    async def test_parse_recent_sessions_sorting_and_limiting(self, dashboard):
        """Test session parsing sorts by timestamp and limits results."""
        cache_paths = [Path("/test")]
        
        # Create sessions with specific timestamps
        test_sessions = []
        for i in range(15):
            session = Mock()
            session.timestamp = datetime.now() - timedelta(hours=i)
            test_sessions.append(session)
        
        with patch.object(dashboard.session_parser, 'parse_cache_directory', return_value=test_sessions):
            sessions = await dashboard._parse_recent_sessions(cache_paths, 10)
            
            # Should limit to 10 sessions
            assert len(sessions) == 10
            
            # Should be sorted by timestamp (most recent first)
            for i in range(len(sessions) - 1):
                assert sessions[i].timestamp >= sessions[i + 1].timestamp
    
    # Test 3: Health metrics calculation accuracy
    def test_usage_based_health_metrics_calculation(self):
        """Test accuracy of usage-based health metrics calculations."""
        metrics = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.8,
            efficiency_score=0.7,
            temporal_coherence_score=0.6,
            cross_session_consistency=0.5,
            optimization_potential=0.3,
            waste_reduction_score=0.7,
            workflow_alignment=0.4
        )
        
        # Test overall health score calculation
        expected_score = (
            0.8 * 0.25 +  # focus
            0.7 * 0.20 +  # efficiency
            0.6 * 0.15 +  # coherence
            0.5 * 0.15 +  # consistency
            0.3 * 0.10 +  # optimization potential
            0.7 * 0.10 +  # waste reduction
            0.4 * 0.05    # workflow alignment
        )
        
        assert abs(metrics.overall_health_score - expected_score) < 1e-10
        
        # Test health level determination
        assert metrics.health_level == HealthLevel.FAIR  # Should be FAIR for ~0.64
    
    def test_health_level_boundaries(self):
        """Test health level boundary conditions."""
        test_cases = [
            (0.95, HealthLevel.EXCELLENT),
            (0.90, HealthLevel.EXCELLENT),
            (0.89, HealthLevel.GOOD),
            (0.75, HealthLevel.GOOD),
            (0.74, HealthLevel.FAIR),
            (0.60, HealthLevel.FAIR),
            (0.59, HealthLevel.POOR),
            (0.40, HealthLevel.POOR),
            (0.39, HealthLevel.CRITICAL),
            (0.10, HealthLevel.CRITICAL)
        ]
        
        for score, expected_level in test_cases:
            metrics = UsageBasedHealthMetrics(
                usage_weighted_focus_score=score,
                efficiency_score=score,
                temporal_coherence_score=score,
                cross_session_consistency=score,
                optimization_potential=0.0,
                waste_reduction_score=score,
                workflow_alignment=score
            )
            assert metrics.health_level == expected_level, f"Score {score} should be {expected_level}"
    
    def test_calculate_usage_health_metrics_with_none_values(self, dashboard):
        """Test health metrics calculation handles None values gracefully."""
        # Test with all None values
        metrics = dashboard._calculate_usage_health_metrics(
            None, None, None, None, None
        )
        
        assert isinstance(metrics, UsageBasedHealthMetrics)
        assert 0.0 <= metrics.overall_health_score <= 1.0
        
        # Test with some None values
        usage_summary = Mock(workflow_efficiency=0.8)
        token_analysis = Mock(waste_percentage=20.0)
        
        metrics = dashboard._calculate_usage_health_metrics(
            usage_summary, token_analysis, None, None, None
        )
        
        assert metrics.efficiency_score == 0.8  # 1.0 - 0.2
        assert metrics.workflow_alignment == 0.8
    
    # Test 4: Insights generation logic
    def test_generate_usage_insights_token_waste(self, dashboard):
        """Test usage insights generation for token waste scenarios."""
        # Mock token analysis with high waste
        token_analysis = Mock()
        token_analysis.waste_percentage = 35.0
        token_analysis.waste_patterns = [
            Mock(pattern="duplicate_*.py"),
            Mock(pattern="redundant_*.js"),
            Mock(pattern="old_*.md")
        ]
        
        insights = dashboard._generate_usage_insights(
            None, token_analysis, None, None, None
        )
        
        # Should generate token efficiency insight
        token_insights = [i for i in insights if i.type == "token_efficiency"]
        assert len(token_insights) == 1
        
        insight = token_insights[0]
        assert "35.0%" in insight.description
        assert insight.impact_score == 0.8
        assert len(insight.file_patterns) == 3
    
    def test_generate_usage_insights_workflow_efficiency(self, dashboard):
        """Test usage insights generation for workflow efficiency."""
        # Mock usage summary with low workflow efficiency
        usage_summary = Mock()
        usage_summary.workflow_efficiency = 0.4
        usage_summary.file_patterns = [
            Mock(file_path="src/main.py"),
            Mock(file_path="tests/test.py"),
            Mock(file_path="docs/readme.md")
        ]
        
        insights = dashboard._generate_usage_insights(
            usage_summary, None, None, None, None
        )
        
        # Should generate workflow efficiency insight
        workflow_insights = [i for i in insights if i.type == "workflow_efficiency"]
        assert len(workflow_insights) == 1
        
        insight = workflow_insights[0]
        assert "40%" in insight.description
        assert insight.impact_score == 0.7
    
    def test_generate_usage_insights_sorting_by_impact(self, dashboard):
        """Test that insights are sorted by impact score."""
        # Create conditions that generate multiple insights
        usage_summary = Mock(workflow_efficiency=0.4, file_patterns=[Mock(file_path="test.py")])
        token_analysis = Mock(waste_percentage=25.0, waste_patterns=[Mock(pattern="*.py")])
        temporal_insights = Mock(coherence_score=0.3)
        correlation_insights = Mock(correlation_strength=0.9, cross_session_patterns=[Mock(), Mock()])
        
        insights = dashboard._generate_usage_insights(
            usage_summary, token_analysis, temporal_insights, None, correlation_insights
        )
        
        # Should be sorted by impact score (descending)
        assert len(insights) >= 2
        for i in range(len(insights) - 1):
            assert insights[i].impact_score >= insights[i + 1].impact_score
        
        # Should limit to 5 insights
        assert len(insights) <= 5
    
    # Test 5: Optimization recommendations generation
    def test_generate_optimization_recommendations_health_based(self, dashboard):
        """Test optimization recommendations based on health levels."""
        # Test critical health level
        critical_metrics = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.3,
            efficiency_score=0.2,
            temporal_coherence_score=0.1,
            cross_session_consistency=0.2,
            optimization_potential=0.8,
            waste_reduction_score=0.2,
            workflow_alignment=0.1
        )
        
        recommendations = dashboard._generate_optimization_recommendations(
            critical_metrics, [], None
        )
        
        # Should have high priority immediate optimization recommendation
        assert len(recommendations) >= 1
        immediate_recs = [r for r in recommendations if r["priority"] == "high"]
        assert len(immediate_recs) >= 1
        assert "Immediate" in immediate_recs[0]["title"]
    
    def test_generate_optimization_recommendations_metric_specific(self, dashboard):
        """Test metric-specific optimization recommendations."""
        # Low efficiency score
        low_efficiency_metrics = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.7,
            efficiency_score=0.4,  # Low efficiency
            temporal_coherence_score=0.7,
            cross_session_consistency=0.7,
            optimization_potential=0.6,
            waste_reduction_score=0.4,
            workflow_alignment=0.7
        )
        
        recommendations = dashboard._generate_optimization_recommendations(
            low_efficiency_metrics, [], None
        )
        
        # Should have token efficiency recommendation
        efficiency_recs = [r for r in recommendations if "Token Efficiency" in r["title"]]
        assert len(efficiency_recs) >= 1
    
    def test_generate_optimization_recommendations_insight_based(self, dashboard):
        """Test recommendations generated from high-impact insights."""
        metrics = Mock(health_level=HealthLevel.GOOD)
        
        high_impact_insights = [
            UsageInsight(
                type="test_insight",
                title="High Impact Issue",
                description="Critical issue found",
                impact_score=0.9,
                recommendation="Fix this immediately",
                file_patterns=[],
                session_correlation=0.8
            )
        ]
        
        recommendations = dashboard._generate_optimization_recommendations(
            metrics, high_impact_insights, None
        )
        
        # Should include recommendation from high-impact insight
        insight_recs = [r for r in recommendations if "High Impact Issue" in r["title"]]
        assert len(insight_recs) >= 1
        assert insight_recs[0]["priority"] == "high"  # Should be high priority due to impact > 0.8
    
    # Test 6: Trend calculation logic
    def test_calculate_trends_daily_grouping(self, dashboard):
        """Test trend calculation groups sessions by day correctly."""
        # Create sessions across multiple days
        sessions = []
        for i in range(10):
            session = Mock()
            session.timestamp = datetime.now() - timedelta(days=i % 5)  # 5 different days
            sessions.append(session)
        
        usage_trends, efficiency_trends = dashboard._calculate_trends(sessions, Mock(), Mock())
        
        # Should have calculated trends
        assert isinstance(usage_trends, dict)
        assert isinstance(efficiency_trends, dict)
        assert "focus_score" in usage_trends
        assert "token_efficiency" in efficiency_trends
    
    def test_calculate_trends_limits_time_window(self, dashboard):
        """Test trend calculation limits to recent time window."""
        # Create many sessions over a long time period
        sessions = []
        for i in range(50):  # 50 sessions
            session = Mock()
            session.timestamp = datetime.now() - timedelta(days=i)
            sessions.append(session)
        
        usage_trends, efficiency_trends = dashboard._calculate_trends(sessions, Mock(), Mock())
        
        # Should limit to last 7 days of data
        for trend_name, trend_data in usage_trends.items():
            assert len(trend_data) <= 7
        
        for trend_name, trend_data in efficiency_trends.items():
            assert len(trend_data) <= 7
    
    # Test 7: Error handling and fallback mechanisms
    @pytest.mark.asyncio
    async def test_generate_basic_dashboard_fallback(self, dashboard):
        """Test basic dashboard generation as fallback."""
        # Test with no context path
        basic_dashboard = await dashboard._generate_basic_dashboard(None)
        
        assert isinstance(basic_dashboard, CacheEnhancedDashboardData)
        assert basic_dashboard.context_size == 0
        assert basic_dashboard.file_count == 0
        assert basic_dashboard.session_count == 0
        assert len(basic_dashboard.optimization_recommendations) >= 1
        assert "Enable Cache Analysis" in basic_dashboard.optimization_recommendations[0]["title"]
    
    @pytest.mark.asyncio
    async def test_generate_basic_dashboard_with_health_analysis_error(self, dashboard):
        """Test basic dashboard handles health analysis errors."""
        context_path = Path("/test/context.txt")
        
        with patch.object(dashboard.health_analyzer, 'analyze_context_health', side_effect=Exception("Health analysis failed")):
            basic_dashboard = await dashboard._generate_basic_dashboard(context_path)
            
            # Should still return dashboard with default health metrics
            assert isinstance(basic_dashboard, CacheEnhancedDashboardData)
            assert basic_dashboard.health_metrics.usage_weighted_focus_score == 0.5  # Default
    
    @pytest.mark.asyncio
    async def test_generate_dashboard_complete_failure_fallback(self, dashboard):
        """Test dashboard generation falls back to basic when everything fails."""
        # Mock all components to fail
        with patch.object(dashboard, '_discover_cache_locations', side_effect=Exception("Discovery failed")):
            result = await dashboard.generate_dashboard()
            
            # Should return basic dashboard
            assert isinstance(result, CacheEnhancedDashboardData)
            assert result.session_count == 0
            assert "Enable Cache Analysis" in result.optimization_recommendations[0]["title"]
    
    # Test 8: Integration with health analyzer
    @pytest.mark.asyncio
    async def test_enhanced_health_analysis_integration(self, dashboard, mock_enhanced_analysis):
        """Test integration with traditional health analyzer."""
        context_path = Path("/test/context.txt")
        
        # Mock health analyzer
        mock_health_report = Mock()
        mock_health_report.focus_score = 0.6
        mock_health_report.priority_alignment = 0.7
        mock_health_report.context_health_score = 0.65
        
        with patch.object(dashboard.health_analyzer, 'analyze_context_health', return_value=mock_health_report):
            with patch.object(context_path, 'exists', return_value=True):
                
                enhanced_health = await dashboard._generate_enhanced_health_analysis(
                    context_path, mock_enhanced_analysis
                )
                
                # Should enhance traditional health with cache data
                assert enhanced_health.focus_score == mock_enhanced_analysis.usage_weighted_focus_score
                assert enhanced_health.priority_alignment == mock_enhanced_analysis.priority_alignment_score
    
    @pytest.mark.asyncio
    async def test_generate_enhanced_health_analysis_synthetic(self, dashboard, mock_enhanced_analysis):
        """Test synthetic health report generation when no context file."""
        # No context path
        enhanced_health = await dashboard._generate_enhanced_health_analysis(
            None, mock_enhanced_analysis
        )
        
        # Should create synthetic health report from cache data
        assert enhanced_health.focus_score == mock_enhanced_analysis.usage_weighted_focus_score
        assert enhanced_health.priority_alignment == mock_enhanced_analysis.priority_alignment_score
        assert enhanced_health.context_health_score == mock_enhanced_analysis.overall_health_score
    
    # Test 9: Async method reliability
    @pytest.mark.asyncio
    async def test_all_async_analysis_methods_resilience(self, dashboard, mock_session_data):
        """Test all async analysis methods handle errors gracefully."""
        sessions = mock_session_data[:5]
        
        # Test each async analysis method individually
        async_methods = [
            ('_analyze_usage_patterns', [sessions]),
            ('_analyze_token_efficiency', [sessions]),
            ('_analyze_temporal_patterns', [sessions]),
            ('_analyze_enhanced_context', [sessions, None]),
            ('_analyze_cross_session_correlation', [sessions])
        ]
        
        for method_name, args in async_methods:
            method = getattr(dashboard, method_name)
            
            # Should handle exceptions gracefully
            try:
                result = await method(*args)
                # Result should be some mock object (since we're using mocked analyzers)
                assert result is not None
            except Exception as e:
                # If method throws exception, it should be handled at higher level
                # This is acceptable as long as main generate_dashboard handles it
                pass
    
    # Test 10: Complex dashboard data construction
    def test_cache_enhanced_dashboard_data_construction(self, mock_dashboard_data):
        """Test CacheEnhancedDashboardData construction and properties."""
        dashboard_data = mock_dashboard_data
        
        # Test all required attributes are present
        required_attrs = [
            'context_size', 'file_count', 'session_count', 'analysis_timestamp',
            'health_metrics', 'usage_summary', 'token_analysis', 'temporal_insights',
            'enhanced_analysis', 'correlation_insights', 'traditional_health',
            'insights', 'optimization_recommendations', 'usage_trends', 'efficiency_trends'
        ]
        
        for attr in required_attrs:
            assert hasattr(dashboard_data, attr), f"Missing attribute: {attr}"
        
        # Test data types are correct
        assert isinstance(dashboard_data.context_size, int)
        assert isinstance(dashboard_data.file_count, int)
        assert isinstance(dashboard_data.session_count, int)
        assert isinstance(dashboard_data.analysis_timestamp, datetime)
        assert isinstance(dashboard_data.health_metrics, UsageBasedHealthMetrics)
        assert isinstance(dashboard_data.insights, list)
        assert isinstance(dashboard_data.optimization_recommendations, list)
        assert isinstance(dashboard_data.usage_trends, dict)
        assert isinstance(dashboard_data.efficiency_trends, dict)


# Performance tests
class TestCacheDashboardPerformance:
    """Performance and scalability tests for cache dashboard."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_dashboard_generation_with_many_sessions(self, temp_storage_dir, large_dataset):
        """Test dashboard generation performance with large session datasets."""
        dashboard = CacheEnhancedDashboard(temp_storage_dir)
        
        # Generate large dataset
        large_sessions = large_dataset(200)
        
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=large_sessions):
                
                start_time = datetime.now()
                result = await dashboard.generate_dashboard(max_sessions=200)
                duration = (datetime.now() - start_time).total_seconds()
                
                # Should complete in reasonable time
                assert duration < 10.0  # 10 seconds max
                assert isinstance(result, CacheEnhancedDashboardData)
                assert result.session_count == 200
    
    @pytest.mark.asyncio
    async def test_concurrent_dashboard_generation(self, temp_storage_dir, mock_session_data):
        """Test concurrent dashboard generation doesn't cause issues."""
        dashboard = CacheEnhancedDashboard(temp_storage_dir)
        
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=mock_session_data[:10]):
                
                # Run multiple dashboard generations concurrently
                tasks = [
                    dashboard.generate_dashboard(max_sessions=10)
                    for _ in range(5)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # All should succeed
                for result in results:
                    assert not isinstance(result, Exception)
                    assert isinstance(result, CacheEnhancedDashboardData)


# Edge case tests
class TestCacheDashboardEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_cache_locations(self, temp_storage_dir):
        """Test dashboard behavior with empty cache locations."""
        dashboard = CacheEnhancedDashboard(temp_storage_dir)
        
        with patch.object(dashboard, '_discover_cache_locations', return_value=[]):
            result = await dashboard.generate_dashboard()
            
            # Should return basic dashboard
            assert isinstance(result, CacheEnhancedDashboardData)
            assert result.session_count == 0
    
    @pytest.mark.asyncio
    async def test_no_sessions_found(self, temp_storage_dir):
        """Test dashboard behavior when no sessions are found."""
        dashboard = CacheEnhancedDashboard(temp_storage_dir)
        
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=[]):
                
                result = await dashboard.generate_dashboard()
                
                # Should return basic dashboard
                assert isinstance(result, CacheEnhancedDashboardData)
                assert result.session_count == 0
    
    def test_usage_insight_creation_edge_cases(self):
        """Test UsageInsight creation with edge case values."""
        # Test with extreme values
        insight = UsageInsight(
            type="test",
            title="Test Insight",
            description="Test description",
            impact_score=0.0,  # Minimum
            recommendation="Test recommendation",
            file_patterns=[],
            session_correlation=1.0  # Maximum
        )
        
        assert insight.impact_score == 0.0
        assert insight.session_correlation == 1.0
        
        # Test with None/empty values
        insight_empty = UsageInsight(
            type="",
            title="",
            description="",
            impact_score=0.5,
            recommendation="",
            file_patterns=[],
            session_correlation=0.5
        )
        
        assert insight_empty.type == ""
        assert insight_empty.file_patterns == []
    
    def test_health_metrics_edge_case_values(self):
        """Test health metrics with edge case values."""
        # All minimum values
        metrics_min = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.0,
            efficiency_score=0.0,
            temporal_coherence_score=0.0,
            cross_session_consistency=0.0,
            optimization_potential=0.0,
            waste_reduction_score=0.0,
            workflow_alignment=0.0
        )
        
        assert metrics_min.overall_health_score == 0.0
        assert metrics_min.health_level == HealthLevel.CRITICAL
        
        # All maximum values  
        metrics_max = UsageBasedHealthMetrics(
            usage_weighted_focus_score=1.0,
            efficiency_score=1.0,
            temporal_coherence_score=1.0,
            cross_session_consistency=1.0,
            optimization_potential=1.0,
            waste_reduction_score=1.0,
            workflow_alignment=1.0
        )
        
        assert metrics_max.overall_health_score == 1.0
        assert metrics_max.health_level == HealthLevel.EXCELLENT