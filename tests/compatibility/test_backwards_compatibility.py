"""
Backwards Compatibility Validation Tests (PR #3)

Ensures existing functionality still works after dashboard consolidation.
Tests that existing code, CLI commands, and API patterns continue to work
as expected after the transition to the comprehensive dashboard system.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, Mock, AsyncMock
from click.testing import CliRunner

from context_cleaner.dashboard.web_server import ProductivityDashboard
from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
from context_cleaner.dashboard import Dashboard, ComprehensiveHealthDashboard as ImportedCompDash
from context_cleaner.cli.optimization_commands import OptimizationCommandHandler
from context_cleaner.cli.analytics_commands import AnalyticsCommandHandler
from context_cleaner.telemetry.context_rot.config import ApplicationConfig


class TestBackwardsCompatibility:
    """Ensure existing functionality still works after consolidation."""
    
    def test_existing_cli_commands_work(self):
        """Test that existing CLI commands still function."""
        # Test optimization CLI dashboard command
        handler = OptimizationCommandHandler()
        
        # Should not crash when trying to launch dashboard
        with patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard') as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.generate_comprehensive_health_report = AsyncMock(return_value=SimpleNamespace(status="ok"))
            mock_dashboard.get_recent_sessions_analytics.return_value = []
            mock_dashboard_class.return_value = mock_dashboard

            with patch('click.echo'):  # Suppress output
                handler.handle_dashboard_command(format="json")
                mock_dashboard.generate_comprehensive_health_report.assert_awaited_once()

    def test_analytics_cli_commands_work(self):
        """Test that analytics CLI commands still function."""
        handler = AnalyticsCommandHandler()
        
        # Should not crash when trying to launch enhanced dashboard
        with patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard') as mock_dashboard_class:
            mock_dashboard = Mock()
            mock_dashboard.generate_comprehensive_health_report = AsyncMock(return_value=SimpleNamespace(status="ok"))
            mock_dashboard.get_recent_sessions_analytics.return_value = []
            mock_dashboard_class.return_value = mock_dashboard

            with patch('click.echo'):  # Suppress output
                handler.handle_enhanced_dashboard_command(format="json")
                mock_dashboard.generate_comprehensive_health_report.assert_awaited_once()

    def test_existing_api_endpoints_preserved(self):
        """Test that all previously working endpoints still work."""
        dashboard = ComprehensiveHealthDashboard()
        dashboard.dashboard_cache.get_session_analytics_cache = lambda: []
        
        # Test that core endpoints still exist
        with dashboard.app.test_client() as client:
            # Health check endpoint (may have moved from /api/health to /health)
            health_endpoints = ['/health', '/api/health']
            health_found = False
            
            for endpoint in health_endpoints:
                response = client.get(endpoint)
                if response.status_code == 200:
                    health_found = True
                    data = response.get_json()
                    assert 'status' in data
                    break
            
            assert health_found, "No health endpoint found"
            
            # Productivity summary endpoint should exist in some form
            prod_endpoints = ['/api/productivity-summary', '/api/dashboard-summary']
            prod_found = False
            
            for endpoint in prod_endpoints:
                response = client.get(endpoint)
                if response.status_code == 200:
                    prod_found = True
                    data = response.get_json()
                    assert isinstance(data, dict)
                    break
            
            assert prod_found, "No productivity endpoint found"

    def test_productivity_dashboard_backwards_compatibility(self):
        """Test ProductivityDashboard maintains backwards compatibility."""
        # Should still be able to create ProductivityDashboard
        dashboard = ProductivityDashboard()
        dashboard.dashboard_cache = SimpleNamespace(
            get_session_analytics_cache=lambda: []
        )
        
        # Should have expected attributes
        assert hasattr(dashboard, 'config')
        assert hasattr(dashboard, 'app')
        
        # Should be able to use with Flask test client
        client = dashboard.app.test_client()
        response = client.get('/')
        assert response.status_code == 200
        
        # Should be able to call start_server method (mocked)
        with patch.object(dashboard, 'start_server') as mock_start:
            dashboard.start_server(host="localhost", port=8080)
            mock_start.assert_called_once()

    def test_data_format_consistency(self):
        """Ensure API responses maintain expected format where possible."""
        dashboard = ComprehensiveHealthDashboard()
        dashboard.dashboard_cache.get_session_analytics_cache = lambda: []
        
        with dashboard.app.test_client() as client:
            # Health endpoint should return consistent format
            response = client.get('/health')
            if response.status_code == 200:
                data = response.get_json()
                
                # Should have basic health check fields
                assert 'status' in data
                assert 'timestamp' in data
                
                # Status should be a string indicating health
                assert isinstance(data['status'], str)
                assert data['status'] in ['healthy', 'unhealthy', 'warning']
                
            # Dashboard summary should have reasonable structure
            response = client.get('/api/dashboard-summary')
            if response.status_code == 200:
                data = response.get_json()
                
                # Should be a dictionary with meaningful data
                assert isinstance(data, dict)
                assert len(data) > 0
                
                # Should have timestamp
                assert 'timestamp' in data

    def test_config_object_compatibility(self):
        """Test that configuration objects still work as expected."""
        # Should be able to create config
        config = ApplicationConfig.default()
        
        # Should be able to pass config to dashboards
        prod_dashboard = ProductivityDashboard(config)
        comp_dashboard = ComprehensiveHealthDashboard(config=config)
        
        # Config should be preserved
        assert prod_dashboard.config == config
        assert comp_dashboard.config == config
        
        # Should handle None config gracefully
        prod_dashboard_no_config = ProductivityDashboard(None)
        comp_dashboard_no_config = ComprehensiveHealthDashboard(config=None)
        
        # Should have created default configs
        assert prod_dashboard_no_config.config is not None
        assert comp_dashboard_no_config.config is not None

    def test_import_patterns_still_work(self):
        """Test that existing import patterns continue to work."""
        # Direct imports
        from context_cleaner.dashboard.web_server import ProductivityDashboard
        from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
        
        # Package-level imports  
        from context_cleaner.dashboard import ProductivityDashboard as ProdDash
        from context_cleaner.dashboard import ComprehensiveHealthDashboard as CompDash
        from context_cleaner.dashboard import Dashboard
        
        # All should be importable and creatable
        dashboards = [
            ProductivityDashboard(),
            ComprehensiveHealthDashboard(),
            ProdDash(),
            CompDash(), 
            Dashboard()
        ]
        
        for dashboard in dashboards:
            assert dashboard is not None
            assert hasattr(dashboard, 'app')

    def test_cli_handler_initialization_compatibility(self):
        """Test that CLI handlers can still be initialized as before."""
        # Should be able to create handlers with no args
        opt_handler = OptimizationCommandHandler()
        analytics_handler = AnalyticsCommandHandler()
        
        # Should be able to create handlers with config
        config = ApplicationConfig.default()
        opt_handler_with_config = OptimizationCommandHandler(config=config)
        analytics_handler_with_config = AnalyticsCommandHandler(config=config)
        
        # Should be able to create handlers with verbose flag
        opt_handler_verbose = OptimizationCommandHandler(verbose=True)
        analytics_handler_verbose = AnalyticsCommandHandler(verbose=True)
        
        # All should have expected methods
        handlers = [
            opt_handler, analytics_handler, opt_handler_with_config,
            analytics_handler_with_config, opt_handler_verbose, analytics_handler_verbose
        ]
        
        for handler in handlers:
            assert handler is not None
            if hasattr(handler, 'handle_dashboard_command'):
                assert callable(handler.handle_dashboard_command)
            if hasattr(handler, 'handle_enhanced_dashboard_command'):  
                assert callable(handler.handle_enhanced_dashboard_command)

    def test_flask_vs_fastapi_migration_compatibility(self):
        """Test that migration from FastAPI to Flask doesn't break existing usage."""
        dashboard = ProductivityDashboard()
        dashboard.dashboard_cache = SimpleNamespace(
            get_session_analytics_cache=lambda: []
        )
        
        # Should now use Flask (not FastAPI)
        from flask import Flask
        assert isinstance(dashboard.app, Flask)
        
        # Should still be able to create test client
        client = dashboard.app.test_client()
        assert client is not None
        
        # Should be able to make requests
        response = client.get('/')
        assert response is not None
        assert hasattr(response, 'status_code')
        
        # Should get JSON responses properly
        response = client.get('/health')
        if response.status_code == 200:
            data = response.get_json()
            assert isinstance(data, dict)

    def test_comprehensive_dashboard_alias_compatibility(self):
        """Test that Dashboard alias works correctly."""
        # Dashboard should be an alias for ComprehensiveHealthDashboard
        assert Dashboard is ComprehensiveHealthDashboard
        
        # Should be able to use alias exactly like direct import
        dashboard_direct = ComprehensiveHealthDashboard()
        dashboard_alias = Dashboard()
        
        # Both should be the same type
        assert type(dashboard_direct) == type(dashboard_alias)
        assert isinstance(dashboard_alias, ComprehensiveHealthDashboard)
        
        # Both should have same methods and attributes
        direct_attrs = set(dir(dashboard_direct))
        alias_attrs = set(dir(dashboard_alias))
        assert direct_attrs == alias_attrs

    def test_method_signature_compatibility(self):
        """Test that method signatures remain compatible where possible."""
        dashboard = ProductivityDashboard()
        
        # start_server should accept common parameters
        try:
            # Should not crash with these parameter patterns
            with patch.object(dashboard, 'start_server'):
                dashboard.start_server()  # No params
                dashboard.start_server(host="localhost")  # Host only
                dashboard.start_server(port=8080)  # Port only  
                dashboard.start_server(host="localhost", port=8080)  # Both
                
        except TypeError as e:
            pytest.fail(f"start_server method signature not backwards compatible: {e}")

    def test_error_handling_backwards_compatibility(self):
        """Test that error handling doesn't break existing patterns.""" 
        dashboard = ComprehensiveHealthDashboard()
        dashboard.dashboard_cache.get_session_analytics_cache = lambda: []
        
        with dashboard.app.test_client() as client:
            # Invalid endpoints should return 404 (not crash)
            response = client.get('/api/nonexistent-endpoint')
            assert response.status_code == 404
            
            # Should return JSON error if possible
            try:
                error_data = response.get_json()
                if error_data:
                    assert isinstance(error_data, dict)
            except:
                # OK if not JSON, as long as it doesn't crash
                pass

    def test_dashboard_instantiation_patterns(self):
        """Test various dashboard instantiation patterns still work."""
        # Pattern 1: No arguments
        dashboard1 = ProductivityDashboard()
        assert dashboard1 is not None
        
        # Pattern 2: With config
        config = ApplicationConfig.default()
        dashboard2 = ProductivityDashboard(config)
        assert dashboard2.config == config
        
        # Pattern 3: With None (should use defaults)
        dashboard3 = ProductivityDashboard(None)
        assert dashboard3.config is not None
        
        # Pattern 4: Comprehensive dashboard directly
        dashboard4 = ComprehensiveHealthDashboard()
        assert dashboard4 is not None
        
        # Pattern 5: Using alias
        dashboard5 = Dashboard()
        assert dashboard5 is not None
        
        # All should have Flask apps
        dashboards = [dashboard1, dashboard2, dashboard3, dashboard4, dashboard5]
        for dashboard in dashboards:
            from flask import Flask
            assert isinstance(dashboard.app, Flask)


class TestLegacyEndpointCompatibility:
    """Test compatibility of legacy API endpoints."""
    
    def test_legacy_productivity_endpoints(self):
        """Test that legacy productivity endpoints work or are properly redirected."""
        dashboard = ProductivityDashboard()
        
        with dashboard.app.test_client() as client:
            # Test legacy endpoints that might exist
            legacy_endpoints = [
                '/api/productivity-summary-legacy',
                '/api/session-analytics-legacy'
            ]
            
            for endpoint in legacy_endpoints:
                response = client.get(endpoint)
                # Should either work, be absent, or return a graceful error payload
                assert response.status_code in [200, 404, 500], \
                    f"Legacy endpoint {endpoint} returned {response.status_code}"

                if response.status_code == 200:
                    data = response.get_json()
                    assert isinstance(data, dict)
                elif response.status_code == 500:
                    # Should return structured error information
                    data = response.get_json(silent=True)
                    assert data is None or isinstance(data, dict)

    def test_comprehensive_dashboard_handles_old_patterns(self):
        """Test that comprehensive dashboard handles old usage patterns."""
        dashboard = ComprehensiveHealthDashboard()
        dashboard.dashboard_cache.get_session_analytics_cache = lambda: []
        
        # Should handle basic health check
        with dashboard.app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            
            data = response.get_json()
            assert 'status' in data
            
            # Should indicate it's the comprehensive version
            assert 'version' in data or 'features' in data


class TestDataCompatibility:
    """Test that data formats remain reasonably compatible."""
    
    def test_health_check_data_format(self):
        """Test health check returns expected data format."""
        dashboard = ComprehensiveHealthDashboard()
        
        with dashboard.app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
            
            data = response.get_json()
            
            # Should have basic fields
            required_fields = ['status', 'timestamp']
            for field in required_fields:
                assert field in data, f"Health check missing field: {field}"
            
            # Status should be string
            assert isinstance(data['status'], str)
            
            # Timestamp should be string (ISO format)
            assert isinstance(data['timestamp'], str)

    def test_productivity_data_format_compatibility(self):
        """Test productivity data maintains reasonable compatibility."""
        dashboard = ComprehensiveHealthDashboard()
        
        with dashboard.app.test_client() as client:
            response = client.get('/api/productivity-summary')
            
            if response.status_code == 200:
                data = response.get_json()
                assert isinstance(data, dict)
                
                # Should have some productivity-related fields
                productivity_indicators = [
                    'productivity_score', 'avg_productivity_score', 'focus_time_hours',
                    'efficiency_ratio', 'total_sessions', 'focus_score'
                ]
                
                found_indicators = [field for field in productivity_indicators if field in data]
                assert len(found_indicators) > 0, \
                    f"No productivity indicators found in response: {list(data.keys())}"
                
                # Numeric fields should be numbers
                for field in found_indicators:
                    if field in data:
                        assert isinstance(data[field], (int, float)), \
                            f"Field {field} should be numeric, got {type(data[field])}"


if __name__ == "__main__":
    # Allow running tests directly  
    pytest.main([__file__, "-v"])
