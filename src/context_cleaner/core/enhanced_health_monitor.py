import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import psutil
import socket

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealthCheck:
    service_name: str
    status: ServiceStatus
    last_check: datetime
    response_time_ms: float
    error_message: Optional[str] = None
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None


class EnhancedHealthMonitor:
    def __init__(self):
        self.health_cache = {}
        self.cache_ttl = timedelta(seconds=30)
        self.timeout_threshold = 5000  # 5 seconds

    async def check_service_health(self, service_name: str) -> ServiceHealthCheck:
        """Check health of a specific service with caching."""
        cache_key = f"health_{service_name}"

        if cache_key in self.health_cache:
            cached_result, timestamp = self.health_cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_result

        start_time = datetime.now()

        try:
            if service_name == "clickhouse":
                health = await self._check_clickhouse_health()
            elif service_name == "telemetry_service":
                health = await self._check_telemetry_health()
            elif service_name == "dashboard_metrics":
                health = await self._check_dashboard_metrics_health()
            elif service_name == "file_system":
                health = await self._check_file_system_health()
            else:
                health = ServiceHealthCheck(
                    service_name=service_name,
                    status=ServiceStatus.UNKNOWN,
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message=f"Unknown service: {service_name}",
                )

            # Cache result
            self.health_cache[cache_key] = (health, datetime.now())
            return health

        except Exception as e:
            error_health = ServiceHealthCheck(
                service_name=service_name,
                status=ServiceStatus.FAILING,
                last_check=datetime.now(),
                response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=str(e),
            )
            self.health_cache[cache_key] = (error_health, datetime.now())
            return error_health

    async def _check_clickhouse_health(self) -> ServiceHealthCheck:
        """Check ClickHouse database connectivity and performance."""
        start_time = datetime.now()

        try:
            # Import here to avoid circular dependencies
            from context_cleaner.database.clickhouse_client import ClickHouseClient

            client = ClickHouseClient()

            # Test basic connectivity
            result = await client.execute_query("SELECT 1")

            # Test table access
            await client.execute_query("SELECT COUNT(*) FROM system.tables LIMIT 1")

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            if response_time > self.timeout_threshold:
                status = ServiceStatus.DEGRADED
                message = f"ClickHouse responding slowly ({response_time:.0f}ms)"
            else:
                status = ServiceStatus.HEALTHY
                message = None

            return ServiceHealthCheck(
                service_name="clickhouse",
                status=status,
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=message,
                metadata={"query_result": result},
            )

        except ImportError:
            return ServiceHealthCheck(
                service_name="clickhouse",
                status=ServiceStatus.FAILING,
                last_check=datetime.now(),
                response_time_ms=0,
                error_message="ClickHouse client not available",
            )
        except Exception as e:
            return ServiceHealthCheck(
                service_name="clickhouse",
                status=ServiceStatus.FAILING,
                last_check=datetime.now(),
                response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=f"ClickHouse connection failed: {str(e)}",
            )

    async def _check_telemetry_health(self) -> ServiceHealthCheck:
        """Check telemetry service health."""
        start_time = datetime.now()

        try:
            # Check if telemetry collection is working
            from context_cleaner.services.telemetry_collector import TelemetryCollector

            collector = TelemetryCollector()

            # Test telemetry data collection
            test_data = await collector.collect_basic_metrics()

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            return ServiceHealthCheck(
                service_name="telemetry_service",
                status=ServiceStatus.HEALTHY if test_data else ServiceStatus.DEGRADED,
                last_check=datetime.now(),
                response_time_ms=response_time,
                metadata={"metrics_collected": len(test_data) if test_data else 0},
            )

        except Exception as e:
            return ServiceHealthCheck(
                service_name="telemetry_service",
                status=ServiceStatus.FAILING,
                last_check=datetime.now(),
                response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=f"Telemetry service failed: {str(e)}",
            )

    async def _check_dashboard_metrics_health(self) -> ServiceHealthCheck:
        """Check dashboard metrics dependencies."""
        start_time = datetime.now()

        try:
            # Check all dashboard dependencies
            clickhouse_health = await self.check_service_health("clickhouse")
            telemetry_health = await self.check_service_health("telemetry_service")

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            # Dashboard is healthy only if all dependencies are healthy
            if (
                clickhouse_health.status == ServiceStatus.HEALTHY
                and telemetry_health.status == ServiceStatus.HEALTHY
            ):
                status = ServiceStatus.HEALTHY
                message = None
            elif clickhouse_health.status in [
                ServiceStatus.HEALTHY,
                ServiceStatus.DEGRADED,
            ] and telemetry_health.status in [
                ServiceStatus.HEALTHY,
                ServiceStatus.DEGRADED,
            ]:
                status = ServiceStatus.DEGRADED
                message = "Some dashboard dependencies are degraded"
            else:
                status = ServiceStatus.FAILING
                message = "Critical dashboard dependencies are failing"

            return ServiceHealthCheck(
                service_name="dashboard_metrics",
                status=status,
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=message,
                dependencies=["clickhouse", "telemetry_service"],
                metadata={
                    "clickhouse_status": clickhouse_health.status.value,
                    "telemetry_status": telemetry_health.status.value,
                },
            )

        except Exception as e:
            return ServiceHealthCheck(
                service_name="dashboard_metrics",
                status=ServiceStatus.FAILING,
                last_check=datetime.now(),
                response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=f"Dashboard metrics health check failed: {str(e)}",
            )

    async def _check_file_system_health(self) -> ServiceHealthCheck:
        """Check file system health and disk space."""
        start_time = datetime.now()

        try:
            # Check disk usage
            disk_usage = psutil.disk_usage("/")
            free_space_gb = disk_usage.free / (1024**3)

            # Check if we have sufficient disk space (at least 1GB)
            if free_space_gb < 1:
                status = ServiceStatus.FAILING
                message = f"Low disk space: {free_space_gb:.1f}GB remaining"
            elif free_space_gb < 5:
                status = ServiceStatus.DEGRADED
                message = f"Limited disk space: {free_space_gb:.1f}GB remaining"
            else:
                status = ServiceStatus.HEALTHY
                message = None

            response_time = (datetime.now() - start_time).total_seconds() * 1000

            return ServiceHealthCheck(
                service_name="file_system",
                status=status,
                last_check=datetime.now(),
                response_time_ms=response_time,
                error_message=message,
                metadata={
                    "free_space_gb": free_space_gb,
                    "total_space_gb": disk_usage.total / (1024**3),
                    "used_space_gb": disk_usage.used / (1024**3),
                },
            )

        except Exception as e:
            return ServiceHealthCheck(
                service_name="file_system",
                status=ServiceStatus.FAILING,
                last_check=datetime.now(),
                response_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=f"File system check failed: {str(e)}",
            )

    async def get_overall_system_health(self) -> Dict[str, ServiceHealthCheck]:
        """Get health status for all critical services."""
        services = [
            "clickhouse",
            "telemetry_service",
            "dashboard_metrics",
            "file_system",
        ]

        # Run health checks in parallel
        health_checks = await asyncio.gather(
            *[self.check_service_health(service) for service in services],
            return_exceptions=True,
        )

        results = {}
        for i, service in enumerate(services):
            if isinstance(health_checks[i], Exception):
                results[service] = ServiceHealthCheck(
                    service_name=service,
                    status=ServiceStatus.FAILING,
                    last_check=datetime.now(),
                    response_time_ms=0,
                    error_message=f"Health check exception: {str(health_checks[i])}",
                )
            else:
                results[service] = health_checks[i]

        return results

    def clear_cache(self):
        """Clear the health check cache."""
        self.health_cache.clear()
