import pytest
import asyncio
from datetime import datetime
import sys
import os

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from context_cleaner.core.enhanced_health_monitor import EnhancedHealthMonitor, ServiceStatus
from context_cleaner.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from context_cleaner.core.api_response_formatter import APIResponseFormatter

class TestEnhancedHealthMonitor:
    
    @pytest.mark.asyncio
    async def test_health_monitor_basic_functionality(self):
        """Test basic health monitoring functionality."""
        monitor = EnhancedHealthMonitor()
        
        # Test file system health (should always work)
        health = await monitor.check_service_health("file_system")
        assert health.service_name == "file_system"
        assert health.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED, ServiceStatus.FAILING]
        assert isinstance(health.response_time_ms, float)
        assert health.last_check is not None
        
    @pytest.mark.asyncio
    async def test_health_monitor_caching(self):
        """Test health check caching mechanism."""
        monitor = EnhancedHealthMonitor()
        
        # First call
        start_time = datetime.now()
        health1 = await monitor.check_service_health("file_system")
        first_call_time = (datetime.now() - start_time).total_seconds()
        
        # Second call (should be cached and faster)
        start_time = datetime.now()
        health2 = await monitor.check_service_health("file_system")
        second_call_time = (datetime.now() - start_time).total_seconds()
        
        assert health1.service_name == health2.service_name
        assert second_call_time < first_call_time  # Cached call should be faster
        
    @pytest.mark.asyncio
    async def test_overall_system_health(self):
        """Test overall system health aggregation."""
        monitor = EnhancedHealthMonitor()
        
        health_results = await monitor.get_overall_system_health()
        
        assert isinstance(health_results, dict)
        assert "file_system" in health_results
        assert all(hasattr(health, 'status') for health in health_results.values())

    @pytest.mark.asyncio
    async def test_unknown_service_handling(self):
        """Test handling of unknown services."""
        monitor = EnhancedHealthMonitor()
        
        health = await monitor.check_service_health("unknown_service")
        assert health.service_name == "unknown_service"
        assert health.status == ServiceStatus.UNKNOWN
        assert health.error_message == "Unknown service: unknown_service"

class TestCircuitBreaker:
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        config = CircuitBreakerConfig(failure_threshold=3, name="test")
        breaker = CircuitBreaker(config)
        
        async def successful_function():
            return "success"
            
        result = await breaker.call(successful_function)
        assert result == "success"
        assert breaker.state.value == "closed"
        
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=2, name="test")
        breaker = CircuitBreaker(config)
        
        async def failing_function():
            raise Exception("Test failure")
            
        # First failure
        with pytest.raises(Exception):
            await breaker.call(failing_function)
        assert breaker.state.value == "closed"
        
        # Second failure should open the circuit
        with pytest.raises(Exception):
            await breaker.call(failing_function)
        assert breaker.state.value == "open"

    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator(self):
        """Test circuit breaker as decorator."""
        config = CircuitBreakerConfig(failure_threshold=1, name="decorator_test")
        breaker = CircuitBreaker(config)
        
        @breaker
        async def decorated_function(should_fail=False):
            if should_fail:
                raise Exception("Intentional failure")
            return "success"
        
        # Should work normally
        result = await decorated_function(False)
        assert result == "success"
        
        # Should fail and open circuit
        with pytest.raises(Exception):
            await decorated_function(True)
        assert breaker.state.value == "open"

    def test_circuit_breaker_state_reporting(self):
        """Test circuit breaker state reporting."""
        config = CircuitBreakerConfig(failure_threshold=3, name="state_test")
        breaker = CircuitBreaker(config)
        
        state = breaker.get_state()
        assert state["name"] == "state_test"
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["success_count"] == 0

class TestAPIResponseFormatter:
    
    def test_success_response_format(self):
        """Test successful response formatting."""
        data = {"key": "value"}
        response = APIResponseFormatter.success(data, "Operation successful")
        
        assert response["status"] == "success"
        assert response["data"] == data
        assert response["message"] == "Operation successful"
        assert response["error"] is None
        assert "timestamp" in response
        
    def test_error_response_format(self):
        """Test error response formatting."""
        response = APIResponseFormatter.error("Test error", "TEST_ERROR")
        
        assert response["status"] == "error"
        assert response["message"] == "Test error"
        assert response["error_code"] == "TEST_ERROR"
        assert response["error"] == "Test error"
        assert "timestamp" in response
        
    def test_degraded_response_format(self):
        """Test degraded response formatting."""
        data = {"limited": "data"}
        response = APIResponseFormatter.degraded(data, "Service degraded")
        
        assert response["status"] == "degraded"
        assert response["data"] == data
        assert response["message"] == "Service degraded"
        assert response["error"] is None
        assert "timestamp" in response

    def test_loading_response_format(self):
        """Test loading response formatting."""
        response = APIResponseFormatter.loading("Processing...", 50.0)
        
        assert response["status"] == "loading"
        assert response["data"] is None
        assert response["message"] == "Processing..."
        assert response["progress"] == 50.0
        assert response["error"] is None
        assert "timestamp" in response

    def test_validate_and_format_success(self):
        """Test validation with successful data."""
        data = {"required_field": "value", "optional_field": "optional"}
        schema = {"required": ["required_field"]}
        
        response = APIResponseFormatter.validate_and_format(data, schema)
        
        assert response["status"] == "success"
        assert response["data"] == data

    def test_validate_and_format_missing_field(self):
        """Test validation with missing required field."""
        data = {"optional_field": "optional"}
        schema = {"required": ["required_field"]}
        
        response = APIResponseFormatter.validate_and_format(data, schema)
        
        assert response["status"] == "error"
        assert "required_field" in response["message"]
        assert response["error_code"] == "INVALID_SCHEMA"

class TestIntegrationScenarios:
    """Test integration scenarios combining all Phase 1 components."""
    
    @pytest.mark.asyncio
    async def test_health_monitor_with_circuit_breaker(self):
        """Test health monitor working with circuit breaker."""
        monitor = EnhancedHealthMonitor()
        config = CircuitBreakerConfig(failure_threshold=2, name="health_test")
        breaker = CircuitBreaker(config)
        
        @breaker
        async def get_service_health():
            return await monitor.check_service_health("file_system")
        
        # Should work normally
        health = await get_service_health()
        assert health.service_name == "file_system"
        assert breaker.state.value == "closed"

    def test_api_formatter_with_health_data(self):
        """Test API formatter with health monitoring data."""
        # Simulate health check results
        health_data = {
            "file_system": {"status": "healthy", "response_time": 45.2},
            "database": {"status": "degraded", "response_time": 1200.0}
        }
        
        # Format as successful response
        response = APIResponseFormatter.success(health_data, "Health check completed")
        
        assert response["status"] == "success"
        assert response["data"] == health_data
        assert response["message"] == "Health check completed"
        
        # Format as degraded service response
        degraded_response = APIResponseFormatter.degraded(
            health_data, 
            "Some services are degraded", 
            "PARTIAL_OUTAGE"
        )
        
        assert degraded_response["status"] == "degraded"
        assert degraded_response["warning_code"] == "PARTIAL_OUTAGE"

if __name__ == "__main__":
    # Run tests manually if needed
    pytest.main([__file__, "-v"])