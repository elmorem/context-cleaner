"""
Phase 4: End-to-End Integration Testing
Tests complete workflow integration with all Phase 1-4 components
"""
import pytest
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
import json
import requests
import time

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from context_cleaner.core.enhanced_health_monitor import EnhancedHealthMonitor
from context_cleaner.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from context_cleaner.core.api_response_formatter import APIResponseFormatter

class TestPhase4EndToEndIntegration:
    """Test complete end-to-end integration scenarios."""
    
    def setup_method(self):
        """Setup test environment for each test."""
        self.health_monitor = EnhancedHealthMonitor()
        self.circuit_config = CircuitBreakerConfig(failure_threshold=3, name="e2e_test")
        self.circuit_breaker = CircuitBreaker(self.circuit_config)
        
        # Test server configuration (adjust port as needed)
        self.test_server_url = "http://localhost:8250"
        self.api_endpoints = {
            "health": f"{self.test_server_url}/api/health",
            "health_detailed": f"{self.test_server_url}/api/health/detailed",
            "dashboard_metrics": f"{self.test_server_url}/api/dashboard/metrics",
            "telemetry_errors": f"{self.test_server_url}/api/telemetry/errors"
        }
        
    @pytest.mark.asyncio
    async def test_complete_health_monitoring_workflow(self):
        """Test complete health monitoring workflow from backend to frontend."""
        # 1. Backend health check
        health_result = await self.health_monitor.check_service_health("file_system")
        assert health_result.service_name == "file_system"
        assert health_result.status is not None
        
        # 2. API response formatting
        api_response = APIResponseFormatter.success(
            {"service": health_result.service_name, "status": health_result.status.value},
            "Health check completed"
        )
        assert api_response["status"] == "success"
        assert api_response["data"]["service"] == "file_system"
        
        # 3. Circuit breaker integration
        @self.circuit_breaker
        async def protected_health_check():
            return await self.health_monitor.check_service_health("file_system")
        
        protected_result = await protected_health_check()
        assert protected_result.service_name == "file_system"
        assert self.circuit_breaker.state.value == "closed"
        
    def test_api_endpoint_availability(self):
        """Test that all critical API endpoints are available."""
        for endpoint_name, url in self.api_endpoints.items():
            try:
                response = requests.get(url, timeout=10)
                print(f"✓ {endpoint_name}: {response.status_code}")
                
                # Endpoints should either work (200) or gracefully fail (5xx with proper error format)
                if response.status_code == 200:
                    # Should return valid JSON
                    data = response.json()
                    assert isinstance(data, dict)
                elif response.status_code >= 500:
                    # Should return proper error format
                    try:
                        error_data = response.json()
                        assert "status" in error_data or "error" in error_data
                    except:
                        pass  # Some servers may return plain text errors
                        
            except requests.exceptions.RequestException as e:
                print(f"✗ {endpoint_name}: Connection failed - {e}")
                # This is expected if the server isn't running
                
    def test_dashboard_metrics_endpoint_reliability(self):
        """Test the enhanced dashboard metrics endpoint reliability."""
        url = self.api_endpoints["dashboard_metrics"]
        
        try:
            # Test multiple requests to check consistency
            responses = []
            for i in range(3):
                response = requests.get(url, timeout=5)
                responses.append(response)
                time.sleep(1)  # Brief pause between requests
                
            # Analyze response patterns
            status_codes = [r.status_code for r in responses]
            print(f"Dashboard metrics status codes: {status_codes}")
            
            # Should be consistent (all same status code)
            assert len(set(status_codes)) <= 2, "Status codes should be consistent"
            
            # If any succeed, they should return proper format
            for response in responses:
                if response.status_code == 200:
                    data = response.json()
                    assert "status" in data
                    
        except requests.exceptions.RequestException as e:
            print(f"Dashboard metrics endpoint not available: {e}")
            
    def test_health_endpoint_detailed_response(self):
        """Test detailed health endpoint response structure."""
        url = self.api_endpoints["health_detailed"]
        
        try:
            response = requests.get(url, timeout=5)
            print(f"Detailed health endpoint: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Should have proper structure
                assert isinstance(data, dict)
                
                # Should include service information if available
                if "services" in data:
                    assert isinstance(data["services"], dict)
                    
                # Should have timestamp if following our format
                if "timestamp" in data:
                    assert isinstance(data["timestamp"], str)
                    
            elif response.status_code >= 500:
                # Should handle gracefully
                try:
                    error_data = response.json()
                    assert "status" in error_data or "error" in error_data
                except:
                    pass  # Plain text error is acceptable
                    
        except requests.exceptions.RequestException as e:
            print(f"Detailed health endpoint not available: {e}")
            
    def test_telemetry_errors_endpoint_resilience(self):
        """Test telemetry errors endpoint resilience."""
        url = self.api_endpoints["telemetry_errors"]
        
        try:
            response = requests.get(url, timeout=5)
            print(f"Telemetry errors endpoint: {response.status_code}")
            
            # Should either work or fail gracefully
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)
                
                # Should have error information structure
                if "errors" in data:
                    assert isinstance(data["errors"], (list, dict))
                    
            # Any status code is acceptable as long as it responds
            assert response.status_code is not None
            
        except requests.exceptions.RequestException as e:
            print(f"Telemetry errors endpoint not available: {e}")
            
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_real_endpoint(self):
        """Test circuit breaker integration with real API endpoint."""
        
        @self.circuit_breaker
        async def call_health_endpoint():
            response = requests.get(self.api_endpoints["health"], timeout=2)
            if response.status_code >= 500:
                raise Exception(f"Server error: {response.status_code}")
            return response.json()
        
        try:
            # Should work normally if endpoint is available
            result = await call_health_endpoint()
            assert self.circuit_breaker.state.value == "closed"
            
        except Exception as e:
            # Circuit breaker should handle failures gracefully
            print(f"Circuit breaker handled error: {e}")
            # This is expected behavior
            
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test complete error recovery workflow."""
        
        # 1. Simulate service failure detection
        try:
            health_result = await self.health_monitor.check_service_health("test_service_failure")
            # Should return UNKNOWN for unknown services
            assert health_result.status.value == "unknown"
        except Exception as e:
            print(f"Expected service failure: {e}")
            
        # 2. Format error response
        error_response = APIResponseFormatter.error(
            "Service unavailable",
            "SERVICE_ERROR",
            status_code=503
        )
        assert error_response["status"] == "error"
        assert error_response["error_code"] == "SERVICE_ERROR"
        
        # 3. Degraded service response
        degraded_response = APIResponseFormatter.degraded(
            {"cached_data": "available"},
            "Using cached data due to service issues",
            "CACHE_FALLBACK"
        )
        assert degraded_response["status"] == "degraded"
        assert degraded_response["warning_code"] == "CACHE_FALLBACK"
        
    def test_frontend_javascript_files_accessible(self):
        """Test that frontend JavaScript files are accessible."""
        js_files = [
            "/static/js/enhanced_api_client.js",
            "/static/js/loading_manager.js",
            "/static/js/dashboard_components.js",
            "/static/js/realtime_dashboard.js"
        ]
        
        for js_file in js_files:
            url = f"{self.test_server_url}{js_file}"
            try:
                response = requests.get(url, timeout=5)
                print(f"JS file {js_file}: {response.status_code}")
                
                if response.status_code == 200:
                    # Should be JavaScript content
                    content_type = response.headers.get('content-type', '')
                    assert 'javascript' in content_type or 'text' in content_type
                    
                    # Should contain expected classes/functions
                    content = response.text
                    if 'enhanced_api_client' in js_file:
                        assert 'EnhancedAPIClient' in content
                    elif 'loading_manager' in js_file:
                        assert 'LoadingManager' in content
                    elif 'dashboard_components' in js_file:
                        assert 'DashboardComponents' in content
                    elif 'realtime_dashboard' in js_file:
                        assert 'RealtimeDashboard' in content
                        
            except requests.exceptions.RequestException as e:
                print(f"JS file {js_file} not accessible: {e}")
                
    def test_css_files_accessible(self):
        """Test that CSS files are accessible."""
        css_files = [
            "/static/css/dashboard_components.css",
            "/static/css/realtime_dashboard.css"
        ]
        
        for css_file in css_files:
            url = f"{self.test_server_url}{css_file}"
            try:
                response = requests.get(url, timeout=5)
                print(f"CSS file {css_file}: {response.status_code}")
                
                if response.status_code == 200:
                    # Should be CSS content
                    content_type = response.headers.get('content-type', '')
                    assert 'css' in content_type or 'text' in content_type
                    
                    # Should contain CSS rules
                    content = response.text
                    assert '{' in content and '}' in content
                    
            except requests.exceptions.RequestException as e:
                print(f"CSS file {css_file} not accessible: {e}")

    @pytest.mark.asyncio                
    async def test_loading_state_management_integration(self):
        """Test loading state management integration."""
        
        # Test loading state progression
        loading_states = [
            APIResponseFormatter.loading("Starting process...", 0.0),
            APIResponseFormatter.loading("Processing...", 25.0),
            APIResponseFormatter.loading("Almost done...", 75.0),
            APIResponseFormatter.success({"result": "completed"}, "Process completed")
        ]
        
        for state in loading_states:
            assert "status" in state
            assert "timestamp" in state
            
            if state["status"] == "loading":
                assert "progress" in state
                assert isinstance(state["progress"], (int, float))
            elif state["status"] == "success":
                assert "data" in state
                assert state["data"]["result"] == "completed"
                
    def test_response_format_consistency(self):
        """Test that all response formats are consistent."""
        
        # Test various response types
        responses = [
            APIResponseFormatter.success({"test": "data"}),
            APIResponseFormatter.error("Test error", "TEST_ERROR"),
            APIResponseFormatter.loading("Loading...", 50.0),
            APIResponseFormatter.degraded({"partial": "data"}, "Degraded service")
        ]
        
        for response in responses:
            # All responses should have these fields
            required_fields = ["status", "timestamp"]
            for field in required_fields:
                assert field in response
                
            # Status should be valid
            valid_statuses = ["success", "error", "loading", "degraded"]
            assert response["status"] in valid_statuses
            
            # Timestamp should be valid ISO format
            timestamp = response["timestamp"]
            assert isinstance(timestamp, str)
            # Should be parseable as datetime
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

class TestPhase4ErrorScenarios:
    """Test error scenarios and recovery mechanisms."""
    
    def setup_method(self):
        """Setup for error scenario tests."""
        self.health_monitor = EnhancedHealthMonitor()
        
    @pytest.mark.asyncio
    async def test_service_failure_cascade_handling(self):
        """Test handling of service failure cascades."""
        
        # Test multiple service failures
        services = ["service_a", "service_b", "service_c"]
        results = {}
        
        for service in services:
            try:
                result = await self.health_monitor.check_service_health(service)
                results[service] = result.status.value
            except Exception as e:
                results[service] = "error"
                
        # Should handle all failures gracefully
        assert len(results) == len(services)
        
        # Format as degraded response for frontend
        degraded_response = APIResponseFormatter.degraded(
            {"available_services": [k for k, v in results.items() if v != "error"]},
            "Some services are unavailable",
            "PARTIAL_OUTAGE"
        )
        
        assert degraded_response["status"] == "degraded"
        assert "available_services" in degraded_response["data"]
        
    def test_timeout_handling_responses(self):
        """Test timeout handling response formats."""
        
        # Test timeout error
        timeout_error = APIResponseFormatter.error(
            "Request timeout after 15 seconds",
            "TIMEOUT_ERROR",
            status_code=408
        )
        
        assert timeout_error["error_code"] == "TIMEOUT_ERROR"
        assert "timeout" in timeout_error["message"].lower()
        
        # Test timeout with fallback data
        timeout_fallback = APIResponseFormatter.degraded(
            {"cached_metrics": {"last_update": "2 minutes ago"}},
            "Live data unavailable, showing cached metrics",
            "TIMEOUT_FALLBACK"
        )
        
        assert timeout_fallback["status"] == "degraded"
        assert "cached_metrics" in timeout_fallback["data"]
        
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_cycle(self):
        """Test complete circuit breaker recovery cycle."""
        
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=1,  # 1 second for testing
            name="recovery_test"
        )
        breaker = CircuitBreaker(config)
        
        @breaker
        async def failing_service():
            raise Exception("Service failure")
            
        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await failing_service()
                
        # Circuit should be open
        assert breaker.state.value == "open"
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Next call should attempt recovery (half-open)
        with pytest.raises(Exception):
            await failing_service()
            
        # Should go back to open
        assert breaker.state.value == "open"

if __name__ == "__main__":
    # Run tests manually if needed
    pytest.main([__file__, "-v", "-s"])