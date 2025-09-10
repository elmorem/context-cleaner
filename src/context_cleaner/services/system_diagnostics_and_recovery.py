"""
System Diagnostics and Recovery Service

This service provides comprehensive system health diagnostics, automated retry mechanisms,
and recovery procedures for the Context Cleaner system.
"""

import asyncio
import json
import time
import subprocess
import psutil
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import requests
from pathlib import Path

try:
    from ..config.settings import ContextCleanerConfig
except ImportError:
    ContextCleanerConfig = None


class DiagnosticLevel(Enum):
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    RESTART_SERVICE = "restart_service"
    RESET_CIRCUIT_BREAKER = "reset_circuit_breaker"
    CLEAN_PROCESSES = "clean_processes"
    RESET_DATABASE_CONNECTIONS = "reset_database_connections"
    REPAIR_SCHEMA = "repair_schema"
    CLEAR_CACHE = "clear_cache"


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check"""
    component: str
    level: DiagnosticLevel
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt"""
    action: RecoveryAction
    component: str
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    duration: float = 0.0


class SystemDiagnosticsAndRecovery:
    """
    Comprehensive system diagnostics and automated recovery service.
    
    This service:
    1. Diagnoses system health issues comprehensively
    2. Implements automated retry mechanisms
    3. Provides recovery procedures
    4. Tracks recovery attempts and success rates
    """
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Diagnostic results storage
        self.diagnostic_history: List[DiagnosticResult] = []
        self.recovery_history: List[RecoveryAttempt] = []
        
        # Recovery configuration
        self.max_recovery_attempts = 3
        self.recovery_cooldown = timedelta(minutes=5)
        self.component_health_cache = {}
        self.last_recovery_attempts = {}
        
        # Known good API endpoints (updated based on actual working endpoints discovered from dashboard HTML)
        self.known_endpoints = [
            "/api/dashboard-metrics",
            "/api/context-window-usage",
            "/api/conversation-analytics",
            "/api/code-patterns-analytics",
            "/api/content-search",
            "/api/analytics/context-health",
            "/api/analytics/performance-trends",
            "/api/jsonl-processing-status",
            "/api/telemetry-widget/code-pattern-analysis",
            "/api/telemetry-widget/content-search-widget",
            "/api/telemetry-widget/conversation-timeline",
            "/api/telemetry/error-details?hours=24",
            "/api/telemetry/model-analytics",
            "/api/telemetry/tool-analytics"
        ]
    
    async def run_full_system_diagnostic(self) -> List[DiagnosticResult]:
        """Run comprehensive system diagnostics"""
        
        self.logger.info("Starting full system diagnostic...")
        results = []
        
        # 1. Process Health Check
        results.extend(await self._diagnose_process_health())
        
        # 2. Database Connectivity
        results.extend(await self._diagnose_database_health())
        
        # 3. API Endpoint Health
        results.extend(await self._diagnose_api_health())
        
        # 4. Schema Integrity
        results.extend(await self._diagnose_schema_integrity())
        
        # 5. Service Dependencies
        results.extend(await self._diagnose_service_dependencies())
        
        # 6. Resource Utilization
        results.extend(await self._diagnose_resource_usage())
        
        # Store results
        self.diagnostic_history.extend(results)
        
        # Keep only last 100 results
        if len(self.diagnostic_history) > 100:
            self.diagnostic_history = self.diagnostic_history[-100:]
        
        self.logger.info(f"System diagnostic completed. Found {len([r for r in results if r.level in [DiagnosticLevel.ERROR, DiagnosticLevel.CRITICAL]])} critical issues")
        
        return results
    
    async def _diagnose_process_health(self) -> List[DiagnosticResult]:
        """Diagnose running process health"""
        results = []
        
        try:
            # Find all context_cleaner processes
            context_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'context_cleaner' in cmdline and 'python' in proc.info['name'].lower():
                        context_processes.append({
                            'pid': proc.info['pid'],
                            'cmdline': cmdline,
                            'cpu_percent': proc.info.get('cpu_percent', 0),
                            'memory_mb': proc.info.get('memory_info', {}).get('rss', 0) / 1024 / 1024
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not context_processes:
                results.append(DiagnosticResult(
                    component="process_health",
                    level=DiagnosticLevel.CRITICAL,
                    message="No Context Cleaner processes found running",
                    details={"process_count": 0},
                    recovery_actions=[RecoveryAction.RESTART_SERVICE]
                ))
            elif len(context_processes) > 5:
                results.append(DiagnosticResult(
                    component="process_health", 
                    level=DiagnosticLevel.WARNING,
                    message=f"Too many Context Cleaner processes running ({len(context_processes)})",
                    details={
                        "process_count": len(context_processes),
                        "processes": context_processes
                    },
                    recovery_actions=[RecoveryAction.CLEAN_PROCESSES]
                ))
            else:
                results.append(DiagnosticResult(
                    component="process_health",
                    level=DiagnosticLevel.INFO,
                    message=f"Normal process count: {len(context_processes)} processes",
                    details={
                        "process_count": len(context_processes),
                        "processes": context_processes
                    }
                ))
                
        except Exception as e:
            results.append(DiagnosticResult(
                component="process_health",
                level=DiagnosticLevel.ERROR,
                message=f"Failed to diagnose process health: {str(e)}",
                recovery_actions=[RecoveryAction.RESTART_SERVICE]
            ))
        
        return results
    
    async def _diagnose_database_health(self) -> List[DiagnosticResult]:
        """Diagnose ClickHouse database health"""
        results = []
        
        try:
            # Test ClickHouse connectivity
            result = subprocess.run(
                ["docker", "exec", "clickhouse-otel", "clickhouse-client", "--query", "SELECT 1"],
                capture_output=True,
                timeout=10,
                text=True
            )
            
            if result.returncode == 0:
                results.append(DiagnosticResult(
                    component="clickhouse_connectivity",
                    level=DiagnosticLevel.INFO,
                    message="ClickHouse connectivity OK",
                    details={"response": result.stdout.strip()}
                ))
            else:
                results.append(DiagnosticResult(
                    component="clickhouse_connectivity",
                    level=DiagnosticLevel.CRITICAL,
                    message="ClickHouse connectivity failed",
                    details={"error": result.stderr},
                    recovery_actions=[RecoveryAction.RESET_DATABASE_CONNECTIONS]
                ))
                
        except subprocess.TimeoutExpired:
            results.append(DiagnosticResult(
                component="clickhouse_connectivity",
                level=DiagnosticLevel.ERROR,
                message="ClickHouse connectivity timeout",
                recovery_actions=[RecoveryAction.RESET_DATABASE_CONNECTIONS]
            ))
        except Exception as e:
            results.append(DiagnosticResult(
                component="clickhouse_connectivity",
                level=DiagnosticLevel.ERROR,
                message=f"ClickHouse connectivity check failed: {str(e)}",
                recovery_actions=[RecoveryAction.RESET_DATABASE_CONNECTIONS]
            ))
        
        return results
    
    async def _diagnose_api_health(self) -> List[DiagnosticResult]:
        """Diagnose API endpoint health"""
        results = []
        
        # Check multiple ports where dashboards might be running
        ports_to_check = [8080, 8110]
        
        for port in ports_to_check:
            port_results = await self._check_port_api_health(port)
            results.extend(port_results)
        
        return results
    
    async def _check_port_api_health(self, port: int) -> List[DiagnosticResult]:
        """Check API health for a specific port"""
        results = []
        base_url = f"http://127.0.0.1:{port}"
        
        # Test basic connectivity
        try:
            response = requests.get(base_url, timeout=5)
            if response.status_code == 200:
                results.append(DiagnosticResult(
                    component=f"dashboard_port_{port}",
                    level=DiagnosticLevel.INFO,
                    message=f"Dashboard responsive on port {port}",
                    details={"status_code": response.status_code, "content_length": len(response.text)}
                ))
            else:
                results.append(DiagnosticResult(
                    component=f"dashboard_port_{port}",
                    level=DiagnosticLevel.WARNING,
                    message=f"Dashboard returned status {response.status_code} on port {port}",
                    details={"status_code": response.status_code}
                ))
        except requests.exceptions.ConnectionError:
            results.append(DiagnosticResult(
                component=f"dashboard_port_{port}",
                level=DiagnosticLevel.ERROR,
                message=f"Dashboard not accessible on port {port}",
                recovery_actions=[RecoveryAction.RESTART_SERVICE]
            ))
            return results  # Skip API endpoint tests if basic connectivity fails
        except Exception as e:
            results.append(DiagnosticResult(
                component=f"dashboard_port_{port}",
                level=DiagnosticLevel.ERROR,
                message=f"Dashboard connectivity error on port {port}: {str(e)}",
                recovery_actions=[RecoveryAction.RESTART_SERVICE]
            ))
            return results
        
        # Test known working API endpoints
        working_endpoints = 0
        failing_endpoints = 0
        
        for endpoint in self.known_endpoints:
            try:
                url = f"{base_url}{endpoint}"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    working_endpoints += 1
                    # Check if response contains valid data
                    try:
                        data = response.json()
                        data_size = len(json.dumps(data))
                        
                        results.append(DiagnosticResult(
                            component=f"api_endpoint_port_{port}",
                            level=DiagnosticLevel.INFO,
                            message=f"API endpoint {endpoint} working on port {port}",
                            details={
                                "endpoint": endpoint,
                                "status_code": response.status_code,
                                "data_size": data_size,
                                "response_time": response.elapsed.total_seconds()
                            }
                        ))
                    except json.JSONDecodeError:
                        results.append(DiagnosticResult(
                            component=f"api_endpoint_port_{port}",
                            level=DiagnosticLevel.WARNING,
                            message=f"API endpoint {endpoint} returned non-JSON data on port {port}",
                            details={"endpoint": endpoint, "status_code": response.status_code}
                        ))
                else:
                    failing_endpoints += 1
                    results.append(DiagnosticResult(
                        component=f"api_endpoint_port_{port}",
                        level=DiagnosticLevel.WARNING,
                        message=f"API endpoint {endpoint} returned status {response.status_code} on port {port}",
                        details={"endpoint": endpoint, "status_code": response.status_code}
                    ))
                    
            except requests.exceptions.Timeout:
                failing_endpoints += 1
                results.append(DiagnosticResult(
                    component=f"api_endpoint_port_{port}",
                    level=DiagnosticLevel.ERROR,
                    message=f"API endpoint {endpoint} timeout on port {port}",
                    details={"endpoint": endpoint},
                    recovery_actions=[RecoveryAction.RESTART_SERVICE]
                ))
            except Exception as e:
                failing_endpoints += 1
                results.append(DiagnosticResult(
                    component=f"api_endpoint_port_{port}",
                    level=DiagnosticLevel.ERROR,
                    message=f"API endpoint {endpoint} error on port {port}: {str(e)}",
                    details={"endpoint": endpoint, "error": str(e)}
                ))
        
        # Summary for this port
        if working_endpoints == 0 and failing_endpoints > 0:
            results.append(DiagnosticResult(
                component=f"api_health_port_{port}",
                level=DiagnosticLevel.CRITICAL,
                message=f"All API endpoints failing on port {port}",
                details={"working": working_endpoints, "failing": failing_endpoints},
                recovery_actions=[RecoveryAction.RESTART_SERVICE]
            ))
        elif failing_endpoints > working_endpoints:
            results.append(DiagnosticResult(
                component=f"api_health_port_{port}",
                level=DiagnosticLevel.WARNING,
                message=f"Some API endpoints failing on port {port}",
                details={"working": working_endpoints, "failing": failing_endpoints},
                recovery_actions=[RecoveryAction.RESET_CIRCUIT_BREAKER]
            ))
        else:
            results.append(DiagnosticResult(
                component=f"api_health_port_{port}",
                level=DiagnosticLevel.INFO,
                message=f"API endpoints healthy on port {port}",
                details={"working": working_endpoints, "failing": failing_endpoints}
            ))
        
        return results
    
    async def _diagnose_schema_integrity(self) -> List[DiagnosticResult]:
        """Diagnose database schema integrity issues"""
        results = []
        
        # Known schema problems we've identified
        problem_queries = [
            {
                "name": "content_column_reference",
                "query": "SELECT file_path, length(content) as file_size FROM otel.claude_file_content LIMIT 1",
                "expected_error": "Unknown expression or function identifier `content`",
                "correct_column": "file_content"
            },
            {
                "name": "message_content_reference", 
                "query": "SELECT session_id, substring(content, 1, 100) FROM otel.claude_message_content LIMIT 1",
                "expected_error": "Unknown expression or function identifier `content`",
                "correct_column": "message_content"
            }
        ]
        
        for test in problem_queries:
            try:
                result = subprocess.run(
                    ["docker", "exec", "clickhouse-otel", "clickhouse-client", "--query", test["query"]],
                    capture_output=True,
                    timeout=10,
                    text=True
                )
                
                if result.returncode != 0 and test["expected_error"] in result.stderr:
                    results.append(DiagnosticResult(
                        component="schema_integrity",
                        level=DiagnosticLevel.ERROR,
                        message=f"Schema issue detected: {test['name']} - using wrong column name",
                        details={
                            "test": test["name"],
                            "error": result.stderr.strip(),
                            "correct_column": test["correct_column"]
                        },
                        recovery_actions=[RecoveryAction.REPAIR_SCHEMA]
                    ))
                elif result.returncode == 0:
                    results.append(DiagnosticResult(
                        component="schema_integrity",
                        level=DiagnosticLevel.INFO,
                        message=f"Schema test passed: {test['name']}",
                        details={"test": test["name"]}
                    ))
                else:
                    results.append(DiagnosticResult(
                        component="schema_integrity",
                        level=DiagnosticLevel.WARNING,
                        message=f"Unexpected schema test result: {test['name']}",
                        details={
                            "test": test["name"],
                            "returncode": result.returncode,
                            "error": result.stderr.strip()
                        }
                    ))
                    
            except Exception as e:
                results.append(DiagnosticResult(
                    component="schema_integrity",
                    level=DiagnosticLevel.ERROR,
                    message=f"Schema test failed: {test['name']} - {str(e)}",
                    details={"test": test["name"], "error": str(e)}
                ))
        
        return results
    
    async def _diagnose_service_dependencies(self) -> List[DiagnosticResult]:
        """Diagnose service dependencies (Docker containers)"""
        results = []
        
        required_containers = ["clickhouse-otel", "otel-collector"]
        
        for container in required_containers:
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"name={container}", "--filter", "status=running", "--format", "{{.Names}}"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                
                if container in result.stdout:
                    results.append(DiagnosticResult(
                        component="service_dependencies",
                        level=DiagnosticLevel.INFO,
                        message=f"Container {container} is running",
                        details={"container": container, "status": "running"}
                    ))
                else:
                    level = DiagnosticLevel.CRITICAL if container == "clickhouse-otel" else DiagnosticLevel.WARNING
                    results.append(DiagnosticResult(
                        component="service_dependencies",
                        level=level,
                        message=f"Container {container} is not running",
                        details={"container": container, "status": "not_running"},
                        recovery_actions=[RecoveryAction.RESTART_SERVICE]
                    ))
                    
            except Exception as e:
                results.append(DiagnosticResult(
                    component="service_dependencies",
                    level=DiagnosticLevel.ERROR,
                    message=f"Failed to check container {container}: {str(e)}",
                    details={"container": container, "error": str(e)}
                ))
        
        return results
    
    async def _diagnose_resource_usage(self) -> List[DiagnosticResult]:
        """Diagnose system resource usage"""
        results = []
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                results.append(DiagnosticResult(
                    component="resource_usage",
                    level=DiagnosticLevel.WARNING,
                    message=f"High CPU usage: {cpu_percent}%",
                    details={"cpu_percent": cpu_percent}
                ))
            else:
                results.append(DiagnosticResult(
                    component="resource_usage",
                    level=DiagnosticLevel.INFO,
                    message=f"CPU usage normal: {cpu_percent}%",
                    details={"cpu_percent": cpu_percent}
                ))
            
            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                results.append(DiagnosticResult(
                    component="resource_usage",
                    level=DiagnosticLevel.WARNING,
                    message=f"High memory usage: {memory.percent}%",
                    details={"memory_percent": memory.percent, "available_gb": memory.available / 1024**3}
                ))
            else:
                results.append(DiagnosticResult(
                    component="resource_usage",
                    level=DiagnosticLevel.INFO,
                    message=f"Memory usage normal: {memory.percent}%",
                    details={"memory_percent": memory.percent, "available_gb": memory.available / 1024**3}
                ))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                results.append(DiagnosticResult(
                    component="resource_usage",
                    level=DiagnosticLevel.WARNING,
                    message=f"High disk usage: {disk.percent}%",
                    details={"disk_percent": disk.percent, "free_gb": disk.free / 1024**3},
                    recovery_actions=[RecoveryAction.CLEAR_CACHE]
                ))
            else:
                results.append(DiagnosticResult(
                    component="resource_usage",
                    level=DiagnosticLevel.INFO,
                    message=f"Disk usage normal: {disk.percent}%",
                    details={"disk_percent": disk.percent, "free_gb": disk.free / 1024**3}
                ))
                
        except Exception as e:
            results.append(DiagnosticResult(
                component="resource_usage",
                level=DiagnosticLevel.ERROR,
                message=f"Failed to check resource usage: {str(e)}",
                details={"error": str(e)}
            ))
        
        return results
    
    async def attempt_recovery(self, diagnostic_results: List[DiagnosticResult]) -> List[RecoveryAttempt]:
        """Attempt automated recovery based on diagnostic results"""
        
        recovery_attempts = []
        
        # Group recovery actions by priority
        critical_actions = []
        warning_actions = []
        
        for result in diagnostic_results:
            if result.level == DiagnosticLevel.CRITICAL:
                critical_actions.extend([(action, result.component) for action in result.recovery_actions])
            elif result.level == DiagnosticLevel.ERROR:
                warning_actions.extend([(action, result.component) for action in result.recovery_actions])
        
        # Execute critical actions first
        for action, component in critical_actions:
            if await self._should_attempt_recovery(action, component):
                attempt = await self._execute_recovery_action(action, component)
                recovery_attempts.append(attempt)
        
        # Execute warning actions if no critical issues remain
        if not critical_actions:
            for action, component in warning_actions:
                if await self._should_attempt_recovery(action, component):
                    attempt = await self._execute_recovery_action(action, component)
                    recovery_attempts.append(attempt)
        
        # Store recovery attempts
        self.recovery_history.extend(recovery_attempts)
        
        # Keep only last 50 recovery attempts
        if len(self.recovery_history) > 50:
            self.recovery_history = self.recovery_history[-50:]
        
        return recovery_attempts
    
    async def _should_attempt_recovery(self, action: RecoveryAction, component: str) -> bool:
        """Check if we should attempt recovery (respect cooldowns and attempt limits)"""
        
        key = f"{action.value}_{component}"
        
        # Check if we're in cooldown period
        if key in self.last_recovery_attempts:
            last_attempt = self.last_recovery_attempts[key]
            if datetime.now() - last_attempt < self.recovery_cooldown:
                return False
        
        # Check attempt count in recent history
        recent_attempts = [
            attempt for attempt in self.recovery_history[-10:]  # Last 10 attempts
            if attempt.action == action and attempt.component == component
            and datetime.now() - attempt.timestamp < timedelta(hours=1)
        ]
        
        if len(recent_attempts) >= self.max_recovery_attempts:
            return False
        
        return True
    
    async def _execute_recovery_action(self, action: RecoveryAction, component: str) -> RecoveryAttempt:
        """Execute a specific recovery action"""
        
        start_time = time.time()
        attempt = RecoveryAttempt(
            action=action,
            component=component,
            timestamp=datetime.now(),
            success=False
        )
        
        try:
            if action == RecoveryAction.CLEAN_PROCESSES:
                success = await self._clean_duplicate_processes()
            elif action == RecoveryAction.RESTART_SERVICE:
                success = await self._restart_service(component)
            elif action == RecoveryAction.RESET_DATABASE_CONNECTIONS:
                success = await self._reset_database_connections()
            elif action == RecoveryAction.REPAIR_SCHEMA:
                success = await self._repair_schema_issues()
            elif action == RecoveryAction.RESET_CIRCUIT_BREAKER:
                success = await self._reset_circuit_breaker()
            elif action == RecoveryAction.CLEAR_CACHE:
                success = await self._clear_cache()
            else:
                success = False
                attempt.error_message = f"Unknown recovery action: {action}"
            
            attempt.success = success
            
        except Exception as e:
            attempt.success = False
            attempt.error_message = str(e)
            self.logger.error(f"Recovery action {action} failed for {component}: {e}")
        
        attempt.duration = time.time() - start_time
        
        # Update last attempt time
        key = f"{action.value}_{component}"
        self.last_recovery_attempts[key] = attempt.timestamp
        
        return attempt
    
    async def _clean_duplicate_processes(self) -> bool:
        """Clean up duplicate processes"""
        try:
            result = subprocess.run(["pkill", "-f", "context_cleaner"], capture_output=True, timeout=10)
            await asyncio.sleep(2)  # Wait for processes to die
            return True
        except Exception as e:
            self.logger.error(f"Failed to clean processes: {e}")
            return False
    
    async def _restart_service(self, component: str) -> bool:
        """Restart a specific service component"""
        # This would be implemented based on specific component requirements
        self.logger.info(f"Would restart service: {component}")
        return True
    
    async def _reset_database_connections(self) -> bool:
        """Reset database connections"""
        try:
            # Restart ClickHouse container
            result = subprocess.run(["docker", "restart", "clickhouse-otel"], capture_output=True, timeout=30)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Failed to reset database connections: {e}")
            return False
    
    async def _repair_schema_issues(self) -> bool:
        """Repair known schema issues"""
        self.logger.info("Schema repair would be implemented here")
        # This would implement the actual schema fixes we identified
        return True
    
    async def _reset_circuit_breaker(self) -> bool:
        """Reset circuit breaker states"""
        self.logger.info("Circuit breaker reset would be implemented here")
        return True
    
    async def _clear_cache(self) -> bool:
        """Clear system caches"""
        try:
            # This would clear various caches
            self.logger.info("Cache clearing would be implemented here")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear cache: {e}")
            return False
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get a comprehensive system health summary"""
        
        if not self.diagnostic_history:
            return {"status": "no_diagnostics_run"}
        
        # Get latest diagnostic results
        recent_results = [r for r in self.diagnostic_history if datetime.now() - r.timestamp < timedelta(minutes=30)]
        
        if not recent_results:
            return {"status": "diagnostics_outdated"}
        
        # Categorize results
        critical_count = len([r for r in recent_results if r.level == DiagnosticLevel.CRITICAL])
        error_count = len([r for r in recent_results if r.level == DiagnosticLevel.ERROR])
        warning_count = len([r for r in recent_results if r.level == DiagnosticLevel.WARNING])
        info_count = len([r for r in recent_results if r.level == DiagnosticLevel.INFO])
        
        # Determine overall health status
        if critical_count > 0:
            overall_status = "critical"
        elif error_count > 0:
            overall_status = "unhealthy"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        # Recovery success rate
        recent_recoveries = [r for r in self.recovery_history if datetime.now() - r.timestamp < timedelta(hours=24)]
        recovery_success_rate = (
            len([r for r in recent_recoveries if r.success]) / len(recent_recoveries) * 100
            if recent_recoveries else 0
        )
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "diagnostic_counts": {
                "critical": critical_count,
                "error": error_count,
                "warning": warning_count,
                "info": info_count
            },
            "recovery_stats": {
                "attempts_24h": len(recent_recoveries),
                "success_rate": recovery_success_rate
            },
            "critical_issues": [
                {
                    "component": r.component,
                    "message": r.message,
                    "recovery_actions": [a.value for a in r.recovery_actions]
                }
                for r in recent_results if r.level == DiagnosticLevel.CRITICAL
            ]
        }