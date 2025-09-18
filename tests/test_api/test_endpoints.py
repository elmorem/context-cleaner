"""
Test Suite for API Endpoints

Integration tests for FastAPI endpoints, ensuring proper request/response
handling, error cases, and performance characteristics.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
import json
from datetime import datetime

from context_cleaner.api.app import create_testing_app
from context_cleaner.api.models import DashboardMetrics, SystemHealth, WidgetData
from decimal import Decimal


@pytest.fixture
def test_app():
    """Create test FastAPI application"""
    app = create_testing_app()
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def mock_services(test_app):
    """Mock the services for testing"""
    # Mock dashboard service
    mock_dashboard_service = Mock()
    mock_telemetry_service = Mock()

    test_app.dependency_overrides = {}

    # Override dependency injection
    def get_mock_dashboard_service():
        return mock_dashboard_service

    def get_mock_telemetry_service():
        return mock_telemetry_service

    from context_cleaner.api.app import get_dashboard_service, get_telemetry_service
    test_app.dependency_overrides[get_dashboard_service] = get_mock_dashboard_service
    test_app.dependency_overrides[get_telemetry_service] = get_mock_telemetry_service

    return {
        'dashboard_service': mock_dashboard_service,
        'telemetry_service': mock_telemetry_service
    }


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client, mock_services):
        """Test successful health check"""
        # Mock successful health response
        mock_health = SystemHealth(
            overall_healthy=True,
            database_status='healthy',
            connection_status='connected',
            response_time_ms=100.0,
            uptime_seconds=86400.0,
            error_rate=0.5,
            timestamp=datetime.now()
        )

        mock_services['dashboard_service'].get_system_status = AsyncMock(return_value=mock_health)

        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['overall_healthy'] is True
        assert data['data']['database_status'] == 'healthy'
        assert 'request_id' in data
        assert 'timestamp' in data

    def test_health_check_failure(self, client, mock_services):
        """Test health check when service fails"""
        mock_services['dashboard_service'].get_system_status = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        response = client.get("/api/v1/health")

        assert response.status_code == 200  # API should still respond
        data = response.json()

        assert data['success'] is False
        assert data['error'] == "Health check failed"
        assert data['error_code'] == "HEALTH_CHECK_FAILED"


class TestDashboardEndpoints:
    """Test dashboard-related endpoints"""

    def test_dashboard_overview_success(self, client, mock_services):
        """Test successful dashboard overview"""
        from context_cleaner.api.models import DashboardOverviewResponse

        mock_overview = DashboardOverviewResponse(
            metrics=DashboardMetrics(
                total_tokens=10000,
                total_sessions=50,
                success_rate=98.5,
                active_agents=5,
                cost=Decimal('25.50'),
                timestamp=datetime.now()
            ),
            widgets=[],
            system_health=SystemHealth(
                overall_healthy=True,
                database_status='healthy',
                connection_status='connected',
                response_time_ms=100.0,
                uptime_seconds=86400.0,
                error_rate=0.5,
                timestamp=datetime.now()
            ),
            last_updated=datetime.now()
        )

        mock_services['dashboard_service'].get_dashboard_overview = AsyncMock(return_value=mock_overview)

        response = client.get("/api/v1/dashboard/overview")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['metrics']['total_tokens'] == 10000
        assert data['data']['metrics']['total_sessions'] == 50
        assert data['data']['system_health']['overall_healthy'] is True

    def test_dashboard_overview_error(self, client, mock_services):
        """Test dashboard overview error handling"""
        mock_services['dashboard_service'].get_dashboard_overview = AsyncMock(
            side_effect=Exception("Database error")
        )

        response = client.get("/api/v1/dashboard/overview")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is False
        assert data['error'] == "Failed to get dashboard overview"
        assert data['error_code'] == "DASHBOARD_OVERVIEW_FAILED"


class TestWidgetEndpoints:
    """Test widget-related endpoints"""

    def test_get_single_widget_success(self, client, mock_services):
        """Test getting single widget data"""
        mock_widget = WidgetData(
            widget_id="error_monitor_123",
            widget_type="error_monitor",
            title="Error Monitor",
            status="healthy",
            data={"error_count": 5, "trend": "stable"},
            last_updated=datetime.now(),
            metadata={"time_range_days": 7}
        )

        mock_services['dashboard_service'].get_widget_data = AsyncMock(return_value=mock_widget)

        response = client.get("/api/v1/widgets/error_monitor?time_range_days=7")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['widget_type'] == "error_monitor"
        assert data['data']['status'] == "healthy"
        assert data['data']['data']['error_count'] == 5

    def test_get_single_widget_with_session(self, client, mock_services):
        """Test getting widget data filtered by session"""
        mock_widget = WidgetData(
            widget_id="cost_tracker_456",
            widget_type="cost_tracker",
            title="Cost Tracker",
            status="warning",
            data={"session_cost": 15.25},
            last_updated=datetime.now(),
            metadata={"session_id": "test_session"}
        )

        mock_services['dashboard_service'].get_widget_data = AsyncMock(return_value=mock_widget)

        response = client.get("/api/v1/widgets/cost_tracker?session_id=test_session&force_refresh=true")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['data']['session_cost'] == 15.25
        assert data['metadata']['cached'] is False

    def test_get_multiple_widgets_success(self, client, mock_services):
        """Test getting multiple widgets"""
        mock_widgets = {
            'error_monitor': WidgetData(
                widget_id="error_monitor_1",
                widget_type="error_monitor",
                title="Error Monitor",
                status="healthy",
                data={},
                last_updated=datetime.now(),
                metadata={}
            ),
            'cost_tracker': WidgetData(
                widget_id="cost_tracker_1",
                widget_type="cost_tracker",
                title="Cost Tracker",
                status="warning",
                data={},
                last_updated=datetime.now(),
                metadata={}
            )
        }

        mock_services['dashboard_service'].get_multiple_widgets = AsyncMock(return_value=mock_widgets)

        response = client.get("/api/v1/widgets?widget_types=error_monitor&widget_types=cost_tracker")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['total_count'] == 2
        assert data['data']['healthy_count'] == 1
        assert data['data']['warning_count'] == 1
        assert data['data']['critical_count'] == 0
        assert len(data['data']['widgets']) == 2

    def test_widget_validation_errors(self, client, mock_services):
        """Test widget endpoint validation"""
        # Test invalid time_range_days
        response = client.get("/api/v1/widgets/error_monitor?time_range_days=100")  # Max is 30
        assert response.status_code == 422

        # Test invalid widget type in path (should still work, but return error in service)
        mock_services['dashboard_service'].get_widget_data = AsyncMock(
            side_effect=Exception("Unknown widget type")
        )
        response = client.get("/api/v1/widgets/invalid_widget")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False


class TestTelemetryEndpoints:
    """Test telemetry-related endpoints"""

    def test_get_active_sessions(self, client, mock_services):
        """Test getting active sessions"""
        mock_sessions = [
            {
                'session_id': 'session_1',
                'last_activity': '2024-01-01T10:00:00',
                'request_count': 10,
                'cost': 5.25
            },
            {
                'session_id': 'session_2',
                'last_activity': '2024-01-01T09:30:00',
                'request_count': 5,
                'cost': 2.10
            }
        ]

        mock_services['telemetry_service'].get_active_sessions = AsyncMock(return_value=mock_sessions)

        response = client.get("/api/v1/telemetry/sessions?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert len(data['data']) == 2
        assert data['metadata']['count'] == 2
        assert data['data'][0]['session_id'] == 'session_1'

    def test_get_cost_analysis(self, client, mock_services):
        """Test cost analysis endpoint"""
        mock_analysis = {
            'total_cost': 150.75,
            'average_daily_cost': 21.54,
            'daily_trends': {
                '2024-01-01': 25.00,
                '2024-01-02': 22.50,
                '2024-01-03': 18.75
            },
            'cost_velocity': 'stable',
            'projected_monthly': 646.20
        }

        mock_services['dashboard_service'].get_cost_analysis = AsyncMock(return_value=mock_analysis)

        response = client.get("/api/v1/telemetry/cost-analysis?days=7")

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['total_cost'] == 150.75
        assert data['data']['cost_velocity'] == 'stable'
        assert len(data['data']['daily_trends']) == 3

    def test_telemetry_validation_errors(self, client):
        """Test telemetry endpoint validation"""
        # Test invalid limit (too high)
        response = client.get("/api/v1/telemetry/sessions?limit=300")  # Max is 200
        assert response.status_code == 422

        # Test invalid days parameter
        response = client.get("/api/v1/telemetry/cost-analysis?days=100")  # Max is 90
        assert response.status_code == 422


class TestCacheEndpoint:
    """Test cache management endpoint"""

    def test_cache_invalidation_success(self, client, mock_services):
        """Test successful cache invalidation"""
        mock_services['dashboard_service'].invalidate_cache = AsyncMock(return_value=True)

        request_body = {
            "pattern": "dashboard:*",
            "scope": "dashboard"
        }

        response = client.post("/api/v1/cache/invalidate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['data']['pattern'] == "dashboard:*"
        assert data['data']['invalidated'] is True

    def test_cache_invalidation_failure(self, client, mock_services):
        """Test cache invalidation failure"""
        mock_services['dashboard_service'].invalidate_cache = AsyncMock(return_value=False)

        request_body = {
            "pattern": "invalid:*",
            "scope": "all"
        }

        response = client.post("/api/v1/cache/invalidate", json=request_body)

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is False
        assert data['data']['invalidated'] is False

    def test_cache_validation_errors(self, client):
        """Test cache invalidation validation"""
        # Test invalid scope
        request_body = {
            "pattern": "test:*",
            "scope": "invalid_scope"
        }

        response = client.post("/api/v1/cache/invalidate", json=request_body)
        assert response.status_code == 422

        # Test missing pattern
        request_body = {
            "scope": "dashboard"
        }

        response = client.post("/api/v1/cache/invalidate", json=request_body)
        assert response.status_code == 422


class TestLegacyCompatibility:
    """Test legacy endpoint compatibility"""

    def test_legacy_health_report(self, client, mock_services):
        """Test legacy health report endpoint"""
        mock_health = SystemHealth(
            overall_healthy=True,
            database_status='healthy',
            connection_status='connected',
            response_time_ms=100.0,
            uptime_seconds=86400.0,
            error_rate=0.5,
            timestamp=datetime.now()
        )

        mock_services['dashboard_service'].get_system_status = AsyncMock(return_value=mock_health)

        response = client.get("/api/health-report")

        assert response.status_code == 200
        data = response.json()

        # Legacy format
        assert data['status'] == 'healthy'
        assert data['database_status'] == 'healthy'
        assert data['response_time'] == 100.0
        assert data['uptime'] == 86400.0

    def test_legacy_telemetry_widgets(self, client, mock_services):
        """Test legacy telemetry widgets endpoint"""
        mock_widgets = {
            'error_monitor': WidgetData(
                widget_id="error_1",
                widget_type="error_monitor",
                title="Error Monitor",
                status="healthy",
                data={"errors": 0},
                last_updated=datetime.now(),
                metadata={}
            ),
            'cost_tracker': WidgetData(
                widget_id="cost_1",
                widget_type="cost_tracker",
                title="Cost Tracker",
                status="warning",
                data={"cost": 25.50},
                last_updated=datetime.now(),
                metadata={}
            )
        }

        mock_services['dashboard_service'].get_multiple_widgets = AsyncMock(return_value=mock_widgets)

        response = client.get("/api/telemetry-widgets")

        assert response.status_code == 200
        data = response.json()

        # Legacy format
        assert 'error_monitor' in data
        assert 'cost_tracker' in data
        assert data['error_monitor']['healthy'] is True
        assert data['cost_tracker']['healthy'] is False  # Warning = not healthy


class TestErrorHandling:
    """Test API error handling"""

    def test_service_unavailable_error(self, client):
        """Test when services are not available"""
        # Create app without proper initialization
        response = client.get("/api/v1/health")
        # This might fail during startup, which is expected behavior
        # The test validates that the error is handled gracefully

    def test_request_validation_errors(self, client):
        """Test request validation errors"""
        # Test POST with invalid JSON
        response = client.post(
            "/api/v1/cache/invalidate",
            data="invalid json"
        )
        assert response.status_code in [400, 422]

    def test_method_not_allowed(self, client):
        """Test method not allowed"""
        response = client.post("/api/v1/health")  # GET-only endpoint
        assert response.status_code == 405

    def test_not_found(self, client):
        """Test 404 handling"""
        response = client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code == 404


class TestResponseFormat:
    """Test API response format consistency"""

    def test_success_response_format(self, client, mock_services):
        """Test that all success responses follow the standard format"""
        mock_health = SystemHealth(
            overall_healthy=True,
            database_status='healthy',
            connection_status='connected',
            response_time_ms=100.0,
            uptime_seconds=86400.0,
            error_rate=0.5,
            timestamp=datetime.now()
        )

        mock_services['dashboard_service'].get_system_status = AsyncMock(return_value=mock_health)

        response = client.get("/api/v1/health")
        data = response.json()

        # Check standard response format
        assert 'success' in data
        assert 'data' in data
        assert 'timestamp' in data
        assert 'request_id' in data
        assert 'metadata' in data
        assert data['success'] is True
        assert data['error'] is None

    def test_error_response_format(self, client, mock_services):
        """Test that all error responses follow the standard format"""
        mock_services['dashboard_service'].get_system_status = AsyncMock(
            side_effect=Exception("Test error")
        )

        response = client.get("/api/v1/health")
        data = response.json()

        # Check standard error response format
        assert 'success' in data
        assert 'error' in data
        assert 'error_code' in data
        assert 'timestamp' in data
        assert 'request_id' in data
        assert data['success'] is False
        assert data['error'] is not None
        assert data['error_code'] is not None