"""
Production Deployment Configuration and Management for Context Rot Meter.

This module provides production deployment utilities, health checks,
and deployment validation for the Context Rot Meter system.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import json
from pathlib import Path
import subprocess
import os
import socket
import sys

from .config import get_config, ContextRotConfig, Environment
from .health_monitor import get_health_monitor, HealthStatus
from .scheduler import get_scheduler
from .data_retention import get_retention_manager

logger = logging.getLogger(__name__)


@dataclass
class DeploymentCheck:
    """Represents a deployment validation check."""

    name: str
    description: str
    passed: bool
    details: Dict[str, Any]
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class DeploymentReport:
    """Complete deployment validation report."""

    environment: Environment
    timestamp: datetime
    overall_status: str  # 'passed', 'failed', 'warning'
    checks: List[DeploymentCheck]
    summary: Dict[str, Any]
    recommendations: List[str]


class ProductionValidator:
    """Validates production readiness of Context Rot Meter."""

    def __init__(self, config: Optional[ContextRotConfig] = None):
        self.config = config or get_config()
        self.health_monitor = get_health_monitor()

    async def validate_deployment(self) -> DeploymentReport:
        """Run complete deployment validation."""
        start_time = datetime.now()
        checks = []

        logger.info("Starting Context Rot Meter deployment validation")

        # Run all validation checks
        validation_checks = [
            self._check_configuration,
            self._check_database_connectivity,
            self._check_security_settings,
            self._check_performance_requirements,
            self._check_data_retention_setup,
            self._check_monitoring_setup,
            self._check_ml_components,
            self._check_resource_availability,
            self._check_network_connectivity,
            self._check_file_permissions,
            self._check_environment_variables,
            self._check_dependency_versions,
        ]

        for check_func in validation_checks:
            try:
                check_result = await check_func()
                checks.append(check_result)
            except Exception as e:
                error_check = DeploymentCheck(
                    name=check_func.__name__,
                    description=f"Check failed with exception",
                    passed=False,
                    details={"exception": str(e)},
                    error_message=str(e),
                )
                checks.append(error_check)

        # Analyze results
        passed_checks = [c for c in checks if c.passed]
        failed_checks = [c for c in checks if not c.passed]

        overall_status = "passed" if len(failed_checks) == 0 else "failed"
        if len(failed_checks) < len(checks) * 0.2:  # Less than 20% failed
            overall_status = "warning"

        # Generate recommendations
        recommendations = self._generate_recommendations(checks)

        summary = {
            "total_checks": len(checks),
            "passed_checks": len(passed_checks),
            "failed_checks": len(failed_checks),
            "validation_time_seconds": (datetime.now() - start_time).total_seconds(),
        }

        report = DeploymentReport(
            environment=self.config.environment,
            timestamp=start_time,
            overall_status=overall_status,
            checks=checks,
            summary=summary,
            recommendations=recommendations,
        )

        logger.info(
            f"Deployment validation completed: {overall_status} ({len(passed_checks)}/{len(checks)} checks passed)"
        )
        return report

    async def _check_configuration(self) -> DeploymentCheck:
        """Validate configuration setup."""
        start_time = time.perf_counter()

        try:
            details = {
                "environment": self.config.environment.value,
                "log_level": self.config.log_level.value,
                "debug_mode": self.config.enable_debug_mode,
                "retention_policy": self.config.retention.retention_policy.value,
                "feature_flags": self.config.feature_flags,
            }

            # Check critical configuration
            issues = []
            if self.config.is_production() and self.config.enable_debug_mode:
                issues.append("Debug mode enabled in production")

            if self.config.is_production() and self.config.log_level.value == "DEBUG":
                issues.append("Debug logging enabled in production")

            if not self.config.security.enable_pii_scrubbing:
                issues.append("PII scrubbing disabled")

            execution_time = (time.perf_counter() - start_time) * 1000

            return DeploymentCheck(
                name="configuration",
                description="Configuration validation",
                passed=len(issues) == 0,
                details=details,
                error_message="; ".join(issues) if issues else None,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            return DeploymentCheck(
                name="configuration",
                description="Configuration validation",
                passed=False,
                details={},
                error_message=str(e),
            )

    async def _check_database_connectivity(self) -> DeploymentCheck:
        """Check database connectivity and setup."""
        start_time = time.perf_counter()

        try:
            from ..clients.clickhouse_client import ClickHouseClient

            clickhouse_client = ClickHouseClient()

            # Test connection
            healthy = await clickhouse_client.health_check()

            details = {
                "clickhouse_healthy": healthy,
                "host": self.config.database.clickhouse_host,
                "port": self.config.database.clickhouse_port,
                "database": self.config.database.clickhouse_database,
            }

            # Check required tables exist
            if healthy:
                try:
                    # Check context rot metrics table
                    result = await clickhouse_client.execute_query(
                        "SELECT count() FROM otel.context_rot_metrics LIMIT 1"
                    )
                    details["context_rot_table_exists"] = True

                    # Check user baselines table
                    result = await clickhouse_client.execute_query(
                        "SELECT count() FROM otel.user_baselines LIMIT 1"
                    )
                    details["user_baselines_table_exists"] = True

                except Exception as e:
                    details["table_check_error"] = str(e)
                    healthy = False

            execution_time = (time.perf_counter() - start_time) * 1000

            return DeploymentCheck(
                name="database_connectivity",
                description="Database connectivity and schema validation",
                passed=healthy,
                details=details,
                error_message="Database not accessible" if not healthy else None,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            return DeploymentCheck(
                name="database_connectivity",
                description="Database connectivity check",
                passed=False,
                details={"error": str(e)},
                error_message=str(e),
            )

    async def _check_security_settings(self) -> DeploymentCheck:
        """Validate security configuration."""
        start_time = time.perf_counter()

        security_config = self.config.security

        details = {
            "pii_scrubbing_enabled": security_config.enable_pii_scrubbing,
            "data_anonymization_enabled": security_config.enable_data_anonymization,
            "content_filtering_enabled": security_config.enable_content_filtering,
            "dangerous_patterns_count": len(security_config.dangerous_content_patterns),
        }

        # Security validation
        issues = []
        if not security_config.enable_pii_scrubbing:
            issues.append("PII scrubbing disabled")

        if not security_config.enable_data_anonymization:
            issues.append("Data anonymization disabled")

        if self.config.is_production():
            if not security_config.enable_content_filtering:
                issues.append("Content filtering disabled in production")

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="security_settings",
            description="Security configuration validation",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_performance_requirements(self) -> DeploymentCheck:
        """Check performance requirements and limits."""
        start_time = time.perf_counter()

        perf_config = self.config.performance

        details = {
            "max_latency_ms": perf_config.max_analysis_latency_ms,
            "max_memory_mb": perf_config.max_memory_usage_mb,
            "max_concurrent": perf_config.max_concurrent_analyses,
            "circuit_breaker_threshold": perf_config.circuit_breaker_failure_threshold,
        }

        # Check current resource usage
        try:
            import psutil

            process = psutil.Process()
            current_memory = process.memory_info().rss / 1024 / 1024
            details["current_memory_mb"] = current_memory

            # Check if we're already near limits
            warnings = []
            if current_memory > perf_config.max_memory_usage_mb * 0.8:
                warnings.append(
                    f"Memory usage {current_memory:.1f}MB near limit {perf_config.max_memory_usage_mb}MB"
                )

        except ImportError:
            warnings = ["psutil not available for resource monitoring"]

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="performance_requirements",
            description="Performance configuration validation",
            passed=len(warnings) == 0,
            details=details,
            error_message="; ".join(warnings) if warnings else None,
            execution_time_ms=execution_time,
        )

    async def _check_data_retention_setup(self) -> DeploymentCheck:
        """Validate data retention configuration."""
        start_time = time.perf_counter()

        retention_config = self.config.retention

        details = {
            "retention_policy": retention_config.retention_policy.value,
            "automatic_cleanup_enabled": retention_config.enable_automatic_cleanup,
            "cleanup_interval_hours": retention_config.cleanup_interval_hours,
            "user_deletion_enabled": retention_config.enable_user_deletion_requests,
        }

        # Validation
        issues = []
        if retention_config.cleanup_interval_hours < 1:
            issues.append("Cleanup interval too frequent (<1 hour)")

        if (
            self.config.is_production()
            and not retention_config.enable_automatic_cleanup
        ):
            issues.append("Automatic cleanup disabled in production")

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="data_retention_setup",
            description="Data retention configuration validation",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_monitoring_setup(self) -> DeploymentCheck:
        """Validate monitoring configuration."""
        start_time = time.perf_counter()

        monitoring_config = self.config.monitoring

        details = {
            "health_monitoring_enabled": monitoring_config.enable_health_monitoring,
            "resource_monitoring_enabled": monitoring_config.enable_resource_monitoring,
            "prometheus_enabled": monitoring_config.enable_prometheus_metrics,
            "check_interval_seconds": monitoring_config.health_check_interval_seconds,
        }

        # Test health monitor
        try:
            health_snapshot = self.health_monitor.get_health_snapshot()
            details["health_monitor_working"] = True
            details["current_health_status"] = health_snapshot.overall_status.value
        except Exception as e:
            details["health_monitor_error"] = str(e)

        issues = []
        if not monitoring_config.enable_health_monitoring:
            issues.append("Health monitoring disabled")

        if monitoring_config.health_check_interval_seconds > 300:
            issues.append("Health check interval too long (>5 minutes)")

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="monitoring_setup",
            description="Monitoring configuration validation",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_ml_components(self) -> DeploymentCheck:
        """Validate ML components availability."""
        start_time = time.perf_counter()

        ml_config = self.config.ml

        details = {
            "ml_analysis_enabled": ml_config.enable_ml_analysis,
            "sentiment_threshold": ml_config.sentiment_confidence_threshold,
            "frustration_threshold": ml_config.frustration_confidence_threshold,
        }

        # Test ML components
        issues = []
        try:
            from .ml_analysis import SentimentPipeline, MLFrustrationDetector

            # Test sentiment pipeline
            pipeline = SentimentPipeline(
                confidence_threshold=ml_config.sentiment_confidence_threshold
            )
            test_result = await pipeline.analyze("This is a test message")
            details["sentiment_pipeline_working"] = True

            # Test frustration detector
            detector = MLFrustrationDetector(
                confidence_threshold=ml_config.frustration_confidence_threshold
            )
            frustration_result = await detector.analyze_user_sentiment(["Test message"])
            details["frustration_detector_working"] = True

        except Exception as e:
            issues.append(f"ML components not working: {str(e)}")
            details["ml_error"] = str(e)

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="ml_components",
            description="ML components validation",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_resource_availability(self) -> DeploymentCheck:
        """Check system resource availability."""
        start_time = time.perf_counter()

        details = {}
        issues = []

        try:
            import psutil

            # Memory check
            memory = psutil.virtual_memory()
            details["total_memory_gb"] = memory.total / (1024**3)
            details["available_memory_gb"] = memory.available / (1024**3)
            details["memory_percent_used"] = memory.percent

            if memory.available < 1024**3:  # Less than 1GB available
                issues.append("Low available memory (<1GB)")

            # Disk space check
            disk = psutil.disk_usage("/")
            details["total_disk_gb"] = disk.total / (1024**3)
            details["available_disk_gb"] = disk.free / (1024**3)
            details["disk_percent_used"] = (disk.used / disk.total) * 100

            if disk.free < 5 * 1024**3:  # Less than 5GB free
                issues.append("Low disk space (<5GB)")

            # CPU check
            cpu_count = psutil.cpu_count()
            details["cpu_count"] = cpu_count

            if cpu_count < 2:
                issues.append("Insufficient CPU cores (<2)")

        except ImportError:
            issues.append("psutil not available for resource monitoring")
        except Exception as e:
            issues.append(f"Resource check failed: {str(e)}")

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="resource_availability",
            description="System resource availability check",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_network_connectivity(self) -> DeploymentCheck:
        """Check network connectivity requirements."""
        start_time = time.perf_counter()

        details = {}
        issues = []

        # Check ClickHouse connectivity
        try:
            host = self.config.database.clickhouse_host
            port = self.config.database.clickhouse_port

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            details["clickhouse_reachable"] = result == 0
            if result != 0:
                issues.append(f"Cannot reach ClickHouse at {host}:{port}")

        except Exception as e:
            issues.append(f"Network check failed: {str(e)}")

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="network_connectivity",
            description="Network connectivity validation",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_file_permissions(self) -> DeploymentCheck:
        """Check file system permissions."""
        start_time = time.perf_counter()

        details = {}
        issues = []

        # Check if we can write to temp directory
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(delete=True) as tmp:
                tmp.write(b"test")
                details["temp_directory_writable"] = True
        except Exception as e:
            issues.append(f"Cannot write to temp directory: {str(e)}")

        # Check current directory permissions
        try:
            current_dir = Path.cwd()
            details["current_directory"] = str(current_dir)
            details["current_directory_writable"] = os.access(current_dir, os.W_OK)

            if not os.access(current_dir, os.W_OK):
                issues.append("Current directory not writable")

        except Exception as e:
            issues.append(f"Permission check failed: {str(e)}")

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="file_permissions",
            description="File system permissions check",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_environment_variables(self) -> DeploymentCheck:
        """Check required environment variables."""
        start_time = time.perf_counter()

        required_vars = [
            "CONTEXT_ROT_ENVIRONMENT",
            "CLICKHOUSE_HOST",
            "CLICKHOUSE_PORT",
        ]

        optional_vars = [
            "CONTEXT_ROT_LOG_LEVEL",
            "CONTEXT_ROT_DEBUG",
            "CLICKHOUSE_USERNAME",
            "CLICKHOUSE_PASSWORD",
        ]

        details = {"required_vars": {}, "optional_vars": {}}

        issues = []

        # Check required variables
        for var in required_vars:
            value = os.getenv(var)
            details["required_vars"][var] = value is not None
            if value is None:
                issues.append(f"Required environment variable {var} not set")

        # Check optional variables
        for var in optional_vars:
            value = os.getenv(var)
            details["optional_vars"][var] = value is not None

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="environment_variables",
            description="Environment variables validation",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    async def _check_dependency_versions(self) -> DeploymentCheck:
        """Check Python and dependency versions."""
        start_time = time.perf_counter()

        details = {
            "python_version": sys.version,
            "python_version_info": sys.version_info[:3],
        }

        issues = []

        # Check Python version
        if sys.version_info < (3, 8):
            issues.append(f"Python version {sys.version_info[:3]} too old, need 3.8+")

        # Check critical dependencies
        critical_deps = ["asyncio", "datetime", "logging", "json"]

        for dep in critical_deps:
            try:
                __import__(dep)
                details[f"{dep}_available"] = True
            except ImportError:
                issues.append(f"Critical dependency {dep} not available")
                details[f"{dep}_available"] = False

        # Check optional dependencies
        optional_deps = ["psutil", "socket"]

        for dep in optional_deps:
            try:
                __import__(dep)
                details[f"{dep}_available"] = True
            except ImportError:
                details[f"{dep}_available"] = False

        execution_time = (time.perf_counter() - start_time) * 1000

        return DeploymentCheck(
            name="dependency_versions",
            description="Python and dependency version check",
            passed=len(issues) == 0,
            details=details,
            error_message="; ".join(issues) if issues else None,
            execution_time_ms=execution_time,
        )

    def _generate_recommendations(self, checks: List[DeploymentCheck]) -> List[str]:
        """Generate deployment recommendations based on check results."""
        recommendations = []

        failed_checks = [c for c in checks if not c.passed]

        if failed_checks:
            recommendations.append(
                "Address all failed checks before production deployment"
            )

        # Specific recommendations based on check patterns
        for check in checks:
            if check.name == "configuration" and not check.passed:
                if "Debug mode" in (check.error_message or ""):
                    recommendations.append(
                        "Disable debug mode in production environment"
                    )
                if "PII scrubbing" in (check.error_message or ""):
                    recommendations.append(
                        "Enable PII scrubbing for privacy compliance"
                    )

            elif check.name == "database_connectivity" and not check.passed:
                recommendations.append(
                    "Verify ClickHouse database is running and accessible"
                )
                recommendations.append("Check network connectivity and firewall rules")

            elif check.name == "resource_availability" and not check.passed:
                if "memory" in (check.error_message or "").lower():
                    recommendations.append("Increase available system memory")
                if "disk" in (check.error_message or "").lower():
                    recommendations.append("Free up disk space")

            elif check.name == "ml_components" and not check.passed:
                recommendations.append("Install required ML dependencies")
                recommendations.append("Verify ML model files are accessible")

        # General recommendations
        if self.config.is_production():
            recommendations.extend(
                [
                    "Enable comprehensive monitoring and alerting",
                    "Set up automated backups for critical data",
                    "Configure log rotation and retention policies",
                    "Set up SSL/TLS for database connections",
                    "Implement proper authentication and authorization",
                ]
            )

        return recommendations

    def save_report(self, report: DeploymentReport, output_path: Path) -> None:
        """Save deployment report to file."""
        report_data = {
            "environment": report.environment.value,
            "timestamp": report.timestamp.isoformat(),
            "overall_status": report.overall_status,
            "summary": report.summary,
            "recommendations": report.recommendations,
            "checks": [
                {
                    "name": check.name,
                    "description": check.description,
                    "passed": check.passed,
                    "details": check.details,
                    "error_message": check.error_message,
                    "execution_time_ms": check.execution_time_ms,
                }
                for check in report.checks
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"Deployment report saved to {output_path}")


async def validate_production_deployment() -> DeploymentReport:
    """Run complete production deployment validation."""
    validator = ProductionValidator()
    return await validator.validate_deployment()


async def quick_health_check() -> Dict[str, Any]:
    """Run quick health check for deployment verification."""
    health_monitor = get_health_monitor()

    try:
        # Get health snapshot
        snapshot = health_monitor.get_health_snapshot()

        return {
            "status": (
                "healthy"
                if snapshot.overall_status == HealthStatus.HEALTHY
                else "unhealthy"
            ),
            "overall_health": snapshot.overall_status.value,
            "active_alerts": len(snapshot.active_alerts),
            "uptime_seconds": snapshot.uptime_seconds,
            "component_count": len(snapshot.component_statuses),
            "timestamp": snapshot.timestamp.isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
