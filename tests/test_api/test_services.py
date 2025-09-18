"""
Test Suite for API Services

Tests the business logic layer including DashboardService and TelemetryService
with proper mocking of dependencies.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from context_cleaner.api.services import DashboardService, TelemetryService
from context_cleaner.api.models import DashboardMetrics, WidgetData, SystemHealth
from context_cleaner.api.repositories import TelemetryRepository
from context_cleaner.api.cache import CacheService
from context_cleaner.api.websocket import EventBus


class MockTelemetryRepository:
    """Mock repository for testing"""

    async def get_dashboard_metrics(self):
        return DashboardMetrics(
            total_tokens=10000,
            total_sessions=50,
            success_rate=98.5,
            active_agents=5,
            cost=Decimal('25.50'),
            timestamp=datetime.now()
        )

    async def get_system_health(self):
        return SystemHealth(
            overall_healthy=True,
            database_status='healthy',
            connection_status='connected',
            response_time_ms=150.0,
            uptime_seconds=86400.0,
            error_rate=1.5,
            timestamp=datetime.now()
        )

    async def get_widget_data(self, widget_type, session_id=None, time_range_days=7):
        return WidgetData(
            widget_id=f"{widget_type}_test",
            widget_type=widget_type,
            title=f"Test {widget_type}",
            status="healthy",
            data={"test_key": "test_value"},
            last_updated=datetime.now(),
            metadata={}
        )

    async def get_active_sessions(self, limit=50):
        return [
            {
                'session_id': 'test_session_1',
                'last_activity': datetime.now().isoformat(),
                'request_count': 10,
                'cost': 5.25
            },
            {
                'session_id': 'test_session_2',
                'last_activity': datetime.now().isoformat(),
                'request_count': 5,
                'cost': 2.10
            }
        ]

    async def get_cost_trends(self, days=7):
        base_date = datetime.now().date()
        return {
            str(base_date - timedelta(days=i)): 10.0 - i
            for i in range(days)
        }


class MockCacheService:
    """Mock cache service for testing"""

    def __init__(self):
        self.cache = {}

    async def get(self, key):
        return self.cache.get(key)

    async def set(self, key, value, ttl=300):
        self.cache[key] = value
        return True

    async def invalidate(self, pattern):
        keys_to_remove = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_remove:
            del self.cache[key]
        return True

    async def clear(self):
        self.cache.clear()
        return True


class MockEventBus:
    """Mock event bus for testing"""

    def __init__(self):
        self.events = []

    async def emit(self, event_type, data):
        self.events.append({'type': event_type, 'data': data})


@pytest.fixture
async def mock_dependencies():
    """Provide mock dependencies for testing"""
    return {
        'telemetry_repo': MockTelemetryRepository(),
        'cache_service': MockCacheService(),
        'event_bus': MockEventBus()
    }


@pytest.fixture
async def dashboard_service(mock_dependencies):
    """Create DashboardService with mocked dependencies"""
    return DashboardService(
        telemetry_repo=mock_dependencies['telemetry_repo'],
        cache_service=mock_dependencies['cache_service'],
        event_bus=mock_dependencies['event_bus']
    )


@pytest.fixture
async def telemetry_service(mock_dependencies):
    """Create TelemetryService with mocked dependencies"""
    return TelemetryService(
        telemetry_repo=mock_dependencies['telemetry_repo'],
        cache_service=mock_dependencies['cache_service']
    )


class TestDashboardService:
    """Test suite for DashboardService"""

    @pytest.mark.asyncio
    async def test_get_dashboard_overview_fresh_data(self, dashboard_service):
        """Test getting dashboard overview with fresh data"""
        overview = await dashboard_service.get_dashboard_overview()

        assert overview.metrics.total_tokens == 10000
        assert overview.metrics.total_sessions == 50
        assert overview.metrics.success_rate == 98.5
        assert overview.metrics.active_agents == 5
        assert overview.metrics.cost == Decimal('25.50')

        assert overview.system_health.overall_healthy is True
        assert overview.system_health.database_status == 'healthy'

        assert len(overview.widgets) > 0  # Should have essential widgets
        assert overview.last_updated is not None

    @pytest.mark.asyncio
    async def test_get_dashboard_overview_cached_data(self, dashboard_service, mock_dependencies):
        """Test getting dashboard overview from cache"""
        cache = mock_dependencies['cache_service']

        # Prime the cache
        cached_data = {
            "metrics": {
                "total_tokens": 5000,
                "total_sessions": 25,
                "success_rate": 95.0,
                "active_agents": 3,
                "cost": 15.25,
                "timestamp": datetime.now().isoformat()
            },
            "system_health": {
                "overall_healthy": True,
                "database_status": "healthy",
                "connection_status": "connected",
                "response_time_ms": 100.0,
                "uptime_seconds": 43200.0,
                "error_rate": 2.0,
                "timestamp": datetime.now().isoformat()
            },
            "widgets": [],
            "last_updated": datetime.now().isoformat()
        }

        await cache.set("dashboard:overview:v1", cached_data)

        overview = await dashboard_service.get_dashboard_overview()

        # Should return cached data, not fresh data
        assert overview.metrics.total_tokens == 5000  # Cached value, not 10000

    @pytest.mark.asyncio
    async def test_get_widget_data_single(self, dashboard_service):
        """Test getting single widget data"""
        widget_data = await dashboard_service.get_widget_data("error_monitor")

        assert widget_data.widget_type == "error_monitor"
        assert widget_data.status == "healthy"
        assert widget_data.data == {"test_key": "test_value"}
        assert widget_data.last_updated is not None

    @pytest.mark.asyncio
    async def test_get_multiple_widgets_parallel(self, dashboard_service):
        """Test getting multiple widgets in parallel"""
        widget_types = ["error_monitor", "cost_tracker", "model_efficiency"]
        widgets_data = await dashboard_service.get_multiple_widgets(widget_types)

        assert len(widgets_data) == 3
        assert "error_monitor" in widgets_data
        assert "cost_tracker" in widgets_data
        assert "model_efficiency" in widgets_data

        for widget_type, widget_data in widgets_data.items():
            assert widget_data.widget_type == widget_type
            assert widget_data.status == "healthy"

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, dashboard_service, mock_dependencies):
        """Test cache invalidation"""
        cache = mock_dependencies['cache_service']

        # Set some cache data
        await cache.set("dashboard:test:key", {"test": "data"})
        await cache.set("widgets:test:key", {"test": "data"})

        # Invalidate dashboard cache
        success = await dashboard_service.invalidate_cache("dashboard:*")
        assert success is True

        # Dashboard cache should be cleared
        assert await cache.get("dashboard:test:key") is None
        # Widgets cache should still exist
        assert await cache.get("widgets:test:key") is not None

    @pytest.mark.asyncio
    async def test_get_cost_analysis(self, dashboard_service):
        """Test cost analysis functionality"""
        analysis = await dashboard_service.get_cost_analysis(days=7)

        assert "total_cost" in analysis
        assert "average_daily_cost" in analysis
        assert "daily_trends" in analysis
        assert "cost_velocity" in analysis
        assert "projected_monthly" in analysis
        assert "analysis_date" in analysis

        assert analysis["total_cost"] > 0
        assert len(analysis["daily_trends"]) == 7

    @pytest.mark.asyncio
    async def test_event_emission_on_metrics_update(self, dashboard_service, mock_dependencies):
        """Test that events are emitted when metrics change significantly"""
        event_bus = mock_dependencies['event_bus']

        # First call to establish baseline
        await dashboard_service.get_dashboard_overview()
        initial_events = len(event_bus.events)

        # Mock repository to return different metrics
        dashboard_service.telemetry_repo.get_dashboard_metrics = AsyncMock(
            return_value=DashboardMetrics(
                total_tokens=20000,  # Significant increase
                total_sessions=50,
                success_rate=98.5,
                active_agents=5,
                cost=Decimal('50.00'),  # Significant increase
                timestamp=datetime.now()
            )
        )

        # Clear cache to force fresh data
        await dashboard_service.cache.clear()

        # Second call should trigger event
        await dashboard_service.get_dashboard_overview()

        # Should have emitted metrics update event
        assert len(event_bus.events) > initial_events

        # Check for metrics update event
        metrics_events = [e for e in event_bus.events if e['type'] == 'dashboard.metrics.updated']
        assert len(metrics_events) > 0


class TestTelemetryService:
    """Test suite for TelemetryService"""

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, telemetry_service):
        """Test getting active sessions"""
        sessions = await telemetry_service.get_active_sessions(limit=10)

        assert len(sessions) == 2  # Mock returns 2 sessions
        assert sessions[0]['session_id'] == 'test_session_1'
        assert sessions[0]['cost'] == 5.25
        assert sessions[1]['session_id'] == 'test_session_2'
        assert sessions[1]['cost'] == 2.10

    @pytest.mark.asyncio
    async def test_get_active_sessions_cached(self, telemetry_service, mock_dependencies):
        """Test getting active sessions from cache"""
        cache = mock_dependencies['cache_service']

        # Prime cache with different data
        cached_sessions = [
            {'session_id': 'cached_session', 'cost': 10.0}
        ]
        await cache.set("sessions:active:50", cached_sessions)

        sessions = await telemetry_service.get_active_sessions(limit=50)

        # Should return cached data
        assert len(sessions) == 1
        assert sessions[0]['session_id'] == 'cached_session'

    @pytest.mark.asyncio
    async def test_get_session_metrics(self, telemetry_service):
        """Test getting metrics for specific session"""
        metrics = await telemetry_service.get_session_metrics("test_session_id")

        assert metrics is not None
        assert metrics['session_id'] == 'test_session_id'
        assert 'status' in metrics
        assert 'start_time' in metrics
        assert 'request_count' in metrics
        assert 'cost' in metrics


class TestServiceErrorHandling:
    """Test error handling in services"""

    @pytest.mark.asyncio
    async def test_dashboard_service_repository_error(self, mock_dependencies):
        """Test dashboard service handles repository errors gracefully"""
        # Create service with failing repository
        failing_repo = Mock()
        failing_repo.get_dashboard_metrics = AsyncMock(side_effect=Exception("Database error"))
        failing_repo.get_system_health = AsyncMock(side_effect=Exception("Database error"))

        service = DashboardService(
            telemetry_repo=failing_repo,
            cache_service=mock_dependencies['cache_service'],
            event_bus=mock_dependencies['event_bus']
        )

        # Should return fallback data, not raise exception
        overview = await service.get_dashboard_overview()

        assert overview is not None
        assert overview.metrics.total_tokens == 0  # Fallback value
        assert overview.system_health.overall_healthy is False  # Fallback value

    @pytest.mark.asyncio
    async def test_widget_service_error_handling(self, mock_dependencies):
        """Test widget data error handling"""
        failing_repo = Mock()
        failing_repo.get_widget_data = AsyncMock(side_effect=Exception("Widget error"))

        service = DashboardService(
            telemetry_repo=failing_repo,
            cache_service=mock_dependencies['cache_service'],
            event_bus=mock_dependencies['event_bus']
        )

        widget_data = await service.get_widget_data("error_monitor")

        assert widget_data is not None
        assert widget_data.status == "error"
        assert "error" in widget_data.data

    @pytest.mark.asyncio
    async def test_cache_service_error_handling(self, mock_dependencies):
        """Test cache service error handling"""
        # Create failing cache service
        failing_cache = Mock()
        failing_cache.get = AsyncMock(side_effect=Exception("Cache error"))
        failing_cache.set = AsyncMock(side_effect=Exception("Cache error"))

        service = DashboardService(
            telemetry_repo=mock_dependencies['telemetry_repo'],
            cache_service=failing_cache,
            event_bus=mock_dependencies['event_bus']
        )

        # Should still work without cache
        overview = await service.get_dashboard_overview()
        assert overview is not None
        assert overview.metrics.total_tokens == 10000  # Fresh data


class TestServicePerformance:
    """Test performance characteristics of services"""

    @pytest.mark.asyncio
    async def test_parallel_widget_fetch_performance(self, dashboard_service):
        """Test that multiple widgets are fetched in parallel"""
        import time

        widget_types = ["error_monitor", "cost_tracker", "model_efficiency", "timeout_risk"]

        start_time = time.time()
        widgets_data = await dashboard_service.get_multiple_widgets(widget_types)
        end_time = time.time()

        # Should complete in reasonable time (parallel execution)
        execution_time = end_time - start_time
        assert execution_time < 1.0  # Should be fast with mocks
        assert len(widgets_data) == 4

    @pytest.mark.asyncio
    async def test_cache_performance(self, dashboard_service, mock_dependencies):
        """Test cache improves performance"""
        import time

        # First call - cache miss
        start_time = time.time()
        overview1 = await dashboard_service.get_dashboard_overview()
        first_call_time = time.time() - start_time

        # Second call - cache hit
        start_time = time.time()
        overview2 = await dashboard_service.get_dashboard_overview()
        second_call_time = time.time() - start_time

        # Second call should be faster (cached)
        assert second_call_time <= first_call_time

        # Both should return same data
        assert overview1.metrics.total_tokens == overview2.metrics.total_tokens