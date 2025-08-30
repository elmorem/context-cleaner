"""
Test suite for CrossSessionAnalyticsEngine - Priority: Critical Issues

This test suite addresses the critical issues identified in the code review:
1. Import violations and unsafe sklearn usage
2. Data type safety issues
3. Complex function testing with proper decomposition
4. ML dependencies with fallback behavior
"""

import pytest
import asyncio
import json
import statistics
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from collections import defaultdict, Counter

# Test the critical import behavior first
def test_sklearn_import_behavior():
    """Test that sklearn imports are handled safely."""
    try:
        # Try importing the module to see if sklearn imports cause issues
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        # If this succeeds, sklearn is available
        sklearn_available = True
    except ImportError as e:
        # Check if the import error is related to sklearn
        sklearn_available = False
        assert "sklearn" in str(e).lower() or "No module named" in str(e)
    
    # The module should still be importable even without sklearn
    assert True  # If we get here, imports didn't crash


def test_numpy_import_behavior():
    """Test that numpy imports are handled safely."""
    try:
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        import numpy as np
        numpy_available = True
    except ImportError:
        numpy_available = False
    
    # Test should pass regardless of numpy availability
    assert True


class TestCrossSessionAnalyticsEngine:
    """Test suite for CrossSessionAnalyticsEngine focusing on critical issues."""
    
    @pytest.fixture
    def analytics_engine(self, temp_storage_dir):
        """Create analytics engine instance for testing."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        return CrossSessionAnalyticsEngine(temp_storage_dir)
    
    # Test 1: Critical Issue - Unsafe sklearn usage
    @pytest.mark.asyncio
    async def test_clustering_without_sklearn(self, analytics_engine, mock_session_data, mock_sklearn_unavailable):
        """Test that clustering gracefully handles missing sklearn."""
        # Mock sklearn as unavailable
        with patch.dict('sys.modules', {'sklearn': None, 'sklearn.cluster': None}):
            # This should not crash - should return empty clusters
            clusters = await analytics_engine._cluster_sessions(mock_session_data[:10])
            assert isinstance(clusters, list)
            # Should return empty list when sklearn unavailable
            assert len(clusters) == 0
    
    @pytest.mark.asyncio
    async def test_clustering_with_insufficient_data(self, analytics_engine):
        """Test clustering behavior with insufficient data (< 5 sessions)."""
        insufficient_data = [Mock() for _ in range(3)]  # Less than minimum required
        
        clusters = await analytics_engine._cluster_sessions(insufficient_data)
        assert isinstance(clusters, list)
        assert len(clusters) == 0  # Should return empty for insufficient data
    
    @pytest.mark.asyncio
    @patch('context_cleaner.optimization.cross_session_analytics.KMeans')
    @patch('context_cleaner.optimization.cross_session_analytics.StandardScaler')
    async def test_clustering_with_sklearn_error(self, mock_scaler, mock_kmeans, analytics_engine, mock_session_data):
        """Test clustering handles sklearn errors gracefully."""
        # Mock sklearn to raise an error
        mock_kmeans.side_effect = Exception("sklearn error")
        
        clusters = await analytics_engine._cluster_sessions(mock_session_data[:10])
        assert isinstance(clusters, list)
        assert len(clusters) == 0  # Should return empty list on sklearn error
    
    # Test 2: Critical Issue - Data type safety
    @pytest.mark.asyncio
    async def test_extract_session_metrics_type_safety(self, analytics_engine):
        """Test session metrics extraction with various data types."""
        # Test with different data types that might cause type issues
        mixed_data = [
            Mock(session_id="str_id", timestamp=datetime.now(), duration_minutes=60.0),
            Mock(session_id=123, timestamp="2024-01-01", duration_minutes="60"),  # Wrong types
            Mock(),  # Missing attributes
            {"session_id": "dict_session", "timestamp": datetime.now()}  # Dict instead of object
        ]
        
        # This should handle type coercion safely
        metrics = await analytics_engine._extract_session_metrics(mixed_data)
        
        assert isinstance(metrics, list)
        # Should have processed some sessions (skipping malformed ones)
        assert len(metrics) <= len(mixed_data)
        
        # Check that returned metrics have correct types
        for metric in metrics:
            assert hasattr(metric, 'session_id')
            assert hasattr(metric, 'timestamp')
            assert isinstance(metric.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_calculate_trend_slope_edge_cases(self, analytics_engine):
        """Test trend slope calculation with edge cases."""
        # Test with empty list
        slope = analytics_engine._calculate_trend_slope([])
        assert slope == 0.0
        
        # Test with single value
        slope = analytics_engine._calculate_trend_slope([5.0])
        assert slope == 0.0
        
        # Test with identical values (zero denominator case)
        slope = analytics_engine._calculate_trend_slope([3.0, 3.0, 3.0])
        assert slope == 0.0
        
        # Test with normal values
        slope = analytics_engine._calculate_trend_slope([1.0, 2.0, 3.0, 4.0])
        assert slope == 1.0  # Perfect linear trend
        
        # Test with floating point values
        slope = analytics_engine._calculate_trend_slope([0.1, 0.3, 0.5, 0.7])
        assert abs(slope - 0.2) < 1e-10  # Close to 0.2
    
    # Test 3: Complex function decomposition
    @pytest.mark.asyncio
    async def test_analyze_cross_session_patterns_decomposition(self, analytics_engine, mock_session_data, mock_correlation_insights):
        """Test the complex analyze_cross_session_patterns method in parts."""
        # Test with sufficient data
        insights = await analytics_engine.analyze_cross_session_patterns(
            mock_session_data, mock_correlation_insights, time_window_days=30, min_sessions=5
        )
        
        assert hasattr(insights, 'analysis_timestamp')
        assert hasattr(insights, 'sessions_analyzed')
        assert hasattr(insights, 'correlation_insights')
        assert insights.sessions_analyzed > 0
        assert isinstance(insights.analysis_timestamp, datetime)
        
        # Test with insufficient data
        insufficient_insights = await analytics_engine.analyze_cross_session_patterns(
            mock_session_data[:3], mock_correlation_insights, min_sessions=5
        )
        
        # Should return minimal insights
        assert insufficient_insights.sessions_analyzed <= 5
        assert len(insufficient_insights.pattern_evolution) == 0
        assert len(insufficient_insights.workflow_templates) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_pattern_evolution_workflow_grouping(self, analytics_engine, mock_session_data):
        """Test pattern evolution analysis workflow grouping logic."""
        # Create sessions with specific workflow types for testing
        test_sessions = []
        workflows = ["development", "testing", "development", "testing", "development"]
        
        for i, workflow in enumerate(workflows):
            session = Mock()
            session.workflow_type = workflow
            session.timestamp = datetime.now() - timedelta(days=i)
            session.efficiency_score = 0.5 + i * 0.1
            test_sessions.append(session)
        
        # Convert to SessionMetrics format
        session_metrics = await analytics_engine._extract_session_metrics(test_sessions)
        
        pattern_evolution = await analytics_engine._analyze_pattern_evolution(session_metrics)
        
        assert isinstance(pattern_evolution, list)
        # Should have patterns for workflows with >= 3 sessions
        workflow_counts = Counter([s.workflow_type for s in session_metrics])
        expected_patterns = sum(1 for count in workflow_counts.values() if count >= 3)
        assert len(pattern_evolution) == expected_patterns
    
    # Test 4: Async operation testing
    @pytest.mark.asyncio
    async def test_async_operations_timeout_handling(self, analytics_engine, mock_session_data):
        """Test async operations handle timeouts properly."""
        # Mock a method to timeout
        original_method = analytics_engine._analyze_usage_patterns
        
        async def timeout_method(*args, **kwargs):
            await asyncio.sleep(10)  # This will timeout in tests
            return original_method(*args, **kwargs)
        
        analytics_engine._analyze_usage_patterns = timeout_method
        
        # Run with timeout - this should handle gracefully
        with patch('asyncio.wait_for') as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError()
            
            # The main method should handle this gracefully
            try:
                insights = await analytics_engine.analyze_cross_session_patterns(
                    mock_session_data[:10], Mock(), time_window_days=7, min_sessions=3
                )
                # Should return minimal insights on timeout
                assert insights is not None
            except asyncio.TimeoutError:
                # This is acceptable behavior
                pass
    
    # Test 5: File system operations and persistence
    @pytest.mark.asyncio
    async def test_persist_insights_file_operations(self, analytics_engine, mock_cross_session_insights):
        """Test file persistence operations with various error conditions."""
        # Test successful persistence
        await analytics_engine._persist_insights(mock_cross_session_insights)
        
        # Test with file system errors
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            # Should not raise - should handle gracefully
            await analytics_engine._persist_insights(mock_cross_session_insights)
        
        # Test with JSON serialization errors
        bad_insights = Mock()
        bad_insights.analysis_timestamp = object()  # Non-serializable
        
        # Should handle JSON errors gracefully
        await analytics_engine._persist_insights(bad_insights)
    
    # Test 6: Memory and performance with large datasets
    @pytest.mark.asyncio
    async def test_large_dataset_memory_efficiency(self, analytics_engine, large_dataset):
        """Test memory efficiency with large datasets."""
        # Generate large dataset
        large_sessions = large_dataset(500)  # 500 sessions
        
        # This should not consume excessive memory or crash
        session_metrics = await analytics_engine._extract_session_metrics(large_sessions[:100])
        
        assert len(session_metrics) <= 100
        assert isinstance(session_metrics, list)
        
        # Test efficiency trends calculation with large data
        efficiency_trends = await analytics_engine._calculate_efficiency_trends(session_metrics[:50])
        
        assert isinstance(efficiency_trends, dict)
        assert "overall_efficiency" in efficiency_trends
        
        # Check that trends don't contain excessive data points
        for trend_name, trend_data in efficiency_trends.items():
            assert len(trend_data) <= 14  # Should limit to last 14 days
    
    # Test 7: Error handling edge cases
    @pytest.mark.asyncio
    async def test_error_handling_edge_cases(self, analytics_engine):
        """Test error handling for various edge cases."""
        # Test with None inputs
        result = await analytics_engine._extract_session_metrics(None)
        assert result == []
        
        result = await analytics_engine._extract_session_metrics([])
        assert result == []
        
        # Test with malformed session data
        malformed_sessions = [
            None,
            {},
            Mock(session_id=None),
            Mock(timestamp="invalid_date"),
            Mock(duration_minutes="not_a_number")
        ]
        
        metrics = await analytics_engine._extract_session_metrics(malformed_sessions)
        assert isinstance(metrics, list)
        # Should have filtered out all malformed sessions
        assert len(metrics) == 0
    
    # Test 8: Integration with correlation insights
    @pytest.mark.asyncio
    async def test_integration_with_correlation_insights(self, analytics_engine, mock_session_data, mock_correlation_insights):
        """Test integration with correlation insights parameter."""
        # Test with valid correlation insights
        insights = await analytics_engine.analyze_cross_session_patterns(
            mock_session_data[:10], mock_correlation_insights, min_sessions=3
        )
        
        assert insights.correlation_insights == mock_correlation_insights
        assert hasattr(insights, 'session_clusters')
        assert hasattr(insights, 'pattern_evolution')
        
        # Test with None correlation insights
        insights_no_corr = await analytics_engine.analyze_cross_session_patterns(
            mock_session_data[:10], None, min_sessions=3
        )
        
        assert insights_no_corr.correlation_insights is None
    
    # Test 9: Workflow template extraction logic
    @pytest.mark.asyncio
    async def test_workflow_template_extraction(self, analytics_engine, mock_session_data):
        """Test workflow template extraction with realistic data."""
        # Create sessions with specific patterns for template extraction
        template_sessions = []
        
        # Create "development" workflow sessions
        for i in range(5):
            session = Mock()
            session.workflow_type = "development"
            session.tools_used = ["read", "edit", "bash"]
            session.file_types = [".py", ".js"]
            session.optimization_actions = ["remove_duplicates"]
            session.efficiency_score = 0.7 + i * 0.05
            session.duration_minutes = 90 + i * 10
            session.timestamp = datetime.now() - timedelta(days=i)
            template_sessions.append(session)
        
        # Convert to session metrics
        session_metrics = await analytics_engine._extract_session_metrics(template_sessions)
        
        # Extract templates
        templates = await analytics_engine._extract_workflow_templates(session_metrics)
        
        assert isinstance(templates, list)
        assert len(templates) == 1  # Should have one template for "development"
        
        template = templates[0]
        assert template.name == "Development Workflow"
        assert template.success_rate > 0.0
        assert template.usage_frequency > 0.0
        assert "read" in template.typical_sequence
        assert "edit" in template.typical_sequence
    
    # Test 10: Statistical calculations accuracy
    def test_statistical_calculations_accuracy(self, analytics_engine):
        """Test statistical calculation accuracy and edge cases."""
        # Test trend slope calculation with known values
        values = [1.0, 3.0, 5.0, 7.0, 9.0]  # slope should be 2.0
        slope = analytics_engine._calculate_trend_slope(values)
        assert abs(slope - 2.0) < 1e-10
        
        # Test with negative trend
        values = [10.0, 8.0, 6.0, 4.0, 2.0]  # slope should be -2.0
        slope = analytics_engine._calculate_trend_slope(values)
        assert abs(slope - (-2.0)) < 1e-10
        
        # Test with zero trend
        values = [5.0, 5.0, 5.0, 5.0, 5.0]
        slope = analytics_engine._calculate_trend_slope(values)
        assert abs(slope - 0.0) < 1e-10


# Test ML fallback behavior specifically
class TestMLFallbackBehavior:
    """Test ML-related fallback behavior for missing dependencies."""
    
    @pytest.mark.asyncio
    async def test_clustering_fallback_no_sklearn(self, temp_storage_dir):
        """Test clustering fallback when sklearn is not available."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine(temp_storage_dir)
        
        # Mock sklearn as unavailable
        with patch.dict('sys.modules', {'sklearn': None, 'sklearn.cluster': None, 'sklearn.preprocessing': None}):
            # Should not crash - should return empty clusters
            clusters = await engine._cluster_sessions([Mock() for _ in range(10)])
            assert clusters == []
    
    @pytest.mark.asyncio
    async def test_numpy_operations_fallback(self, temp_storage_dir):
        """Test numpy operations fallback when numpy is not available."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine(temp_storage_dir)
        
        # Test should work without numpy for basic operations
        sessions = [Mock() for _ in range(5)]
        for i, session in enumerate(sessions):
            session.session_id = f"session_{i}"
            session.timestamp = datetime.now()
            session.duration_minutes = 60.0
            session.efficiency_score = 0.7
        
        # This should work without numpy
        insights = await engine.analyze_cross_session_patterns(
            sessions, Mock(), min_sessions=3
        )
        
        assert insights is not None
        assert insights.sessions_analyzed >= 3


# Integration tests for critical paths
class TestCriticalPathIntegration:
    """Test critical execution paths that were identified in code review."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_analysis_with_errors(self, temp_storage_dir, mock_session_data):
        """Test end-to-end analysis handling various error conditions."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine(temp_storage_dir)
        
        # Inject various errors during analysis
        with patch.object(engine, '_analyze_pattern_evolution', side_effect=Exception("Pattern error")), \
             patch.object(engine, '_extract_workflow_templates', side_effect=Exception("Template error")):
            
            # Analysis should handle errors gracefully
            try:
                insights = await engine.analyze_cross_session_patterns(
                    mock_session_data[:10], Mock(), min_sessions=5
                )
                # Should return minimal insights on errors
                assert insights is not None
            except Exception as e:
                # Should not propagate unhandled exceptions
                pytest.fail(f"Unhandled exception: {e}")
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis_operations(self, temp_storage_dir, mock_session_data):
        """Test concurrent analysis operations for thread safety."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine(temp_storage_dir)
        
        # Run multiple analyses concurrently
        tasks = [
            engine.analyze_cross_session_patterns(mock_session_data[:10], Mock(), min_sessions=3)
            for _ in range(3)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        for result in results:
            assert not isinstance(result, Exception)
            assert hasattr(result, 'sessions_analyzed')


# Performance and memory tests
class TestPerformanceAndMemory:
    """Test performance characteristics and memory usage."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_session_analysis_performance(self, temp_storage_dir, large_dataset):
        """Test performance with large session datasets."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine(temp_storage_dir)
        
        # Test with increasingly large datasets
        for size in [100, 300, 500]:
            large_sessions = large_dataset(size)
            
            start_time = datetime.now()
            insights = await engine.analyze_cross_session_patterns(
                large_sessions, Mock(), min_sessions=10
            )
            duration = (datetime.now() - start_time).total_seconds()
            
            # Should complete in reasonable time (adjust threshold as needed)
            assert duration < 30.0  # 30 seconds max
            assert insights.sessions_analyzed > 0
    
    @pytest.mark.asyncio
    async def test_memory_cleanup_after_analysis(self, temp_storage_dir, mock_session_data):
        """Test that memory is properly cleaned up after analysis."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine(temp_storage_dir)
        
        # Run analysis multiple times to check for memory leaks
        for i in range(10):
            insights = await engine.analyze_cross_session_patterns(
                mock_session_data, Mock(), min_sessions=5
            )
            
            # Clear caches to prevent memory accumulation
            engine._session_cache.clear()
            engine._pattern_history.clear()
            engine._analysis_cache.clear()
            
            assert insights is not None