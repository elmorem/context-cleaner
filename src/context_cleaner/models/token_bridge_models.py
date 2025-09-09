"""
Token Bridge Data Models

Data models for Enhanced Token Analysis Bridge service, enabling structured
storage and retrieval of token analysis results in ClickHouse database.
Integrates with existing SessionTokenMetrics and provides validation.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import json


class BridgeOperationStatus(Enum):
    """Status enumeration for bridge operations."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"


class HealthStatus(Enum):
    """Health status enumeration for bridge service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class BridgeResult:
    """
    Result of a bridge storage operation.

    Contains comprehensive status information, metrics, and error details
    for bridge operations including token storage, retrieval, and health checks.
    """

    # Operation status
    success: bool
    status: BridgeOperationStatus = BridgeOperationStatus.SUCCESS
    operation_type: str = "store_session_metrics"

    # Metrics
    records_stored: int = 0
    total_tokens: int = 0
    processing_time_seconds: float = 0.0

    # Session context
    session_id: Optional[str] = None
    session_ids: List[str] = field(default_factory=list)

    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None

    def add_error(self, error: str):
        """Add an error message to the result."""
        self.errors.append(error)
        if self.success and self.status == BridgeOperationStatus.SUCCESS:
            self.success = False
            self.status = BridgeOperationStatus.FAILED

    def add_warning(self, warning: str):
        """Add a warning message to the result."""
        self.warnings.append(warning)
        if self.status == BridgeOperationStatus.SUCCESS and self.success:
            self.status = BridgeOperationStatus.PARTIAL_SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "status": self.status.value,
            "operation_type": self.operation_type,
            "records_stored": self.records_stored,
            "total_tokens": self.total_tokens,
            "processing_time_seconds": self.processing_time_seconds,
            "session_id": self.session_id,
            "session_ids": self.session_ids,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }


@dataclass
class SessionTokenMetrics:
    """
    Enhanced token metrics for bridge storage.

    Extends the existing SessionTokenMetrics with additional fields
    required for database storage and dashboard integration.
    Compatible with existing enhanced token counter.
    """

    # Session identification
    session_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Token counts from usage statistics
    reported_input_tokens: int = 0
    reported_output_tokens: int = 0
    reported_cache_creation_tokens: int = 0
    reported_cache_read_tokens: int = 0

    # Enhanced token analysis results
    calculated_input_tokens: int = 0
    calculated_total_tokens: int = 0

    # Analysis metadata
    accuracy_ratio: float = 0.0
    undercount_percentage: float = 0.0
    files_processed: int = 0

    # Content categories breakdown
    content_categories: Dict[str, int] = field(
        default_factory=lambda: {
            "claude_md": 0,
            "custom_agents": 0,
            "mcp_tools": 0,
            "system_prompts": 0,
            "system_tools": 0,
            "user_messages": 0,
        }
    )

    # Processing metadata for bridge operations
    bridge_stored_at: Optional[datetime] = None
    bridge_correlation_id: Optional[str] = None
    data_source: str = "enhanced_analysis"

    @property
    def total_reported_tokens(self) -> int:
        """Total tokens from existing usage statistics."""
        return (
            self.reported_input_tokens
            + self.reported_output_tokens
            + self.reported_cache_creation_tokens
            + self.reported_cache_read_tokens
        )

    def calculate_accuracy_ratio(self):
        """Calculate and update accuracy ratio."""
        if self.total_reported_tokens > 0:
            self.accuracy_ratio = self.calculated_total_tokens / self.total_reported_tokens
        else:
            self.accuracy_ratio = 0.0

    def calculate_undercount_percentage(self):
        """Calculate and update undercount percentage."""
        if self.calculated_total_tokens > 0:
            missed_tokens = max(0, self.calculated_total_tokens - self.total_reported_tokens)
            self.undercount_percentage = (missed_tokens / self.calculated_total_tokens) * 100
        else:
            self.undercount_percentage = 0.0

    def validate(self) -> List[str]:
        """
        Validate token metrics data.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.session_id or not isinstance(self.session_id, str):
            errors.append("session_id must be a non-empty string")

        if self.reported_input_tokens < 0:
            errors.append("reported_input_tokens cannot be negative")

        if self.reported_output_tokens < 0:
            errors.append("reported_output_tokens cannot be negative")

        if self.calculated_total_tokens < 0:
            errors.append("calculated_total_tokens cannot be negative")

        if self.accuracy_ratio < 0:
            errors.append("accuracy_ratio cannot be negative")

        if self.undercount_percentage < 0 or self.undercount_percentage > 100:
            errors.append("undercount_percentage must be between 0 and 100")

        if self.start_time and self.end_time and self.start_time > self.end_time:
            errors.append("start_time cannot be after end_time")

        return errors

    def to_clickhouse_record(self) -> Dict[str, Any]:
        """
        Convert to ClickHouse-compatible record format.

        Returns:
            Dictionary formatted for ClickHouse insertion
        """
        return {
            "session_id": self.session_id,
            "timestamp": (self.end_time or self.start_time or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else None,
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            # Token counts
            "reported_input_tokens": self.reported_input_tokens,
            "reported_output_tokens": self.reported_output_tokens,
            "reported_cache_creation_tokens": self.reported_cache_creation_tokens,
            "reported_cache_read_tokens": self.reported_cache_read_tokens,
            "total_reported_tokens": self.total_reported_tokens,
            # Enhanced analysis
            "calculated_input_tokens": self.calculated_input_tokens,
            "calculated_total_tokens": self.calculated_total_tokens,
            "accuracy_ratio": self.accuracy_ratio,
            "undercount_percentage": self.undercount_percentage,
            "files_processed": self.files_processed,
            # Content categories (as JSON)
            "content_categories": json.dumps(self.content_categories),
            # Metadata
            "data_source": self.data_source,
            "bridge_correlation_id": self.bridge_correlation_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


@dataclass
class BridgeHealthStatus:
    """
    Health status for Enhanced Token Analysis Bridge service.

    Provides comprehensive health monitoring including database connectivity,
    recent operation success rates, and performance metrics.
    """

    # Overall health
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Database connectivity
    database_connected: bool = False
    database_response_time_ms: Optional[float] = None
    last_connection_error: Optional[str] = None

    # Recent operations
    recent_success_rate: float = 0.0
    recent_operations_count: int = 0
    last_successful_operation: Optional[datetime] = None
    last_failed_operation: Optional[datetime] = None

    # Performance metrics
    average_processing_time_ms: float = 0.0
    total_sessions_stored: int = 0
    total_tokens_stored: int = 0

    # System resources
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None

    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "database_connected": self.database_connected,
            "database_response_time_ms": self.database_response_time_ms,
            "last_connection_error": self.last_connection_error,
            "recent_success_rate": self.recent_success_rate,
            "recent_operations_count": self.recent_operations_count,
            "last_successful_operation": (
                self.last_successful_operation.isoformat() if self.last_successful_operation else None
            ),
            "last_failed_operation": self.last_failed_operation.isoformat() if self.last_failed_operation else None,
            "average_processing_time_ms": self.average_processing_time_ms,
            "total_sessions_stored": self.total_sessions_stored,
            "total_tokens_stored": self.total_tokens_stored,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
        }


@dataclass
class BridgeConfiguration:
    """
    Configuration for Enhanced Token Analysis Bridge service.

    Centralizes bridge service settings including database connection,
    performance tuning, and operation timeouts.
    """

    # Database connection
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_database: str = "otel"
    connection_timeout_seconds: int = 30

    # Performance settings
    batch_size: int = 1000
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    operation_timeout_seconds: int = 300

    # Health monitoring
    health_check_interval_seconds: int = 60
    performance_window_minutes: int = 15

    # Circuit breaker
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60

    # Validation
    enable_validation: bool = True
    max_undercount_percentage: float = 200.0  # Allow up to 200% undercount

    def validate(self) -> List[str]:
        """
        Validate configuration settings.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.clickhouse_port <= 0 or self.clickhouse_port > 65535:
            errors.append("clickhouse_port must be between 1 and 65535")

        if self.batch_size <= 0:
            errors.append("batch_size must be positive")

        if self.max_retries < 0:
            errors.append("max_retries cannot be negative")

        if self.retry_backoff_factor <= 0:
            errors.append("retry_backoff_factor must be positive")

        if self.operation_timeout_seconds <= 0:
            errors.append("operation_timeout_seconds must be positive")

        if self.failure_threshold <= 0:
            errors.append("failure_threshold must be positive")

        return errors
