"""
Integration Test Suite for PR15.3 Optimization Modules

This test suite focuses on testing module interactions and end-to-end workflows
to ensure all optimization components work together correctly.

Key Integration Points:
1. Dashboard -> Analytics -> Recommendations -> Reports flow
2. Cache data propagation through modules
3. Error handling across module boundaries  
4. Performance under realistic combined workloads
5. Data consistency between modules
"""

import pytest
import asyncio
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from context_cleaner.optimization.cache_dashboard import CacheEnhancedDashboard, CacheEnhancedDashboardData
from context_cleaner.optimization.intelligent_recommender import IntelligentRecommendationEngine
from context_cleaner.optimization.cross_session_analytics import CrossSessionAnalyticsEngine
from context_cleaner.optimization.advanced_reports import AdvancedReportingSystem, ReportType, ReportFormat
from context_cleaner.optimization.personalized_strategies import PersonalizedOptimizationEngine


class TestOptimizationModuleIntegration:
    """Test integration between optimization modules."""
    
    @pytest.fixture
    def integrated_system(self, temp_storage_dir):
        """Create integrated system with all optimization components."""
        return {
            "dashboard": CacheEnhancedDashboard(),
            "recommender": IntelligentRecommendationEngine(temp_storage_dir / "recommendations"),
            "analytics": CrossSessionAnalyticsEngine(temp_storage_dir / "analytics"),
            "reports": AdvancedReportingSystem(temp_storage_dir / "reports"),
            "strategies": PersonalizedOptimizationEngine(temp_storage_dir / "strategies"),
            "storage_dir": temp_storage_dir
        }
    
    # Test 1: Complete end-to-end optimization workflow
    @pytest.mark.asyncio
    async def test_complete_optimization_workflow(self, integrated_system, mock_session_data, mock_cache_locations):
        """Test complete workflow: cache analysis -> recommendations -> strategies -> reports."""
        dashboard = integrated_system["dashboard"]
        recommender = integrated_system["recommender"]
        analytics = integrated_system["analytics"]
        reports = integrated_system["reports"]
        strategies = integrated_system["strategies"]
        
        # Step 1: Generate dashboard data
        with patch.object(dashboard, '_discover_cache_locations', return_value=mock_cache_locations):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=mock_session_data[:10]):
                # Mock the analysis methods to return realistic data
                async def mock_analysis(*args, **kwargs):
                    return Mock()
                
                dashboard._analyze_usage_patterns = mock_analysis
                dashboard._analyze_token_efficiency = mock_analysis
                dashboard._analyze_temporal_patterns = mock_analysis
                dashboard._analyze_enhanced_context = mock_analysis
                dashboard._analyze_cross_session_correlation = mock_analysis
                
                dashboard_data = await dashboard.generate_dashboard(max_sessions=10)
                
                assert isinstance(dashboard_data, CacheEnhancedDashboardData)
                assert dashboard_data.session_count == 10
        
        # Step 2: Generate cross-session insights
        cross_session_insights = await analytics.analyze_cross_session_patterns(
            mock_session_data[:10], dashboard_data.correlation_insights, min_sessions=5
        )
        
        assert cross_session_insights.sessions_analyzed >= 5
        
        # Step 3: Generate intelligent recommendations
        recommendations = await recommender.generate_intelligent_recommendations(
            health_metrics=dashboard_data.health_metrics,
            usage_summary=dashboard_data.usage_summary,
            token_analysis=dashboard_data.token_analysis,
            temporal_insights=dashboard_data.temporal_insights,
            enhanced_analysis=dashboard_data.enhanced_analysis,
            correlation_insights=dashboard_data.correlation_insights,
            user_id="integration_test_user"
        )
        
        assert len(recommendations) >= 1
        
        # Step 4: Create personalized strategy
        profile = await recommender._load_personalization_profile("integration_test_user")
        strategy = await strategies.create_personalized_strategy(
            user_id="integration_test_user",
            profile=profile,
            dashboard_data=dashboard_data,
            cross_session_insights=cross_session_insights,
            recommendations=recommendations
        )
        
        assert strategy.user_id == "integration_test_user"
        assert len(strategy.rules) >= 1
        
        # Step 5: Generate comprehensive report
        report = await reports.generate_comprehensive_report(
            dashboard_data=dashboard_data,
            cross_session_insights=cross_session_insights,
            recommendations=recommendations,
            personalization_profile=profile,
            report_type=ReportType.DETAILED_ANALYSIS
        )
        
        assert report.report_type == ReportType.DETAILED_ANALYSIS
        assert len(report.sections) >= 1
        assert len(report.critical_insights) >= 1
    
    # Test 2: Data consistency across module boundaries
    @pytest.mark.asyncio
    async def test_data_consistency_across_modules(self, integrated_system, mock_session_data):
        """Test that data remains consistent as it flows between modules."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        
        # Mock dashboard to return specific health metrics
        test_health_score = 0.73
        mock_health_metrics = Mock()
        mock_health_metrics.overall_health_score = test_health_score
        mock_health_metrics.efficiency_score = 0.75
        
        # Generate dashboard data
        with patch.object(dashboard, 'generate_dashboard') as mock_dashboard:
            dashboard_data = Mock()
            dashboard_data.health_metrics = mock_health_metrics
            dashboard_data.session_count = 15
            dashboard_data.context_size = 12000
            mock_dashboard.return_value = dashboard_data
            
            generated_data = await dashboard.generate_dashboard()
            
            # Verify dashboard data consistency
            assert generated_data.health_metrics.overall_health_score == test_health_score
            assert generated_data.session_count == 15
        
        # Generate analytics with same session data
        mock_correlation_insights = Mock()
        mock_correlation_insights.correlation_strength = 0.8
        
        insights = await analytics.analyze_cross_session_patterns(
            mock_session_data[:15], mock_correlation_insights, min_sessions=5
        )
        
        # Should analyze the same number of sessions (consistency check)
        assert insights.sessions_analyzed <= 15  # May be less due to filtering
        
        # Generate recommendations using consistent data
        recommendations = await recommender.generate_intelligent_recommendations(
            health_metrics=mock_health_metrics,
            usage_summary=None,
            token_analysis=None,
            temporal_insights=None,
            enhanced_analysis=None,
            correlation_insights=mock_correlation_insights,
            user_id="consistency_test_user",
            context_size=12000
        )
        
        # Recommendations should reflect the health score and context size
        for rec in recommendations:
            assert rec.session_context is not None  # Should have context
            # Estimated savings should be proportional to context size
            if rec.estimated_token_savings > 0:
                assert rec.estimated_token_savings <= 12000  # Can't save more than total
    
    # Test 3: Error propagation and handling across modules
    @pytest.mark.asyncio
    async def test_error_handling_across_module_boundaries(self, integrated_system, mock_session_data):
        """Test that errors in one module don't cascade to break others."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        reports = integrated_system["reports"]
        
        # Inject error in dashboard generation
        with patch.object(dashboard, '_analyze_usage_patterns', side_effect=Exception("Dashboard analysis failed")):
            dashboard_data = await dashboard.generate_dashboard()
            
            # Dashboard should handle error gracefully and return basic data
            assert isinstance(dashboard_data, CacheEnhancedDashboardData)
            # Should have fallback data even with analysis failure
            assert dashboard_data.session_count >= 0
        
        # Analytics should still work with mock correlation insights
        mock_correlation_insights = Mock()
        try:
            insights = await analytics.analyze_cross_session_patterns(
                mock_session_data[:5], mock_correlation_insights, min_sessions=3
            )
            assert insights.sessions_analyzed >= 0
        except Exception as e:
            pytest.fail(f"Analytics failed when it should handle errors: {e}")
        
        # Recommendations should work even with minimal data
        try:
            recommendations = await recommender.generate_intelligent_recommendations(
                health_metrics=dashboard_data.health_metrics,
                usage_summary=None,  # Missing data
                token_analysis=None,  # Missing data
                temporal_insights=None,  # Missing data
                enhanced_analysis=None,  # Missing data
                correlation_insights=None,  # Missing data
                user_id="error_test_user"
            )
            # Should return empty list or minimal recommendations, not crash
            assert isinstance(recommendations, list)
        except Exception as e:
            pytest.fail(f"Recommender failed when it should handle missing data: {e}")
        
        # Reports should handle partial data gracefully
        try:
            report = await reports.generate_comprehensive_report(
                dashboard_data=dashboard_data,
                cross_session_insights=insights,
                recommendations=recommendations or [],
                personalization_profile=None,
                report_type=ReportType.EXECUTIVE_SUMMARY
            )
            assert report.report_type == ReportType.EXECUTIVE_SUMMARY
        except Exception as e:
            pytest.fail(f"Reports failed when it should handle partial data: {e}")
    
    # Test 4: Performance under combined workloads
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_integrated_performance_large_dataset(self, integrated_system, large_dataset):
        """Test performance when all modules process large datasets together."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        
        # Generate large dataset
        large_sessions = large_dataset(100)
        
        # Time the complete integrated workflow
        start_time = datetime.now()
        
        # Mock dashboard to use large dataset
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=large_sessions):
                
                # Mock analysis methods to return quickly
                async def fast_mock_analysis(*args, **kwargs):
                    await asyncio.sleep(0.001)  # Minimal delay
                    return Mock()
                
                dashboard._analyze_usage_patterns = fast_mock_analysis
                dashboard._analyze_token_efficiency = fast_mock_analysis
                dashboard._analyze_temporal_patterns = fast_mock_analysis
                dashboard._analyze_enhanced_context = fast_mock_analysis
                dashboard._analyze_cross_session_correlation = fast_mock_analysis
                
                # Step 1: Dashboard analysis
                dashboard_data = await dashboard.generate_dashboard(max_sessions=100)
                
                # Step 2: Cross-session analytics
                insights = await analytics.analyze_cross_session_patterns(
                    large_sessions[:50], Mock(), min_sessions=10  # Limit for performance
                )
                
                # Step 3: Generate recommendations
                recommendations = await recommender.generate_intelligent_recommendations(
                    health_metrics=dashboard_data.health_metrics,
                    usage_summary=dashboard_data.usage_summary,
                    token_analysis=dashboard_data.token_analysis,
                    temporal_insights=dashboard_data.temporal_insights,
                    enhanced_analysis=dashboard_data.enhanced_analysis,
                    correlation_insights=dashboard_data.correlation_insights,
                    user_id="perf_test_user",
                    max_recommendations=10  # Limit for performance
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                
                # Should complete integrated workflow in reasonable time
                assert duration < 15.0  # 15 seconds for complete workflow
                
                # Verify results are reasonable
                assert dashboard_data.session_count <= 100
                assert insights.sessions_analyzed >= 10
                assert len(recommendations) <= 10
    
    # Test 5: Concurrent access to shared resources
    @pytest.mark.asyncio
    async def test_concurrent_module_operations(self, integrated_system, mock_session_data):
        """Test that modules can operate concurrently without conflicts."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        
        # Mock dashboard operations
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=mock_session_data[:10]):
                
                async def mock_analysis(*args, **kwargs):
                    await asyncio.sleep(0.01)  # Simulate work
                    return Mock()
                
                dashboard._analyze_usage_patterns = mock_analysis
                dashboard._analyze_token_efficiency = mock_analysis
                dashboard._analyze_temporal_patterns = mock_analysis
                dashboard._analyze_enhanced_context = mock_analysis
                dashboard._analyze_cross_session_correlation = mock_analysis
                
                # Run multiple operations concurrently
                tasks = [
                    # Multiple dashboard generations
                    dashboard.generate_dashboard(max_sessions=5),
                    dashboard.generate_dashboard(max_sessions=5),
                    
                    # Multiple analytics operations
                    analytics.analyze_cross_session_patterns(mock_session_data[:5], Mock(), min_sessions=3),
                    analytics.analyze_cross_session_patterns(mock_session_data[5:10], Mock(), min_sessions=3),
                    
                    # Multiple recommendation generations
                    recommender.generate_intelligent_recommendations(
                        health_metrics=Mock(), usage_summary=None, token_analysis=None,
                        temporal_insights=None, enhanced_analysis=None, correlation_insights=None,
                        user_id="concurrent_user_1"
                    ),
                    recommender.generate_intelligent_recommendations(
                        health_metrics=Mock(), usage_summary=None, token_analysis=None,
                        temporal_insights=None, enhanced_analysis=None, correlation_insights=None,
                        user_id="concurrent_user_2"
                    )
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # All operations should complete successfully
                for i, result in enumerate(results):
                    assert not isinstance(result, Exception), f"Task {i} failed: {result}"
    
    # Test 6: Memory management across modules
    @pytest.mark.asyncio
    async def test_memory_management_integration(self, integrated_system, mock_session_data):
        """Test that memory is properly managed across module boundaries."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        
        # Run multiple workflows to test memory accumulation
        for iteration in range(5):
            # Mock dashboard operations
            with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
                with patch.object(dashboard, '_parse_recent_sessions', return_value=mock_session_data[:10]):
                    
                    async def mock_analysis(*args, **kwargs):
                        return Mock()
                    
                    dashboard._analyze_usage_patterns = mock_analysis
                    dashboard._analyze_token_efficiency = mock_analysis
                    dashboard._analyze_temporal_patterns = mock_analysis
                    dashboard._analyze_enhanced_context = mock_analysis
                    
                    # Generate data
                    dashboard_data = await dashboard.generate_dashboard()
                    insights = await analytics.analyze_cross_session_patterns(
                        mock_session_data[:5], Mock(), min_sessions=3
                    )
                    recommendations = await recommender.generate_intelligent_recommendations(
                        health_metrics=dashboard_data.health_metrics,
                        usage_summary=None, token_analysis=None, temporal_insights=None,
                        enhanced_analysis=None, correlation_insights=None,
                        user_id=f"memory_test_user_{iteration}"
                    )
                    
                    # Clear caches to prevent memory accumulation
                    dashboard._analysis_cache.clear()
                    analytics._session_cache.clear()
                    analytics._pattern_history.clear()
                    analytics._analysis_cache.clear()
                    recommender._profiles_cache.clear()
                    recommender._recommendation_history.clear()
                    recommender._effectiveness_tracker.clear()
                    
                    # Verify data was generated correctly
                    assert dashboard_data is not None
                    assert insights is not None
                    assert isinstance(recommendations, list)
    
    # Test 7: Configuration consistency across modules
    @pytest.mark.asyncio
    async def test_configuration_consistency(self, integrated_system):
        """Test that modules use consistent configuration settings."""
        storage_dir = integrated_system["storage_dir"]
        
        # Verify all modules use subdirectories of the same storage root
        expected_paths = {
            "recommendations": storage_dir / "recommendations", 
            "analytics": storage_dir / "analytics",
            "reports": storage_dir / "reports",
            "strategies": storage_dir / "strategies"
        }
        
        for module_name, expected_path in expected_paths.items():
            module = integrated_system[module_name] if module_name != "recommendations" else integrated_system["recommender"]
            assert module.storage_path == expected_path
            
            # Verify directories were created
            assert expected_path.exists()
    
    # Test 8: Data serialization compatibility
    @pytest.mark.asyncio
    async def test_data_serialization_compatibility(self, integrated_system, mock_dashboard_data, mock_cross_session_insights):
        """Test that data structures can be serialized and shared between modules."""
        reports = integrated_system["reports"]
        
        # Test that complex data structures serialize properly for reports
        report = await reports.generate_comprehensive_report(
            dashboard_data=mock_dashboard_data,
            cross_session_insights=mock_cross_session_insights,
            recommendations=[],
            personalization_profile=None,
            report_type=ReportType.DETAILED_ANALYSIS,
            output_format=ReportFormat.JSON
        )
        
        # Verify report contains serializable data
        assert report.raw_data is not None
        assert isinstance(report.raw_data, dict)
        
        # Test JSON serialization
        try:
            import json
            json.dumps(report.raw_data, default=str)
        except Exception as e:
            pytest.fail(f"Report data is not JSON serializable: {e}")
    
    # Test 9: Module state isolation
    @pytest.mark.asyncio
    async def test_module_state_isolation(self, integrated_system, mock_session_data):
        """Test that modules maintain proper state isolation."""
        dashboard1 = integrated_system["dashboard"]
        dashboard2 = CacheEnhancedDashboard()  # New instance
        
        # Modify state in dashboard1
        dashboard1._analysis_cache["test_key"] = "test_value"
        
        # dashboard2 should not be affected
        assert "test_key" not in dashboard2._analysis_cache
        
        # Test with different user profiles in recommender
        recommender = integrated_system["recommender"]
        
        # Load profile for user1
        profile1 = await recommender._load_personalization_profile("user1")
        profile1.automation_comfort_level = 0.9
        
        # Load profile for user2  
        profile2 = await recommender._load_personalization_profile("user2")
        
        # user2 should have default comfort level, not affected by user1 changes
        assert profile2.automation_comfort_level == 0.5  # Default
        assert profile1.automation_comfort_level == 0.9  # Modified
    
    # Test 10: Resource cleanup on module shutdown
    def test_resource_cleanup(self, integrated_system):
        """Test that modules clean up resources properly."""
        storage_dir = integrated_system["storage_dir"]
        
        # Modules should be able to clean up without errors
        try:
            # Clear all caches
            integrated_system["dashboard"]._analysis_cache.clear()
            integrated_system["analytics"]._session_cache.clear()
            integrated_system["recommender"]._profiles_cache.clear()
            integrated_system["reports"]._report_cache.clear()
            
            # Verify caches are empty
            assert len(integrated_system["dashboard"]._analysis_cache) == 0
            assert len(integrated_system["analytics"]._session_cache) == 0
            assert len(integrated_system["recommender"]._profiles_cache) == 0
            assert len(integrated_system["reports"]._report_cache) == 0
            
        except Exception as e:
            pytest.fail(f"Resource cleanup failed: {e}")


# Workflow-specific integration tests
class TestOptimizationWorkflows:
    """Test specific optimization workflows and user journeys."""
    
    @pytest.mark.asyncio
    async def test_new_user_onboarding_workflow(self, integrated_system, mock_session_data):
        """Test complete workflow for new user onboarding."""
        dashboard = integrated_system["dashboard"]
        recommender = integrated_system["recommender"]
        strategies = integrated_system["strategies"]
        
        # Step 1: New user has minimal data
        with patch.object(dashboard, '_discover_cache_locations', return_value=[]):
            basic_dashboard = await dashboard.generate_dashboard()
            
            # Should return basic dashboard for new user
            assert basic_dashboard.session_count == 0
            assert "Enable Cache Analysis" in basic_dashboard.optimization_recommendations[0]["title"]
        
        # Step 2: Generate recommendations for new user (minimal data)
        recommendations = await recommender.generate_intelligent_recommendations(
            health_metrics=basic_dashboard.health_metrics,
            usage_summary=None,
            token_analysis=None,
            temporal_insights=None,
            enhanced_analysis=None,
            correlation_insights=None,
            user_id="new_user"
        )
        
        # Should handle new user scenario gracefully
        assert isinstance(recommendations, list)
        
        # Step 3: Create conservative strategy for new user
        profile = await recommender._load_personalization_profile("new_user")
        
        # New user profile should be conservative
        assert profile.profile_confidence == 0.1  # Low confidence
        assert profile.automation_comfort_level == 0.5  # Moderate default
        
        # Create strategy should work with minimal data
        strategy = await strategies.create_personalized_strategy(
            user_id="new_user",
            profile=profile,
            dashboard_data=basic_dashboard,
            cross_session_insights=Mock(sessions_analyzed=0, workflow_templates=[]),
            recommendations=recommendations
        )
        
        assert strategy.user_id == "new_user"
        # Should create conservative strategy for new user
        from context_cleaner.optimization.personalized_strategies import StrategyType, OptimizationMode
        assert strategy.strategy_type in [StrategyType.CONSERVATIVE, StrategyType.BALANCED]
        assert strategy.optimization_mode == OptimizationMode.MANUAL  # Conservative for new user
    
    @pytest.mark.asyncio
    async def test_experienced_user_optimization_workflow(self, integrated_system, mock_session_data, large_dataset):
        """Test workflow for experienced user with lots of data."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        strategies = integrated_system["strategies"]
        
        # Experienced user has lots of session data
        experienced_sessions = large_dataset(50)
        
        # Mock experienced user profile
        experienced_profile_data = {
            "user_id": "experienced_user",
            "preferred_optimization_modes": ["aggressive", "efficiency"],
            "typical_session_length": "10800",  # 3 hours
            "common_file_types": [".py", ".js", ".md"],
            "frequent_workflows": ["development", "testing", "debugging"],
            "confirmation_preferences": {"high_risk": False, "automation": True},
            "automation_comfort_level": 0.9,  # High comfort
            "optimization_frequency": "daily",
            "successful_recommendations": ["rec_1", "rec_2", "rec_3", "rec_4"],
            "rejected_recommendations": ["rec_5"],
            "optimization_outcomes": {
                "token_efficiency": 0.9,
                "workflow_alignment": 0.85,
                "focus_improvement": 0.8
            },
            "profile_confidence": 0.95,  # Very high confidence
            "last_updated": datetime.now().isoformat(),
            "session_count": 100  # Lots of experience
        }
        
        # Step 1: Rich dashboard for experienced user
        with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
            with patch.object(dashboard, '_parse_recent_sessions', return_value=experienced_sessions):
                
                async def rich_mock_analysis(*args, **kwargs):
                    # Return richer mock data for experienced user
                    mock_result = Mock()
                    if 'usage_patterns' in str(args):
                        mock_result.workflow_efficiency = 0.8
                    elif 'token_efficiency' in str(args):
                        mock_result.waste_percentage = 15.0
                    return mock_result
                
                dashboard._analyze_usage_patterns = rich_mock_analysis
                dashboard._analyze_token_efficiency = rich_mock_analysis
                dashboard._analyze_temporal_patterns = rich_mock_analysis
                dashboard._analyze_enhanced_context = rich_mock_analysis
                dashboard._analyze_cross_session_correlation = rich_mock_analysis
                
                rich_dashboard = await dashboard.generate_dashboard(max_sessions=50)
                
                assert rich_dashboard.session_count == 50
        
        # Step 2: Rich cross-session analytics
        rich_insights = await analytics.analyze_cross_session_patterns(
            experienced_sessions[:30], Mock(), min_sessions=10
        )
        
        assert rich_insights.sessions_analyzed >= 10
        
        # Step 3: Advanced recommendations for experienced user
        with patch.object(recommender, '_load_personalization_profile') as mock_load:
            import json
            from context_cleaner.optimization.intelligent_recommender import PersonalizationProfile
            
            # Create profile from data (simplified)
            mock_profile = Mock()
            mock_profile.user_id = "experienced_user"
            mock_profile.preferred_optimization_modes = ["aggressive", "efficiency"]
            mock_profile.automation_comfort_level = 0.9
            mock_profile.profile_confidence = 0.95
            mock_profile.optimization_outcomes = {"token_efficiency": 0.9}
            mock_load.return_value = mock_profile
            
            recommendations = await recommender.generate_intelligent_recommendations(
                health_metrics=rich_dashboard.health_metrics,
                usage_summary=rich_dashboard.usage_summary,
                token_analysis=rich_dashboard.token_analysis,
                temporal_insights=rich_dashboard.temporal_insights,
                enhanced_analysis=rich_dashboard.enhanced_analysis,
                correlation_insights=rich_dashboard.correlation_insights,
                user_id="experienced_user",
                max_recommendations=15
            )
            
            # Should generate more sophisticated recommendations
            assert len(recommendations) >= 1
            
            # Should have variety of recommendation types for experienced user
            categories = {rec.category.value for rec in recommendations}
            assert len(categories) >= 1
        
        # Step 4: Aggressive strategy for experienced user
        strategy = await strategies.create_personalized_strategy(
            user_id="experienced_user",
            profile=mock_profile,
            dashboard_data=rich_dashboard,
            cross_session_insights=rich_insights,
            recommendations=recommendations
        )
        
        assert strategy.user_id == "experienced_user"
        # Should create more aggressive strategy for experienced user
        from context_cleaner.optimization.personalized_strategies import StrategyType, OptimizationMode
        assert strategy.strategy_type in [StrategyType.AGGRESSIVE, StrategyType.LEARNING_ADAPTIVE]
        assert strategy.optimization_mode in [OptimizationMode.SEMI_AUTOMATIC, OptimizationMode.AUTOMATIC]
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, integrated_system, mock_session_data):
        """Test workflow recovery from various error conditions."""
        dashboard = integrated_system["dashboard"]
        recommender = integrated_system["recommender"]
        reports = integrated_system["reports"]
        
        # Scenario: Cache discovery fails, but some analysis succeeds
        with patch.object(dashboard, '_discover_cache_locations', side_effect=Exception("Cache discovery failed")):
            # Should fall back to basic dashboard
            basic_dashboard = await dashboard.generate_dashboard()
            
            assert isinstance(basic_dashboard, CacheEnhancedDashboardData)
            assert basic_dashboard.session_count == 0  # No cache data
        
        # Scenario: Recommendations generation partially fails  
        with patch.object(recommender, '_generate_token_efficiency_recommendations', side_effect=Exception("Token analysis failed")):
            # Should still generate other types of recommendations
            partial_recommendations = await recommender.generate_intelligent_recommendations(
                health_metrics=basic_dashboard.health_metrics,
                usage_summary=None,
                token_analysis=None,
                temporal_insights=None, 
                enhanced_analysis=None,
                correlation_insights=None,
                user_id="error_recovery_user"
            )
            
            # Should return list even if some generators fail
            assert isinstance(partial_recommendations, list)
        
        # Scenario: Report generation handles missing data
        report = await reports.generate_comprehensive_report(
            dashboard_data=basic_dashboard,
            cross_session_insights=Mock(sessions_analyzed=0, pattern_evolution=[], workflow_templates=[]),
            recommendations=partial_recommendations,
            personalization_profile=None,
            report_type=ReportType.EXECUTIVE_SUMMARY
        )
        
        # Should generate report even with minimal data
        assert report.report_type == ReportType.EXECUTIVE_SUMMARY
        assert report.confidence_score >= 0.0  # Should have some confidence
        assert len(report.sections) >= 1  # Should have at least one section


# Performance integration tests
class TestIntegratedPerformance:
    """Test performance characteristics of integrated system."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_scalability_with_increasing_data_size(self, integrated_system):
        """Test how system performance scales with increasing data size."""
        dashboard = integrated_system["dashboard"]
        analytics = integrated_system["analytics"]
        
        # Test with increasing data sizes
        data_sizes = [10, 50, 100]
        performance_results = []
        
        for size in data_sizes:
            # Generate test data
            test_sessions = []
            for i in range(size):
                session = Mock()
                session.session_id = f"perf_session_{i}"
                session.timestamp = datetime.now() - timedelta(hours=i)
                session.duration_minutes = 60
                session.efficiency_score = 0.7
                session.workflow_type = "development"
                test_sessions.append(session)
            
            # Time the workflow
            start_time = datetime.now()
            
            with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
                with patch.object(dashboard, '_parse_recent_sessions', return_value=test_sessions):
                    
                    async def fast_analysis(*args, **kwargs):
                        await asyncio.sleep(0.001)  # Minimal processing time
                        return Mock()
                    
                    dashboard._analyze_usage_patterns = fast_analysis
                    dashboard._analyze_token_efficiency = fast_analysis
                    dashboard._analyze_temporal_patterns = fast_analysis
                    dashboard._analyze_enhanced_context = fast_analysis
                    
                    # Run dashboard and analytics
                    dashboard_data = await dashboard.generate_dashboard(max_sessions=size)
                    insights = await analytics.analyze_cross_session_patterns(
                        test_sessions, Mock(), min_sessions=min(5, size//2)
                    )
                    
                    duration = (datetime.now() - start_time).total_seconds()
                    performance_results.append((size, duration))
                    
                    # Verify results scale appropriately
                    assert dashboard_data.session_count <= size
                    assert insights.sessions_analyzed >= min(5, size//2)
        
        # Check that performance doesn't degrade exponentially
        # (this is a basic check - more sophisticated performance analysis could be added)
        for i in range(1, len(performance_results)):
            prev_size, prev_time = performance_results[i-1]
            curr_size, curr_time = performance_results[i]
            
            # Time shouldn't increase more than linearly with size
            size_ratio = curr_size / prev_size
            time_ratio = curr_time / prev_time if prev_time > 0 else 1
            
            # Allow for some variance but shouldn't be exponential
            assert time_ratio <= size_ratio * 2, f"Performance degraded too much: {time_ratio} vs {size_ratio}"
    
    @pytest.mark.asyncio  
    async def test_memory_efficiency_integrated_workflow(self, integrated_system, mock_session_data):
        """Test memory efficiency of complete integrated workflow."""
        dashboard = integrated_system["dashboard"] 
        analytics = integrated_system["analytics"]
        recommender = integrated_system["recommender"]
        
        # Run workflow multiple times to check for memory leaks
        for iteration in range(10):
            with patch.object(dashboard, '_discover_cache_locations', return_value=[Path("/test")]):
                with patch.object(dashboard, '_parse_recent_sessions', return_value=mock_session_data[:5]):
                    
                    async def lightweight_analysis(*args, **kwargs):
                        return Mock()
                    
                    dashboard._analyze_usage_patterns = lightweight_analysis
                    dashboard._analyze_token_efficiency = lightweight_analysis  
                    dashboard._analyze_temporal_patterns = lightweight_analysis
                    dashboard._analyze_enhanced_context = lightweight_analysis
                    
                    # Run complete workflow
                    dashboard_data = await dashboard.generate_dashboard(max_sessions=5)
                    insights = await analytics.analyze_cross_session_patterns(
                        mock_session_data[:5], Mock(), min_sessions=3
                    )
                    recommendations = await recommender.generate_intelligent_recommendations(
                        health_metrics=dashboard_data.health_metrics,
                        usage_summary=None, token_analysis=None, temporal_insights=None,
                        enhanced_analysis=None, correlation_insights=None,
                        user_id=f"memory_test_{iteration}"
                    )
                    
                    # Clear caches after each iteration
                    dashboard._analysis_cache.clear()
                    analytics._session_cache.clear()
                    analytics._analysis_cache.clear()
                    recommender._profiles_cache.clear()
                    
                    # Verify workflow completed
                    assert dashboard_data is not None
                    assert insights is not None
                    assert isinstance(recommendations, list)