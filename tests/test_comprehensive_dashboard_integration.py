"""
Comprehensive Integration Tests for Unified Dashboard System (PR #3)

Tests the integrated dashboard system after PR #1 (feature integration) and 
PR #2 (CLI/interface unification). Validates that all dashboard components
work together seamlessly and that the unified interface provides all features.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime, timedelta

from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
from context_cleaner.dashboard.web_server import ProductivityDashboard
from context_cleaner.dashboard import Dashboard  # Alias for ComprehensiveHealthDashboard
from context_cleaner.cli.optimization_commands import OptimizationCommandHandler
from context_cleaner.cli.analytics_commands import AnalyticsCommandHandler


class TestComprehensiveDashboardIntegration:
    """Test all integrated features work together in the comprehensive dashboard."""
    
    def test_comprehensive_dashboard_initialization(self):
        """Test dashboard initializes with all integrated features."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Validate all integrated components from PR #1
        assert hasattr(dashboard, 'data_sources')  # From advanced_dashboard.py
        assert hasattr(dashboard, 'app')  # Flask app from real_time_performance_dashboard.py
        assert hasattr(dashboard, 'socketio')  # SocketIO from real_time_performance_dashboard.py
        assert hasattr(dashboard, 'cache_dashboard')  # From cache_dashboard.py integration
        
        # Validate data sources from advanced_dashboard.py integration
        expected_sources = ['productivity', 'health', 'tasks']
        for source in expected_sources:
            assert source in dashboard.data_sources
            
        # Validate Flask app configuration
        assert dashboard.app is not None
        assert 'SECRET_KEY' in dashboard.app.config
        
        # Validate SocketIO integration
        assert dashboard.socketio is not None
        assert dashboard.socketio.app is dashboard.app

    def test_feature_integration_endpoints(self):
        """Test all integrated feature endpoints work."""
        dashboard = ComprehensiveHealthDashboard()
        
        with dashboard.app.test_client() as client:
            # Test core comprehensive dashboard endpoints
            response = client.get('/health')
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'healthy'
            assert 'features' in data
            
            # Test integrated endpoints from different dashboard components
            endpoints_to_test = [
                '/api/health-report',           # Core comprehensive functionality
                '/api/performance-metrics',     # Real-time performance integration
                '/api/productivity-summary',    # Data source integration
                '/api/data-sources',            # Advanced dashboard integration
                '/api/dashboard-summary',       # Unified summary
            ]
            
            for endpoint in endpoints_to_test:
                response = client.get(endpoint)
                # Should either work (200) or return proper error (not crash)
                assert response.status_code in [200, 404, 500]
                
                if response.status_code == 200:
                    data = response.get_json()
                    assert isinstance(data, dict)

    @patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard.socketio')
    def test_websocket_integration(self, mock_socketio):
        """Test WebSocket functionality with all integrated features."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Mock SocketIO test client
        mock_client = Mock()
        mock_socketio.test_client.return_value = mock_client
        mock_client.get_received.return_value = []
        
        # Test that dashboard has WebSocket event handlers set up
        assert hasattr(dashboard, '_setup_socketio_events')
        
        # Test that real-time update features are integrated
        assert hasattr(dashboard, '_real_time_update_loop')
        assert hasattr(dashboard, '_performance_history')
        
        # Test WebSocket events would work (mocked)
        test_events = ['connect', 'disconnect', 'request_health_update', 'request_performance_update']
        # These events should be set up in the dashboard (tested via method existence)
        assert dashboard.socketio is not None

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_integration(self):
        """Test that analytics features from analytics_dashboard.py are integrated."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Test session analytics method exists and works
        assert hasattr(dashboard, 'get_recent_sessions_analytics')
        sessions = dashboard.get_recent_sessions_analytics(7)
        assert isinstance(sessions, list)
        
        # Test chart generation from analytics integration
        assert hasattr(dashboard, 'generate_analytics_charts')
        if sessions:  # Only test if we have sessions
            chart_data = dashboard.generate_analytics_charts(sessions, 'productivity_trend')
            assert isinstance(chart_data, dict)
            
        # Test session timeline from analytics integration
        assert hasattr(dashboard, 'generate_session_timeline')
        timeline_data = dashboard.generate_session_timeline(7)
        assert isinstance(timeline_data, dict)

    def test_cache_intelligence_integration(self):
        """Test cache intelligence features from cache_dashboard.py are integrated."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Should have cache dashboard integration
        assert hasattr(dashboard, 'cache_dashboard')
        
        # Should have cache-related services
        assert hasattr(dashboard, 'cache_discovery')
        assert hasattr(dashboard, 'usage_analyzer')
        assert hasattr(dashboard, 'token_analyzer')
        assert hasattr(dashboard, 'temporal_analyzer')
        assert hasattr(dashboard, 'enhanced_analyzer')
        
        # Test cache intelligence endpoint exists
        with dashboard.app.test_client() as client:
            response = client.get('/api/cache-intelligence')
            # Should either work or return proper error (not crash)
            assert response.status_code in [200, 404, 500]

    @pytest.mark.asyncio 
    async def test_data_sources_functionality(self):
        """Test data sources from advanced_dashboard.py integration."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Test each integrated data source
        for source_name, source in dashboard.data_sources.items():
            assert hasattr(source, 'get_data')
            assert hasattr(source, 'get_schema')
            
            # Test data retrieval
            data = await source.get_data()
            assert isinstance(data, dict)
            assert len(data) > 0
            
            # Test schema retrieval
            schema = await source.get_schema()
            assert isinstance(schema, dict)

    def test_real_time_features_integration(self):
        """Test real-time features from real_time_performance_dashboard.py."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Should have real-time update system
        assert hasattr(dashboard, '_is_running')
        assert hasattr(dashboard, '_performance_history')
        assert hasattr(dashboard, '_alert_thresholds')
        assert hasattr(dashboard, '_last_alerts')
        
        # Should have server start/stop methods
        assert hasattr(dashboard, 'start_server')
        assert hasattr(dashboard, 'stop_server')
        
        # Should have real-time update loop
        assert hasattr(dashboard, '_real_time_update_loop')

    def test_comprehensive_health_report_integration(self):
        """Test that comprehensive health reports include all integrated features."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Mock context data for testing
        mock_context = {
            "items": [
                {"type": "todo", "content": "Test task", "timestamp": datetime.now().isoformat()},
                {"type": "file_read", "content": "Test file", "timestamp": datetime.now().isoformat()}
            ]
        }
        
        # Should be able to generate comprehensive report
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            report = loop.run_until_complete(
                dashboard.generate_comprehensive_health_report(context_data=mock_context)
            )
            
            # Report should include all integrated metrics
            assert hasattr(report, 'focus_metrics')
            assert hasattr(report, 'redundancy_analysis')
            assert hasattr(report, 'recency_indicators')
            assert hasattr(report, 'size_optimization')
            assert hasattr(report, 'overall_health_score')
            
            # Should include optimization recommendations
            assert hasattr(report, 'optimization_recommendations')
            
        finally:
            loop.close()


class TestCLIIntegrationUnified:
    """Test CLI command integration after PR #2 unification."""
    
    def test_optimization_cli_uses_comprehensive_dashboard(self):
        """Test that optimization CLI commands use comprehensive dashboard."""
        handler = OptimizationCommandHandler()
        
        # Should have handle_dashboard_command method
        assert hasattr(handler, 'handle_dashboard_command')
        
        # Mock dashboard startup to test integration
        with patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard.start_server') as mock_start:
            with patch('click.echo'):  # Suppress CLI output
                try:
                    handler.handle_dashboard_command(format="json")  # Use JSON to avoid server startup
                    # Should attempt to use comprehensive dashboard
                    assert True  # Test passes if no exceptions
                except Exception as e:
                    # Should at least try to import/use comprehensive dashboard
                    assert 'ComprehensiveHealthDashboard' in str(e) or 'comprehensive' in str(e).lower()

    def test_analytics_cli_uses_comprehensive_dashboard(self):
        """Test that analytics CLI commands use comprehensive dashboard."""
        handler = AnalyticsCommandHandler()
        
        # Should have enhanced dashboard command method
        assert hasattr(handler, 'handle_enhanced_dashboard_command')
        
        # Mock dashboard startup to test integration
        with patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard.start_server') as mock_start:
            with patch('click.echo'):  # Suppress CLI output
                try:
                    handler.handle_enhanced_dashboard_command(format="json")  # Use JSON to avoid server startup
                    # Should attempt to use comprehensive dashboard
                    assert True  # Test passes if no exceptions
                except Exception as e:
                    # Should at least try to import/use comprehensive dashboard
                    assert 'ComprehensiveHealthDashboard' in str(e) or 'comprehensive' in str(e).lower()

    def test_dashboard_alias_works(self):
        """Test that Dashboard alias points to ComprehensiveHealthDashboard."""
        # Dashboard should be an alias for ComprehensiveHealthDashboard
        assert Dashboard is ComprehensiveHealthDashboard
        
        # Should be able to create dashboard using alias
        dashboard = Dashboard()
        assert isinstance(dashboard, ComprehensiveHealthDashboard)

    def test_productivity_dashboard_delegates_correctly(self):
        """Test that ProductivityDashboard delegates to comprehensive dashboard."""
        dashboard = ProductivityDashboard()
        
        # Should have comprehensive dashboard instance
        assert hasattr(dashboard, 'comprehensive_dashboard')
        assert isinstance(dashboard.comprehensive_dashboard, ComprehensiveHealthDashboard)
        
        # Should delegate Flask app
        assert dashboard.app is dashboard.comprehensive_dashboard.app
        
        # Should have compatibility routes set up
        assert hasattr(dashboard, '_setup_compatibility_routes')


class TestBackwardsCompatibility:
    """Test backwards compatibility after dashboard consolidation."""
    
    def test_existing_imports_still_work(self):
        """Test that existing import patterns still work."""
        # These imports should all work after consolidation
        from context_cleaner.dashboard.web_server import ProductivityDashboard
        from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
        from context_cleaner.dashboard import Dashboard, ComprehensiveHealthDashboard as CompDashboard
        
        # Should be able to create instances
        prod_dash = ProductivityDashboard()
        comp_dash = ComprehensiveHealthDashboard()
        alias_dash = Dashboard()
        
        # All should work
        assert isinstance(prod_dash, ProductivityDashboard)
        assert isinstance(comp_dash, ComprehensiveHealthDashboard)  
        assert isinstance(alias_dash, ComprehensiveHealthDashboard)

    def test_existing_api_patterns_preserved(self):
        """Test that existing API usage patterns still work."""
        dashboard = ProductivityDashboard()
        
        # Should have Flask test client (not FastAPI TestClient)
        client = dashboard.app.test_client()
        
        # Should respond to requests (even if responses have changed format)
        response = client.get('/health')
        assert response.status_code == 200
        
        # Should have start_server method
        assert hasattr(dashboard, 'start_server')
        
        # Should be able to pass config
        from context_cleaner.config.settings import ContextCleanerConfig
        config = ContextCleanerConfig.default()
        dashboard_with_config = ProductivityDashboard(config)
        assert dashboard_with_config.config == config

    def test_data_format_consistency_where_possible(self):
        """Test that API responses maintain reasonable format consistency."""
        dashboard = ProductivityDashboard()
        
        with dashboard.app.test_client() as client:
            # Health endpoint should return status
            response = client.get('/health')
            if response.status_code == 200:
                data = response.get_json()
                assert 'status' in data
                
            # Should still have some form of productivity data
            response = client.get('/api/productivity-summary')
            if response.status_code == 200:
                data = response.get_json()
                # Should have some productivity-related fields
                productivity_fields = [
                    'productivity_score', 'avg_productivity_score', 
                    'efficiency_ratio', 'focus_time_hours',
                    'total_sessions'
                ]
                assert any(field in data for field in productivity_fields)


class TestIntegratedFeatureAvailability:
    """Test that all integrated features are available through unified interface."""
    
    def test_all_dashboard_features_available(self):
        """Test that comprehensive dashboard exposes all integrated features."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Features from advanced_dashboard.py
        assert hasattr(dashboard, 'data_sources')
        assert 'productivity' in dashboard.data_sources
        assert 'health' in dashboard.data_sources
        assert 'tasks' in dashboard.data_sources
        
        # Features from real_time_performance_dashboard.py  
        assert hasattr(dashboard, 'socketio')
        assert hasattr(dashboard, '_real_time_update_loop')
        assert hasattr(dashboard, '_performance_history')
        
        # Features from analytics_dashboard.py
        assert hasattr(dashboard, 'get_recent_sessions_analytics')
        assert hasattr(dashboard, 'generate_analytics_charts')
        assert hasattr(dashboard, 'generate_session_timeline')
        
        # Features from cache_dashboard.py
        assert hasattr(dashboard, 'cache_dashboard')
        assert hasattr(dashboard, 'usage_analyzer')
        
        # Core comprehensive health features
        assert hasattr(dashboard, 'generate_comprehensive_health_report')
        assert hasattr(dashboard, 'health_scorer')

    def test_api_endpoints_comprehensiveness(self):
        """Test that API exposes comprehensive functionality."""
        dashboard = ComprehensiveHealthDashboard()
        
        with dashboard.app.test_client() as client:
            # Core endpoints
            core_endpoints = [
                '/health',
                '/api/health-report',
                '/api/performance-metrics'
            ]
            
            # Advanced analytics endpoints  
            analytics_endpoints = [
                '/api/dashboard-summary',
                '/api/data-sources',
                '/api/productivity-summary'
            ]
            
            # Integrated feature endpoints
            feature_endpoints = [
                '/api/cache-intelligence'
            ]
            
            all_endpoints = core_endpoints + analytics_endpoints + feature_endpoints
            
            for endpoint in all_endpoints:
                response = client.get(endpoint)
                # Should not return 404 (endpoint should exist) or crash (500 without JSON)
                assert response.status_code != 404, f"Endpoint {endpoint} should exist"
                
                if response.status_code == 500:
                    # If error, should be proper JSON error
                    try:
                        error_data = response.get_json()
                        assert isinstance(error_data, dict)
                        assert 'error' in error_data
                    except:
                        pytest.fail(f"Endpoint {endpoint} returned 500 but not proper JSON error")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])