"""
Enhanced Token Analysis Bridge Service

Core service for bridging Enhanced Token Analysis data to ClickHouse database.
Resolves the critical 2.768 billion token data loss issue by providing
structured storage and retrieval of enhanced token analysis results.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from contextlib import asynccontextmanager

from ..telemetry.clients.clickhouse_client import ClickHouseClient
from ..analysis.enhanced_token_counter import EnhancedTokenCounterService, SessionTokenMetrics as AnalysisSessionMetrics
from ..models.token_bridge_models import (
    BridgeResult,
    SessionTokenMetrics,
    BridgeHealthStatus,
    BridgeConfiguration,
    BridgeOperationStatus,
    HealthStatus,
)
from ..exceptions.bridge_exceptions import (
    BridgeError,
    BridgeConnectionError,
    BridgeValidationError,
    BridgeStorageError,
    BridgeTimeoutError,
    BridgeCircuitBreakerError,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker for bridge operations.

    Prevents cascading failures by temporarily disabling operations
    when failure rate exceeds threshold.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    async def call(self, operation: Callable, *args, **kwargs):
        """Execute operation with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise BridgeCircuitBreakerError(
                    failure_count=self.failure_count,
                    failure_threshold=self.failure_threshold,
                    recovery_time_seconds=self.recovery_timeout,
                )

        try:
            result = await operation(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        return (datetime.now() - self.last_failure_time).seconds > self.recovery_timeout

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class TokenAnalysisBridge:
    """
    Enhanced Token Analysis Bridge Service.

    Bridges Enhanced Token Analysis results to ClickHouse database, enabling
    dashboard visualization of comprehensive token metrics including the
    2.768 billion tokens detected by enhanced analysis.
    """

    def __init__(
        self,
        clickhouse_client: Optional[ClickHouseClient] = None,
        enhanced_counter: Optional[EnhancedTokenCounterService] = None,
        config: Optional[BridgeConfiguration] = None,
    ):
        self.config = config or BridgeConfiguration()
        self.clickhouse_client = clickhouse_client or ClickHouseClient(
            host=self.config.clickhouse_host, port=self.config.clickhouse_port, database=self.config.clickhouse_database
        )
        self.enhanced_counter = enhanced_counter or EnhancedTokenCounterService()

        # Circuit breaker for database operations
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.failure_threshold, recovery_timeout=self.config.recovery_timeout_seconds
        )

        # Performance tracking
        self.operation_history: List[Dict[str, Any]] = []
        self.lock = asyncio.Lock()

        logger.info("Token Analysis Bridge initialized")

    async def store_session_metrics(
        self, session_metrics: SessionTokenMetrics, force_update: bool = False, correlation_id: Optional[str] = None
    ) -> BridgeResult:
        """
        Store enhanced session token metrics in ClickHouse database.

        Args:
            session_metrics: Enhanced token metrics to store
            force_update: Force update even if session exists
            correlation_id: Optional correlation ID for tracking

        Returns:
            BridgeResult with operation status and metrics

        Raises:
            BridgeValidationError: When session metrics fail validation
            BridgeStorageError: When database storage fails
            BridgeConnectionError: When database connection fails
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()

        result = BridgeResult(
            success=True,
            operation_type="store_session_metrics",
            session_id=session_metrics.session_id,
            correlation_id=correlation_id,
        )

        try:
            # Validate input data
            if self.config.enable_validation:
                validation_errors = await self._validate_session_metrics(session_metrics)
                if validation_errors:
                    raise BridgeValidationError(
                        message="Session metrics validation failed",
                        validation_failures=validation_errors,
                        session_id=session_metrics.session_id,
                    )

            # Check if session already exists (unless force_update)
            if not force_update:
                existing = await self._get_existing_session(session_metrics.session_id)
                if existing:
                    result.add_warning(f"Session {session_metrics.session_id} already exists, skipping")
                    return result

            # Prepare session for storage
            session_metrics.bridge_stored_at = datetime.now()
            session_metrics.bridge_correlation_id = correlation_id
            session_metrics.calculate_accuracy_ratio()
            session_metrics.calculate_undercount_percentage()

            # Store using circuit breaker
            await self.circuit_breaker.call(self._store_session_record, session_metrics)

            result.records_stored = 1
            result.total_tokens = session_metrics.calculated_total_tokens
            result.processing_time_seconds = time.time() - start_time

            await self._record_operation_success(result)

            logger.info(
                f"Stored session metrics for {session_metrics.session_id}: "
                f"{session_metrics.calculated_total_tokens} tokens"
            )

            return result

        except (BridgeValidationError, BridgeStorageError, BridgeConnectionError, BridgeCircuitBreakerError):
            result.success = False
            result.processing_time_seconds = time.time() - start_time
            await self._record_operation_failure(result)
            raise
        except Exception as e:
            result.add_error(f"Unexpected error: {str(e)}")
            result.processing_time_seconds = time.time() - start_time
            await self._record_operation_failure(result)

            logger.error(f"Unexpected error storing session metrics: {e}")
            raise BridgeStorageError(
                message=f"Failed to store session metrics: {str(e)}",
                session_ids=[session_metrics.session_id],
                underlying_error=e,
            )

    async def get_session_metrics(
        self, session_id: str, include_metadata: bool = False
    ) -> Optional[SessionTokenMetrics]:
        """
        Retrieve stored session token metrics from database.

        Args:
            session_id: Session identifier to retrieve
            include_metadata: Include bridge metadata in response

        Returns:
            SessionTokenMetrics if found, None otherwise

        Raises:
            BridgeConnectionError: When database connection fails
        """
        try:
            query = """
            SELECT * FROM otel.enhanced_token_summaries 
            WHERE session_id = {session_id:String}
            ORDER BY created_at DESC
            LIMIT 1
            """

            results = await self.clickhouse_client.execute_query(query, params={"session_id": session_id})

            if not results:
                return None

            record = results[0]
            return await self._convert_from_clickhouse_record(record, include_metadata)

        except Exception as e:
            logger.error(f"Error retrieving session metrics for {session_id}: {e}")
            raise BridgeConnectionError(message=f"Failed to retrieve session metrics: {str(e)}", underlying_error=e)

    async def bulk_store_sessions(
        self,
        sessions: List[SessionTokenMetrics],
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[BridgeResult]:
        """
        Store multiple session metrics in batches.

        Args:
            sessions: List of session metrics to store
            batch_size: Batch size for storage (uses config default if None)
            progress_callback: Optional progress callback function

        Returns:
            List of BridgeResult objects for each batch
        """
        batch_size = batch_size or self.config.batch_size
        results: List[BridgeResult] = []

        for i in range(0, len(sessions), batch_size):
            batch = sessions[i : i + batch_size]
            batch_result = await self._store_session_batch(batch)
            results.append(batch_result)

            if progress_callback:
                progress_callback(min(i + batch_size, len(sessions)), len(sessions))

        return results

    async def health_check(self) -> BridgeHealthStatus:
        """
        Comprehensive health check for bridge service.

        Validates database connectivity, recent operation success rate,
        and system performance metrics.

        Returns:
            BridgeHealthStatus with comprehensive health information
        """
        start_time = time.time()

        health = BridgeHealthStatus(status=HealthStatus.HEALTHY, message="Service is healthy")

        try:
            # Test database connectivity
            db_start = time.time()
            is_connected = await self.clickhouse_client.health_check()
            health.database_response_time_ms = (time.time() - db_start) * 1000
            health.database_connected = is_connected

            if not is_connected:
                health.status = HealthStatus.UNHEALTHY
                health.message = "Database connection failed"
                health.last_connection_error = "Health check failed"
                return health

            # Check recent operation success rate
            recent_operations = await self._get_recent_operations()
            if recent_operations:
                successful_ops = sum(1 for op in recent_operations if op.get("success", False))
                health.recent_success_rate = (successful_ops / len(recent_operations)) * 100
                health.recent_operations_count = len(recent_operations)

                if health.recent_success_rate < 90:
                    health.status = HealthStatus.DEGRADED
                    health.message = f"Success rate below threshold: {health.recent_success_rate:.1f}%"

            # Get performance metrics
            if recent_operations:
                processing_times = [op.get("processing_time", 0) for op in recent_operations]
                health.average_processing_time_ms = (sum(processing_times) / len(processing_times)) * 1000

            # Get storage statistics
            stats = await self._get_storage_statistics()
            health.total_sessions_stored = stats.get("total_sessions", 0)
            health.total_tokens_stored = stats.get("total_tokens", 0)

        except Exception as e:
            health.status = HealthStatus.UNHEALTHY
            health.message = f"Health check failed: {str(e)}"
            health.last_connection_error = str(e)

            logger.error(f"Health check failed: {e}")

        return health

    async def _validate_session_metrics(self, metrics: SessionTokenMetrics) -> List[str]:
        """Validate session metrics before storage."""
        errors = metrics.validate()

        # Additional bridge-specific validations
        if metrics.undercount_percentage > self.config.max_undercount_percentage:
            errors.append(
                f"Undercount percentage {metrics.undercount_percentage}% exceeds maximum {self.config.max_undercount_percentage}%"
            )

        return errors

    async def _get_existing_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Check if session already exists in database."""
        try:
            query = (
                "SELECT session_id FROM otel.enhanced_token_summaries WHERE session_id = {session_id:String} LIMIT 1"
            )
            results = await self.clickhouse_client.execute_query(query, params={"session_id": session_id})
            return results[0] if results else None
        except Exception:
            return None

    async def _store_session_record(self, session_metrics: SessionTokenMetrics):
        """Store single session record in ClickHouse."""
        record = session_metrics.to_clickhouse_record()

        success = await self.clickhouse_client.bulk_insert("enhanced_token_summaries", [record])

        if not success:
            raise BridgeStorageError(
                message="Failed to insert session record",
                session_ids=[session_metrics.session_id],
                table_name="enhanced_token_summaries",
            )

    async def _store_session_batch(self, sessions: List[SessionTokenMetrics]) -> BridgeResult:
        """Store a batch of session metrics."""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())

        result = BridgeResult(
            success=True,
            operation_type="bulk_store_sessions",
            session_ids=[s.session_id for s in sessions],
            correlation_id=correlation_id,
        )

        try:
            records = []
            total_tokens = 0

            for session in sessions:
                if self.config.enable_validation:
                    errors = await self._validate_session_metrics(session)
                    if errors:
                        result.add_error(f"Session {session.session_id}: {'; '.join(errors)}")
                        continue

                session.bridge_stored_at = datetime.now()
                session.bridge_correlation_id = correlation_id
                session.calculate_accuracy_ratio()
                session.calculate_undercount_percentage()

                records.append(session.to_clickhouse_record())
                total_tokens += session.calculated_total_tokens

            if records:
                success = await self.clickhouse_client.bulk_insert("enhanced_token_summaries", records)

                if success:
                    result.records_stored = len(records)
                    result.total_tokens = total_tokens
                else:
                    result.add_error("Bulk insert failed")

            result.processing_time_seconds = time.time() - start_time
            return result

        except Exception as e:
            result.add_error(f"Batch storage failed: {str(e)}")
            result.processing_time_seconds = time.time() - start_time
            return result

    async def _convert_from_clickhouse_record(
        self, record: Dict[str, Any], include_metadata: bool = False
    ) -> SessionTokenMetrics:
        """Convert ClickHouse record back to SessionTokenMetrics."""
        import json

        metrics = SessionTokenMetrics(
            session_id=record["session_id"],
            start_time=datetime.fromisoformat(record["start_time"]) if record.get("start_time") else None,
            end_time=datetime.fromisoformat(record["end_time"]) if record.get("end_time") else None,
            reported_input_tokens=record.get("reported_input_tokens", 0),
            reported_output_tokens=record.get("reported_output_tokens", 0),
            reported_cache_creation_tokens=record.get("reported_cache_creation_tokens", 0),
            reported_cache_read_tokens=record.get("reported_cache_read_tokens", 0),
            calculated_input_tokens=record.get("calculated_input_tokens", 0),
            calculated_total_tokens=record.get("calculated_total_tokens", 0),
            accuracy_ratio=record.get("accuracy_ratio", 0.0),
            undercount_percentage=record.get("undercount_percentage", 0.0),
            files_processed=record.get("files_processed", 0),
            data_source=record.get("data_source", "enhanced_analysis"),
        )

        # Parse content categories from JSON
        if record.get("content_categories"):
            try:
                metrics.content_categories = json.loads(record["content_categories"])
            except json.JSONDecodeError:
                pass

        # Include bridge metadata if requested
        if include_metadata:
            metrics.bridge_stored_at = (
                datetime.fromisoformat(record["created_at"]) if record.get("created_at") else None
            )
            metrics.bridge_correlation_id = record.get("bridge_correlation_id")

        return metrics

    async def _record_operation_success(self, result: BridgeResult):
        """Record successful operation for performance tracking."""
        async with self.lock:
            self.operation_history.append(
                {
                    "timestamp": datetime.now(),
                    "success": True,
                    "operation_type": result.operation_type,
                    "processing_time": result.processing_time_seconds,
                    "records_stored": result.records_stored,
                    "total_tokens": result.total_tokens,
                }
            )

            # Keep only recent history
            cutoff = datetime.now() - timedelta(minutes=self.config.performance_window_minutes)
            self.operation_history = [op for op in self.operation_history if op["timestamp"] > cutoff]

    async def _record_operation_failure(self, result: BridgeResult):
        """Record failed operation for performance tracking."""
        async with self.lock:
            self.operation_history.append(
                {
                    "timestamp": datetime.now(),
                    "success": False,
                    "operation_type": result.operation_type,
                    "processing_time": result.processing_time_seconds,
                    "errors": result.errors,
                }
            )

    async def _get_recent_operations(self) -> List[Dict[str, Any]]:
        """Get recent operations for health monitoring."""
        async with self.lock:
            return self.operation_history.copy()

    async def _get_storage_statistics(self) -> Dict[str, int]:
        """Get storage statistics from ClickHouse."""
        try:
            query = """
            SELECT 
                COUNT(*) as total_sessions,
                SUM(calculated_total_tokens) as total_tokens
            FROM otel.enhanced_token_summaries
            """

            results = await self.clickhouse_client.execute_query(query)
            if results:
                return {
                    "total_sessions": int(results[0].get("total_sessions", 0)),
                    "total_tokens": int(results[0].get("total_tokens", 0)),
                }

        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")

        return {"total_sessions": 0, "total_tokens": 0}
