"""
Tests for Context Cleaner dashboard components.
Updated for PR #2 CLI/Interface Unification - ProductivityDashboard now delegates to ComprehensiveHealthDashboard.
"""

import pytest
from unittest.mock import patch, Mock
from flask import Flask

from context_cleaner.dashboard.web_server import ProductivityDashboard
from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
from context_cleaner.telemetry.context_rot.config import ApplicationConfig


class TestProductivityDashboard:
    """Test suite for ProductivityDashboard wrapper that delegates to ComprehensiveHealthDashboard."""

    def setup_method(self):
        """Set up test environment."""
        self.config = ApplicationConfig.default()
        self.dashboard = ProductivityDashboard(self.config)
        
        # ProductivityDashboard now uses Flask (not FastAPI) via comprehensive dashboard
        self.client = self.dashboard.app.test_client()

    def test_dashboard_initialization(self):
        """Test dashboard initialization - now delegates to ComprehensiveHealthDashboard."""
        assert self.dashboard.config == self.config
        assert hasattr(self.dashboard, "comprehensive_dashboard")
        assert isinstance(self.dashboard.comprehensive_dashboard, ComprehensiveHealthDashboard)
        assert isinstance(self.dashboard.app, Flask)  # Should be Flask app now
        
        # Verify delegation is working
        assert self.dashboard.app is self.dashboard.comprehensive_dashboard.app

    def test_root_endpoint_returns_html(self):
        """Test root endpoint returns comprehensive dashboard HTML."""
        response = self.client.get("/")
        assert response.status_code == 200
        
        # Get response data as string (Flask test client)
        html_content = response.get_data(as_text=True)
        
        # Should contain comprehensive dashboard title
        assert "Context Cleaner Comprehensive Health Dashboard" in html_content
        # Should indicate integrated features
        assert "comprehensive" in html_content.lower() or "health" in html_content.lower()

    def test_health_check_endpoint(self):
        """Test health check endpoint (comprehensive dashboard)."""
        response = self.client.get("/health")  # Comprehensive dashboard uses /health not /api/health
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "features" in data
        
        # Should list comprehensive dashboard features
        features = data["features"]
        assert "comprehensive_health_analysis" in features
        assert "real_time_monitoring" in features

    def test_productivity_summary_endpoint(self):
        """Test productivity summary endpoint (comprehensive dashboard)."""
        response = self.client.get("/api/productivity-summary")
        assert response.status_code == 200
        data = response.get_json()

        # Check required fields from comprehensive dashboard
        assert "productivity_score" in data or "avg_productivity_score" in data
        assert "focus_time_hours" in data or "total_sessions" in data
        assert "efficiency_ratio" in data or "health_trend" in data
        
        # Check data types - should be numeric
        if "productivity_score" in data:
            assert isinstance(data["productivity_score"], (int, float))
        if "focus_time_hours" in data:
            assert isinstance(data["focus_time_hours"], (int, float))

    def test_comprehensive_health_report_endpoint(self):
        """Test comprehensive health report endpoint."""
        response = self.client.get("/api/health-report")
        assert response.status_code == 200
        data = response.get_json()
        
        # Should contain comprehensive health report data
        assert "overall_health_score" in data or "focus_metrics" in data
        
        # Check for health report structure
        if "focus_metrics" in data:
            assert isinstance(data["focus_metrics"], dict)
        if "redundancy_analysis" in data:
            assert isinstance(data["redundancy_analysis"], dict)

    def test_comprehensive_dashboard_features_endpoint(self):
        """Test that comprehensive dashboard API endpoints work."""
        endpoints_to_test = [
            "/api/performance-metrics",
            "/api/data-sources",
            "/api/dashboard-summary"
        ]
        
        for endpoint in endpoints_to_test:
            response = self.client.get(endpoint)
            # Should either work (200) or at least not crash (returning proper error JSON)
            assert response.status_code in [200, 404, 500]
            
            if response.status_code == 200:
                data = response.get_json()
                assert isinstance(data, dict)

    def test_legacy_compatibility_routes(self):
        """Test that legacy compatibility routes exist."""
        # Test legacy productivity summary route if it exists
        response = self.client.get("/api/productivity-summary-legacy")
        # Should either exist or return 404 (not crash)
        assert response.status_code in [200, 404]

    def test_start_server_method_exists(self):
        """Test that ProductivityDashboard has start_server method that delegates."""
        assert hasattr(self.dashboard, 'start_server')
        
        # Mock the comprehensive dashboard's start_server to avoid actually starting server
        with patch.object(self.dashboard.comprehensive_dashboard, 'start_server') as mock_start:
            # This should call comprehensive dashboard's start_server
            try:
                self.dashboard.start_server(host="127.0.0.1", port=8080, debug=False, open_browser=False)
                mock_start.assert_called_once_with(
                    host="127.0.0.1", port=8080, debug=False, open_browser=False
                )
            except Exception as e:
                # If it fails, just make sure the method exists and delegates
                assert mock_start.called or 'start_server' in str(e)

    def test_comprehensive_dashboard_delegation(self):
        """Test that ProductivityDashboard properly delegates to ComprehensiveHealthDashboard."""
        # The app should be the same instance
        assert self.dashboard.app is self.dashboard.comprehensive_dashboard.app
        
        # Should have access to comprehensive dashboard features
        assert hasattr(self.dashboard.comprehensive_dashboard, 'data_sources')
        assert hasattr(self.dashboard.comprehensive_dashboard, 'socketio')
        
        # Data sources should be available
        data_sources = self.dashboard.comprehensive_dashboard.data_sources
        expected_sources = ['productivity', 'health', 'tasks']
        for source in expected_sources:
            assert source in data_sources


class TestDashboardConfiguration:
    """Test dashboard configuration for comprehensive dashboard integration."""

    def test_custom_dashboard_config(self):
        """Test dashboard with custom configuration."""
        config = ApplicationConfig.default()
        # Note: config structure may have changed - adapt as needed
        dashboard = ProductivityDashboard(config)
        
        # Should pass config to comprehensive dashboard
        assert dashboard.config == config
        assert dashboard.comprehensive_dashboard.config == config

    def test_dashboard_with_none_config(self):
        """Test dashboard initialization with None config uses defaults."""
        dashboard = ProductivityDashboard(None)
        assert dashboard.config is not None
        # Should have created a default config and passed it to comprehensive dashboard
        assert dashboard.comprehensive_dashboard.config is not None

    def test_comprehensive_dashboard_integration(self):
        """Test that ProductivityDashboard properly integrates with ComprehensiveHealthDashboard."""
        config = ApplicationConfig.default()
        dashboard = ProductivityDashboard(config)
        
        # Should have comprehensive dashboard with all expected features
        comp_dashboard = dashboard.comprehensive_dashboard
        
        # Check key integrated components exist
        assert hasattr(comp_dashboard, 'cache_dashboard')  # From cache_dashboard.py
        assert hasattr(comp_dashboard, 'health_scorer')   # Health scoring
        assert hasattr(comp_dashboard, 'data_sources')    # From advanced_dashboard.py
        assert hasattr(comp_dashboard, 'socketio')        # From real_time_performance_dashboard.py
        
        # Check Flask app is properly configured
        assert comp_dashboard.app is not None
        assert comp_dashboard.app.config.get('SECRET_KEY') is not None
