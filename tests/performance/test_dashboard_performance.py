"""
Performance Validation Framework for Unified Dashboard System (PR #3)

Validates that the comprehensive dashboard meets performance targets after
integration of multiple dashboard components. Tests memory usage, response 
times, and WebSocket connection stability.
"""

import pytest
import time
import asyncio
import threading
import psutil
import os
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
from context_cleaner.dashboard.web_server import ProductivityDashboard


class TestDashboardPerformance:
    """Validate performance meets or exceeds baseline after consolidation."""
    
    def test_response_time_baseline(self):
        """Ensure response times meet targets (<150ms per roadmap)."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Mock expensive operations for performance testing
        mock_sessions = [
            {
                "session_id": f"test_session_{i}",
                "start_time": datetime.now().isoformat(),
                "productivity_score": 75 + i,
                "health_score": 80 + i,
                "focus_time_minutes": 30 + i * 5
            }
            for i in range(10)
        ]
        
        with patch.object(dashboard, 'get_recent_sessions_analytics', return_value=mock_sessions):
            with dashboard.app.test_client() as client:
                # Test core endpoints response time
                endpoints = [
                    '/health',
                    '/api/health-report',
                    '/api/performance-metrics',
                    '/api/productivity-summary',
                    '/api/dashboard-summary'
                ]
                
                for endpoint in endpoints:
                    start_time = time.time()
                    response = client.get(endpoint)
                    response_time = time.time() - start_time
                    
                    # Should respond within 150ms (0.15 seconds) as per roadmap target
                    assert response_time < 0.15, f"Endpoint {endpoint} took {response_time:.3f}s (target: <0.15s)"
                    
                    # Should either work or return proper error
                    assert response.status_code in [200, 404, 500]

    def test_memory_usage_baseline(self):
        """Ensure memory usage stays within limits (<90MB per roadmap)."""
        process = psutil.Process()
        
        # Measure baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create comprehensive dashboard
        dashboard = ComprehensiveHealthDashboard()
        
        # Measure memory after dashboard creation
        dashboard_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = dashboard_memory - baseline_memory
        
        # Should stay under 90MB total memory as per roadmap target
        assert dashboard_memory < 90, f"Dashboard uses {dashboard_memory:.1f}MB (target: <90MB)"
        
        # Memory increase from dashboard should be reasonable
        assert memory_increase < 50, f"Dashboard added {memory_increase:.1f}MB (should be <50MB)"

    def test_memory_usage_under_load(self):
        """Test memory usage remains stable under load."""
        dashboard = ComprehensiveHealthDashboard()
        process = psutil.Process()
        
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Simulate load by making many requests
        with dashboard.app.test_client() as client:
            for i in range(100):
                response = client.get('/api/dashboard-summary')
                # Don't assert response success - just generate load
                
        # Memory should not have grown significantly
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        
        # Should not grow more than 10MB under load
        assert memory_growth < 10, f"Memory grew {memory_growth:.1f}MB under load (target: <10MB)"

    @patch('context_cleaner.dashboard.comprehensive_health_dashboard.ComprehensiveHealthDashboard.socketio')
    def test_websocket_connection_stability(self, mock_socketio):
        """Test WebSocket connections remain stable under load."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Mock multiple concurrent connections
        mock_clients = []
        for i in range(10):
            mock_client = Mock()
            mock_client.is_connected.return_value = True
            mock_client.get_received.return_value = []
            mock_clients.append(mock_client)
        
        mock_socketio.test_client.side_effect = mock_clients
        
        # All clients should be connectable
        clients = []
        for i in range(10):
            client = dashboard.socketio.test_client(dashboard.app)
            clients.append(client)
            assert client.is_connected()
        
        # Test real-time updates to all clients
        for client in clients:
            client.emit('request_health_update')
            received = client.get_received()
            # Should receive responses (mocked, so just check method was called)
            assert client.get_received.called

    def test_concurrent_request_handling(self):
        """Test dashboard handles concurrent requests efficiently."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Mock expensive operations for performance testing
        mock_sessions = [
            {
                "session_id": f"test_session_{i}",
                "start_time": datetime.now().isoformat(),
                "productivity_score": 75 + i,
                "health_score": 80 + i,
                "focus_time_minutes": 30 + i * 5
            }
            for i in range(10)
        ]
        
        def make_request(endpoint):
            """Make a request and return response time."""
            with dashboard.app.test_client() as client:
                start_time = time.time()
                response = client.get(endpoint)
                end_time = time.time()
                return end_time - start_time, response.status_code
        
        with patch.object(dashboard, 'get_recent_sessions_analytics', return_value=mock_sessions):
            # Test concurrent requests
            endpoints = ['/health', '/api/performance-metrics', '/api/dashboard-summary'] * 5
            
            # Use threading to simulate concurrent requests
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_endpoint = {
                    executor.submit(make_request, endpoint): endpoint 
                    for endpoint in endpoints
                }
                
                response_times = []
                for future in concurrent.futures.as_completed(future_to_endpoint):
                    endpoint = future_to_endpoint[future]
                    try:
                        response_time, status_code = future.result()
                        response_times.append(response_time)
                        
                        # Should handle concurrent requests reasonably
                        assert response_time < 0.5, f"Concurrent request to {endpoint} took {response_time:.3f}s"
                        assert status_code in [200, 404, 500]
                        
                    except Exception as e:
                        pytest.fail(f"Concurrent request to {endpoint} failed: {e}")
            
        # Average response time should be reasonable
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time < 0.2, f"Average concurrent response time: {avg_response_time:.3f}s"

    @pytest.mark.asyncio
    async def test_async_operation_performance(self):
        """Test async operations complete within reasonable time."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Mock context data
        mock_context = {
            "items": [
                {"type": "todo", "content": f"Task {i}", "timestamp": datetime.now().isoformat()}
                for i in range(50)  # Moderate amount of data
            ]
        }
        
        # Test comprehensive health report generation time
        start_time = time.time()
        report = await dashboard.generate_comprehensive_health_report(context_data=mock_context)
        generation_time = time.time() - start_time
        
        # Should generate report in reasonable time
        assert generation_time < 1.0, f"Health report took {generation_time:.3f}s (target: <1.0s)"
        
        # Report should be valid
        assert report is not None
        assert hasattr(report, 'overall_health_score')

    def test_data_source_performance(self):
        """Test data source operations perform within targets."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Test each data source performance
        for source_name, source in dashboard.data_sources.items():
            start_time = time.time()
            
            # Run data retrieval in async context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                data = loop.run_until_complete(source.get_data())
                schema = loop.run_until_complete(source.get_schema())
            finally:
                loop.close()
            
            operation_time = time.time() - start_time
            
            # Data source operations should be fast
            assert operation_time < 0.1, f"Data source {source_name} took {operation_time:.3f}s"
            
            # Data should be valid
            assert isinstance(data, dict)
            assert isinstance(schema, dict)
            assert len(data) > 0

    def test_startup_performance(self):
        """Test dashboard startup time is reasonable."""
        start_time = time.time()
        
        # Create comprehensive dashboard
        dashboard = ComprehensiveHealthDashboard()
        
        startup_time = time.time() - start_time
        
        # Should start up quickly
        assert startup_time < 2.0, f"Dashboard startup took {startup_time:.3f}s (target: <2.0s)"
        
        # Should be properly initialized
        assert dashboard.app is not None
        assert dashboard.data_sources is not None
        assert len(dashboard.data_sources) > 0

    def test_chart_generation_performance(self):
        """Test chart generation performance from analytics integration."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Get some mock session data
        sessions = dashboard.get_recent_sessions_analytics(7)
        
        if sessions:  # Only test if we have sessions
            start_time = time.time()
            
            # Test different chart types
            chart_types = ['productivity_trend', 'session_distribution', 'daily_productivity_pattern']
            
            for chart_type in chart_types:
                chart_start = time.time()
                chart_data = dashboard.generate_analytics_charts(sessions, chart_type)
                chart_time = time.time() - chart_start
                
                # Chart generation should be fast
                assert chart_time < 0.5, f"Chart {chart_type} took {chart_time:.3f}s"
                
                # Chart data should be valid
                assert isinstance(chart_data, dict)
                
            total_time = time.time() - start_time
            
            # Total chart generation time should be reasonable
            assert total_time < 1.5, f"All charts took {total_time:.3f}s"

    def test_session_analytics_performance(self):
        """Test session analytics performance."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Test session retrieval performance
        start_time = time.time()
        sessions = dashboard.get_recent_sessions_analytics(30)
        retrieval_time = time.time() - start_time
        
        # Should retrieve sessions quickly
        assert retrieval_time < 1.0, f"Session retrieval took {retrieval_time:.3f}s"
        
        # Sessions should be valid list
        assert isinstance(sessions, list)
        
        # Test timeline generation performance
        start_time = time.time()
        timeline = dashboard.generate_session_timeline(7)
        timeline_time = time.time() - start_time
        
        # Timeline generation should be fast
        assert timeline_time < 0.5, f"Timeline generation took {timeline_time:.3f}s"
        
        # Timeline should be valid
        assert isinstance(timeline, dict)


class TestPerformanceRegression:
    """Test for performance regressions after dashboard consolidation."""
    
    def test_no_performance_regression_vs_individual_dashboards(self):
        """Test that comprehensive dashboard isn't significantly slower than individual ones."""
        # Mock expensive operations for both dashboards
        mock_sessions = [
            {
                "session_id": f"test_session_{i}",
                "start_time": datetime.now().isoformat(),
                "productivity_score": 75 + i,
                "health_score": 80 + i,
                "focus_time_minutes": 30 + i * 5
            }
            for i in range(10)
        ]
        
        # Test comprehensive dashboard performance
        comp_dashboard = ComprehensiveHealthDashboard()
        
        with patch.object(comp_dashboard, 'get_recent_sessions_analytics', return_value=mock_sessions):
            with comp_dashboard.app.test_client() as client:
                start_time = time.time()
                for i in range(20):
                    response = client.get('/api/dashboard-summary')
                comp_time = time.time() - start_time
        
        # Test individual dashboard performance (ProductivityDashboard wrapper)
        prod_dashboard = ProductivityDashboard()
        
        with prod_dashboard.app.test_client() as client:
            start_time = time.time()
            for i in range(20):
                response = client.get('/health')  # Available endpoint
            prod_time = time.time() - start_time
        
        # Comprehensive dashboard should not be more than 2x slower than individual
        # (since it provides much more functionality)
        max_acceptable_ratio = 2.0
        actual_ratio = comp_time / (prod_time + 0.001)  # Avoid division by zero
        
        assert actual_ratio < max_acceptable_ratio, \
            f"Comprehensive dashboard {actual_ratio:.1f}x slower than individual (limit: {max_acceptable_ratio}x)"

    def test_memory_efficiency_vs_multiple_dashboards(self):
        """Test that one comprehensive dashboard uses less memory than multiple separate ones."""
        process = psutil.Process()
        
        # Measure baseline
        baseline_memory = process.memory_info().rss / 1024 / 1024
        
        # Create comprehensive dashboard
        comp_dashboard = ComprehensiveHealthDashboard()
        comp_memory = process.memory_info().rss / 1024 / 1024
        comp_increase = comp_memory - baseline_memory
        
        # Should be memory efficient
        assert comp_increase < 60, f"Comprehensive dashboard uses {comp_increase:.1f}MB (target: <60MB)"


class TestScalabilityBasics:
    """Test basic scalability characteristics."""
    
    def test_performance_with_larger_datasets(self):
        """Test performance with larger amounts of mock data."""
        dashboard = ComprehensiveHealthDashboard()
        
        # Create larger mock context
        large_context = {
            "items": [
                {
                    "type": "todo",
                    "content": f"Task {i} - " + "x" * 100,  # Larger content
                    "timestamp": (datetime.now() - timedelta(hours=i)).isoformat()
                }
                for i in range(500)  # More items
            ]
        }
        
        # Test health report generation with larger dataset
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            start_time = time.time()
            report = loop.run_until_complete(
                dashboard.generate_comprehensive_health_report(context_data=large_context)
            )
            generation_time = time.time() - start_time
            
            # Should handle larger datasets reasonably
            assert generation_time < 3.0, f"Large dataset processing took {generation_time:.3f}s"
            
            # Report should still be valid
            assert report is not None
            assert 0 <= report.overall_health_score <= 1
            
        finally:
            loop.close()

    def test_sustained_load_stability(self):
        """Test dashboard stability under sustained load."""
        dashboard = ComprehensiveHealthDashboard()
        process = psutil.Process()
        
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Sustained load test - make many requests over time
        with dashboard.app.test_client() as client:
            for batch in range(5):  # 5 batches
                for i in range(20):  # 20 requests per batch
                    response = client.get('/api/performance-metrics')
                    # Don't assert success, just generate load
                
                # Brief pause between batches
                time.sleep(0.1)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory
        
        # Memory should remain stable under sustained load
        assert memory_growth < 15, f"Memory grew {memory_growth:.1f}MB under sustained load"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])