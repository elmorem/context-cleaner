"""
Tests for Comprehensive Error Handling System (Phase 3 component).
"""

import pytest
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from context_cleaner.utils.error_handling import (
    ErrorHandler,
    ContextCleanerError,
    StorageError,
    AnalysisError,
    IntegrationError,
    PerformanceError,
    ErrorSeverity,
    ErrorCategory,
    error_handler,
    get_error_handler
)
from context_cleaner.config.settings import ContextCleanerConfig


@pytest.fixture
def error_handler_instance(test_config):
    """Create ErrorHandler instance for testing."""
    return ErrorHandler(test_config)


class TestContextCleanerError:
    """Test suite for custom exception classes."""

    def test_context_cleaner_error_creation(self):
        """Test creation of base ContextCleanerError."""
        details = {"context": "test", "value": 42}
        cause = ValueError("Original error")
        
        error = ContextCleanerError(
            message="Test error message",
            category=ErrorCategory.ANALYSIS,
            severity=ErrorSeverity.HIGH,
            details=details,
            cause=cause
        )
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.ANALYSIS
        assert error.severity == ErrorSeverity.HIGH
        assert error.details == details
        assert error.cause == cause
        assert error.timestamp is not None
        assert "analysis_" in error.error_id

    def test_specialized_error_classes(self):
        """Test specialized error class inheritance."""
        storage_error = StorageError("Storage failed")
        assert storage_error.category == ErrorCategory.STORAGE
        
        analysis_error = AnalysisError("Analysis failed")
        assert analysis_error.category == ErrorCategory.ANALYSIS
        
        integration_error = IntegrationError("Integration failed")
        assert integration_error.category == ErrorCategory.INTEGRATION
        
        performance_error = PerformanceError("Performance issue")
        assert performance_error.category == ErrorCategory.PERFORMANCE


class TestErrorHandler:
    """Test suite for ErrorHandler class."""

    def test_error_handler_initialization(self, error_handler_instance):
        """Test proper initialization of error handler."""
        assert error_handler_instance.circuit_breaker_threshold == 5
        assert error_handler_instance.critical_error_count == 0
        assert error_handler_instance.circuit_broken is False
        assert len(error_handler_instance.recent_errors) == 0
        assert len(error_handler_instance.error_counts) == 0
        assert len(error_handler_instance.recovery_strategies) > 0

    def test_handle_context_cleaner_error(self, error_handler_instance):
        """Test handling of ContextCleanerError."""
        error = AnalysisError(
            "Test analysis error",
            severity=ErrorSeverity.MEDIUM,
            details={"operation": "test"}
        )
        
        result = error_handler_instance.handle_error(error)
        
        assert result is True  # Should be handled
        assert len(error_handler_instance.recent_errors) == 1
        assert error_handler_instance.recent_errors[0] == error
        
        # Check error counts
        error_key = f"{ErrorCategory.ANALYSIS.value}_{ErrorSeverity.MEDIUM.value}"
        assert error_handler_instance.error_counts[error_key] == 1

    def test_handle_unknown_error(self, error_handler_instance):
        """Test handling of unknown exception types."""
        error = ValueError("Unknown error")
        context = {"function": "test_function"}
        
        result = error_handler_instance.handle_error(error, context)
        
        assert result is True  # Should be handled with classification
        assert len(error_handler_instance.recent_errors) == 1
        
        handled_error = error_handler_instance.recent_errors[0]
        assert isinstance(handled_error, ContextCleanerError)
        assert handled_error.message == "Unknown error"
        assert handled_error.cause == error

    def test_error_classification(self, error_handler_instance):
        """Test automatic error classification."""
        # Test storage error classification
        storage_error = IOError("File permission denied")
        classified = error_handler_instance._classify_error(storage_error, {})
        assert classified.category == ErrorCategory.STORAGE
        
        # Test memory error classification
        memory_error = MemoryError("Out of memory")
        classified = error_handler_instance._classify_error(memory_error, {})
        assert classified.severity == ErrorSeverity.CRITICAL
        
        # Test analysis error classification
        data_error = Exception("Data processing failed")
        classified = error_handler_instance._classify_error(data_error, {})
        assert classified.category == ErrorCategory.ANALYSIS

    def test_circuit_breaker_activation(self, error_handler_instance):
        """Test circuit breaker activation on critical errors."""
        # Add critical errors up to threshold
        for i in range(5):
            critical_error = ContextCleanerError(
                f"Critical error {i}",
                severity=ErrorSeverity.CRITICAL
            )
            result = error_handler_instance.handle_error(critical_error)
            
            if i < 4:
                assert result is True
                assert error_handler_instance.circuit_broken is False
            else:
                assert result is False  # Circuit should break
                assert error_handler_instance.circuit_broken is True

    def test_recovery_strategies(self, error_handler_instance):
        """Test recovery strategies for different error categories."""
        # Test storage error recovery
        storage_error = StorageError("Permission denied", severity=ErrorSeverity.MEDIUM)
        recovery_result = error_handler_instance._attempt_recovery(storage_error)
        assert recovery_result is True
        
        # Test analysis error recovery
        analysis_error = AnalysisError("Data invalid", severity=ErrorSeverity.MEDIUM)
        recovery_result = error_handler_instance._attempt_recovery(analysis_error)
        assert recovery_result is True
        
        # Test critical error - should not recover
        critical_error = ContextCleanerError("System failure", severity=ErrorSeverity.CRITICAL)
        recovery_result = error_handler_instance._attempt_recovery(critical_error)
        assert recovery_result is False

    def test_error_sanitization(self, error_handler_instance):
        """Test sanitization of sensitive information in errors."""
        details = {
            "traceback": "Error in /home/user/secret/file.py at line 42",
            "context": {
                "password": "secret123",
                "api_key": "abc123def456",
                "safe_data": "public info"
            }
        }
        
        sanitized = error_handler_instance._sanitize_error_details(details)
        
        # Check traceback sanitization
        assert "/home/user/secret/file.py" not in sanitized["traceback"]
        assert "[PATH]" in sanitized["traceback"]
        
        # Check context sanitization
        assert sanitized["context"]["password"] == "[REDACTED]"
        assert sanitized["context"]["api_key"] == "[REDACTED]"
        assert sanitized["context"]["safe_data"] == "public info"

    def test_error_summary_empty(self, error_handler_instance):
        """Test error summary with no errors."""
        summary = error_handler_instance.get_error_summary(hours=24)
        
        assert summary["total_errors"] == 0
        assert summary["status"] == "healthy"
        assert summary["circuit_broken"] is False

    def test_error_summary_with_errors(self, error_handler_instance):
        """Test error summary with various errors."""
        # Add different types of errors
        errors = [
            AnalysisError("Analysis failed", severity=ErrorSeverity.MEDIUM),
            StorageError("Storage error", severity=ErrorSeverity.LOW),
            PerformanceError("Slow operation", severity=ErrorSeverity.HIGH),
            IntegrationError("Connection failed", severity=ErrorSeverity.MEDIUM)
        ]
        
        for error in errors:
            error_handler_instance.handle_error(error)
        
        summary = error_handler_instance.get_error_summary(hours=1)
        
        assert summary["total_errors"] == 4
        assert summary["status"] == "degraded"  # Due to high severity error
        assert len(summary["by_category"]) == 4
        assert len(summary["by_severity"]) >= 2
        assert summary["most_common_category"] in ["analysis", "storage", "performance", "integration"]

    def test_error_logging(self, error_handler_instance, caplog):
        """Test error logging functionality."""
        with caplog.at_level(logging.WARNING):
            error = AnalysisError("Test logging error", severity=ErrorSeverity.MEDIUM)
            error_handler_instance.handle_error(error)
        
        # Check that error was logged
        assert len(caplog.records) >= 1
        log_record = caplog.records[-1]
        assert "ANALYSIS" in log_record.message
        assert "Test logging error" in log_record.message


class TestErrorDecorator:
    """Test suite for error_handler decorator."""

    def test_error_decorator_success(self):
        """Test error decorator with successful function."""
        @error_handler(category=ErrorCategory.ANALYSIS)
        def successful_function(x, y):
            return x + y
        
        result = successful_function(2, 3)
        assert result == 5

    def test_error_decorator_with_exception(self):
        """Test error decorator with function that raises exception."""
        @error_handler(
            category=ErrorCategory.ANALYSIS,
            severity=ErrorSeverity.MEDIUM,
            fallback_return="fallback_value"
        )
        def failing_function():
            raise ValueError("Test error")
        
        result = failing_function()
        assert result == "fallback_value"

    def test_error_decorator_unhandled_error(self):
        """Test error decorator with critical error that can't be handled."""
        @error_handler(category=ErrorCategory.SYSTEM, severity=ErrorSeverity.CRITICAL)
        def critical_failure():
            raise SystemError("Critical system error")
        
        # Should re-raise critical errors
        with pytest.raises(SystemError):
            critical_failure()


class TestGlobalErrorHandler:
    """Test suite for global error handler functionality."""

    def test_global_error_handler_singleton(self):
        """Test global error handler singleton pattern."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2  # Should be the same instance

    def test_global_error_handler_functionality(self):
        """Test global error handler basic functionality."""
        handler = get_error_handler()
        
        test_error = AnalysisError("Global handler test")
        result = handler.handle_error(test_error)
        
        assert result is True
        assert len(handler.recent_errors) >= 1


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling system."""

    def test_error_handler_with_storage(self, error_handler_instance):
        """Test error handler integration with storage system."""
        # Add some errors
        for i in range(3):
            error = AnalysisError(f"Test error {i}", severity=ErrorSeverity.MEDIUM)
            error_handler_instance.handle_error(error)
        
        # Test save functionality
        try:
            error_handler_instance._save_error_history()
        except Exception as e:
            pytest.fail(f"Error saving failed: {e}")
        
        # Test load functionality
        try:
            error_handler_instance._load_error_history()
        except Exception as e:
            pytest.fail(f"Error loading failed: {e}")

    def test_error_handling_performance_impact(self, error_handler_instance):
        """Test performance impact of error handling."""
        import time
        
        # Measure time for handling multiple errors
        start_time = time.perf_counter()
        
        for i in range(100):
            error = AnalysisError(f"Performance test error {i}")
            error_handler_instance.handle_error(error)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Should handle 100 errors in reasonable time (< 1 second)
        assert total_time < 1.0
        
        # Verify all errors were handled
        assert len(error_handler_instance.recent_errors) == 100

    def test_error_handler_with_logging_system(self, error_handler_instance, tmp_path):
        """Test error handler integration with logging system."""
        # Create temporary log file
        log_file = tmp_path / "test_errors.log"
        
        # Setup file handler for testing
        file_handler = logging.FileHandler(log_file)
        error_handler_instance.logger.addHandler(file_handler)
        
        # Generate errors
        error = ContextCleanerError("Test logged error", severity=ErrorSeverity.HIGH)
        error_handler_instance.handle_error(error)
        
        # Verify error was logged to file
        file_handler.close()
        log_content = log_file.read_text()
        assert "Test logged error" in log_content
        assert "HIGH" in log_content or "ERROR" in log_content

    def test_complete_error_handling_workflow(self, error_handler_instance):
        """Test complete error handling workflow."""
        # Simulate realistic error scenarios
        
        # 1. Storage permission error
        storage_error = StorageError("Permission denied accessing data directory")
        result = error_handler_instance.handle_error(storage_error)
        assert result is True  # Should be recoverable
        
        # 2. Performance timeout
        perf_error = PerformanceError("Operation timeout after 30 seconds")
        result = error_handler_instance.handle_error(perf_error)
        assert result is True  # Should be recoverable
        
        # 3. Analysis data error
        analysis_error = AnalysisError("Invalid data format in analysis")
        result = error_handler_instance.handle_error(analysis_error)
        assert result is True  # Should be recoverable
        
        # 4. Critical system error
        system_error = ContextCleanerError("Memory corruption detected", severity=ErrorSeverity.CRITICAL)
        result = error_handler_instance.handle_error(system_error)
        assert result is True  # First critical error should be handled
        
        # Generate comprehensive error summary
        summary = error_handler_instance.get_error_summary(hours=1)
        
        assert summary["total_errors"] == 4
        assert summary["status"] in ["degraded", "unstable"]  # Due to critical error
        assert len(summary["by_category"]) >= 3
        assert summary["by_severity"]["critical"] == 1


if __name__ == "__main__":
    pytest.main([__file__])