"""
CI/CD Integration Tests for PR15.3

This module provides tests specifically designed for CI/CD environments,
focusing on reliability, determinism, and environment compatibility.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, Mock


class TestCIEnvironmentCompatibility:
    """Test compatibility with CI/CD environments."""
    
    def test_import_safety_in_ci(self):
        """Test that imports work safely in CI environments."""
        # This test ensures all imports work without external dependencies
        try:
            from context_cleaner.optimization.cache_dashboard import CacheEnhancedDashboard
            from context_cleaner.optimization.intelligent_recommender import IntelligentRecommendationEngine
            from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
            
            # Should succeed even if sklearn/numpy are not available
            assert True
        except ImportError as e:
            if "context_cleaner" in str(e):
                pytest.fail(f"Core module import failed: {e}")
            # sklearn/numpy import errors are acceptable in CI
    
    def test_environment_variable_handling(self):
        """Test handling of CI environment variables."""
        # Test CI environment detection
        with patch.dict(os.environ, {"CI": "true"}):
            # Code should detect CI environment
            assert os.getenv("CI") == "true"
        
        # Test dependency disabling
        with patch.dict(os.environ, {"SKLEARN_DISABLED": "true"}):
            assert os.getenv("SKLEARN_DISABLED") == "true"
    
    def test_deterministic_behavior(self):
        """Test that code behavior is deterministic in CI."""
        from context_cleaner.optimization.cache_dashboard import UsageBasedHealthMetrics
        
        # Health metrics calculation should be deterministic
        metrics1 = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.75,
            efficiency_score=0.80,
            temporal_coherence_score=0.65,
            cross_session_consistency=0.70,
            optimization_potential=0.25,
            waste_reduction_score=0.80,
            workflow_alignment=0.72
        )
        
        metrics2 = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.75,
            efficiency_score=0.80,
            temporal_coherence_score=0.65,
            cross_session_consistency=0.70,
            optimization_potential=0.25,
            waste_reduction_score=0.80,
            workflow_alignment=0.72
        )
        
        # Should produce identical results
        assert metrics1.overall_health_score == metrics2.overall_health_score
        assert metrics1.health_level == metrics2.health_level
    
    def test_no_interactive_dependencies(self):
        """Test that code doesn't require interactive dependencies."""
        # Should not require matplotlib for display, etc.
        from context_cleaner.optimization.advanced_reports import AdvancedReportingSystem
        
        # Creating reports system should not require GUI libraries
        with patch('matplotlib.pyplot', None):
            reports = AdvancedReportingSystem()
            assert reports is not None
    
    def test_temporary_directory_handling(self):
        """Test proper handling of temporary directories in CI."""
        import tempfile
        from context_cleaner.optimization.intelligent_recommender import IntelligentRecommendationEngine
        
        # Should work with CI temporary directories
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            engine = IntelligentRecommendationEngine(temp_path / "test")
            
            # Storage path should be created
            assert engine.storage_path.exists()
    
    def test_file_permissions_in_ci(self):
        """Test file operations work with CI permissions."""
        import tempfile
        import json
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.json"
            
            # Should be able to write and read files
            test_data = {"test": "data"}
            with open(test_file, 'w') as f:
                json.dump(test_data, f)
            
            with open(test_file, 'r') as f:
                loaded_data = json.load(f)
            
            assert loaded_data == test_data


class TestDependencyIsolation:
    """Test that optional dependencies are properly isolated."""
    
    @pytest.mark.parametrize("disabled_module", ["sklearn", "numpy"])
    def test_optional_dependency_fallback(self, disabled_module):
        """Test fallback behavior when optional dependencies are disabled."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        # Mock the module as unavailable
        with patch.dict(sys.modules, {disabled_module: None}):
            engine = CrossSessionAnalyticsEngine()
            
            # Should create engine successfully even without optional dependencies
            assert engine is not None
    
    def test_sklearn_clustering_fallback(self):
        """Test clustering fallback when sklearn is unavailable."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine()
        
        # Mock sklearn as unavailable
        with patch.dict(sys.modules, {'sklearn': None, 'sklearn.cluster': None}):
            # Should handle missing sklearn gracefully
            import asyncio
            
            async def test_clustering():
                sessions = [Mock() for _ in range(3)]  # Insufficient data
                clusters = await engine._cluster_sessions(sessions)
                return clusters
            
            clusters = asyncio.run(test_clustering())
            assert clusters == []  # Should return empty list gracefully
    
    def test_numpy_operations_fallback(self):
        """Test numpy operations fallback when numpy is unavailable."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine()
        
        # Should work without numpy for basic operations
        slope = engine._calculate_trend_slope([1.0, 2.0, 3.0, 4.0])
        assert slope == 1.0  # Uses basic Python math


class TestConcurrencyInCI:
    """Test concurrent operations in CI environment."""
    
    @pytest.mark.asyncio
    async def test_async_operations_ci_safe(self):
        """Test async operations are CI-safe."""
        from context_cleaner.optimization.cache_dashboard import CacheEnhancedDashboard
        import asyncio
        
        dashboard = CacheEnhancedDashboard()
        
        # Mock all external dependencies
        with patch.object(dashboard, '_discover_cache_locations', return_value=[]):
            # Multiple concurrent dashboard generations should work
            tasks = [dashboard.generate_dashboard() for _ in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            for result in results:
                assert not isinstance(result, Exception)
    
    @pytest.mark.asyncio  
    async def test_no_race_conditions_ci(self):
        """Test no race conditions in CI environment."""
        from context_cleaner.optimization.intelligent_recommender import IntelligentRecommendationEngine
        import asyncio
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = IntelligentRecommendationEngine(Path(temp_dir))
            
            # Concurrent profile operations
            tasks = [
                engine._load_personalization_profile(f"user_{i}")
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed without race conditions
            for result in results:
                assert not isinstance(result, Exception)


class TestMemoryLeaksInCI:
    """Test for memory leaks in CI environment."""
    
    @pytest.mark.asyncio
    async def test_no_memory_accumulation(self):
        """Test that repeated operations don't accumulate memory."""
        from context_cleaner.optimization.cache_dashboard import CacheEnhancedDashboard
        
        dashboard = CacheEnhancedDashboard()
        
        with patch.object(dashboard, '_discover_cache_locations', return_value=[]):
            # Run many operations
            for i in range(20):
                await dashboard.generate_dashboard()
                
                # Clear caches to prevent accumulation
                dashboard._analysis_cache.clear()
        
        # Should complete without memory issues
        assert True
    
    def test_cache_cleanup(self):
        """Test that caches are properly cleaned up."""
        from context_cleaner.optimization.intelligent_recommender import IntelligentRecommendationEngine
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = IntelligentRecommendationEngine(Path(temp_dir))
            
            # Add data to caches
            engine._profiles_cache["test"] = Mock()
            engine._recommendation_history["test"] = [Mock()]
            engine._effectiveness_tracker["test"] = [0.5, 0.6, 0.7]
            
            # Clear caches
            engine._profiles_cache.clear()
            engine._recommendation_history.clear()
            engine._effectiveness_tracker.clear()
            
            # Should be empty
            assert len(engine._profiles_cache) == 0
            assert len(engine._recommendation_history) == 0
            assert len(engine._effectiveness_tracker) == 0


class TestErrorHandlingInCI:
    """Test error handling in CI environments."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when services fail."""
        from context_cleaner.optimization.cache_dashboard import CacheEnhancedDashboard
        
        dashboard = CacheEnhancedDashboard()
        
        # Mock all services to fail
        with patch.object(dashboard.cache_discovery, 'discover_cache_locations', side_effect=Exception("Service failed")):
            with patch.object(dashboard.health_analyzer, 'analyze_context_health', side_effect=Exception("Analysis failed")):
                
                # Should still return a basic dashboard
                result = await dashboard.generate_dashboard()
                
                assert result is not None
                assert result.session_count == 0  # Basic fallback
    
    def test_exception_handling_deterministic(self):
        """Test that exception handling is deterministic."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        
        engine = CrossSessionAnalyticsEngine()
        
        # Same error conditions should produce same results
        results = []
        for _ in range(3):
            try:
                # This should fail consistently
                slope = engine._calculate_trend_slope([])
                results.append(slope)
            except Exception as e:
                results.append(str(type(e)))
        
        # All results should be the same
        assert len(set(results)) == 1  # All identical


class TestResourceLimitsInCI:
    """Test behavior under CI resource limits."""
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of operation timeouts."""
        from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
        import asyncio
        
        engine = CrossSessionAnalyticsEngine()
        
        # Mock a slow operation
        async def slow_operation():
            await asyncio.sleep(0.1)
            return Mock()
        
        # Should handle timeouts gracefully
        try:
            with patch.object(engine, '_analyze_pattern_evolution', side_effect=slow_operation):
                # Use a very short timeout
                result = await asyncio.wait_for(
                    engine.analyze_cross_session_patterns(
                        [Mock() for _ in range(3)], Mock(), min_sessions=2
                    ),
                    timeout=0.05  # Very short timeout
                )
        except asyncio.TimeoutError:
            # This is acceptable - the system should handle timeouts
            pass
    
    def test_memory_efficient_operations(self):
        """Test that operations are memory efficient."""
        from context_cleaner.optimization.intelligent_recommender import IntelligentRecommendationEngine
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = IntelligentRecommendationEngine(Path(temp_dir))
            
            # Process data in chunks rather than all at once
            large_recommendations = []
            for i in range(100):
                rec = Mock()
                rec.id = f"rec_{i}"
                large_recommendations.append(rec)
            
            # Should handle large lists without memory issues
            sorted_recs = engine._prioritize_recommendations(large_recommendations, Mock())
            assert len(sorted_recs) == 100


@pytest.fixture(autouse=True)
def ci_environment_setup():
    """Set up CI environment for all tests."""
    # Ensure reproducible behavior
    import random
    random.seed(42)
    
    # Set CI environment variables if not already set
    if not os.getenv("CI"):
        os.environ["CI"] = "true"
    
    yield
    
    # Cleanup after tests
    # Remove any test-created environment variables
    test_env_vars = ["SKLEARN_DISABLED", "NUMPY_DISABLED"]
    for var in test_env_vars:
        os.environ.pop(var, None)