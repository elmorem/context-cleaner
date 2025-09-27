"""ClickHouse client for telemetry data access with enhanced connection management."""

import os
import asyncio
import time
import threading
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import subprocess
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
import random
import contextlib
from typing import List  # Add List to imports

from urllib import request as urllib_request
from urllib import error as urllib_error

from .base import TelemetryClient, SessionMetrics, ErrorEvent, TelemetryEvent

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Connection status enumeration."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionMetrics:
    """Metrics for connection health monitoring."""
    
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    average_response_time_ms: float = 0.0
    last_success_timestamp: Optional[datetime] = None
    last_failure_timestamp: Optional[datetime] = None
    consecutive_failures: int = 0
    connection_established_at: datetime = field(default_factory=datetime.now)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_queries == 0:
            return 100.0
        return (self.successful_queries / self.total_queries) * 100.0
    
    @property 
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        return 100.0 - self.success_rate


@dataclass
class AdaptiveConnectionPool:
    """Adaptive connection pool management for ClickHouse operations with performance optimization."""

    # Pool sizing configuration
    min_connections: int = 2
    max_connections: int = 10
    initial_connections: int = 5

    # Timeout configuration
    connection_timeout_seconds: int = 30
    query_timeout_seconds: int = 60
    health_check_interval_seconds: int = 30  # More frequent health checks

    # Adaptive sizing parameters
    high_load_threshold: float = 0.8  # Scale up when 80% connections busy
    low_load_threshold: float = 0.3   # Scale down when 30% connections busy
    scale_up_factor: float = 1.5      # Increase by 50%
    scale_down_factor: float = 0.8    # Decrease by 20%
    load_check_interval: int = 60     # Check load every 60 seconds

    # Circuit breaker configuration
    max_consecutive_failures: int = 3
    circuit_breaker_timeout: int = 60

    # Performance monitoring
    slow_query_threshold_ms: int = 1000  # Queries > 1s are considered slow

    # Internal state
    active_connections: int = 0
    busy_connections: int = 0
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    _last_health_check: datetime = field(default_factory=datetime.now)
    _last_load_check: datetime = field(default_factory=datetime.now)
    _circuit_breaker_open: bool = False
    _circuit_breaker_open_until: Optional[datetime] = None

    # Query performance tracking
    _slow_queries_count: int = 0
    _query_response_times: List[float] = field(default_factory=list)

    def get_current_load(self) -> float:
        """Calculate current connection pool load."""
        if self.active_connections == 0:
            return 0.0
        return self.busy_connections / self.active_connections

    def should_scale_up(self) -> bool:
        """Check if pool should be scaled up."""
        return (self.get_current_load() > self.high_load_threshold and
                self.active_connections < self.max_connections)

    def should_scale_down(self) -> bool:
        """Check if pool should be scaled down."""
        return (self.get_current_load() < self.low_load_threshold and
                self.active_connections > self.min_connections)

    def get_target_pool_size(self) -> int:
        """Calculate target pool size based on current load."""
        current_load = self.get_current_load()

        if current_load > self.high_load_threshold:
            # Scale up
            target = int(self.active_connections * self.scale_up_factor)
            return min(target, self.max_connections)
        elif current_load < self.low_load_threshold:
            # Scale down
            target = int(self.active_connections * self.scale_down_factor)
            return max(target, self.min_connections)
        else:
            # No scaling needed
            return self.active_connections

    def record_query_performance(self, response_time_ms: float):
        """Record query performance metrics."""
        self._query_response_times.append(response_time_ms)

        # Keep only last 100 queries for moving average
        if len(self._query_response_times) > 100:
            self._query_response_times.pop(0)

        # Track slow queries
        if response_time_ms > self.slow_query_threshold_ms:
            self._slow_queries_count += 1

    def get_average_response_time(self) -> float:
        """Get average response time from recent queries."""
        if not self._query_response_times:
            return 0.0
        return sum(self._query_response_times) / len(self._query_response_times)


class ClickHouseClient(TelemetryClient):
    """High-performance ClickHouse client with adaptive pooling, caching, and monitoring."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9000,
        database: str = "otel",
        max_connections: int = 10,
        min_connections: int = 2,
        connection_timeout: int = 30,
        query_timeout: int = 60,
        enable_health_monitoring: bool = True,
        enable_query_caching: bool = True,
        cache_service: Optional[Any] = None  # Will be injected
    ):
        self.host = host
        self.port = port
        self.database = database
        self.connection_string = f"tcp://{host}:{port}"
        self.http_host = os.getenv("CLICKHOUSE_HTTP_HOST", host)
        self.http_port = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
        self.http_url = f"http://{self.http_host}:{self.http_port}"
        self._http_timeout = query_timeout

        # Adaptive connection pool management
        self.pool = AdaptiveConnectionPool(
            min_connections=min_connections,
            max_connections=max_connections,
            initial_connections=min(max_connections, 5),
            connection_timeout_seconds=connection_timeout,
            query_timeout_seconds=query_timeout
        )

        # Feature flags
        self.enable_health_monitoring = enable_health_monitoring
        self.enable_query_caching = enable_query_caching

        # Query caching integration
        self._cache_service = cache_service
        self._query_cache_ttl = {
            'health': 30,      # Health checks cached for 30s
            'stats': 300,      # Stats cached for 5 minutes
            'metrics': 60,     # Metrics cached for 1 minute
            'aggregated': 900, # Aggregated data cached for 15 minutes
        }
        
        # Connection state
        self._is_initialized = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._thread_local = threading.local()
        
        # Performance monitoring
        self._performance_stats = {
            'queries_executed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_query_time_ms': 0,
            'slow_queries': 0,
            'pool_adjustments': 0
        }

        logger.info(f"Initialized high-performance ClickHouseClient: "
                   f"host={host}, port={port}, database={database}, "
                   f"pool=[{min_connections}-{max_connections}], "
                   f"caching={enable_query_caching}")

    def close(self):
        """Release network resources."""
        # No persistent HTTP session to close when using urllib
        return
    
    def _get_lock(self):
        """Get appropriate lock for current execution context."""
        if not hasattr(self._thread_local, 'lock'):
            # Always use threading lock - simpler and works across contexts
            self._thread_local.lock = threading.Lock()
        return self._thread_local.lock
    
    @contextlib.asynccontextmanager
    async def _lock_context(self):
        """Async context manager for thread lock."""
        lock = self._get_lock()
        await asyncio.get_event_loop().run_in_executor(None, lock.acquire)
        try:
            yield
        finally:
            lock.release()
    
    async def initialize(self) -> bool:
        """Initialize the client with connection pooling and health monitoring."""
        if self._is_initialized:
            return True
        
        try:
            async with self._lock_context():
                if self._is_initialized:
                    return True
                
                # Test initial connection
                health_ok = await self._perform_health_check()
                if not health_ok:
                    logger.error("Failed initial health check during initialization")
                    return False
                
                # Start health monitoring task
                if self.enable_health_monitoring:
                    self._health_check_task = asyncio.create_task(self._health_monitor_loop())
                
                self._is_initialized = True
                logger.info("ClickHouseClient initialization completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to initialize ClickHouseClient: {e}")
            return False
    
    async def close(self):
        """Clean shutdown of client and resources."""
        if self._health_check_task and not self._health_check_task.cancelled():
            self._health_check_task.cancel()
            try:
                await asyncio.wait_for(self._health_check_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            finally:
                self._health_check_task = None
        
        async with self._lock_context():
            self._is_initialized = False
            logger.info("ClickHouseClient closed successfully")
    
    async def _health_monitor_loop(self):
        """Background task for periodic health monitoring."""
        while True:
            try:
                await asyncio.sleep(self.pool.health_check_interval_seconds)
                await self._perform_health_check()
            except asyncio.CancelledError:
                logger.debug("Health monitor loop cancelled")
                break
            except Exception as e:
                logger.warning(f"Health monitor error: {e}")
    
    async def _perform_health_check(self) -> bool:
        """Perform health check and update connection status."""
        start_time = time.time()
        
        try:
            # Simple health check query
            result = await self._execute_raw_query("SELECT 1 as health", timeout=10)
            response_time_ms = (time.time() - start_time) * 1000
            
            success = len(result) > 0 and result[0].get('health') == 1
            
            if success:
                self._record_successful_query(response_time_ms)
                self._reset_circuit_breaker()
                return True
            else:
                self._record_failed_query("Invalid health check response")
                return False
                
        except Exception as e:
            self._record_failed_query(str(e))
            return False
    
    def _record_successful_query(self, response_time_ms: float):
        """Record successful query for metrics."""
        metrics = self.pool.metrics
        metrics.total_queries += 1
        metrics.successful_queries += 1
        metrics.consecutive_failures = 0
        metrics.last_success_timestamp = datetime.now()
        
        # Update average response time (exponential moving average)
        if metrics.average_response_time_ms == 0:
            metrics.average_response_time_ms = response_time_ms
        else:
            metrics.average_response_time_ms = (
                metrics.average_response_time_ms * 0.9 + response_time_ms * 0.1
            )
    
    def _record_failed_query(self, error_message: str):
        """Record failed query for metrics."""
        metrics = self.pool.metrics
        metrics.total_queries += 1
        metrics.failed_queries += 1
        metrics.consecutive_failures += 1
        metrics.last_failure_timestamp = datetime.now()

        logger.warning(f"Query failed: {error_message}")

        # Check if this is a "container not found" error - don't trip circuit breaker for this
        if self._is_container_not_found_error(error_message):
            logger.info("Container not found - this is expected during startup, not tripping circuit breaker")
            # Reset consecutive failures for container not found errors
            # as this is a startup condition, not a service failure
            metrics.consecutive_failures = 0
            return

        # Trip circuit breaker if too many consecutive failures
        if metrics.consecutive_failures >= self.pool.max_consecutive_failures:
            self._trip_circuit_breaker()
    
    def _trip_circuit_breaker(self):
        """Trip the circuit breaker to prevent further queries."""
        self.pool._circuit_breaker_open = True
        self.pool._circuit_breaker_open_until = (
            datetime.now() + timedelta(seconds=60)  # 60-second timeout
        )
        logger.error(f"Circuit breaker tripped after {self.pool.metrics.consecutive_failures} "
                    f"consecutive failures")
    
    def _reset_circuit_breaker(self):
        """Reset the circuit breaker after successful query."""
        if self.pool._circuit_breaker_open:
            self.pool._circuit_breaker_open = False
            self.pool._circuit_breaker_open_until = None
            logger.info("Circuit breaker reset after successful query")
    
    def reset_circuit_breaker_manually(self):
        """Manually reset the circuit breaker and clear failure metrics."""
        self.pool._circuit_breaker_open = False
        self.pool._circuit_breaker_open_until = None
        self.pool.metrics.consecutive_failures = 0
        logger.info("Circuit breaker manually reset and failure count cleared")
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        if not self.pool._circuit_breaker_open:
            return False
        
        if (self.pool._circuit_breaker_open_until and 
            datetime.now() > self.pool._circuit_breaker_open_until):
            # Timeout expired, allow one test query
            self.pool._circuit_breaker_open = False
            self.pool._circuit_breaker_open_until = None
            logger.info("Circuit breaker timeout expired, allowing test query")
            return False
        
        return True

    def _is_container_not_found_error(self, error_message: str) -> bool:
        """Check if the error is due to container not being found/running."""
        container_not_found_patterns = [
            "No such container",
            "container not found",
            "Cannot connect to the Docker daemon",
            "container.*not running",
            "Container .* is not running"
        ]

        error_lower = error_message.lower()
        for pattern in container_not_found_patterns:
            import re
            if re.search(pattern.lower(), error_lower):
                return True
        return False

    async def get_connection_status(self) -> ConnectionStatus:
        """Get current connection status."""
        if self._is_circuit_breaker_open():
            return ConnectionStatus.UNHEALTHY
        
        metrics = self.pool.metrics
        
        if metrics.total_queries == 0:
            return ConnectionStatus.UNKNOWN
        
        success_rate = metrics.success_rate
        response_time = metrics.average_response_time_ms
        
        if success_rate >= 95 and response_time < 1000:
            return ConnectionStatus.HEALTHY
        elif success_rate >= 80 and response_time < 5000:
            return ConnectionStatus.DEGRADED
        else:
            return ConnectionStatus.UNHEALTHY
    
    async def get_connection_metrics(self) -> Dict[str, Any]:
        """Get detailed connection metrics."""
        metrics = self.pool.metrics
        status = await self.get_connection_status()
        
        return {
            "status": status.value,
            "total_queries": metrics.total_queries,
            "successful_queries": metrics.successful_queries,
            "failed_queries": metrics.failed_queries,
            "success_rate_percent": metrics.success_rate,
            "failure_rate_percent": metrics.failure_rate,
            "average_response_time_ms": metrics.average_response_time_ms,
            "consecutive_failures": metrics.consecutive_failures,
            "circuit_breaker_open": self.pool._circuit_breaker_open,
            "last_success": metrics.last_success_timestamp.isoformat() if metrics.last_success_timestamp else None,
            "last_failure": metrics.last_failure_timestamp.isoformat() if metrics.last_failure_timestamp else None,
            "connection_established_at": metrics.connection_established_at.isoformat(),
            "max_connections": self.pool.max_connections,
            "active_connections": self.pool.active_connections,
        }
    
    async def _execute_raw_query(self, query: str, timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute raw query with connection management."""
        timeout = timeout or self.pool.query_timeout_seconds
        
        try:
            try:
                params = "default_format=JSONEachRow"
                url = f"{self.http_url}/?{params}"
                req = urllib_request.Request(
                    url,
                    data=query.encode("utf-8"),
                    headers={
                        "Content-Type": "text/plain; charset=utf-8",
                        "Accept": "application/json"
                    },
                    method="POST",
                )

                with urllib_request.urlopen(req, timeout=timeout) as response:
                    body = response.read().decode("utf-8")

                results = []
                for line in body.strip().split('\n'):
                    if line:
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON line: {line}, error: {e}")
                return results
            except urllib_error.URLError as http_error:
                logger.warning(
                    "HTTP query path failed (%s). Falling back to docker exec.",
                    http_error,
                )

            # Fall back to docker exec when HTTP path fails
            cmd = [
                "docker", "exec", "clickhouse-otel",
                "clickhouse-client",
                "--query", query,
                "--format", "JSONEachRow"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            if result.returncode != 0:
                raise RuntimeError(f"ClickHouse query failed: {result.stderr}")

            results = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON line: {line}, error: {e}")

            return results
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ClickHouse query timed out after {timeout}s")
        except Exception as e:
            raise RuntimeError(f"ClickHouse query error: {e}")
        
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None,
                           cache_key: Optional[str] = None, cache_ttl: int = 300) -> List[Dict[str, Any]]:
        """Execute a query with adaptive pooling, caching, and performance monitoring."""
        # Check if client is initialized
        if not self._is_initialized:
            await self.initialize()

        # Check circuit breaker
        if self._is_circuit_breaker_open():
            raise RuntimeError("Circuit breaker is open due to consecutive failures")

        # Try cache first if enabled and cache_key provided
        if self.enable_query_caching and cache_key and self._cache_service:
            try:
                cached_result = await self._cache_service.get(cache_key)
                if cached_result is not None:
                    self._performance_stats['cache_hits'] += 1
                    logger.debug(f"Cache hit for query: {cache_key}")
                    return cached_result
                else:
                    self._performance_stats['cache_misses'] += 1
            except Exception as e:
                logger.warning(f"Cache retrieval error for {cache_key}: {e}")

        # Adaptive pool management
        await self._manage_pool_size()

        start_time = time.time()
        
        try:
            # Handle parameterized queries by substituting parameters
            final_query = query
            if params:
                for key, value in params.items():
                    if isinstance(value, str):
                        # Escape and quote string values
                        escaped_value = value.replace("'", "\\'").replace("\\", "\\\\")
                        final_query = final_query.replace(f"{{{key}:String}}", f"'{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        final_query = final_query.replace(f"{{{key}:UInt32}}", str(value))
                        final_query = final_query.replace(f"{{{key}:Float64}}", str(value))
                        final_query = final_query.replace(f"{{{key}:Int32}}", str(value))
            
            # Execute query with monitoring
            results = await self._execute_raw_query(final_query)
            
            # Record success and performance metrics
            response_time_ms = (time.time() - start_time) * 1000
            self._record_successful_query(response_time_ms)
            self.pool.record_query_performance(response_time_ms)

            # Update performance stats
            self._performance_stats['queries_executed'] += 1
            self._performance_stats['total_query_time_ms'] += response_time_ms

            if response_time_ms > self.pool.slow_query_threshold_ms:
                self._performance_stats['slow_queries'] += 1
                logger.warning(f"Slow query detected: {response_time_ms:.1f}ms")

            # Cache the result if caching is enabled
            if (self.enable_query_caching and cache_key and self._cache_service and
                response_time_ms < 5000):  # Don't cache very slow queries
                try:
                    await self._cache_service.set(cache_key, results, cache_ttl)
                    logger.debug(f"Cached query result: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache storage error for {cache_key}: {e}")

            return results
            
        except Exception as e:
            # Record failure
            self._record_failed_query(str(e))
            logger.error(f"ClickHouse query failed: {e}")
            return []
    
    async def bulk_insert_enhanced(self, table_name: str, records: List[Dict[str, Any]], 
                                 batch_size: int = 1000, max_retries: int = 3) -> Dict[str, Any]:
        """
        Enhanced bulk insert with batching, retries, and detailed result tracking.
        
        Args:
            table_name: Target table name
            records: List of records to insert
            batch_size: Number of records per batch
            max_retries: Maximum retry attempts per batch
            
        Returns:
            Dictionary with insertion results and metrics
        """
        if not records:
            return {
                "success": True,
                "total_records": 0,
                "successful_records": 0,
                "failed_records": 0,
                "batches_processed": 0,
                "batches_failed": 0,
                "processing_time_seconds": 0.0,
                "errors": []
            }
        
        start_time = time.time()
        successful_records = 0
        failed_records = 0
        batches_processed = 0
        batches_failed = 0
        errors = []
        
        # Process records in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            batch_success = False
            
            # Retry logic for each batch
            for attempt in range(max_retries + 1):
                try:
                    success = await self.bulk_insert(table_name, batch)
                    if success:
                        successful_records += len(batch)
                        batches_processed += 1
                        batch_success = True
                        break
                    else:
                        raise RuntimeError("Bulk insert returned False")
                        
                except Exception as e:
                    if attempt == max_retries:
                        error_msg = f"Batch {i//batch_size + 1} failed after {max_retries + 1} attempts: {e}"
                        errors.append(error_msg)
                        failed_records += len(batch)
                        batches_failed += 1
                        logger.error(error_msg)
                    else:
                        # Exponential backoff
                        wait_time = 2 ** attempt
                        await asyncio.sleep(wait_time)
        
        processing_time = time.time() - start_time
        overall_success = failed_records == 0
        
        result = {
            "success": overall_success,
            "total_records": len(records),
            "successful_records": successful_records,
            "failed_records": failed_records,
            "batches_processed": batches_processed,
            "batches_failed": batches_failed,
            "processing_time_seconds": processing_time,
            "average_records_per_second": len(records) / processing_time if processing_time > 0 else 0,
            "errors": errors
        }
        
        logger.info(f"Bulk insert completed: {successful_records}/{len(records)} records successful "
                   f"in {processing_time:.2f}s ({result['average_records_per_second']:.1f} records/sec)")
        
        return result
    
    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get comprehensive metrics for a specific session."""
        query = f"""
        SELECT 
            LogAttributes['session.id'] as session_id,
            MIN(Timestamp) as start_time,
            MAX(Timestamp) as end_time,
            COUNT(*) as api_calls,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
            SUM(toFloat64OrNull(LogAttributes['input_tokens'])) as total_input_tokens,
            SUM(toFloat64OrNull(LogAttributes['output_tokens'])) as total_output_tokens,
            SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as error_count
        FROM otel.otel_logs
        WHERE LogAttributes['session.id'] = '{session_id}'
            AND Body IN ('claude_code.api_request', 'claude_code.api_error')
        GROUP BY LogAttributes['session.id']
        """
        
        results = await self.execute_query(query)
        if not results:
            return None
            
        data = results[0]
        
        # Get tools used in this session
        tools_query = f"""
        SELECT DISTINCT LogAttributes['tool_name'] as tool
        FROM otel.otel_logs
        WHERE LogAttributes['session.id'] = '{session_id}'
            AND Body = 'claude_code.tool_decision'
            AND LogAttributes['tool_name'] != ''
        """
        
        tools_results = await self.execute_query(tools_query)
        tools_used = [t['tool'] for t in tools_results]
        
        return SessionMetrics(
            session_id=data['session_id'],
            start_time=datetime.fromisoformat(data['start_time'].replace('Z', '+00:00')),
            end_time=datetime.fromisoformat(data['end_time'].replace('Z', '+00:00')) if data['end_time'] else None,
            api_calls=int(data['api_calls']),
            total_cost=float(data['total_cost'] or 0),
            total_input_tokens=int(data['total_input_tokens'] or 0),
            total_output_tokens=int(data['total_output_tokens'] or 0),
            error_count=int(data['error_count']),
            tools_used=tools_used
        )
    
    async def get_recent_errors(self, hours: int = 24) -> List[ErrorEvent]:
        """Get recent error events within specified time window."""
        query = f"""
        SELECT 
            Timestamp,
            LogAttributes['session.id'] as session_id,
            LogAttributes['error'] as error_type,
            toFloat64OrNull(LogAttributes['duration_ms']) as duration_ms,
            LogAttributes['model'] as model,
            toInt32OrNull(LogAttributes['input_tokens']) as input_tokens,
            LogAttributes['terminal.type'] as terminal_type
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_error'
            AND Timestamp >= now() - INTERVAL {hours} HOUR
        ORDER BY Timestamp DESC
        """
        
        results = await self.execute_query(query)
        
        errors = []
        for row in results:
            errors.append(ErrorEvent(
                timestamp=datetime.fromisoformat(row['Timestamp'].replace('Z', '+00:00')),
                session_id=row['session_id'],
                error_type=row['error_type'],
                duration_ms=float(row['duration_ms']),
                model=row['model'],
                input_tokens=row['input_tokens'],
                terminal_type=row['terminal_type']
            ))
        
        return errors
    
    async def get_cost_trends(self, days: int = 7) -> Dict[str, float]:
        """Get cost trends over specified number of days."""
        query = f"""
        SELECT 
            toDate(Timestamp) as date,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as daily_cost
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_request'
            AND Timestamp >= now() - INTERVAL {days} DAY
            AND LogAttributes['cost_usd'] != ''
        GROUP BY date
        ORDER BY date DESC
        """
        
        results = await self.execute_query(query)
        return {row['date']: float(row['daily_cost']) for row in results}
    
    async def get_current_session_cost(self, session_id: str) -> float:
        """Get the current cost for an active session."""
        query = f"""
        SELECT SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as session_cost
        FROM otel.otel_logs
        WHERE LogAttributes['session.id'] = '{session_id}'
            AND Body = 'claude_code.api_request'
            AND LogAttributes['cost_usd'] != ''
        """
        
        results = await self.execute_query(query)
        if results and results[0]['session_cost']:
            return float(results[0]['session_cost'])
        return 0.0
    
    async def get_model_usage_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get model usage statistics over specified period."""
        query = f"""
        SELECT 
            LogAttributes['model'] as model,
            COUNT(*) as request_count,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
            AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration_ms,
            SUM(toFloat64OrNull(LogAttributes['input_tokens'])) as total_input_tokens,
            SUM(toFloat64OrNull(LogAttributes['output_tokens'])) as total_output_tokens
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_request'
            AND Timestamp >= now() - INTERVAL {days} DAY
            AND LogAttributes['model'] != ''
        GROUP BY LogAttributes['model']
        ORDER BY request_count DESC
        """
        
        results = await self.execute_query(query)
        
        stats = {}
        for row in results:
            model = row['model']
            stats[model] = {
                'request_count': int(row['request_count']),
                'total_cost': float(row['total_cost'] or 0),
                'avg_duration_ms': float(row['avg_duration_ms'] or 0),
                'total_input_tokens': int(row['total_input_tokens'] or 0),
                'total_output_tokens': int(row['total_output_tokens'] or 0),
                'cost_per_token': float(row['total_cost'] or 0) / max(int(row['total_input_tokens'] or 0), 1)
            }
        
        return stats
    
    async def get_total_aggregated_stats(self) -> Dict[str, Any]:
        """Get total aggregated statistics across all sessions."""
        try:
            # Get total tokens from official Claude Code token usage metrics
            # This includes input, output, cacheRead, and cacheCreation tokens
            token_query = """
            SELECT 
                Attributes['type'] as token_type,
                SUM(Value) as total_tokens
            FROM otel.otel_metrics_sum
            WHERE MetricName = 'claude_code.token.usage'
            GROUP BY token_type
            """
            
            token_results = await self.execute_query(token_query)
            
            # Calculate total tokens from all types (input + output + cacheRead + cacheCreation)
            total_tokens = 0
            token_breakdown = {}
            for row in token_results:
                token_type = row['token_type']
                tokens = int(row['total_tokens'])
                token_breakdown[token_type] = tokens
                total_tokens += tokens
            
            # Get sessions, costs, and API calls from OTEL logs
            stats_query = """
            SELECT 
                COUNT(DISTINCT LogAttributes['session.id']) as total_sessions,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                COUNT(*) as total_api_calls,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as total_errors,
                MIN(Timestamp) as earliest_session,
                MAX(Timestamp) as latest_session
            FROM otel.otel_logs
            WHERE Body IN ('claude_code.api_request', 'claude_code.api_error')
            """
            
            stats_results = await self.execute_query(stats_query)
            if not stats_results:
                return self._get_fallback_stats()
            
            data = stats_results[0]
            
            # Get active agents/tools count
            tools_query = """
            SELECT COUNT(DISTINCT LogAttributes['tool_name']) as unique_tools
            FROM otel.otel_logs
            WHERE Body = 'claude_code.tool_decision'
                AND LogAttributes['tool_name'] != ''
                AND Timestamp >= now() - INTERVAL 30 DAY
            """
            
            tools_results = await self.execute_query(tools_query)
            unique_tools = tools_results[0]['unique_tools'] if tools_results else 0
            
            # Calculate success rate
            total_requests = int(data['total_api_calls'])
            total_errors = int(data['total_errors'])
            success_rate = ((total_requests - total_errors) / max(total_requests, 1)) * 100 if total_requests > 0 else 0
            
            return {
                'total_tokens': f"{total_tokens:,}",
                'total_sessions': f"{int(data['total_sessions'] or 0):,}",
                'success_rate': f"{success_rate:.1f}%",
                'active_agents': str(unique_tools),
                'total_cost': f"${float(data['total_cost'] or 0):.2f}",
                'total_errors': int(data['total_errors'] or 0),
                'earliest_session': data['earliest_session'],
                'latest_session': data['latest_session'],
                'raw_total_tokens': total_tokens,
                'raw_total_sessions': int(data['total_sessions'] or 0),
                'raw_success_rate': success_rate,
                'token_breakdown': token_breakdown  # Include breakdown for debugging
            }
            
        except Exception as e:
            print(f"Error getting aggregated stats: {e}")
            return self._get_fallback_stats()
    
    def _get_fallback_stats(self) -> Dict[str, Any]:
        """Fallback stats when ClickHouse query fails."""
        return {
            'total_tokens': '0',
            'total_sessions': '0',
            'success_rate': '0.0%',
            'active_agents': '0',
            'total_cost': '$0.00',
            'total_errors': 0,
            'earliest_session': None,
            'latest_session': None,
            'raw_total_tokens': 0,
            'raw_total_sessions': 0,
            'raw_success_rate': 0.0
        }

    async def health_check(self) -> bool:
        """Check if ClickHouse connection is healthy with enhanced diagnostics."""
        return await self._perform_health_check()
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check with detailed metrics."""
        start_time = time.time()
        
        health_results = {
            "overall_healthy": False,
            "connection_status": "unknown",
            "database_accessible": False,
            "response_time_ms": 0.0,
            "error_message": None,
            "metrics": await self.get_connection_metrics(),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Basic connectivity test
            basic_health = await self._perform_health_check()
            health_results["overall_healthy"] = basic_health
            
            # Get connection status
            status = await self.get_connection_status()
            health_results["connection_status"] = status.value
            
            # Test database access
            try:
                results = await self._execute_raw_query(f"SHOW TABLES FROM {self.database}")
                health_results["database_accessible"] = True
                health_results["tables_found"] = len(results)
            except Exception as e:
                health_results["database_accessible"] = False
                health_results["database_error"] = str(e)
            
            health_results["response_time_ms"] = (time.time() - start_time) * 1000
            
        except Exception as e:
            health_results["error_message"] = str(e)
            health_results["response_time_ms"] = (time.time() - start_time) * 1000
        
        return health_results

    async def _manage_pool_size(self):
        """Adaptive pool size management based on current load."""
        try:
            current_time = datetime.now()

            # Check if it's time to evaluate pool size
            if (current_time - self.pool._last_load_check).seconds < self.pool.load_check_interval:
                return

            self.pool._last_load_check = current_time
            target_size = self.pool.get_target_pool_size()

            if target_size != self.pool.active_connections:
                logger.info(f"Adjusting pool size: {self.pool.active_connections} -> {target_size} "
                           f"(load: {self.pool.get_current_load():.2f})")

                self.pool.active_connections = target_size
                self._performance_stats['pool_adjustments'] += 1

        except Exception as e:
            logger.warning(f"Pool size management error: {e}")

    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        try:
            connection_metrics = await self.get_connection_metrics()

            avg_query_time = 0.0
            if self._performance_stats['queries_executed'] > 0:
                avg_query_time = (self._performance_stats['total_query_time_ms'] /
                                self._performance_stats['queries_executed'])

            cache_hit_rate = 0.0
            total_cache_ops = self._performance_stats['cache_hits'] + self._performance_stats['cache_misses']
            if total_cache_ops > 0:
                cache_hit_rate = (self._performance_stats['cache_hits'] / total_cache_ops) * 100

            return {
                **connection_metrics,
                'performance': {
                    'queries_executed': self._performance_stats['queries_executed'],
                    'average_query_time_ms': round(avg_query_time, 2),
                    'slow_queries': self._performance_stats['slow_queries'],
                    'slow_query_percentage': round(
                        (self._performance_stats['slow_queries'] /
                         max(self._performance_stats['queries_executed'], 1)) * 100, 2
                    ),
                    'total_query_time_ms': self._performance_stats['total_query_time_ms']
                },
                'caching': {
                    'enabled': self.enable_query_caching,
                    'cache_hits': self._performance_stats['cache_hits'],
                    'cache_misses': self._performance_stats['cache_misses'],
                    'cache_hit_rate_percent': round(cache_hit_rate, 2)
                },
                'pool_management': {
                    'current_size': self.pool.active_connections,
                    'min_size': self.pool.min_connections,
                    'max_size': self.pool.max_connections,
                    'current_load': round(self.pool.get_current_load(), 2),
                    'adjustments_made': self._performance_stats['pool_adjustments'],
                    'average_response_time_ms': round(self.pool.get_average_response_time(), 2)
                }
            }

        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {'error': str(e)}

    def set_cache_service(self, cache_service):
        """Inject cache service for query caching."""
        self._cache_service = cache_service
        logger.info("Query caching enabled with injected cache service")

    def optimize_for_dashboard_queries(self):
        """Optimize client settings for dashboard query patterns."""
        # Adjust cache TTLs for dashboard-specific queries
        self._query_cache_ttl.update({
            'dashboard_overview': 60,      # Dashboard overview cached for 1 minute
            'widget_data': 30,             # Widget data cached for 30 seconds
            'health_metrics': 15,          # Health metrics cached for 15 seconds
            'cost_trends': 300,            # Cost trends cached for 5 minutes
            'usage_stats': 180,            # Usage stats cached for 3 minutes
        })

        # Optimize pool for dashboard workload
        self.pool.high_load_threshold = 0.7  # Scale up earlier for responsive dashboard
        self.pool.slow_query_threshold_ms = 500  # Dashboard queries should be fast

        logger.info("Client optimized for dashboard query patterns")

    async def execute_dashboard_query(self, query: str, query_type: str = 'widget_data',
                                    params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a dashboard query with optimized caching."""
        # Generate cache key based on query and params
        cache_key = f"dashboard:{query_type}:{hash(query)}:{hash(str(params))}"
        cache_ttl = self._query_cache_ttl.get(query_type, 60)

        return await self.execute_query(query, params, cache_key, cache_ttl)

    # ===== JSONL CONTENT METHODS =====
    
    async def bulk_insert(self, table_name: str, records: List[Dict[str, Any]]) -> bool:
        """Bulk insert records into specified table."""
        if not records:
            return True
            
        try:
            # Convert records to JSON lines format with datetime handling
            def default_serializer(obj):
                if isinstance(obj, datetime):
                    # Format timestamp in ClickHouse-compatible format
                    return obj.strftime('%Y-%m-%d %H:%M:%S')
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            json_lines = '\n'.join([json.dumps(record, default=default_serializer) for record in records])
            
            # Use clickhouse-client with JSONEachRow format for bulk insert
            cmd = [
                "docker", "exec", "-i", "clickhouse-otel", 
                "clickhouse-client", 
                "--query", f"INSERT INTO otel.{table_name} FORMAT JSONEachRow",
            ]
            
            result = subprocess.run(
                cmd, 
                input=json_lines, 
                text=True, 
                capture_output=True, 
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Bulk insert failed for {table_name}: {result.stderr}")
                return False
            
            logger.info(f"Successfully inserted {len(records)} records into {table_name}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Bulk insert timed out for {table_name}")
            return False
        except Exception as e:
            logger.error(f"Bulk insert error for {table_name}: {e}")
            return False
    
    async def get_jsonl_content_stats(self) -> Dict[str, Any]:
        """Get statistics about JSONL content storage."""
        try:
            stats = {}
            
            # Message content stats
            message_query = """
            SELECT 
                count() as total_messages,
                uniq(session_id) as unique_sessions,
                sum(message_length) as total_characters,
                avg(message_length) as avg_message_length,
                sum(input_tokens) as total_input_tokens,
                sum(output_tokens) as total_output_tokens,
                sum(cost_usd) as total_cost,
                countIf(contains_code_blocks) as messages_with_code,
                min(timestamp) as earliest_message,
                max(timestamp) as latest_message
            FROM otel.claude_message_content
            WHERE timestamp >= now() - INTERVAL 30 DAY
            """
            
            message_results = await self.execute_query(message_query)
            stats['messages'] = message_results[0] if message_results else {}
            
            # File content stats
            file_query = """
            SELECT 
                count() as total_file_accesses,
                uniq(file_path) as unique_files,
                sum(file_size) as total_file_bytes,
                avg(file_size) as avg_file_size,
                avg(line_count) as avg_line_count,
                countIf(contains_secrets) as files_with_secrets,
                countIf(contains_imports) as files_with_imports
            FROM otel.claude_file_content
            WHERE timestamp >= now() - INTERVAL 30 DAY
            """
            
            file_results = await self.execute_query(file_query)
            stats['files'] = file_results[0] if file_results else {}
            
            # Tool results stats
            tool_query = """
            SELECT 
                count() as total_tool_executions,
                uniq(tool_name) as unique_tools,
                countIf(success) as successful_executions,
                round(countIf(success) * 100.0 / count(), 2) as success_rate,
                sum(output_size) as total_output_bytes
            FROM otel.claude_tool_results
            WHERE timestamp >= now() - INTERVAL 30 DAY
            """
            
            tool_results = await self.execute_query(tool_query)
            stats['tools'] = tool_results[0] if tool_results else {}
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting JSONL content stats: {e}")
            return {}

    async def get_model_token_stats(self, time_range_days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get model-specific token statistics from official Claude Code metrics."""
        try:
            # Get token data by model and type from official metrics
            token_query = f"""
            SELECT 
                Attributes['model'] as model,
                Attributes['type'] as token_type,
                SUM(Value) as total_tokens
            FROM otel.otel_metrics_sum
            WHERE MetricName = 'claude_code.token.usage'
                AND TimeUnix >= now() - INTERVAL {time_range_days} DAY
                AND Attributes['model'] IS NOT NULL
                AND Attributes['type'] IS NOT NULL
            GROUP BY Attributes['model'], Attributes['type']
            ORDER BY Attributes['model'], total_tokens DESC
            """
            
            token_results = await self.execute_query(token_query)
            
            # Get cost and request count from OTEL logs (still needed for these metrics)
            cost_query = f"""
            SELECT 
                LogAttributes['model'] as model,
                COUNT(*) as request_count,
                AVG(toFloat64OrNull(LogAttributes['cost_usd'])) as avg_cost,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration
            FROM otel.otel_logs 
            WHERE Body = 'claude_code.api_request'
                AND Timestamp >= now() - INTERVAL {time_range_days} DAY
                AND LogAttributes['model'] IS NOT NULL
                AND LogAttributes['cost_usd'] IS NOT NULL
            GROUP BY LogAttributes['model']
            ORDER BY request_count DESC
            """
            
            cost_results = await self.execute_query(cost_query)
            
            # Combine token and cost data by model
            model_stats = {}
            
            # Process token data first
            for row in token_results:
                model = row['model']
                token_type = row['token_type']
                tokens = int(row['total_tokens'])
                
                if model not in model_stats:
                    model_stats[model] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'cache_read_tokens': 0,
                        'cache_creation_tokens': 0,
                        'total_tokens': 0,
                        'request_count': 0,
                        'avg_cost': 0.0,
                        'total_cost': 0.0,
                        'avg_duration': 0.0
                    }
                
                # Map token types to our structure
                if token_type == 'input':
                    model_stats[model]['input_tokens'] = tokens
                elif token_type == 'output':
                    model_stats[model]['output_tokens'] = tokens
                elif token_type == 'cacheRead':
                    model_stats[model]['cache_read_tokens'] = tokens
                elif token_type == 'cacheCreation':
                    model_stats[model]['cache_creation_tokens'] = tokens
                
                model_stats[model]['total_tokens'] += tokens
            
            # Add cost and request data
            for row in cost_results:
                model = row['model']
                if model in model_stats:
                    model_stats[model].update({
                        'request_count': int(row['request_count']),
                        'avg_cost': float(row['avg_cost'] or 0),
                        'total_cost': float(row['total_cost'] or 0),
                        'avg_duration': float(row['avg_duration'] or 0)
                    })
            
            # Calculate efficiency metrics
            for model, stats in model_stats.items():
                total_tokens = stats['total_tokens']
                total_cost = stats['total_cost']
                
                if total_tokens > 0 and total_cost > 0:
                    stats['cost_per_token'] = total_cost / total_tokens
                    stats['tokens_per_dollar'] = total_tokens / total_cost
                else:
                    stats['cost_per_token'] = 0
                    stats['tokens_per_dollar'] = 0
            
            return model_stats
            
        except Exception as e:
            logger.error(f"Error getting model token stats: {e}")
            return {}

    async def bulk_insert_optimized(self, table_name: str, records: List[Dict[str, Any]],
                                   batch_size: int = 2000, enable_compression: bool = True) -> Dict[str, Any]:
        """Optimized bulk insert with larger batches and compression."""
        # Use larger batch sizes for better performance with 2.768B tokens
        optimized_batch_size = min(batch_size, 2000)  # Increased from 1000

        # Enhanced bulk insert with monitoring
        result = await self.bulk_insert_enhanced(table_name, records, optimized_batch_size)

        # Update performance stats
        if result['success']:
            insert_rate = result['average_records_per_second']
            logger.info(f"Bulk insert completed: {insert_rate:.1f} records/sec")

        return result
