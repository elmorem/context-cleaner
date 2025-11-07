"""
Scheduled Services for Context Rot Meter.

This module provides background services including automated data cleanup,
health monitoring, and maintenance tasks.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

from .config import get_config, ContextRotConfig
from .data_retention import DataRetentionManager, get_retention_manager
from .health_monitor import get_health_monitor, ContextRotHealthMonitor

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""

    name: str
    interval_seconds: int
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    task_function: Callable
    enabled: bool = True
    max_execution_time_seconds: int = 300  # 5 minutes default
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.next_run is None:
            self.next_run = datetime.now() + timedelta(seconds=self.interval_seconds)

    def should_run(self) -> bool:
        """Check if task should run now."""
        return self.enabled and self.next_run and datetime.now() >= self.next_run

    def update_next_run(self):
        """Update next run time."""
        self.last_run = datetime.now()
        self.next_run = self.last_run + timedelta(seconds=self.interval_seconds)
        self.retry_count = 0

    def schedule_retry(self, delay_seconds: int = 300):
        """Schedule task retry after failure."""
        self.retry_count += 1
        self.next_run = datetime.now() + timedelta(seconds=delay_seconds)


class ContextRotScheduler:
    """Main scheduler for Context Rot background services."""

    def __init__(self, config: Optional[ContextRotConfig] = None):
        self.config = config or get_config()
        self.health_monitor = get_health_monitor()
        self.retention_manager: Optional[DataRetentionManager] = None

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._tasks: Dict[str, ScheduledTask] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)

        # Initialize scheduled tasks
        self._initialize_tasks()

    def _initialize_tasks(self):
        """Initialize all scheduled tasks."""
        # Data retention cleanup
        if self.config.retention.enable_automatic_cleanup:
            self._tasks["data_cleanup"] = ScheduledTask(
                name="data_cleanup",
                interval_seconds=self.config.retention.cleanup_interval_hours * 3600,
                task_function=self._run_data_cleanup,
                last_run=None,
                max_execution_time_seconds=1800,  # 30 minutes
            )

        # Health monitoring
        if self.config.monitoring.enable_health_monitoring:
            self._tasks["health_check"] = ScheduledTask(
                name="health_check",
                interval_seconds=self.config.monitoring.health_check_interval_seconds,
                task_function=self._run_health_check,
                last_run=None,
                max_execution_time_seconds=60,  # 1 minute
            )

        # Metrics cleanup (clean old metrics from memory)
        self._tasks["metrics_cleanup"] = ScheduledTask(
            name="metrics_cleanup",
            interval_seconds=3600,  # Every hour
            task_function=self._run_metrics_cleanup,
            last_run=None,
            max_execution_time_seconds=300,  # 5 minutes
        )

        # Alert cleanup (clean resolved alerts)
        self._tasks["alert_cleanup"] = ScheduledTask(
            name="alert_cleanup",
            interval_seconds=3600,  # Every hour
            task_function=self._run_alert_cleanup,
            last_run=None,
            max_execution_time_seconds=300,  # 5 minutes
        )

        # Configuration reload (check for config changes)
        self._tasks["config_reload"] = ScheduledTask(
            name="config_reload",
            interval_seconds=300,  # Every 5 minutes
            task_function=self._run_config_reload,
            last_run=None,
            max_execution_time_seconds=30,  # 30 seconds
        )

        # System maintenance (optimize database, clean logs, etc.)
        self._tasks["system_maintenance"] = ScheduledTask(
            name="system_maintenance",
            interval_seconds=86400,  # Daily
            task_function=self._run_system_maintenance,
            last_run=None,
            max_execution_time_seconds=3600,  # 1 hour
        )

    async def start(self):
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

        # Start health monitoring
        self.health_monitor.start_monitoring(
            self.config.monitoring.health_check_interval_seconds
        )

        logger.info("Context Rot Meter scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False

        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # Stop health monitoring
        self.health_monitor.stop_monitoring()

        # Shutdown executor
        self._executor.shutdown(wait=True)

        logger.info("Context Rot Meter scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Check and run due tasks
                await self._check_and_run_tasks()

                # Sleep for a short interval
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)  # Wait longer after error

    async def _check_and_run_tasks(self):
        """Check and run due scheduled tasks."""
        for task_name, task in self._tasks.items():
            if task.should_run():
                try:
                    await self._execute_task(task)
                except Exception as e:
                    logger.error(f"Failed to execute task {task_name}: {e}")

                    # Schedule retry if under retry limit
                    if task.retry_count < task.max_retries:
                        retry_delay = min(
                            300 * (task.retry_count + 1), 3600
                        )  # Exponential backoff, max 1 hour
                        task.schedule_retry(retry_delay)
                        logger.info(
                            f"Scheduled retry #{task.retry_count + 1} for task {task_name} in {retry_delay} seconds"
                        )
                    else:
                        # Max retries reached, schedule next regular run
                        task.update_next_run()
                        logger.error(
                            f"Task {task_name} failed after {task.max_retries} retries"
                        )

    async def _execute_task(self, task: ScheduledTask):
        """Execute a scheduled task with timeout."""
        start_time = time.time()

        logger.debug(f"Executing task: {task.name}")

        try:
            # Run task with timeout
            await asyncio.wait_for(
                task.task_function(), timeout=task.max_execution_time_seconds
            )

            # Update next run time on success
            task.update_next_run()

            execution_time = time.time() - start_time
            logger.info(
                f"Task {task.name} completed successfully in {execution_time:.2f}s"
            )

            # Record metrics
            component_monitor = self.health_monitor.get_component_monitor("scheduler")
            component_monitor.record_operation(
                f"task_{task.name}", execution_time * 1000, success=True
            )

        except asyncio.TimeoutError:
            logger.error(
                f"Task {task.name} timed out after {task.max_execution_time_seconds}s"
            )
            raise
        except Exception as e:
            logger.error(f"Task {task.name} failed: {e}")
            raise

    async def _run_data_cleanup(self):
        """Execute data retention cleanup."""
        logger.info("Starting scheduled data cleanup")

        # Initialize retention manager if not done
        if self.retention_manager is None:
            from ..clients.clickhouse_client import ClickHouseClient

            clickhouse_client = ClickHouseClient()
            self.retention_manager = get_retention_manager(
                clickhouse_client, self.config.retention.retention_policy
            )

        # Execute cleanup for all categories
        cleanup_results = await self.retention_manager.execute_retention_policy(
            category=None, dry_run=False  # All categories
        )

        # Log results
        total_deleted = sum(result.records_deleted for result in cleanup_results)
        total_storage_freed = sum(result.storage_freed_mb for result in cleanup_results)

        logger.info(
            f"Data cleanup completed: {total_deleted} records deleted, {total_storage_freed:.2f}MB freed"
        )

        # Record metrics
        self.health_monitor.metric_collector.set_gauge(
            "data_cleanup_records_deleted", total_deleted, {"cleanup_type": "scheduled"}
        )
        self.health_monitor.metric_collector.set_gauge(
            "data_cleanup_storage_freed_mb",
            total_storage_freed,
            {"cleanup_type": "scheduled"},
        )

    async def _run_health_check(self):
        """Execute health check."""
        logger.debug("Running scheduled health check")

        # Perform comprehensive health check
        await self.health_monitor.perform_health_checks()

        # Get health snapshot
        snapshot = self.health_monitor.get_health_snapshot()

        # Log any critical issues
        if snapshot.overall_status.value in ["critical", "error"]:
            logger.error(f"System health check failed: {snapshot.overall_status.value}")

            # Create alert for critical health issues
            for alert in snapshot.active_alerts:
                if alert.severity in ["critical", "error"]:
                    logger.critical(f"Critical alert: {alert.title} - {alert.message}")

    async def _run_metrics_cleanup(self):
        """Clean up old metrics from memory."""
        logger.debug("Running metrics cleanup")

        # Clean old metrics (keep last 24 hours by default)
        retention_hours = self.config.monitoring.metrics_retention_hours
        current_count = len(self.health_monitor.metric_collector.metrics_history)

        # Keep only recent metrics
        cutoff_time = datetime.now() - timedelta(hours=retention_hours)
        self.health_monitor.metric_collector.metrics_history = [
            metric
            for metric in self.health_monitor.metric_collector.metrics_history
            if metric.timestamp >= cutoff_time
        ]

        cleaned_count = current_count - len(
            self.health_monitor.metric_collector.metrics_history
        )

        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} old metrics from memory")

    async def _run_alert_cleanup(self):
        """Clean up resolved alerts."""
        logger.debug("Running alert cleanup")

        # Clean resolved alerts older than 24 hours
        cleaned_count = self.health_monitor.alert_manager.cleanup_resolved_alerts(
            max_age_hours=24
        )

        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} old resolved alerts")

    async def _run_config_reload(self):
        """Check for configuration changes and reload if needed."""
        logger.debug("Checking for configuration changes")

        try:
            from .config import get_config_manager

            config_manager = get_config_manager()

            # This would check file timestamps or other change indicators
            # For now, we'll just ensure config is loaded
            current_config = config_manager.get_config()

            # Could implement more sophisticated change detection here
            # such as file modification time checking, config hash comparison, etc.

        except Exception as e:
            logger.error(f"Configuration check failed: {e}")

    async def _run_system_maintenance(self):
        """Perform system maintenance tasks."""
        logger.info("Running system maintenance")

        try:
            # Database maintenance (if ClickHouse client available)
            if self.retention_manager and self.retention_manager.clickhouse_client:
                # Optimize tables (ClickHouse specific)
                try:
                    await self.retention_manager.clickhouse_client.execute_query(
                        "OPTIMIZE TABLE otel.context_rot_metrics FINAL"
                    )
                    await self.retention_manager.clickhouse_client.execute_query(
                        "OPTIMIZE TABLE otel.user_baselines FINAL"
                    )
                    logger.info("Database table optimization completed")
                except Exception as e:
                    logger.warning(f"Database optimization failed: {e}")

            # System health snapshot for archival
            health_snapshot = self.health_monitor.get_health_snapshot()
            logger.info(
                f"System health: {health_snapshot.overall_status.value}, {len(health_snapshot.active_alerts)} active alerts"
            )

            # Memory usage report
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()

            logger.info(
                f"Resource usage: {memory_mb:.1f}MB memory, {cpu_percent:.1f}% CPU"
            )

            # Record maintenance metrics
            self.health_monitor.metric_collector.set_gauge(
                "system_maintenance_memory_mb", memory_mb
            )
            self.health_monitor.metric_collector.set_gauge(
                "system_maintenance_cpu_percent", cpu_percent
            )

        except Exception as e:
            logger.error(f"System maintenance failed: {e}")

    def get_task_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all scheduled tasks."""
        status = {}

        for task_name, task in self._tasks.items():
            status[task_name] = {
                "enabled": task.enabled,
                "interval_seconds": task.interval_seconds,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
            }

        return status

    def enable_task(self, task_name: str) -> bool:
        """Enable a scheduled task."""
        if task_name in self._tasks:
            self._tasks[task_name].enabled = True
            logger.info(f"Task {task_name} enabled")
            return True
        return False

    def disable_task(self, task_name: str) -> bool:
        """Disable a scheduled task."""
        if task_name in self._tasks:
            self._tasks[task_name].enabled = False
            logger.info(f"Task {task_name} disabled")
            return True
        return False

    def run_task_now(self, task_name: str) -> bool:
        """Trigger immediate execution of a task."""
        if task_name in self._tasks:
            task = self._tasks[task_name]
            task.next_run = datetime.now()
            logger.info(f"Task {task_name} scheduled for immediate execution")
            return True
        return False


# Global scheduler instance
_scheduler: Optional[ContextRotScheduler] = None


def get_scheduler() -> ContextRotScheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ContextRotScheduler()
    return _scheduler


async def start_background_services(config: Optional[ContextRotConfig] = None):
    """Start all Context Rot Meter background services."""
    scheduler = get_scheduler()
    if config:
        scheduler.config = config

    await scheduler.start()
    logger.info("Context Rot Meter background services started")


async def stop_background_services():
    """Stop all Context Rot Meter background services."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
    logger.info("Context Rot Meter background services stopped")
