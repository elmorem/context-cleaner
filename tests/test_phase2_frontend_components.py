import pytest
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
import json

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from context_cleaner.core.api_response_formatter import APIResponseFormatter

class TestFrontendIntegration:
    """Test Phase 2 frontend component integration with backend systems."""
    
    def setup_method(self):
        """Setup test environment for each test."""
        self.test_responses = {
            "success": APIResponseFormatter.success({"test": "data"}, "Test successful"),
            "error": APIResponseFormatter.error("Test error", "TEST_ERROR"),
            "loading": APIResponseFormatter.loading("Loading test data...", 25.5),
            "degraded": APIResponseFormatter.degraded({"partial": "data"}, "Service degraded")
        }
    
    def test_api_response_integration_with_frontend_expectations(self):
        """Test that API responses match frontend component expectations."""
        
        # Test success response structure
        success_response = self.test_responses["success"]
        assert success_response["status"] == "success"
        assert "data" in success_response
        assert "timestamp" in success_response
        assert success_response["error"] is None
        
        # Test error response structure for frontend error handling
        error_response = self.test_responses["error"]
        assert error_response["status"] == "error"
        assert "error_code" in error_response
        assert error_response["message"] == "Test error"
        
        # Test loading response structure for loading manager
        loading_response = self.test_responses["loading"]
        assert loading_response["status"] == "loading"
        assert loading_response["progress"] == 25.5
        assert loading_response["data"] is None
    
    def test_timeout_scenarios_for_frontend_handling(self):
        """Test various timeout scenarios that frontend should handle."""
        
        # Test timeout error response
        timeout_error = APIResponseFormatter.error(
            "Request timeout", 
            "TIMEOUT_ERROR", 
            status_code=408
        )
        
        assert timeout_error["status"] == "error"
        assert timeout_error["error_code"] == "TIMEOUT_ERROR"
        assert "timeout" in timeout_error["message"].lower()
        
        # Test degraded service response for partial failures
        degraded_response = APIResponseFormatter.degraded(
            {"cached_data": "available"}, 
            "Service temporarily unavailable, showing cached data",
            "CACHE_FALLBACK"
        )
        
        assert degraded_response["status"] == "degraded"
        assert degraded_response["warning_code"] == "CACHE_FALLBACK"
        assert "cached_data" in degraded_response["data"]
    
    def test_loading_state_progression_responses(self):
        """Test loading state progression for frontend loading manager."""
        
        # Test initial loading state
        initial_loading = APIResponseFormatter.loading("Initializing...", 0.0)
        assert initial_loading["progress"] == 0.0
        assert "initializing" in initial_loading["message"].lower()
        
        # Test progress update
        progress_loading = APIResponseFormatter.loading("Processing data...", 50.0)
        assert progress_loading["progress"] == 50.0
        assert progress_loading["status"] == "loading"
        
        # Test completion response
        completion = APIResponseFormatter.success(
            {"processed": "data"}, 
            "Processing complete"
        )
        assert completion["status"] == "success"
        assert completion["data"]["processed"] == "data"
    
    def test_retry_scenario_responses(self):
        """Test retry scenario handling for frontend retry logic."""
        
        # Test retriable error
        retriable_error = APIResponseFormatter.error(
            "Service temporarily unavailable",
            "SERVICE_UNAVAILABLE",
            status_code=503
        )
        
        assert retriable_error["error_code"] == "SERVICE_UNAVAILABLE"
        assert retriable_error["status"] == "error"
        
        # Test non-retriable error
        client_error = APIResponseFormatter.error(
            "Invalid request format",
            "INVALID_REQUEST",
            status_code=400
        )
        
        assert client_error["error_code"] == "INVALID_REQUEST"
        assert client_error["status"] == "error"
    
    def test_batch_request_response_handling(self):
        """Test batch request response structure for frontend processing."""
        
        # Simulate batch response
        batch_data = [
            {"id": 1, "status": "success", "data": {"result": "A"}},
            {"id": 2, "status": "error", "error": "Failed to process"},
            {"id": 3, "status": "success", "data": {"result": "C"}}
        ]
        
        batch_response = APIResponseFormatter.success(
            batch_data, 
            "Batch processing completed with partial failures"
        )
        
        assert batch_response["status"] == "success"
        assert len(batch_response["data"]) == 3
        assert batch_response["data"][0]["status"] == "success"
        assert batch_response["data"][1]["status"] == "error"
    
    def test_health_check_response_format(self):
        """Test health check response format for frontend monitoring."""
        
        # Test healthy system response
        healthy_data = {
            "overall_status": "healthy",
            "services": {
                "file_system": {"status": "healthy", "response_time": 45.2},
                "processing": {"status": "healthy", "response_time": 123.4}
            }
        }
        
        health_response = APIResponseFormatter.success(
            healthy_data, 
            "All systems operational"
        )
        
        assert health_response["status"] == "success"
        assert health_response["data"]["overall_status"] == "healthy"
        assert "services" in health_response["data"]
        
        # Test degraded system response
        degraded_data = {
            "overall_status": "degraded",
            "services": {
                "file_system": {"status": "healthy", "response_time": 45.2},
                "processing": {"status": "degraded", "response_time": 2500.0}
            }
        }
        
        degraded_health = APIResponseFormatter.degraded(
            degraded_data,
            "Some services experiencing issues",
            "PARTIAL_OUTAGE"
        )
        
        assert degraded_health["status"] == "degraded"
        assert degraded_health["warning_code"] == "PARTIAL_OUTAGE"

class TestFrontendErrorHandling:
    """Test frontend error handling scenarios."""
    
    def test_network_error_responses(self):
        """Test network error response formats."""
        
        # Test connection timeout
        timeout_response = APIResponseFormatter.error(
            "Connection timeout after 15 seconds",
            "CONNECTION_TIMEOUT",
            status_code=408
        )
        
        assert "timeout" in timeout_response["message"].lower()
        assert timeout_response["error_code"] == "CONNECTION_TIMEOUT"
        
        # Test network unavailable
        network_error = APIResponseFormatter.error(
            "Network unreachable",
            "NETWORK_ERROR",
            status_code=503
        )
        
        assert "network" in network_error["message"].lower()
        assert network_error["error_code"] == "NETWORK_ERROR"
    
    def test_server_error_responses(self):
        """Test server error response formats."""
        
        # Test internal server error
        server_error = APIResponseFormatter.error(
            "Internal server error occurred",
            "INTERNAL_ERROR",
            status_code=500
        )
        
        assert server_error["error_code"] == "INTERNAL_ERROR"
        assert server_error["status"] == "error"
        
        # Test service unavailable
        unavailable_error = APIResponseFormatter.error(
            "Service temporarily unavailable",
            "SERVICE_UNAVAILABLE", 
            status_code=503
        )
        
        assert unavailable_error["error_code"] == "SERVICE_UNAVAILABLE"
    
    def test_validation_error_responses(self):
        """Test validation error response formats."""
        
        # Test invalid data format
        validation_data = {"incomplete": "data"}
        validation_schema = {"required": ["required_field", "another_field"]}
        
        validation_response = APIResponseFormatter.validate_and_format(
            validation_data, 
            validation_schema
        )
        
        assert validation_response["status"] == "error"
        assert validation_response["error_code"] == "INVALID_SCHEMA"
        assert "required_field" in validation_response["message"]

class TestProgressiveFeedbackScenarios:
    """Test progressive feedback scenarios for loading management."""
    
    def test_short_operation_flow(self):
        """Test short operation that completes quickly."""
        
        # Start loading
        initial = APIResponseFormatter.loading("Processing...", 0.0)
        assert initial["status"] == "loading"
        assert initial["progress"] == 0.0
        
        # Quick completion (under 3 seconds)
        completion = APIResponseFormatter.success(
            {"result": "processed"},
            "Operation completed successfully"
        )
        assert completion["status"] == "success"
    
    def test_medium_operation_flow(self):
        """Test medium operation with progress updates."""
        
        # Initial loading
        initial = APIResponseFormatter.loading("Starting process...", 0.0)
        
        # Progress updates
        progress_25 = APIResponseFormatter.loading("Processing files...", 25.0)
        progress_50 = APIResponseFormatter.loading("Analyzing data...", 50.0)
        progress_75 = APIResponseFormatter.loading("Generating results...", 75.0)
        
        # Completion
        completion = APIResponseFormatter.success(
            {"files_processed": 100, "analysis_complete": True},
            "Processing completed"
        )
        
        assert all(resp["status"] == "loading" for resp in [initial, progress_25, progress_50, progress_75])
        assert completion["status"] == "success"
    
    def test_long_operation_with_timeout_warning(self):
        """Test long operation that triggers timeout warnings."""
        
        # Initial loading
        initial = APIResponseFormatter.loading("Starting complex operation...", 0.0)
        
        # Progressive feedback after timeout threshold
        warning = APIResponseFormatter.degraded(
            {"partial_progress": "available"},
            "Operation is taking longer than expected",
            "TIMEOUT_WARNING"
        )
        
        assert initial["status"] == "loading"
        assert warning["status"] == "degraded"
        assert warning["warning_code"] == "TIMEOUT_WARNING"
    
    def test_operation_timeout_and_recovery(self):
        """Test operation timeout and recovery scenarios."""
        
        # Timeout error
        timeout = APIResponseFormatter.error(
            "Operation timed out after 30 seconds",
            "OPERATION_TIMEOUT",
            status_code=408
        )
        
        # Retry attempt
        retry_loading = APIResponseFormatter.loading("Retrying operation...", 0.0)
        
        # Successful recovery
        recovery = APIResponseFormatter.success(
            {"recovered": True, "retry_count": 1},
            "Operation completed on retry"
        )
        
        assert timeout["status"] == "error"
        assert retry_loading["status"] == "loading"
        assert recovery["status"] == "success"

class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with frontend responses."""
    
    def test_circuit_open_response(self):
        """Test response when circuit breaker is open."""
        
        circuit_open_error = APIResponseFormatter.error(
            "Service temporarily unavailable due to repeated failures",
            "CIRCUIT_BREAKER_OPEN",
            status_code=503
        )
        
        assert circuit_open_error["status"] == "error"
        assert circuit_open_error["error_code"] == "CIRCUIT_BREAKER_OPEN"
        assert "temporarily unavailable" in circuit_open_error["message"].lower()
    
    def test_circuit_half_open_response(self):
        """Test response when circuit breaker is in half-open state."""
        
        half_open_response = APIResponseFormatter.degraded(
            {"limited_functionality": True},
            "Service is recovering, limited functionality available",
            "CIRCUIT_HALF_OPEN"
        )
        
        assert half_open_response["status"] == "degraded"
        assert half_open_response["warning_code"] == "CIRCUIT_HALF_OPEN"
        assert half_open_response["data"]["limited_functionality"] is True

if __name__ == "__main__":
    # Run tests manually if needed
    pytest.main([__file__, "-v"])