"""
System Health Monitoring for Context Rot Meter.

This module provides comprehensive health monitoring and alerting
for the Context Rot Meter system, including performance metrics,
error tracking, and system availability monitoring.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import json
import psutil
import threading
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class MetricType(Enum):
    """Types of system metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = None
    description: str = ""
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


@dataclass
class SystemHealthSnapshot:
    """Complete system health snapshot."""
    timestamp: datetime
    overall_status: HealthStatus
    component_statuses: Dict[str, HealthStatus]
    metrics: List[HealthMetric]
    active_alerts: List['Alert']
    performance_summary: Dict[str, Any]
    resource_usage: Dict[str, float]
    uptime_seconds: float
    version: str


@dataclass
class Alert:
    """System alert definition."""
    id: str
    severity: str  # info, warning, error, critical
    component: str
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MetricCollector:
    """Collects and aggregates system metrics."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.current_metrics = {}
        self._lock = threading.Lock()
        self._start_time = time.time()
    
    def record_metric(self, metric: HealthMetric) -> None:
        """Record a new metric."""
        with self._lock:
            self.metrics_history.append(metric)
            key = f"{metric.name}:{json.dumps(metric.labels, sort_keys=True)}"
            self.current_metrics[key] = metric
    
    def increment_counter(self, name: str, labels: Dict[str, str] = None, amount: int = 1) -> None:
        """Increment a counter metric."""
        metric = HealthMetric(
            name=name,
            value=amount,
            metric_type=MetricType.COUNTER,
            timestamp=datetime.now(),
            labels=labels or {}
        )
        
        # If counter exists, add to it
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        if key in self.current_metrics:
            existing = self.current_metrics[key]
            metric.value += existing.value
        
        self.record_metric(metric)
    
    def set_gauge(self, name: str, value: Union[int, float], labels: Dict[str, str] = None) -> None:
        """Set a gauge metric value."""
        metric = HealthMetric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            timestamp=datetime.now(),
            labels=labels or {}
        )
        self.record_metric(metric)
    
    def record_timer(self, name: str, duration_ms: float, labels: Dict[str, str] = None) -> None:
        """Record a timing metric."""
        metric = HealthMetric(
            name=name,
            value=duration_ms,
            metric_type=MetricType.TIMER,
            timestamp=datetime.now(),
            labels=labels or {},
            description=f"Duration: {duration_ms:.2f}ms"
        )
        self.record_metric(metric)
    
    def get_metric_summary(self, name: str, time_window_minutes: int = 5) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        relevant_metrics = [
            m for m in self.metrics_history 
            if m.name == name and m.timestamp >= cutoff_time
        ]
        
        if not relevant_metrics:
            return {"count": 0, "latest": None}
        
        values = [m.value for m in relevant_metrics]
        
        return {
            "count": len(values),
            "latest": relevant_metrics[-1].value,
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "total": sum(values) if relevant_metrics[0].metric_type == MetricType.COUNTER else None
        }
    
    def get_recent_metrics(self, minutes: int = 5) -> List[HealthMetric]:
        """Get metrics from the last N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_uptime_seconds(self) -> float:
        """Get system uptime in seconds."""
        return time.time() - self._start_time


class ComponentHealthMonitor:
    """Monitors health of individual system components."""
    
    def __init__(self, component_name: str, metric_collector: MetricCollector):
        self.component_name = component_name
        self.metric_collector = metric_collector
        self.last_heartbeat = datetime.now()
        self.error_count = 0
        self.warning_count = 0
        self.current_status = HealthStatus.HEALTHY
        
    def heartbeat(self) -> None:
        """Record component heartbeat."""
        self.last_heartbeat = datetime.now()
        self.metric_collector.increment_counter(
            "component_heartbeat",
            {"component": self.component_name}
        )
    
    def record_error(self, error_message: str = "") -> None:
        """Record component error."""
        self.error_count += 1
        self.metric_collector.increment_counter(
            "component_errors",
            {"component": self.component_name}
        )
        
        logger.error(f"{self.component_name} error: {error_message}")
        self._update_status()
    
    def record_warning(self, warning_message: str = "") -> None:
        """Record component warning."""
        self.warning_count += 1
        self.metric_collector.increment_counter(
            "component_warnings",
            {"component": self.component_name}
        )
        
        logger.warning(f"{self.component_name} warning: {warning_message}")
        self._update_status()
    
    def record_operation(self, operation_name: str, duration_ms: float, success: bool = True) -> None:
        """Record component operation metrics."""
        labels = {
            "component": self.component_name,
            "operation": operation_name,
            "status": "success" if success else "failure"
        }
        
        self.metric_collector.record_timer(f"component_operation_duration", duration_ms, labels)
        self.metric_collector.increment_counter("component_operations", labels)
        
        if not success:
            self.record_error(f"Operation {operation_name} failed")
    
    def get_health_status(self) -> HealthStatus:
        """Get current component health status."""
        # Check if component is responsive (heartbeat within last 2 minutes)
        if datetime.now() - self.last_heartbeat > timedelta(minutes=2):
            return HealthStatus.CRITICAL
        
        # Check error rate in last 5 minutes
        recent_errors = self.metric_collector.get_metric_summary(
            "component_errors", time_window_minutes=5
        )
        
        if recent_errors["count"] > 10:
            return HealthStatus.ERROR
        elif recent_errors["count"] > 5:
            return HealthStatus.WARNING
        elif recent_errors["count"] > 2:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    def _update_status(self) -> None:
        """Update component status based on recent metrics."""
        self.current_status = self.get_health_status()


class AlertManager:
    """Manages system alerts and notifications."""
    
    def __init__(self, metric_collector: MetricCollector):
        self.metric_collector = metric_collector
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self._alert_counter = 0
    
    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add alert handler function."""
        self.alert_handlers.append(handler)
    
    def create_alert(self, severity: str, component: str, title: str, message: str, 
                    metadata: Dict[str, Any] = None) -> Alert:
        """Create new alert."""
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            severity=severity,
            component=component,
            title=title,
            message=message,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.active_alerts[alert_id] = alert
        self._notify_handlers(alert)
        
        # Record alert metric
        self.metric_collector.increment_counter(
            "alerts_created",
            {"severity": severity, "component": component}
        )
        
        logger.warning(f"Alert created: [{severity}] {component}: {title}")
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_timestamp = datetime.now()
        
        self.metric_collector.increment_counter(
            "alerts_resolved",
            {"severity": alert.severity, "component": alert.component}
        )
        
        logger.info(f"Alert resolved: {alert.title}")
        return True
    
    def get_active_alerts(self, component: str = None, severity: str = None) -> List[Alert]:
        """Get active alerts with optional filtering."""
        alerts = [a for a in self.active_alerts.values() if not a.resolved]
        
        if component:
            alerts = [a for a in alerts if a.component == component]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def cleanup_resolved_alerts(self, max_age_hours: int = 24) -> int:
        """Clean up old resolved alerts."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        to_remove = [
            alert_id for alert_id, alert in self.active_alerts.items()
            if alert.resolved and alert.resolved_timestamp and alert.resolved_timestamp < cutoff_time
        ]
        
        for alert_id in to_remove:
            del self.active_alerts[alert_id]
        
        return len(to_remove)
    
    def _notify_handlers(self, alert: Alert) -> None:
        """Notify all alert handlers."""
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")


class ContextRotHealthMonitor:
    """Main health monitor for Context Rot Meter system."""
    
    def __init__(self, enable_resource_monitoring: bool = True):
        self.metric_collector = MetricCollector(max_history=10000)
        self.alert_manager = AlertManager(self.metric_collector)
        self.component_monitors: Dict[str, ComponentHealthMonitor] = {}
        self.enable_resource_monitoring = enable_resource_monitoring
        
        # Performance thresholds
        self.performance_thresholds = {
            "analysis_latency_ms": 100,  # Max real-time analysis latency
            "memory_usage_mb": 256,     # Max memory usage
            "error_rate_percent": 5,    # Max error rate
            "cpu_usage_percent": 80     # Max CPU usage
        }
        
        # Health check interval
        self._monitoring_active = False
        self._monitoring_task = None
        
        # Initialize core component monitors
        self._initialize_component_monitors()
        
        # Setup default alert handlers
        self._setup_default_alert_handlers()
    
    def _initialize_component_monitors(self) -> None:
        """Initialize monitors for core components."""
        components = [
            "context_rot_analyzer",
            "ml_frustration_detector", 
            "adaptive_thresholds",
            "security_analyzer",
            "context_rot_widget",
            "clickhouse_client",
            "error_recovery_manager"
        ]
        
        for component in components:
            self.component_monitors[component] = ComponentHealthMonitor(
                component, self.metric_collector
            )
    
    def get_component_monitor(self, component_name: str) -> ComponentHealthMonitor:
        """Get or create component monitor."""
        if component_name not in self.component_monitors:
            self.component_monitors[component_name] = ComponentHealthMonitor(
                component_name, self.metric_collector
            )
        
        return self.component_monitors[component_name]
    
    def start_monitoring(self, check_interval_seconds: int = 30) -> None:
        """Start background health monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(check_interval_seconds)
        )
        
        logger.info("Health monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._monitoring_active = False
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
        
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self, interval_seconds: int) -> None:
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                await self.perform_health_checks()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def perform_health_checks(self) -> None:
        """Perform comprehensive health checks."""
        # Check resource usage
        if self.enable_resource_monitoring:
            await self._check_resource_usage()
        
        # Check component health
        await self._check_component_health()
        
        # Check performance metrics
        await self._check_performance_metrics()
        
        # Cleanup old alerts
        self.alert_manager.cleanup_resolved_alerts()
    
    async def _check_resource_usage(self) -> None:
        """Check system resource usage."""
        try:
            # Memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            self.metric_collector.set_gauge("memory_usage_mb", memory_mb)
            
            if memory_mb > self.performance_thresholds["memory_usage_mb"]:
                self.alert_manager.create_alert(
                    "warning", "system", "High Memory Usage",
                    f"Memory usage {memory_mb:.1f}MB exceeds threshold {self.performance_thresholds['memory_usage_mb']}MB",
                    {"memory_mb": memory_mb}
                )
            
            # CPU usage
            cpu_percent = process.cpu_percent()
            self.metric_collector.set_gauge("cpu_usage_percent", cpu_percent)
            
            if cpu_percent > self.performance_thresholds["cpu_usage_percent"]:
                self.alert_manager.create_alert(
                    "warning", "system", "High CPU Usage",
                    f"CPU usage {cpu_percent:.1f}% exceeds threshold {self.performance_thresholds['cpu_usage_percent']}%",
                    {"cpu_percent": cpu_percent}
                )
        
        except Exception as e:
            logger.error(f"Resource monitoring error: {e}")
    
    async def _check_component_health(self) -> None:
        """Check health of all components."""
        for name, monitor in self.component_monitors.items():
            status = monitor.get_health_status()
            
            if status in [HealthStatus.ERROR, HealthStatus.CRITICAL]:
                self.alert_manager.create_alert(
                    "error" if status == HealthStatus.ERROR else "critical",
                    name,
                    f"Component {name} Unhealthy",
                    f"Component {name} status: {status.value}",
                    {"component_status": status.value}
                )
    
    async def _check_performance_metrics(self) -> None:
        """Check performance metrics against thresholds."""
        # Check analysis latency
        latency_summary = self.metric_collector.get_metric_summary(
            "component_operation_duration", time_window_minutes=5
        )
        
        if latency_summary["count"] > 0:
            avg_latency = latency_summary["avg"]
            max_latency = latency_summary["max"]
            
            if avg_latency > self.performance_thresholds["analysis_latency_ms"]:
                self.alert_manager.create_alert(
                    "warning", "performance", "High Analysis Latency",
                    f"Average analysis latency {avg_latency:.1f}ms exceeds threshold",
                    {"avg_latency_ms": avg_latency, "max_latency_ms": max_latency}
                )
    
    def get_health_snapshot(self) -> SystemHealthSnapshot:
        """Get complete system health snapshot."""
        # Determine overall status
        component_statuses = {
            name: monitor.get_health_status()
            for name, monitor in self.component_monitors.items()
        }
        
        overall_status = self._calculate_overall_status(component_statuses)
        
        # Get recent metrics
        recent_metrics = self.metric_collector.get_recent_metrics(minutes=5)
        
        # Get active alerts
        active_alerts = self.alert_manager.get_active_alerts()
        
        # Performance summary
        performance_summary = {
            "analysis_latency": self.metric_collector.get_metric_summary("component_operation_duration"),
            "error_rate": self.metric_collector.get_metric_summary("component_errors"),
            "operations_per_minute": self.metric_collector.get_metric_summary("component_operations")
        }
        
        # Resource usage summary
        resource_usage = {}
        for metric in recent_metrics:
            if metric.name in ["memory_usage_mb", "cpu_usage_percent"]:
                resource_usage[metric.name] = metric.value
        
        return SystemHealthSnapshot(
            timestamp=datetime.now(),
            overall_status=overall_status,
            component_statuses=component_statuses,
            metrics=recent_metrics,
            active_alerts=active_alerts,
            performance_summary=performance_summary,
            resource_usage=resource_usage,
            uptime_seconds=self.metric_collector.get_uptime_seconds(),
            version="1.0.0"
        )
    
    def _calculate_overall_status(self, component_statuses: Dict[str, HealthStatus]) -> HealthStatus:
        """Calculate overall system status from component statuses."""
        if not component_statuses:
            return HealthStatus.ERROR
        
        statuses = list(component_statuses.values())
        
        if any(s == HealthStatus.CRITICAL for s in statuses):
            return HealthStatus.CRITICAL
        elif any(s == HealthStatus.ERROR for s in statuses):
            return HealthStatus.ERROR
        elif any(s == HealthStatus.WARNING for s in statuses):
            return HealthStatus.WARNING
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _setup_default_alert_handlers(self) -> None:
        """Setup default alert handlers."""
        def log_alert_handler(alert: Alert) -> None:
            """Log alerts to standard logging."""
            level = {
                "info": logging.INFO,
                "warning": logging.WARNING, 
                "error": logging.ERROR,
                "critical": logging.CRITICAL
            }.get(alert.severity, logging.INFO)
            
            logger.log(level, f"ALERT [{alert.severity.upper()}] {alert.component}: {alert.title} - {alert.message}")
        
        self.alert_manager.add_alert_handler(log_alert_handler)
    
    def export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric in self.metric_collector.get_recent_metrics(minutes=60):
            labels = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
            labels_str = f"{{{labels}}}" if labels else ""
            
            lines.append(f'# HELP {metric.name} {metric.description}')
            lines.append(f'# TYPE {metric.name} {metric.metric_type.value}')
            lines.append(f'{metric.name}{labels_str} {metric.value} {int(metric.timestamp.timestamp() * 1000)}')
        
        return "\n".join(lines)


# Global health monitor instance
_health_monitor: Optional[ContextRotHealthMonitor] = None

def get_health_monitor() -> ContextRotHealthMonitor:
    """Get global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = ContextRotHealthMonitor()
    return _health_monitor