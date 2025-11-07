"""
Bridge Service Exception Hierarchy

Custom exception classes for Enhanced Token Analysis Bridge service operations.
Provides granular error handling for different failure modes including database
connectivity, data validation, and storage operations.
"""

from typing import List, Optional, Dict, Any


class BridgeError(Exception):
    """
    Base exception for Enhanced Token Analysis Bridge operations.

    Provides common error handling infrastructure for all bridge-related
    failures including error categorization and detailed context.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and telemetry."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }

    def __str__(self) -> str:
        """Enhanced string representation with context."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class BridgeConnectionError(BridgeError):
    """
    Database connection failures during bridge operations.

    Raised when the bridge service cannot establish or maintain
    connection to ClickHouse database. Includes retry context
    and connection diagnostics.
    """

    def __init__(
        self,
        message: str = "Failed to connect to database",
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        retry_count: int = 0,
        underlying_error: Optional[Exception] = None,
    ):
        context = {
            "host": host,
            "port": port,
            "database": database,
            "retry_count": retry_count,
            "underlying_error": str(underlying_error) if underlying_error else None,
        }

        super().__init__(
            message=message, error_code="BRIDGE_CONNECTION_FAILED", context=context
        )

        self.host = host
        self.port = port
        self.database = database
        self.retry_count = retry_count
        self.underlying_error = underlying_error


class BridgeValidationError(BridgeError):
    """
    Data validation failures during bridge operations.

    Raised when token analysis data fails validation before storage.
    Includes details about validation failures, invalid fields,
    and corrective actions.
    """

    def __init__(
        self,
        message: str = "Data validation failed",
        validation_failures: Optional[List[str]] = None,
        invalid_fields: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ):
        context = {
            "validation_failures": validation_failures or [],
            "invalid_fields": invalid_fields or {},
            "session_id": session_id,
        }

        super().__init__(
            message=message, error_code="BRIDGE_VALIDATION_FAILED", context=context
        )

        self.validation_failures = validation_failures or []
        self.invalid_fields = invalid_fields or {}
        self.session_id = session_id

    def add_validation_failure(self, field: str, error: str):
        """Add a validation failure for a specific field."""
        self.validation_failures.append(f"{field}: {error}")
        self.context["validation_failures"] = self.validation_failures


class BridgeStorageError(BridgeError):
    """
    Data storage operation failures during bridge operations.

    Raised when the bridge service fails to store token analysis
    data in ClickHouse. Includes transaction context, affected
    records, and recovery options.
    """

    def __init__(
        self,
        message: str = "Failed to store data",
        operation_type: Optional[str] = None,
        affected_records: int = 0,
        session_ids: Optional[List[str]] = None,
        table_name: Optional[str] = None,
        underlying_error: Optional[Exception] = None,
    ):
        context = {
            "operation_type": operation_type,
            "affected_records": affected_records,
            "session_ids": session_ids or [],
            "table_name": table_name,
            "underlying_error": str(underlying_error) if underlying_error else None,
        }

        super().__init__(
            message=message, error_code="BRIDGE_STORAGE_FAILED", context=context
        )

        self.operation_type = operation_type
        self.affected_records = affected_records
        self.session_ids = session_ids or []
        self.table_name = table_name
        self.underlying_error = underlying_error


class BridgeTimeoutError(BridgeError):
    """
    Timeout failures during bridge operations.

    Raised when bridge operations exceed configured timeout limits.
    Includes timing context and suggested retry strategies.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        operation_type: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        elapsed_seconds: Optional[float] = None,
    ):
        context = {
            "operation_type": operation_type,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed_seconds,
        }

        super().__init__(message=message, error_code="BRIDGE_TIMEOUT", context=context)

        self.operation_type = operation_type
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds


class BridgeCircuitBreakerError(BridgeError):
    """
    Circuit breaker activation during bridge operations.

    Raised when the bridge service's circuit breaker opens due to
    repeated failures. Includes failure statistics and recovery
    time estimates.
    """

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        failure_count: int = 0,
        failure_threshold: int = 5,
        recovery_time_seconds: Optional[float] = None,
    ):
        context = {
            "failure_count": failure_count,
            "failure_threshold": failure_threshold,
            "recovery_time_seconds": recovery_time_seconds,
        }

        super().__init__(
            message=message, error_code="BRIDGE_CIRCUIT_OPEN", context=context
        )

        self.failure_count = failure_count
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds


class BridgeDataIntegrityError(BridgeError):
    """
    Data integrity violations during bridge operations.

    Raised when stored token data doesn't match expected values
    or when data corruption is detected during verification.
    """

    def __init__(
        self,
        message: str = "Data integrity violation detected",
        expected_tokens: Optional[int] = None,
        actual_tokens: Optional[int] = None,
        session_id: Optional[str] = None,
        variance_percentage: Optional[float] = None,
    ):
        context = {
            "expected_tokens": expected_tokens,
            "actual_tokens": actual_tokens,
            "session_id": session_id,
            "variance_percentage": variance_percentage,
        }

        super().__init__(
            message=message, error_code="BRIDGE_DATA_INTEGRITY", context=context
        )

        self.expected_tokens = expected_tokens
        self.actual_tokens = actual_tokens
        self.session_id = session_id
        self.variance_percentage = variance_percentage
