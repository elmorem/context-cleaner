"""
Tests for Context Cleaner dashboard components.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient

from context_cleaner.dashboard.web_server import ProductivityDashboard
from context_cleaner.config.settings import ContextCleanerConfig


class TestProductivityDashboard:
    """Test suite for ProductivityDashboard web server."""

    def setup_method(self):
        """Set up test environment."""
        self.config = ContextCleanerConfig.default()
        self.dashboard = ProductivityDashboard(self.config)
        self.client = TestClient(self.dashboard.app)

    def test_dashboard_initialization(self):
        """Test dashboard initialization."""
        assert self.dashboard.config == self.config
        assert hasattr(self.dashboard, "analyzer")
        assert hasattr(self.dashboard, "app")

    def test_root_endpoint_returns_html(self):
        """Test root endpoint returns HTML dashboard."""
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "Context Cleaner Dashboard" in response.text
        assert "Bootstrap" in response.text
        assert "plotly" in response.text.lower()

    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_productivity_summary_endpoint(self):
        """Test productivity summary endpoint."""
        response = self.client.get("/api/productivity-summary")
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "period_days" in data
        assert "avg_productivity_score" in data
        assert "total_sessions" in data
        assert "optimization_events" in data
        assert "health_trend" in data
        assert "recommendations" in data
        assert "last_updated" in data

        # Check data types
        assert isinstance(data["avg_productivity_score"], (int, float))
        assert isinstance(data["total_sessions"], int)
        assert isinstance(data["recommendations"], list)

    def test_productivity_summary_with_days_parameter(self):
        """Test productivity summary with custom days parameter."""
        response = self.client.get("/api/productivity-summary?days=14")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 14

    def test_session_analytics_endpoint(self):
        """Test session analytics endpoint."""
        response = self.client.get("/api/session-analytics")
        assert response.status_code == 200
        data = response.json()

        # Check required sections
        assert "session_types" in data
        assert "hourly_productivity" in data
        assert "weekly_trends" in data
        assert "optimization_impact" in data

        # Check data structure
        assert isinstance(data["session_types"], dict)
        assert isinstance(data["hourly_productivity"], dict)
        assert isinstance(data["weekly_trends"], dict)
        assert isinstance(data["optimization_impact"], dict)

        # Check specific values
        assert "avg_improvement" in data["optimization_impact"]
        assert "success_rate" in data["optimization_impact"]

    def test_recommendations_endpoint(self):
        """Test recommendations endpoint."""
        response = self.client.get("/api/recommendations")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) > 0

        # Check recommendation structure
        for rec in data:
            assert "type" in rec
            assert "priority" in rec
            assert "title" in rec
            assert "description" in rec
            assert "action" in rec
            assert rec["priority"] in ["high", "medium", "low"]

    def test_export_data_endpoint(self):
        """Test data export endpoint."""
        response = self.client.post("/api/privacy/export-data")
        assert response.status_code == 200
        data = response.json()

        assert "export_timestamp" in data
        assert "version" in data
        assert "sessions" in data
        assert "privacy_notice" in data
        assert isinstance(data["sessions"], list)

    def test_delete_data_endpoint(self):
        """Test data deletion endpoint."""
        response = self.client.delete("/api/privacy/delete-data")
        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "timestamp" in data
        assert "deleted successfully" in data["message"]

    def test_html_dashboard_contains_required_elements(self):
        """Test HTML dashboard contains all required UI elements."""
        response = self.client.get("/")
        html_content = response.text

        # Check for key UI components
        assert 'id="productivity-score"' in html_content
        assert 'id="total-sessions"' in html_content
        assert 'id="optimizations"' in html_content
        assert 'id="health-trend"' in html_content

        # Check for charts
        assert 'id="productivity-chart"' in html_content
        assert 'id="hourly-chart"' in html_content

        # Check for recommendations section
        assert 'id="recommendations-list"' in html_content

        # Check for privacy controls
        assert "exportData()" in html_content
        assert "deleteData()" in html_content

        # Check for privacy notice
        assert "Privacy Notice" in html_content
        assert "processed locally" in html_content

    def test_html_dashboard_javascript_functions(self):
        """Test HTML dashboard contains required JavaScript functions."""
        response = self.client.get("/")
        html_content = response.text

        # Check for main functions
        assert "function loadDashboard()" in html_content
        assert "function exportData()" in html_content
        assert "function deleteData()" in html_content

        # Check for API calls
        assert "'/api/productivity-summary'" in html_content
        assert "'/api/session-analytics'" in html_content
        assert "'/api/recommendations'" in html_content

        # Check for chart creation
        assert "Plotly.newPlot" in html_content

        # Check for auto-refresh
        assert "setInterval(loadDashboard" in html_content

    def test_invalid_endpoint_returns_404(self):
        """Test invalid endpoints return 404."""
        response = self.client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_dashboard_error_handling(self):
        """Test dashboard handles errors gracefully."""
        # This test would need to mock internal errors
        # For now, just ensure endpoints don't crash
        endpoints = [
            "/api/health",
            "/api/productivity-summary",
            "/api/session-analytics",
            "/api/recommendations",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            assert response.status_code in [200, 500]  # Either success or handled error
            if response.status_code == 500:
                # Should return JSON error response
                assert response.headers.get("content-type", "").startswith(
                    "application/json"
                )


class TestDashboardConfiguration:
    """Test dashboard configuration and customization."""

    def test_custom_dashboard_config(self):
        """Test dashboard with custom configuration."""
        config = ContextCleanerConfig.default()
        config.dashboard.port = 9000
        config.dashboard.host = "0.0.0.0"
        config.dashboard.auto_refresh = False

        dashboard = ProductivityDashboard(config)
        assert dashboard.config.dashboard.port == 9000
        assert dashboard.config.dashboard.host == "0.0.0.0"
        assert dashboard.config.dashboard.auto_refresh is False

    @patch("uvicorn.run")
    def test_dashboard_server_startup(self, mock_uvicorn):
        """Test dashboard server startup."""
        config = ContextCleanerConfig.default()
        dashboard = ProductivityDashboard(config)

        dashboard.start_server("localhost", 8548)

        # Verify uvicorn.run was called with correct parameters
        mock_uvicorn.assert_called_once_with(
            dashboard.app, host="localhost", port=8548, log_level="info"
        )

    def test_dashboard_with_none_config(self):
        """Test dashboard initialization with None config uses defaults."""
        dashboard = ProductivityDashboard(None)
        assert dashboard.config is not None
        assert dashboard.config.dashboard.port == 8548  # Default port
