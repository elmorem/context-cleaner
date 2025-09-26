"""
API/UI Consistency Checker

This module provides comprehensive monitoring of API endpoint availability
versus dashboard UI display consistency. It helps identify when APIs return
valid data but the dashboard UI shows loading states or stale data.
"""

import asyncio
import time
import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from datetime import datetime, timedelta
import psutil

try:
    from context_cleaner.telemetry.context_rot.config import ApplicationConfig
    from context_cleaner.api.models import create_error_response
except ImportError:
    # Fallback for testing
    ApplicationConfig = None
    create_error_response = None


class ConsistencyStatus(Enum):
    CONSISTENT = "consistent"
    API_WORKING_UI_LOADING = "api_working_ui_loading"
    API_ERROR_UI_SHOWING_DATA = "api_error_ui_showing_data"
    BOTH_FAILING = "both_failing"
    UNKNOWN = "unknown"


class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Simple circuit breaker implementation for API endpoints"""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

    def __post_init__(self):
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls
        return False

    def record_success(self):
        """Record a successful operation"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            self.half_open_calls += 1
            if self.success_count >= 2:  # Require 2 successes to close
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        else:
            self.failure_count = max(0, self.failure_count - 1)  # Gradually reduce failure count

    def record_failure(self):
        """Record a failed operation"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = time.time()
        else:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_failure_time = time.time()

    def get_state_info(self) -> dict:
        """Get current circuit breaker state information"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute()
        }


@dataclass
class APIEndpointTest:
    """Configuration for testing a specific API endpoint"""
    path: str
    method: str = "GET"
    expected_keys: List[str] = field(default_factory=list)
    timeout: float = 5.0
    critical: bool = True
    
    
@dataclass
class ConsistencyCheckResult:
    """Result of an API/UI consistency check"""
    endpoint: str
    api_status: str
    api_response_time: float
    api_data_size: int
    api_error: Optional[str]
    ui_status: str
    ui_error: Optional[str]
    consistency_status: ConsistencyStatus
    timestamp: datetime
    recommendations: List[str] = field(default_factory=list)


class APIUIConsistencyChecker:
    """
    Monitors consistency between API endpoints and dashboard UI display.
    
    This service tests all dashboard API endpoints and attempts to verify
    that the UI is properly consuming and displaying the data.
    """
    
    def __init__(self, config: Optional[ApplicationConfig] = None, dashboard_host: str = "127.0.0.1", dashboard_port: Optional[int] = None):
        # Use default config if none provided
        if config is None and ApplicationConfig is not None:
            self.config = ApplicationConfig.default()
        else:
            self.config = config
        self.dashboard_host = dashboard_host
        self.initial_dashboard_port = dashboard_port
        self.dashboard_port = dashboard_port or 8080  # Fallback default
        self.base_url = f"http://{dashboard_host}:{self.dashboard_port}"
        self.logger = logging.getLogger(__name__)

        # Dynamic port discovery
        self.dynamic_port_discovery = True
        
        # Define all dashboard API endpoints to test
        self.api_endpoints = self._define_api_endpoints()
        
        # Results storage
        self.last_check_results: Dict[str, ConsistencyCheckResult] = {}
        self.check_history: List[Dict[str, ConsistencyCheckResult]] = []
        
        # Configuration and cadence controls (ENV overrides for tuning)
        self.check_interval = float(os.getenv("CONTEXT_CLEANER_CONSISTENCY_INTERVAL", "300"))
        self.ui_check_timeout = float(os.getenv("CONTEXT_CLEANER_CONSISTENCY_UI_TIMEOUT", "5.0"))
        self.startup_delay = float(os.getenv("CONTEXT_CLEANER_CONSISTENCY_STARTUP_DELAY", "15.0"))
        self.http_session_timeout = float(os.getenv("CONTEXT_CLEANER_CONSISTENCY_HTTP_TIMEOUT", "30.0"))
        self.http_connector_limit = int(os.getenv("CONTEXT_CLEANER_CONSISTENCY_HTTP_LIMIT", "4"))
        self.max_endpoints_per_cycle = int(os.getenv("CONTEXT_CLEANER_CONSISTENCY_ENDPOINT_BATCH", "5"))
        self.ui_min_content_length = int(os.getenv("CONTEXT_CLEANER_CONSISTENCY_MIN_HTML", "2000"))
        self.fd_logging_enabled = os.getenv("CONTEXT_CLEANER_CONSISTENCY_LOG_FDS", "false").strip().lower() in {"1", "true", "yes", "on"}
        self._fd_process = psutil.Process() if self.fd_logging_enabled else None
        self._fd_baseline: Optional[int] = None

        # UI readiness heuristics
        self.ui_ready_markers = (
            "telemetry-widget",
            "data-widget",
            "dashboard-root",
            "context-cleaner",
            "window.__CONTEXT_CLEANER",
        )

        # Endpoint batching state
        self._endpoint_cursor = 0

        # Task management and error recovery
        self.monitoring_task: Optional[asyncio.Task] = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10  # Increased from 3 to be more tolerant of temporary issues
        self.is_running = False
        self.shutdown_event = asyncio.Event()

        # Startup grace period - don't fail health checks during this time
        self.startup_grace_period = 60.0  # seconds - 60 second grace period for system startup
        self.start_time = time.time()  # Track when monitoring started

        # Circuit breakers for API endpoints (one per endpoint)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._initialize_circuit_breakers()
        
    def _define_api_endpoints(self) -> List[APIEndpointTest]:
        """Define all API endpoints that should be tested - these are the ACTUAL endpoints discovered from dashboard HTML"""
        return [
            # Core dashboard analytics endpoints
            APIEndpointTest("/api/dashboard-metrics", expected_keys=["active_agents", "last_updated", "model_efficiency", "orchestration_status", "success_rate"]),
            APIEndpointTest("/api/context-window-usage", expected_keys=["active_directories", "directories", "estimated_total_tokens", "success", "total_size_mb"]),
            APIEndpointTest("/api/conversation-analytics", expected_keys=["last_updated", "range", "summary", "timeline"]),
            APIEndpointTest("/api/code-patterns-analytics", expected_keys=["last_updated", "patterns"]),
            APIEndpointTest("/api/content-search", method="GET", expected_keys=["results", "status", "message"]),
            
            # Analytics endpoints
            APIEndpointTest("/api/analytics/context-health", expected_keys=["compression_rate", "context_size_kb", "error_rate", "relevance_score", "sessions_today"]),
            APIEndpointTest("/api/analytics/performance-trends", expected_keys=["cache_hit_rate", "events_prev_week", "events_this_week", "response_time_seconds", "status"]),
            
            # JSONL processing endpoints
            APIEndpointTest("/api/jsonl-processing-status", expected_keys=["database_healthy", "error_rate", "last_updated", "privacy_level", "processing_rate"]),
            
            # Telemetry widget endpoints (actual working endpoints)
            APIEndpointTest("/api/telemetry-widget/code-pattern-analysis", expected_keys=["alerts", "data", "last_updated", "status", "title"]),
            APIEndpointTest("/api/telemetry-widget/content-search-widget", expected_keys=["alerts", "data", "last_updated", "status", "title"]),
            APIEndpointTest("/api/telemetry-widget/conversation-timeline", expected_keys=["alerts", "data", "last_updated", "status", "title"]),
            
            # Telemetry analytics endpoints
            APIEndpointTest("/api/telemetry/error-details?hours=24", expected_keys=["error_breakdown", "error_summary", "raw_breakdown", "recent_errors"]),
            APIEndpointTest("/api/telemetry/model-analytics", expected_keys=["avg_response_time", "cost_efficiency_ratio", "cost_per_query_type", "detailed_analytics_available", "efficiency_score"]),
            APIEndpointTest("/api/telemetry/tool-analytics", expected_keys=["common_sequences", "efficiency_score", "optimization_suggestions", "tool_usage_stats"]),
            
            # Data explorer endpoint (now supports GET for health checks)
            APIEndpointTest("/api/data-explorer/query", method="GET", expected_keys=["status", "message", "example_query"], critical=False),
        ]

    async def discover_dashboard_port(self) -> Optional[int]:
        """
        Dynamically discover the actual dashboard port by checking running processes.
        Returns the discovered port or None if not found.
        """
        import subprocess
        import psutil

        self.logger.info("🔍 PORT_DISCOVERY: Starting dynamic port discovery for dashboard...")
        discovery_start = time.time()

        try:
            # Method 1: Check for gunicorn processes with context_cleaner
            self.logger.debug("🔍 PORT_DISCOVERY: Scanning running processes for gunicorn...")
            found_processes = 0

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if not proc.info['cmdline']:
                        continue

                    cmdline = ' '.join(proc.info['cmdline']).lower()
                    found_processes += 1

                    # Look for gunicorn processes running context_cleaner dashboard
                    if ('gunicorn' in cmdline and 'context_cleaner' in cmdline):
                        self.logger.info(f"🔍 PORT_DISCOVERY: Found gunicorn process PID {proc.info['pid']}: {cmdline[:100]}...")

                        # Extract port from --bind argument
                        for i, arg in enumerate(proc.info['cmdline']):
                            if arg == '--bind' and i + 1 < len(proc.info['cmdline']):
                                bind_arg = proc.info['cmdline'][i + 1]
                                self.logger.debug(f"🔍 PORT_DISCOVERY: Found --bind argument: {bind_arg}")

                                if ':' in bind_arg:
                                    port_str = bind_arg.split(':')[-1]
                                    try:
                                        port = int(port_str)
                                        discovery_duration = time.time() - discovery_start
                                        self.logger.info(f"🔍 PORT_DISCOVERY: ✅ Successfully discovered dashboard port {port} from gunicorn process PID {proc.info['pid']} in {discovery_duration:.2f}s")
                                        return port
                                    except ValueError as ve:
                                        self.logger.warning(f"🔍 PORT_DISCOVERY: Invalid port format '{port_str}': {ve}")
                                        continue

                except (psutil.NoSuchProcess, psutil.AccessDenied) as pe:
                    self.logger.debug(f"🔍 PORT_DISCOVERY: Process access error: {pe}")
                    continue

            self.logger.debug(f"🔍 PORT_DISCOVERY: Scanned {found_processes} processes, no gunicorn context_cleaner found")

            # Method 2: Check comprehensive port ranges for active services
            port_ranges = [
                # Most common Context Cleaner ports
                [8110, 8080, 8090, 8100, 8120, 8111, 8112, 8113, 8114, 8115],
                # Extended common ranges
                list(range(8000, 8020)),  # 8000-8019
                list(range(8050, 8070)),  # 8050-8069
                list(range(8080, 8130)),  # 8080-8129 (extended around default)
                list(range(8200, 8220)),  # 8200-8219
                list(range(9000, 9020)),  # 9000-9019
                # Additional ranges from port conflict manager
                list(range(8300, 8310)),  # 8300-8309
                list(range(8400, 8410)),  # 8400-8409
                list(range(8500, 8510)),  # 8500-8509
                list(range(8600, 8610)),  # 8600-8609
                list(range(8700, 8710)),  # 8700-8709
                list(range(8800, 8810)),  # 8800-8809
                list(range(8900, 8910)),  # 8900-8909
                list(range(9100, 9110)),  # 9100-9109
                list(range(9200, 9210)),  # 9200-9209
            ]

            # Flatten and deduplicate ports, prioritizing most common ones first
            all_ports = []
            for port_range in port_ranges:
                all_ports.extend(port_range)

            # Remove duplicates while preserving order
            seen = set()
            common_ports = []
            for port in all_ports:
                if port not in seen:
                    common_ports.append(port)
                    seen.add(port)

            self.logger.info(f"🔍 PORT_DISCOVERY: Testing {len(common_ports)} ports across multiple ranges for dashboard services...")
            self.logger.debug(f"🔍 PORT_DISCOVERY: Port ranges: 8000-8019, 8050-8069, 8080-8129, 8200-8219, 8300-8309, 8400-8409, 8500-8509, 8600-8609, 8700-8709, 8800-8809, 8900-8909, 9000-9019, 9100-9109, 9200-9209")

            # Test ports in batches for better performance
            batch_size = 20
            for batch_start in range(0, len(common_ports), batch_size):
                batch_end = min(batch_start + batch_size, len(common_ports))
                batch_ports = common_ports[batch_start:batch_end]

                self.logger.debug(f"🔍 PORT_DISCOVERY: Testing batch {batch_start//batch_size + 1}: ports {batch_ports[0]}-{batch_ports[-1]} ({len(batch_ports)} ports)")

                for i, port in enumerate(batch_ports):
                    overall_index = batch_start + i
                    port_test_start = time.time()

                    try:
                        # Special logging for key ports
                        if port in [8110, 8080]:  # Expected or default ports
                            self.logger.info(f"🔍 PORT_DISCOVERY: 🎯 Testing KEY port {port} ({overall_index+1}/{len(common_ports)})...")
                        elif overall_index % 50 == 0:  # Log progress every 50 ports
                            self.logger.info(f"🔍 PORT_DISCOVERY: Progress: testing port {port} ({overall_index+1}/{len(common_ports)})...")
                        else:
                            self.logger.debug(f"🔍 PORT_DISCOVERY: Testing port {port} ({overall_index+1}/{len(common_ports)})...")

                        # Quick connection test with reduced timeout for efficiency
                        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1)) as session:
                            # Try multiple endpoints to detect dashboard
                            test_endpoints = ["/api/dashboard-metrics", "/api/context-window-usage", "/api/health", "/"]

                            for test_endpoint in test_endpoints:
                                try:
                                    test_url = f"http://{self.dashboard_host}:{port}{test_endpoint}"

                                    if port in [8110, 8080]:
                                        self.logger.info(f"🔍 PORT_DISCOVERY: 🎯 Making request to {test_url}")

                                    async with session.get(test_url) as response:
                                        port_test_duration = time.time() - port_test_start

                                        if port in [8110, 8080]:
                                            self.logger.info(f"🔍 PORT_DISCOVERY: 🎯 Port {port} endpoint {test_endpoint} responded with status {response.status} in {port_test_duration:.2f}s")
                                        else:
                                            self.logger.debug(f"🔍 PORT_DISCOVERY: Port {port} endpoint {test_endpoint} responded with status {response.status} in {port_test_duration:.2f}s")

                                        if response.status == 200:
                                            # Found a working endpoint - this looks like our dashboard
                                            if test_endpoint in ["/api/dashboard-metrics", "/api/context-window-usage"]:
                                                # These are definitely dashboard endpoints
                                                discovery_duration = time.time() - discovery_start
                                                self.logger.info(f"🔍 PORT_DISCOVERY: ✅ Successfully discovered dashboard port {port} via {test_endpoint} endpoint in {discovery_duration:.2f}s")
                                                return port
                                            elif test_endpoint == "/api/health":
                                                # Check health response format
                                                try:
                                                    data = await response.json()
                                                    if port in [8110, 8080]:
                                                        self.logger.info(f"🔍 PORT_DISCOVERY: 🎯 Port {port} health response: {json.dumps(data, indent=2)}")
                                                    else:
                                                        self.logger.debug(f"🔍 PORT_DISCOVERY: Port {port} health response: {json.dumps(data, indent=2)}")

                                                    if isinstance(data, dict) and ('status' in data or 'healthy' in data):
                                                        discovery_duration = time.time() - discovery_start
                                                        self.logger.info(f"🔍 PORT_DISCOVERY: ✅ Successfully discovered dashboard port {port} via health check in {discovery_duration:.2f}s")
                                                        return port
                                                except:
                                                    pass
                                            elif test_endpoint == "/" and response.headers.get('content-type', '').startswith('text/html'):
                                                # Main page with HTML - likely dashboard
                                                discovery_duration = time.time() - discovery_start
                                                self.logger.info(f"🔍 PORT_DISCOVERY: ✅ Successfully discovered dashboard port {port} via main page in {discovery_duration:.2f}s")
                                                return port

                                except Exception as endpoint_error:
                                    if port in [8110, 8080]:
                                        self.logger.debug(f"🔍 PORT_DISCOVERY: 🎯 Port {port} endpoint {test_endpoint} failed: {str(endpoint_error)[:50]}")
                                    continue

                    except Exception as conn_error:
                        port_test_duration = time.time() - port_test_start

                        if port in [8110, 8080]:
                            self.logger.warning(f"🔍 PORT_DISCOVERY: 🎯 Port {port} connection FAILED in {port_test_duration:.2f}s: {str(conn_error)}")
                        else:
                            self.logger.debug(f"🔍 PORT_DISCOVERY: Port {port} connection failed in {port_test_duration:.2f}s: {str(conn_error)[:100]}")
                        continue

            discovery_duration = time.time() - discovery_start
            self.logger.warning(f"🔍 PORT_DISCOVERY: ❌ No dashboard port found after checking {len(common_ports)} ports in {discovery_duration:.2f}s")

        except Exception as e:
            discovery_duration = time.time() - discovery_start
            self.logger.error(f"🔍 PORT_DISCOVERY: ❌ Discovery failed after {discovery_duration:.2f}s: {e}")
            import traceback
            self.logger.error(f"🔍 PORT_DISCOVERY: Discovery error traceback:\n{traceback.format_exc()}")

        return None

    async def update_dashboard_port_if_needed(self) -> bool:
        """
        Update the dashboard port if dynamic discovery is enabled and current port is failing.
        Returns True if port was updated, False otherwise.
        """
        if not self.dynamic_port_discovery:
            return False

        # Only try to discover if we don't have an initial port or if current connections are failing
        discovered_port = await self.discover_dashboard_port()

        if discovered_port and discovered_port != self.dashboard_port:
            old_port = self.dashboard_port
            self.dashboard_port = discovered_port
            self.base_url = f"http://{self.dashboard_host}:{self.dashboard_port}"

            self.logger.info(f"🔄 Updated dashboard port from {old_port} to {discovered_port}")

            # Clear circuit breaker states since we're connecting to a new port
            self._circuit_breakers.clear()

            return True

        return False

    async def test_api_endpoint(
        self,
        endpoint_test: APIEndpointTest,
        *,
        session: aiohttp.ClientSession,
    ) -> Tuple[str, float, int, Optional[str], Any]:
        """Test a single API endpoint using a shared HTTP session."""

        start_time = time.time()
        self.logger.debug(
            f"🔗 ENDPOINT_TEST: Starting test for {endpoint_test.path} (method: {endpoint_test.method})"
        )

        # Check circuit breaker before making request
        circuit_breaker = self._circuit_breakers.get(endpoint_test.path)
        if circuit_breaker and not circuit_breaker.can_execute():
            response_time = time.time() - start_time
            state_info = circuit_breaker.get_state_info()
            self.logger.warning(
                f"🔗 ENDPOINT_TEST: Circuit breaker OPEN for {endpoint_test.path}: {state_info}"
            )
            return (
                "circuit_open",
                response_time,
                0,
                f"Circuit breaker {state_info['state']}: {circuit_breaker.failure_count} failures",
                None,
            )

        try:
            url = f"{self.base_url}{endpoint_test.path}"
            request_start = time.time()
            request_timeout = aiohttp.ClientTimeout(total=endpoint_test.timeout)

            async with session.request(
                endpoint_test.method,
                url,
                timeout=request_timeout,
            ) as response:
                response_time = time.time() - start_time
                request_duration = time.time() - request_start

                self.logger.debug(
                    f"🔗 ENDPOINT_TEST: {endpoint_test.path} responded with status {response.status} in {request_duration:.2f}s"
                )

                if response.status == 200:
                    try:
                        json_start = time.time()
                        data = await response.json()
                        json_duration = time.time() - json_start
                        data_size = len(json.dumps(data))
                        self.logger.debug(
                            f"🔗 ENDPOINT_TEST: {endpoint_test.path} JSON parsing took {json_duration:.2f}s, size: {data_size} bytes"
                        )

                        missing_keys = [
                            key for key in endpoint_test.expected_keys if key not in data
                        ]

                        if missing_keys:
                            result = (
                                "partial",
                                response_time,
                                data_size,
                                f"Missing keys: {missing_keys}",
                                data,
                            )
                            self._record_circuit_breaker_result(endpoint_test.path, "partial")
                            return result

                        result = ("success", response_time, data_size, None, data)
                        self._record_circuit_breaker_result(endpoint_test.path, "success")
                        return result

                    except json.JSONDecodeError as json_error:
                        result = (
                            "invalid_json",
                            response_time,
                            0,
                            f"JSON decode error: {json_error}",
                            None,
                        )
                        self._record_circuit_breaker_result(endpoint_test.path, "invalid_json")
                        return result

                error_text = await response.text()
                result = (
                    "error",
                    response_time,
                    len(error_text),
                    f"HTTP {response.status}: {error_text}",
                    None,
                )
                self._record_circuit_breaker_result(endpoint_test.path, "error")
                return result

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            result = (
                "timeout",
                response_time,
                0,
                f"Request timeout after {endpoint_test.timeout}s",
                None,
            )
            self._record_circuit_breaker_result(endpoint_test.path, "timeout")
            return result

        except Exception as exc:
            response_time = time.time() - start_time
            error_type = type(exc).__name__
            error_msg = str(exc)

            self.logger.warning(
                f"🔗 ENDPOINT_TEST: ❌ {endpoint_test.path} failed after {response_time:.2f}s: {error_type}"
            )
            self.logger.debug(
                f"🔗 ENDPOINT_TEST: Full error for {endpoint_test.path}: {error_msg}"
            )

            if "cannot connect" in error_msg.lower() or "connection refused" in error_msg.lower():
                self.logger.warning(
                    f"🔗 ENDPOINT_TEST: Connection error to {self.base_url}{endpoint_test.path}"
                )
            elif "timeout" in error_msg.lower():
                self.logger.warning(
                    f"🔗 ENDPOINT_TEST: Timeout error for {endpoint_test.path} after {endpoint_test.timeout}s"
                )
            elif "ssl" in error_msg.lower():
                self.logger.warning(
                    f"🔗 ENDPOINT_TEST: SSL/TLS error for {endpoint_test.path}"
                )

            circuit_breaker = self._circuit_breakers.get(endpoint_test.path)
            if circuit_breaker:
                old_state = circuit_breaker.state.value
                self._record_circuit_breaker_result(endpoint_test.path, "error")
                new_state = circuit_breaker.state.value
                if old_state != new_state:
                    self.logger.warning(
                        f"🔗 CIRCUIT_BREAKER: {endpoint_test.path} state changed: {old_state} → {new_state} (failures: {circuit_breaker.failure_count})"
                    )

            result = ("error", response_time, 0, error_msg, None)
            return result

    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for each API endpoint"""
        for endpoint in self.api_endpoints:
            # Use different failure thresholds based on criticality
            failure_threshold = 3 if endpoint.critical else 5
            recovery_timeout = 30 if endpoint.critical else 60

            self._circuit_breakers[endpoint.path] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max_calls=2
            )

    def _record_circuit_breaker_result(self, endpoint_path: str, status: str):
        """Record the result in the circuit breaker"""
        circuit_breaker = self._circuit_breakers.get(endpoint_path)
        if circuit_breaker:
            if status in ["success", "partial"]:  # Consider partial success as success
                circuit_breaker.record_success()
            elif status in ["error", "timeout", "invalid_json"]:
                circuit_breaker.record_failure()

    async def check_ui_widget_status(
        self,
        endpoint_path: str,
        *,
        session: aiohttp.ClientSession,
        dashboard_html: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """Classify the dashboard UI state using a shared session and cached HTML."""

        try:
            if dashboard_html is None:
                dashboard_html = await self.fetch_dashboard_html(session)

            if dashboard_html is None:
                return "error", "Dashboard HTML unavailable"

            return self._classify_dashboard_html(dashboard_html)

        except Exception as exc:  # pragma: no cover - defensive
            return "error", str(exc)

    async def fetch_dashboard_html(self, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch the dashboard HTML once per cycle."""

        try:
            async with session.get(
                self.base_url,
                timeout=aiohttp.ClientTimeout(total=self.ui_check_timeout),
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    self.logger.debug(
                        f"🌐 DASHBOARD_HTML: Retrieved {len(html)} bytes from {self.base_url}"
                    )
                    return html

                self.logger.debug(
                    f"🌐 DASHBOARD_HTML: HTTP {response.status} while fetching dashboard root"
                )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug(f"🌐 DASHBOARD_HTML: Failed to fetch dashboard HTML: {exc}")

        return None

    def _classify_dashboard_html(self, html: str) -> Tuple[str, Optional[str]]:
        """Apply lightweight heuristics to classify dashboard readiness."""

        content_length = len(html)
        lowered = html.lower()

        if content_length < self.ui_min_content_length:
            return "minimal", (
                f"Dashboard HTML length {content_length} below threshold {self.ui_min_content_length}"
            )

        if "data-dashboard-error" in lowered or "runtime error" in lowered or "stack trace" in lowered:
            return "error", "Dashboard HTML contains error indicators"

        ready_marker = any(marker.lower() in lowered for marker in self.ui_ready_markers)
        loading_marker = (
            "data-loading" in lowered
            or "aria-busy=\"true\"" in lowered
            or "loading..." in lowered
        )

        if ready_marker:
            return "loaded", None

        if loading_marker:
            return "loading", "Dashboard HTML indicates loading state"

        # Default to loaded when content looks healthy but markers were absent
        return "loaded", None

    async def wait_for_dashboard_ready(self, max_wait: float = 60.0, check_interval: float = 2.0) -> bool:
        """Wait for the dashboard to be ready before starting consistency checks"""
        wait_start_time = time.time()
        attempt_count = 0
        last_error = None
        last_status_code = None
        last_content_length = None

        self.logger.info(f"🌐 DASHBOARD_WAIT: Starting dashboard readiness check for {self.base_url}")
        self.logger.info(f"🌐 DASHBOARD_WAIT: Max wait: {max_wait}s, check interval: {check_interval}s")

        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            attempt_count += 1
            attempt_start = time.time()

            try:
                self.logger.debug(f"🌐 DASHBOARD_WAIT: Attempt #{attempt_count} - checking {self.base_url}")

                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5.0)) as session:
                    async with session.get(self.base_url) as response:
                        attempt_duration = time.time() - attempt_start
                        last_status_code = response.status

                        if response.status == 200:
                            html_content = await response.text()
                            last_content_length = len(html_content)

                            self.logger.debug(f"🌐 DASHBOARD_WAIT: Attempt #{attempt_count} - HTTP 200, content length: {last_content_length}")

                            if len(html_content) > 1000:  # Basic check that we got a real dashboard
                                elapsed_time = time.time() - wait_start_time
                                self.logger.info(f"🌐 DASHBOARD_READY: Dashboard is ready after {elapsed_time:.2f}s, {attempt_count} attempts")
                                self.logger.info(f"🌐 DASHBOARD_READY: Final status: HTTP {response.status}, content length: {last_content_length}")
                                return True
                            else:
                                self.logger.debug(f"🌐 DASHBOARD_WAIT: Content too short ({last_content_length} bytes), dashboard may not be fully loaded")
                        else:
                            self.logger.debug(f"🌐 DASHBOARD_WAIT: Attempt #{attempt_count} - HTTP {response.status} (took {attempt_duration:.2f}s)")

            except asyncio.CancelledError:
                elapsed_time = time.time() - wait_start_time
                self.logger.info(f"🌐 DASHBOARD_WAIT: Dashboard readiness check cancelled after {elapsed_time:.2f}s, {attempt_count} attempts")
                raise  # Re-raise cancellation
            except Exception as e:
                attempt_duration = time.time() - attempt_start
                last_error = str(e)
                self.logger.debug(f"🌐 DASHBOARD_WAIT: Attempt #{attempt_count} failed after {attempt_duration:.2f}s: {e}")

            # Log periodic status
            if attempt_count % 10 == 0:  # Every 10 attempts
                elapsed_time = time.time() - wait_start_time
                self.logger.info(f"🌐 DASHBOARD_WAIT: Still waiting... {attempt_count} attempts in {elapsed_time:.1f}s")
                self.logger.info(f"🌐 DASHBOARD_WAIT: Last status: {last_status_code}, last error: {last_error}")

            await asyncio.sleep(check_interval)

        # Dashboard never became ready
        elapsed_time = time.time() - wait_start_time
        self.logger.warning(f"🌐 DASHBOARD_TIMEOUT: Dashboard not ready after {elapsed_time:.2f}s ({attempt_count} attempts)")
        self.logger.warning(f"🌐 DASHBOARD_TIMEOUT: Last status: {last_status_code}, last content length: {last_content_length}")
        self.logger.warning(f"🌐 DASHBOARD_TIMEOUT: Last error: {last_error}")
        self.logger.warning(f"🌐 DASHBOARD_TIMEOUT: Proceeding with monitoring anyway...")
        return False
    
    def determine_consistency_status(self, api_status: str, ui_status: str, api_data_size: int) -> ConsistencyStatus:
        """Determine the overall consistency status"""
        
        if api_status == "success" and ui_status == "loaded" and api_data_size > 0:
            return ConsistencyStatus.CONSISTENT
            
        elif api_status == "success" and api_data_size > 0 and ui_status in ["loading", "minimal"]:
            return ConsistencyStatus.API_WORKING_UI_LOADING
            
        elif api_status in ["error", "timeout"] and ui_status == "loaded":
            return ConsistencyStatus.API_ERROR_UI_SHOWING_DATA
            
        elif api_status in ["error", "timeout"] and ui_status in ["error", "loading"]:
            return ConsistencyStatus.BOTH_FAILING
            
        else:
            return ConsistencyStatus.UNKNOWN
    
    def generate_recommendations(self, result: ConsistencyCheckResult) -> List[str]:
        """Generate actionable recommendations based on the consistency check"""
        recommendations = []
        
        if result.consistency_status == ConsistencyStatus.API_WORKING_UI_LOADING:
            recommendations.extend([
                "API is returning data but UI shows loading state",
                "Check JavaScript console for frontend errors", 
                "Verify WebSocket connections for real-time updates",
                "Check if frontend is properly consuming API endpoints",
                "Consider clearing browser cache or restarting dashboard service"
            ])
            
        elif result.consistency_status == ConsistencyStatus.API_ERROR_UI_SHOWING_DATA:
            recommendations.extend([
                "UI is showing data but API is failing",
                "UI may be showing cached/stale data",
                "Check API endpoint implementation",
                "Verify database connections for API endpoints"
            ])
            
        elif result.consistency_status == ConsistencyStatus.BOTH_FAILING:
            recommendations.extend([
                "Both API and UI are failing",
                "Check dashboard service health",
                "Verify database connectivity", 
                "Check for system resource issues",
                "Consider restarting dashboard service"
            ])
            
        if result.api_response_time > 5.0:
            recommendations.append(f"API response time is slow ({result.api_response_time:.2f}s)")
            
        if result.api_data_size == 0 and result.api_status == "success":
            recommendations.append("API returned empty data - check data sources")
            
        return recommendations
    
    async def run_consistency_check(
        self,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> Dict[str, ConsistencyCheckResult]:
        """Run a consistency check using a shared session and batched endpoints."""

        owns_session = session is None
        if owns_session:
            timeout = aiohttp.ClientTimeout(total=self.http_session_timeout)
            connector = aiohttp.TCPConnector(limit_per_host=self.http_connector_limit)
            session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        assert session is not None  # For type-checkers

        endpoints_to_check = self._select_endpoints_for_cycle()
        if not endpoints_to_check:
            self.logger.debug("Consistency check skipped: no endpoints configured")
            return {}

        self.logger.info(
            f"Starting API/UI consistency check for {len(endpoints_to_check)} endpoints (batch mode)"
        )

        if self.fd_logging_enabled:
            fd_before = self._capture_fd_count()
            if fd_before is not None:
                self.logger.debug(f"🔍 FD_MONITOR: descriptors before cycle={fd_before}")
                if self._fd_baseline is None:
                    self._fd_baseline = fd_before

        cycle_results: Dict[str, ConsistencyCheckResult] = {}

        try:
            dashboard_html = await self.fetch_dashboard_html(session)

            for endpoint_test in endpoints_to_check:
                self.logger.debug(f"Testing endpoint: {endpoint_test.path}")

                api_status, response_time, data_size, api_error, api_data = await self.test_api_endpoint(
                    endpoint_test,
                    session=session,
                )

                ui_status, ui_error = await self.check_ui_widget_status(
                    endpoint_test.path,
                    session=session,
                    dashboard_html=dashboard_html,
                )

                consistency_status = self.determine_consistency_status(
                    api_status,
                    ui_status,
                    data_size,
                )

                result = ConsistencyCheckResult(
                    endpoint=endpoint_test.path,
                    api_status=api_status,
                    api_response_time=response_time,
                    api_data_size=data_size,
                    api_error=api_error,
                    ui_status=ui_status,
                    ui_error=ui_error,
                    consistency_status=consistency_status,
                    timestamp=datetime.now(),
                )

                result.recommendations = self.generate_recommendations(result)
                cycle_results[endpoint_test.path] = result

            if cycle_results:
                self.last_check_results.update(cycle_results)
                self.check_history.append({
                    "timestamp": datetime.now(),
                    "results": cycle_results.copy(),
                })
                if len(self.check_history) > 50:
                    self.check_history = self.check_history[-50:]

            self.logger.info(
                f"Consistency check completed. Found {self._count_inconsistencies(cycle_results)} inconsistencies"
            )

            if self.fd_logging_enabled:
                fd_after = self._capture_fd_count()
                if fd_after is not None:
                    delta = (
                        None
                        if self._fd_baseline is None
                        else fd_after - self._fd_baseline
                    )
                    self.logger.debug(
                        f"🔍 FD_MONITOR: descriptors after cycle={fd_after} (Δ{delta})"
                    )

            return cycle_results

        finally:
            if owns_session:
                await session.close()
    
    def _select_endpoints_for_cycle(self) -> List[APIEndpointTest]:
        """Return the next batch of endpoints to evaluate."""

        if not self.api_endpoints:
            return []

        if (
            self.max_endpoints_per_cycle <= 0
            or self.max_endpoints_per_cycle >= len(self.api_endpoints)
        ):
            return list(self.api_endpoints)

        batch_size = max(1, self.max_endpoints_per_cycle)
        selected: List[APIEndpointTest] = []
        total = len(self.api_endpoints)

        for _ in range(batch_size):
            index = self._endpoint_cursor % total
            selected.append(self.api_endpoints[index])
            self._endpoint_cursor = (self._endpoint_cursor + 1) % total

        return selected

    def _capture_fd_count(self) -> Optional[int]:
        """Capture the current file descriptor count when enabled."""

        if not self.fd_logging_enabled or self._fd_process is None:
            return None

        try:
            return self._fd_process.num_fds()
        except Exception:  # pragma: no cover - platform dependent
            return None

    def _count_inconsistencies(self, results: Dict[str, ConsistencyCheckResult]) -> int:
        """Count the number of inconsistencies found"""
        return len([r for r in results.values() 
                   if r.consistency_status != ConsistencyStatus.CONSISTENT])
    
    def get_critical_issues(self) -> List[ConsistencyCheckResult]:
        """Get list of critical consistency issues that need immediate attention"""
        critical_issues = []
        
        for result in self.last_check_results.values():
            if result.consistency_status == ConsistencyStatus.API_WORKING_UI_LOADING:
                critical_issues.append(result)
            elif result.consistency_status == ConsistencyStatus.BOTH_FAILING:
                critical_issues.append(result)
                
        return critical_issues
    
    def get_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of the consistency check results"""
        if not self.last_check_results:
            if create_error_response:
                raise create_error_response(
                    "No consistency check results available",
                    "NO_CONSISTENCY_RESULTS",
                    404
                )
            else:
                return {"error": "No consistency check results available"}  # Fallback for testing
            
        total_endpoints = len(self.last_check_results)
        consistent_count = len([r for r in self.last_check_results.values() 
                               if r.consistency_status == ConsistencyStatus.CONSISTENT])
        
        inconsistent_count = total_endpoints - consistent_count
        
        # Group by consistency status
        status_counts = {}
        for status in ConsistencyStatus:
            status_counts[status.value] = len([r for r in self.last_check_results.values() 
                                              if r.consistency_status == status])
        
        # Get worst offenders (slowest APIs)
        slow_apis = sorted([r for r in self.last_check_results.values()], 
                          key=lambda x: x.api_response_time, reverse=True)[:5]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_endpoints": total_endpoints,
            "consistent_endpoints": consistent_count,
            "inconsistent_endpoints": inconsistent_count,
            "consistency_percentage": (consistent_count / total_endpoints) * 100,
            "status_breakdown": status_counts,
            "critical_issues": len(self.get_critical_issues()),
            "slowest_apis": [
                {
                    "endpoint": r.endpoint,
                    "response_time": r.api_response_time,
                    "status": r.api_status
                } for r in slow_apis
            ],
            "recommendations": self._get_top_recommendations()
        }
    
    def _get_top_recommendations(self) -> List[str]:
        """Get the most common recommendations across all endpoints"""
        all_recommendations = []
        for result in self.last_check_results.values():
            all_recommendations.extend(result.recommendations)
            
        # Count recommendations and return most common ones
        from collections import Counter
        recommendation_counts = Counter(all_recommendations)
        return [rec for rec, count in recommendation_counts.most_common(10)]
    
    async def start_monitoring(self):
        """Start continuous monitoring of API/UI consistency with robust error recovery"""
        self.is_running = True
        self.consecutive_failures = 0
        start_time = time.time()
        loop_iteration = 0

        self.logger.info("🚀 MONITOR_START: Starting API/UI consistency monitoring with error recovery...")
        self.logger.info(f"🚀 MONITOR_START: Check interval: {self.check_interval}s, startup delay: {self.startup_delay}s")

        try:
            # Add startup delay to allow dashboard to fully initialize
            self.logger.info(f"🔄 MONITOR_START: Waiting {self.startup_delay}s for dashboard to initialize...")
            await asyncio.sleep(self.startup_delay)

            # Discover actual dashboard port before starting checks
            if self.dynamic_port_discovery:
                try:
                    self.logger.info("🔄 MONITOR_START: Attempting dynamic port discovery...")
                    port_updated = await self.update_dashboard_port_if_needed()
                    if port_updated:
                        self.logger.info("🔄 MONITOR_START: Dashboard port updated successfully")
                    else:
                        self.logger.info(f"🔄 MONITOR_START: Using configured dashboard port {self.dashboard_port}")
                except Exception as e:
                    self.logger.warning(f"🔄 MONITOR_START: Port discovery failed, continuing with port {self.dashboard_port}: {e}")

            # Wait for dashboard to be ready before starting checks
            try:
                dashboard_ready = await self.wait_for_dashboard_ready()
                if not dashboard_ready:
                    self.logger.warning("🚀 MONITOR_START: Dashboard not ready, attempting port discovery...")

                    # If dashboard is not ready on current port, try dynamic discovery
                    if self.dynamic_port_discovery:
                        try:
                            port_updated = await self.update_dashboard_port_if_needed()
                            if port_updated:
                                self.logger.info("🚀 MONITOR_START: Port updated, retrying dashboard ready check...")
                                dashboard_ready = await self.wait_for_dashboard_ready()
                                if dashboard_ready:
                                    self.logger.info("🚀 MONITOR_START: Dashboard now ready after port update!")
                                else:
                                    self.logger.warning("🚀 MONITOR_START: Dashboard still not ready after port update")
                        except Exception as e:
                            self.logger.warning(f"🚀 MONITOR_START: Port discovery failed: {e}")

                    if not dashboard_ready:
                        self.logger.warning("🚀 MONITOR_START: Dashboard not ready, but continuing anyway")
                else:
                    self.logger.info("🚀 MONITOR_START: Dashboard confirmed ready, beginning monitoring loop")
            except asyncio.CancelledError:
                startup_duration = time.time() - start_time
                self.logger.info(f"🚀 MONITOR_CANCELLED: Dashboard ready check was cancelled after {startup_duration:.2f}s during startup")
                raise  # Re-raise to properly handle cancellation

            self.logger.info("🔄 MONITOR_LOOP: Entering main monitoring loop")

            while not self.shutdown_event.is_set():
                loop_iteration += 1
                loop_start = time.time()

                try:
                    self.logger.debug(f"🔄 MONITOR_LOOP: Iteration #{loop_iteration} starting")

                    # Run consistency check with timeout protection
                    check_start = time.time()
                    timeout_obj = aiohttp.ClientTimeout(total=self.http_session_timeout)
                    connector = aiohttp.TCPConnector(limit_per_host=self.http_connector_limit)

                    async with aiohttp.ClientSession(
                        timeout=timeout_obj,
                        connector=connector,
                    ) as session:
                        await asyncio.wait_for(
                            self.run_consistency_check(session=session),
                            timeout=self.check_interval * 0.8,  # Use 80% of interval as timeout
                        )

                    check_duration = time.time() - check_start

                    # Reset failure counter on success
                    old_failures = self.consecutive_failures
                    self.consecutive_failures = 0

                    self.logger.debug(f"🔄 MONITOR_LOOP: Iteration #{loop_iteration} completed in {check_duration:.2f}s")

                    if old_failures > 0:
                        self.logger.info(f"🔄 MONITOR_RECOVERY: Recovered from {old_failures} consecutive failures")

                    # Log critical issues
                    critical_issues = self.get_critical_issues()
                    if critical_issues:
                        self.logger.warning(f"🔄 MONITOR_ISSUES: Found {len(critical_issues)} critical API/UI consistency issues:")
                        for issue in critical_issues:
                            self.logger.warning(f"🔄 MONITOR_ISSUES:   {issue.endpoint}: {issue.consistency_status.value}")

                    # Calculate sleep time accounting for check duration
                    check_duration = time.time() - check_start
                    sleep_time = max(0, self.check_interval - check_duration)

                    if sleep_time > 0:
                        self.logger.debug(f"🔄 MONITOR_LOOP: Sleeping for {sleep_time:.2f}s until next check")
                        await asyncio.wait_for(
                            self.shutdown_event.wait(),
                            timeout=sleep_time
                        )

                    loop_duration = time.time() - loop_start
                    if loop_duration > self.check_interval * 1.2:  # If loop took >20% longer than expected
                        self.logger.info(f"🔄 MONITOR_SLOW: Loop iteration took {loop_duration:.2f}s (expected {self.check_interval}s)")

                except asyncio.TimeoutError:
                    loop_duration = time.time() - loop_start
                    self.consecutive_failures += 1
                    self.logger.warning(f"🔄 MONITOR_TIMEOUT: Iteration #{loop_iteration} timed out after {loop_duration:.2f}s")
                    self.logger.warning(f"🔄 MONITOR_TIMEOUT: Failure {self.consecutive_failures}/{self.max_consecutive_failures}")

                    # Use exponential backoff for consecutive failures
                    backoff_sleep = min(self.check_interval * (2 ** min(self.consecutive_failures - 1, 3)), 300)
                    self.logger.warning(f"🔄 MONITOR_TIMEOUT: Using exponential backoff: {backoff_sleep:.2f}s")
                    await asyncio.sleep(backoff_sleep)

                except Exception as e:
                    loop_duration = time.time() - loop_start
                    self.consecutive_failures += 1
                    self.logger.error(f"🔄 MONITOR_ERROR: Exception in iteration #{loop_iteration} after {loop_duration:.2f}s")
                    self.logger.error(f"🔄 MONITOR_ERROR: Failure {self.consecutive_failures}/{self.max_consecutive_failures}: {str(e)}")

                    import traceback
                    self.logger.error(f"🔄 MONITOR_ERROR: Traceback:\n{traceback.format_exc()}")

                    if self.consecutive_failures >= self.max_consecutive_failures:
                        self.logger.error("🔄 MONITOR_RECOVERY: Max consecutive failures reached, entering recovery mode...")

                        # Try dynamic port discovery during recovery
                        if self.dynamic_port_discovery:
                            try:
                                self.logger.info("🔄 MONITOR_RECOVERY: Attempting dynamic port discovery...")
                                port_updated = await self.update_dashboard_port_if_needed()
                                if port_updated:
                                    self.logger.info("🔄 MONITOR_RECOVERY: Port updated during recovery, may resolve connection issues")
                            except Exception as port_error:
                                self.logger.warning(f"🔄 MONITOR_RECOVERY: Port discovery during recovery failed: {port_error}")

                        # Wait longer before retrying, but don't give up
                        recovery_sleep = self.check_interval * 5
                        self.logger.error(f"🔄 MONITOR_RECOVERY: Recovery mode sleep: {recovery_sleep}s")
                        await asyncio.sleep(recovery_sleep)
                        self.consecutive_failures = 0  # Reset after extended wait
                        self.logger.info("🔄 MONITOR_RECOVERY: Exiting recovery mode, resetting failure count")
                    else:
                        # Use exponential backoff for failures
                        backoff_sleep = min(self.check_interval * (2 ** (self.consecutive_failures - 1)), 120)
                        self.logger.warning(f"🔄 MONITOR_ERROR: Using exponential backoff: {backoff_sleep:.2f}s")
                        await asyncio.sleep(backoff_sleep)

        except asyncio.CancelledError:
            total_runtime = time.time() - start_time
            self.logger.info(f"🛑 MONITOR_CANCELLED: Consistency monitoring task cancelled after {total_runtime:.2f}s")
            self.logger.info(f"🛑 MONITOR_CANCELLED: Completed {loop_iteration} iterations, {self.consecutive_failures} consecutive failures")
            raise
        except Exception as e:
            total_runtime = time.time() - start_time
            self.logger.error(f"🛑 MONITOR_FATAL: Fatal error in consistency monitoring after {total_runtime:.2f}s")
            self.logger.error(f"🛑 MONITOR_FATAL: Completed {loop_iteration} iterations, {self.consecutive_failures} consecutive failures")
            self.logger.error(f"🛑 MONITOR_FATAL: Fatal exception: {str(e)}")

            import traceback
            self.logger.error(f"🛑 MONITOR_FATAL: Fatal traceback:\n{traceback.format_exc()}")
            raise
        finally:
            total_runtime = time.time() - start_time
            self.is_running = False
            self.logger.info(f"🛑 MONITOR_STOPPED: Consistency monitoring stopped after {total_runtime:.2f}s")
            self.logger.info(f"🛑 MONITOR_STOPPED: Final stats - {loop_iteration} iterations, {self.consecutive_failures} consecutive failures")

    async def stop_monitoring(self):
        """Gracefully stop the monitoring loop"""
        self.logger.info("Stopping API/UI consistency monitoring...")
        self.shutdown_event.set()
        self.is_running = False

    def is_monitoring_healthy(self) -> bool:
        """Check if the monitoring service is in a healthy state"""

        # Check if we're still in startup grace period
        startup_age = time.time() - self.start_time
        if startup_age < self.startup_grace_period:
            self.logger.debug(f"💊 HEALTH_INTERNAL: In startup grace period ({startup_age:.1f}s / {self.startup_grace_period}s)")
            return True  # Always healthy during startup grace period

        health_info = {
            "is_running": self.is_running,
            "consecutive_failures": self.consecutive_failures,
            "max_consecutive_failures": self.max_consecutive_failures,
            "has_monitoring_task": hasattr(self, 'monitoring_task') and self.monitoring_task is not None,
            "task_done": None,
            "task_cancelled": None,
            "task_has_exception": None,
            "startup_age_seconds": startup_age
        }

        # Check task status if available
        if hasattr(self, 'monitoring_task') and self.monitoring_task:
            task = self.monitoring_task
            health_info["task_done"] = task.done()
            health_info["task_cancelled"] = task.cancelled()

            if task.done() and not task.cancelled():
                try:
                    health_info["task_has_exception"] = task.exception() is not None
                except:
                    health_info["task_has_exception"] = "unknown"

        # Determine health status
        if not self.is_running:
            self.logger.warning(f"💊 HEALTH_INTERNAL: ❌ Service NOT RUNNING - consecutive_failures: {self.consecutive_failures}, task_status: {health_info}")
            return False

        # Allow for some failures, but not too many consecutive ones
        failure_ratio = self.consecutive_failures / self.max_consecutive_failures if self.max_consecutive_failures > 0 else 0
        if self.consecutive_failures >= self.max_consecutive_failures:
            # Check if failures are mostly UI loading states (not critical)
            recent_issues = list(self.last_check_results.values())
            ui_loading_count = sum(1 for issue in recent_issues if 'ui_loading' in issue.status.value)
            total_issues = len(recent_issues)

            if total_issues > 0 and ui_loading_count / total_issues > 0.8:  # More than 80% are UI loading issues
                self.logger.info(f"💊 HEALTH_INTERNAL: 🔄 UI loading states detected ({ui_loading_count}/{total_issues}), not marking as unhealthy")
                self.logger.info(f"💊 HEALTH_INTERNAL: This suggests APIs work but WebSocket/real-time updates may be failing")
                return True  # Don't restart for UI loading issues

            self.logger.error(f"💊 HEALTH_INTERNAL: ❌ TOO MANY FAILURES - {self.consecutive_failures}/{self.max_consecutive_failures} consecutive failures")
            self.logger.error(f"💊 HEALTH_INTERNAL: Failure context - port: {self.dashboard_port}, base_url: {self.base_url}")
            self.logger.error(f"💊 HEALTH_INTERNAL: Full health info - {health_info}")
            return False
        elif failure_ratio > 0.7:  # Log warning when approaching failure threshold
            self.logger.warning(f"💊 HEALTH_INTERNAL: ⚠️  Approaching failure threshold - {self.consecutive_failures}/{self.max_consecutive_failures} failures ({failure_ratio:.1%})")

        # Check if task is dead but is_running is still True (shouldn't happen but let's be safe)
        if hasattr(self, 'monitoring_task') and self.monitoring_task:
            task = self.monitoring_task
            if task.done() and not task.cancelled():
                try:
                    exception = task.exception()
                    if exception:
                        self.logger.error(f"💊 HEALTH_INTERNAL: Monitoring task has exception but is_running=True - {health_info}")
                        self.logger.error(f"💊 HEALTH_INTERNAL: Task exception: {exception}")
                        return False
                except:
                    pass  # Ignore exception checking errors

        # Log periodic health status for monitoring
        if hasattr(self, '_last_health_log_time'):
            if time.time() - self._last_health_log_time > 60:  # Log every minute when healthy
                self.logger.info(f"💊 HEALTH_INTERNAL: ✅ Service healthy - failures: {self.consecutive_failures}/{self.max_consecutive_failures}, port: {self.dashboard_port}")
                self._last_health_log_time = time.time()
        else:
            self._last_health_log_time = time.time()
            self.logger.info(f"💊 HEALTH_INTERNAL: ✅ Service healthy - failures: {self.consecutive_failures}/{self.max_consecutive_failures}, port: {self.dashboard_port}")

        self.logger.debug(f"💊 HEALTH_INTERNAL: Detailed health info - {health_info}")
        return True

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers"""
        status = {}
        for endpoint_path, circuit_breaker in self._circuit_breakers.items():
            status[endpoint_path] = circuit_breaker.get_state_info()
        return status
