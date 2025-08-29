"""
Alert Management System
Provides intelligent alerting and notification capabilities for productivity 
and system monitoring with customizable rules and delivery methods.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
import hashlib

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCondition(Enum):
    """Types of alert conditions"""
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    TREND = "trend"
    CUSTOM = "custom"


class DeliveryMethod(Enum):
    """Alert delivery methods"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    SMS = "sms"
    DESKTOP = "desktop"
    IN_APP = "in_app"


@dataclass
class AlertRule:
    """Configuration for an alert rule"""
    rule_id: str
    name: str
    description: str
    condition_type: AlertCondition
    data_source: str
    metric_key: str
    condition_config: Dict[str, Any]
    severity: AlertSeverity
    enabled: bool = True
    
    # Delivery configuration
    delivery_methods: List[DeliveryMethod] = field(default_factory=list)
    delivery_config: Dict[str, Any] = field(default_factory=dict)
    
    # Timing and suppression
    evaluation_interval: int = 60  # seconds
    suppress_duration: int = 300   # seconds to suppress repeated alerts
    max_alerts_per_hour: int = 10
    
    # Conditions
    tags: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"


@dataclass
class Alert:
    """An active or historical alert"""
    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    metric_value: Any
    threshold_value: Any = None
    
    # Timing
    triggered_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Context
    data_source: str = ""
    metric_key: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Actions
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class AlertDelivery:
    """Record of alert delivery attempt"""
    delivery_id: str
    alert_id: str
    method: DeliveryMethod
    recipient: str
    status: str  # sent, failed, pending
    attempt_count: int = 1
    last_attempt: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


class AlertConditionEvaluator:
    """Evaluates alert conditions against data"""
    
    def __init__(self):
        self.evaluators = {
            AlertCondition.THRESHOLD: self.evaluate_threshold,
            AlertCondition.ANOMALY: self.evaluate_anomaly,
            AlertCondition.PATTERN: self.evaluate_pattern,
            AlertCondition.TREND: self.evaluate_trend,
            AlertCondition.CUSTOM: self.evaluate_custom
        }
    
    async def evaluate(self, rule: AlertRule, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]] = None) -> Optional[Alert]:
        """Evaluate a rule against current data"""
        evaluator = self.evaluators.get(rule.condition_type)
        if not evaluator:
            logger.error(f"No evaluator for condition type: {rule.condition_type}")
            return None
        
        return await evaluator(rule, current_data, historical_data or [])
    
    async def evaluate_threshold(self, rule: AlertRule, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """Evaluate threshold-based conditions"""
        metric_value = self._extract_metric_value(current_data, rule.metric_key)
        if metric_value is None:
            return None
        
        config = rule.condition_config
        operator = config.get('operator', 'gt')  # gt, lt, gte, lte, eq, ne
        threshold = config.get('threshold')
        
        if threshold is None:
            logger.error(f"Threshold not specified for rule {rule.rule_id}")
            return None
        
        triggered = False
        if operator == 'gt':
            triggered = metric_value > threshold
        elif operator == 'lt':
            triggered = metric_value < threshold
        elif operator == 'gte':
            triggered = metric_value >= threshold
        elif operator == 'lte':
            triggered = metric_value <= threshold
        elif operator == 'eq':
            triggered = metric_value == threshold
        elif operator == 'ne':
            triggered = metric_value != threshold
        
        if triggered:
            return Alert(
                alert_id=self._generate_alert_id(rule, metric_value),
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                title=f"{rule.name} Threshold Alert",
                message=f"{rule.metric_key} is {metric_value} (threshold: {operator} {threshold})",
                metric_value=metric_value,
                threshold_value=threshold,
                data_source=rule.data_source,
                metric_key=rule.metric_key,
                context=current_data
            )
        
        return None
    
    async def evaluate_anomaly(self, rule: AlertRule, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """Evaluate anomaly detection conditions"""
        if len(historical_data) < 10:  # Need enough historical data
            return None
        
        metric_value = self._extract_metric_value(current_data, rule.metric_key)
        if metric_value is None:
            return None
        
        # Extract historical values
        historical_values = []
        for data_point in historical_data:
            value = self._extract_metric_value(data_point, rule.metric_key)
            if value is not None:
                historical_values.append(value)
        
        if len(historical_values) < 5:
            return None
        
        # Calculate statistical measures
        mean = sum(historical_values) / len(historical_values)
        variance = sum((x - mean) ** 2 for x in historical_values) / len(historical_values)
        std_dev = variance ** 0.5
        
        config = rule.condition_config
        sensitivity = config.get('sensitivity', 2.0)  # Standard deviations
        
        # Check if current value is anomalous
        z_score = abs(metric_value - mean) / std_dev if std_dev > 0 else 0
        
        if z_score > sensitivity:
            return Alert(
                alert_id=self._generate_alert_id(rule, metric_value),
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                title=f"{rule.name} Anomaly Detected",
                message=f"{rule.metric_key} is {metric_value} (z-score: {z_score:.2f}, mean: {mean:.2f})",
                metric_value=metric_value,
                threshold_value=sensitivity,
                data_source=rule.data_source,
                metric_key=rule.metric_key,
                context={**current_data, 'z_score': z_score, 'mean': mean, 'std_dev': std_dev}
            )
        
        return None
    
    async def evaluate_pattern(self, rule: AlertRule, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """Evaluate pattern-based conditions"""
        config = rule.condition_config
        pattern_type = config.get('pattern_type', 'consecutive')
        window_size = config.get('window_size', 5)
        threshold = config.get('threshold')
        operator = config.get('operator', 'gt')
        
        if len(historical_data) < window_size:
            return None
        
        # Get recent values including current
        recent_values = []
        for data_point in historical_data[-window_size+1:] + [current_data]:
            value = self._extract_metric_value(data_point, rule.metric_key)
            if value is not None:
                recent_values.append(value)
        
        if len(recent_values) < window_size:
            return None
        
        triggered = False
        
        if pattern_type == 'consecutive':
            # All values in window meet condition
            if operator == 'gt':
                triggered = all(v > threshold for v in recent_values)
            elif operator == 'lt':
                triggered = all(v < threshold for v in recent_values)
        
        elif pattern_type == 'increasing':
            # Values are consistently increasing
            triggered = all(recent_values[i] < recent_values[i+1] for i in range(len(recent_values)-1))
        
        elif pattern_type == 'decreasing':
            # Values are consistently decreasing
            triggered = all(recent_values[i] > recent_values[i+1] for i in range(len(recent_values)-1))
        
        if triggered:
            return Alert(
                alert_id=self._generate_alert_id(rule, recent_values[-1]),
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                title=f"{rule.name} Pattern Alert",
                message=f"Pattern '{pattern_type}' detected in {rule.metric_key} over {window_size} periods",
                metric_value=recent_values[-1],
                threshold_value=threshold,
                data_source=rule.data_source,
                metric_key=rule.metric_key,
                context={**current_data, 'pattern_values': recent_values, 'pattern_type': pattern_type}
            )
        
        return None
    
    async def evaluate_trend(self, rule: AlertRule, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """Evaluate trend-based conditions"""
        config = rule.condition_config
        trend_window = config.get('trend_window', 10)
        trend_threshold = config.get('trend_threshold', 0.1)  # Minimum trend strength
        trend_direction = config.get('trend_direction', 'decreasing')  # increasing, decreasing
        
        if len(historical_data) < trend_window:
            return None
        
        # Get recent values
        recent_data = historical_data[-trend_window:] + [current_data]
        values = []
        timestamps = []
        
        for i, data_point in enumerate(recent_data):
            value = self._extract_metric_value(data_point, rule.metric_key)
            if value is not None:
                values.append(value)
                timestamps.append(i)  # Use index as time proxy
        
        if len(values) < trend_window:
            return None
        
        # Calculate linear regression slope
        n = len(values)
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(timestamps, values))
        sum_x2 = sum(x * x for x in timestamps)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Normalize slope by average value to get trend strength
        avg_value = sum_y / n
        trend_strength = abs(slope / avg_value) if avg_value != 0 else 0
        
        triggered = False
        if trend_direction == 'decreasing' and slope < -trend_threshold:
            triggered = trend_strength >= trend_threshold
        elif trend_direction == 'increasing' and slope > trend_threshold:
            triggered = trend_strength >= trend_threshold
        
        if triggered:
            return Alert(
                alert_id=self._generate_alert_id(rule, values[-1]),
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                title=f"{rule.name} Trend Alert",
                message=f"{trend_direction.title()} trend detected in {rule.metric_key} (strength: {trend_strength:.3f})",
                metric_value=values[-1],
                threshold_value=trend_threshold,
                data_source=rule.data_source,
                metric_key=rule.metric_key,
                context={
                    **current_data, 
                    'trend_slope': slope, 
                    'trend_strength': trend_strength,
                    'trend_values': values
                }
            )
        
        return None
    
    async def evaluate_custom(self, rule: AlertRule, current_data: Dict[str, Any], historical_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """Evaluate custom conditions using provided code"""
        config = rule.condition_config
        custom_code = config.get('code', '')
        
        if not custom_code:
            return None
        
        try:
            # Create safe execution environment
            context = {
                'current_data': current_data,
                'historical_data': historical_data,
                'metric_value': self._extract_metric_value(current_data, rule.metric_key),
                'len': len,
                'sum': sum,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round
            }
            
            # Execute custom condition code
            result = eval(custom_code, {"__builtins__": {}}, context)
            
            if result:
                return Alert(
                    alert_id=self._generate_alert_id(rule, context.get('metric_value')),
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    status=AlertStatus.ACTIVE,
                    title=f"{rule.name} Custom Alert",
                    message=f"Custom condition triggered for {rule.metric_key}",
                    metric_value=context.get('metric_value'),
                    data_source=rule.data_source,
                    metric_key=rule.metric_key,
                    context=current_data
                )
        
        except Exception as e:
            logger.error(f"Error evaluating custom condition for rule {rule.rule_id}: {e}")
        
        return None
    
    def _extract_metric_value(self, data: Dict[str, Any], metric_key: str) -> Any:
        """Extract metric value from data using dot notation"""
        keys = metric_key.split('.')
        value = data
        
        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    return None
            return value
        except (KeyError, IndexError, ValueError, TypeError):
            return None
    
    def _generate_alert_id(self, rule: AlertRule, metric_value: Any) -> str:
        """Generate unique alert ID"""
        timestamp = datetime.now().isoformat()
        content = f"{rule.rule_id}_{metric_value}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class AlertDeliveryService:
    """Handles delivery of alerts through various channels"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.delivery_handlers = {
            DeliveryMethod.EMAIL: self._deliver_email,
            DeliveryMethod.WEBHOOK: self._deliver_webhook,
            DeliveryMethod.SLACK: self._deliver_slack,
            DeliveryMethod.DISCORD: self._deliver_discord,
            DeliveryMethod.DESKTOP: self._deliver_desktop,
            DeliveryMethod.IN_APP: self._deliver_in_app
        }
    
    async def deliver_alert(self, alert: Alert, delivery_method: DeliveryMethod, recipient: str, config: Dict[str, Any] = None) -> AlertDelivery:
        """Deliver an alert using specified method"""
        delivery_id = self._generate_delivery_id(alert, delivery_method, recipient)
        
        delivery = AlertDelivery(
            delivery_id=delivery_id,
            alert_id=alert.alert_id,
            method=delivery_method,
            recipient=recipient,
            status="pending"
        )
        
        handler = self.delivery_handlers.get(delivery_method)
        if not handler:
            delivery.status = "failed"
            delivery.error_message = f"No handler for delivery method: {delivery_method}"
            return delivery
        
        try:
            success = await handler(alert, recipient, config or {})
            delivery.status = "sent" if success else "failed"
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            logger.error(f"Error delivering alert {alert.alert_id} via {delivery_method}: {e}")
        
        return delivery
    
    async def _deliver_email(self, alert: Alert, recipient: str, config: Dict[str, Any]) -> bool:
        """Deliver alert via email"""
        smtp_config = {**self.config.get('email', {}), **config}
        
        smtp_host = smtp_config.get('smtp_host', 'localhost')
        smtp_port = smtp_config.get('smtp_port', 587)
        smtp_username = smtp_config.get('smtp_username', '')
        smtp_password = smtp_config.get('smtp_password', '')
        from_address = smtp_config.get('from_address', 'alerts@localhost')
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = from_address
        msg['To'] = recipient
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
        
        # Create HTML body
        html_body = f"""
        <html>
        <body>
            <h2 style="color: {self._get_severity_color(alert.severity)};">{alert.title}</h2>
            
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><td><strong>Alert ID:</strong></td><td>{alert.alert_id}</td></tr>
                <tr><td><strong>Severity:</strong></td><td>{alert.severity.value.upper()}</td></tr>
                <tr><td><strong>Triggered:</strong></td><td>{alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                <tr><td><strong>Data Source:</strong></td><td>{alert.data_source}</td></tr>
                <tr><td><strong>Metric:</strong></td><td>{alert.metric_key}</td></tr>
                <tr><td><strong>Current Value:</strong></td><td>{alert.metric_value}</td></tr>
                {f'<tr><td><strong>Threshold:</strong></td><td>{alert.threshold_value}</td></tr>' if alert.threshold_value is not None else ''}
            </table>
            
            <h3>Message</h3>
            <p>{alert.message}</p>
            
            <h3>Context</h3>
            <pre>{json.dumps(alert.context, indent=2)}</pre>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        try:
            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_username and smtp_password:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    async def _deliver_webhook(self, alert: Alert, recipient: str, config: Dict[str, Any]) -> bool:
        """Deliver alert via webhook"""
        webhook_url = recipient  # recipient is the webhook URL
        
        payload = {
            'alert_id': alert.alert_id,
            'rule_id': alert.rule_id,
            'rule_name': alert.rule_name,
            'severity': alert.severity.value,
            'status': alert.status.value,
            'title': alert.title,
            'message': alert.message,
            'metric_value': alert.metric_value,
            'threshold_value': alert.threshold_value,
            'triggered_at': alert.triggered_at.isoformat(),
            'data_source': alert.data_source,
            'metric_key': alert.metric_key,
            'context': alert.context
        }
        
        headers = config.get('headers', {'Content-Type': 'application/json'})
        timeout = config.get('timeout', 10)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    return response.status < 400
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    async def _deliver_slack(self, alert: Alert, recipient: str, config: Dict[str, Any]) -> bool:
        """Deliver alert via Slack"""
        slack_webhook = config.get('webhook_url') or recipient
        
        color_map = {
            AlertSeverity.LOW: "#36a64f",
            AlertSeverity.MEDIUM: "#ff9900",
            AlertSeverity.HIGH: "#ff6b6b",
            AlertSeverity.CRITICAL: "#d73502"
        }
        
        payload = {
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "#36a64f"),
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Data Source", "value": alert.data_source, "short": True},
                        {"title": "Metric", "value": alert.metric_key, "short": True},
                        {"title": "Value", "value": str(alert.metric_value), "short": True},
                        {"title": "Alert ID", "value": alert.alert_id, "short": False}
                    ],
                    "timestamp": int(alert.triggered_at.timestamp())
                }
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    slack_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    async def _deliver_discord(self, alert: Alert, recipient: str, config: Dict[str, Any]) -> bool:
        """Deliver alert via Discord webhook"""
        discord_webhook = config.get('webhook_url') or recipient
        
        color_map = {
            AlertSeverity.LOW: 3447003,      # Blue
            AlertSeverity.MEDIUM: 16776960,  # Yellow
            AlertSeverity.HIGH: 16733525,    # Orange
            AlertSeverity.CRITICAL: 15158332 # Red
        }
        
        payload = {
            "embeds": [
                {
                    "title": alert.title,
                    "description": alert.message,
                    "color": color_map.get(alert.severity, 3447003),
                    "fields": [
                        {"name": "Severity", "value": alert.severity.value.upper(), "inline": True},
                        {"name": "Data Source", "value": alert.data_source, "inline": True},
                        {"name": "Metric", "value": alert.metric_key, "inline": True},
                        {"name": "Value", "value": str(alert.metric_value), "inline": True},
                        {"name": "Alert ID", "value": f"`{alert.alert_id}`", "inline": False}
                    ],
                    "timestamp": alert.triggered_at.isoformat(),
                    "footer": {"text": f"Rule: {alert.rule_name}"}
                }
            ]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    discord_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 204
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
    
    async def _deliver_desktop(self, alert: Alert, recipient: str, config: Dict[str, Any]) -> bool:
        """Deliver alert as desktop notification"""
        try:
            # This would typically use a desktop notification library
            # For now, we'll log it as a placeholder
            logger.info(f"Desktop notification: {alert.title} - {alert.message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send desktop notification: {e}")
            return False
    
    async def _deliver_in_app(self, alert: Alert, recipient: str, config: Dict[str, Any]) -> bool:
        """Store alert for in-app notification"""
        try:
            # This would typically store in a database or message queue
            # For now, we'll log it as a placeholder
            logger.info(f"In-app notification for {recipient}: {alert.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to store in-app notification: {e}")
            return False
    
    def _get_severity_color(self, severity: AlertSeverity) -> str:
        """Get color for severity level"""
        colors = {
            AlertSeverity.LOW: "#28a745",
            AlertSeverity.MEDIUM: "#ffc107", 
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.CRITICAL: "#dc3545"
        }
        return colors.get(severity, "#6c757d")
    
    def _generate_delivery_id(self, alert: Alert, method: DeliveryMethod, recipient: str) -> str:
        """Generate unique delivery ID"""
        content = f"{alert.alert_id}_{method.value}_{recipient}_{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class AlertManager:
    """Main alert management system"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("alert_config.json")
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.suppressed_alerts: Dict[str, datetime] = {}
        self.alert_counts: Dict[str, int] = {}  # Hourly alert counts by rule
        
        self.condition_evaluator = AlertConditionEvaluator()
        self.delivery_service = AlertDeliveryService()
        
        # Background tasks
        self.evaluation_tasks: Dict[str, asyncio.Task] = {}
        self.running = False
        
        # Load configuration
        self.load_configuration()
    
    def add_rule(self, rule: AlertRule):
        """Add or update an alert rule"""
        self.rules[rule.rule_id] = rule
        self.save_configuration()
        
        # Start evaluation task if manager is running
        if self.running and rule.enabled:
            self._start_rule_evaluation(rule)
    
    def remove_rule(self, rule_id: str):
        """Remove an alert rule"""
        if rule_id in self.rules:
            # Stop evaluation task
            if rule_id in self.evaluation_tasks:
                self.evaluation_tasks[rule_id].cancel()
                del self.evaluation_tasks[rule_id]
            
            del self.rules[rule_id]
            self.save_configuration()
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get alert rule by ID"""
        return self.rules.get(rule_id)
    
    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """List all alert rules"""
        rules = list(self.rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return sorted(rules, key=lambda r: r.created_at)
    
    def enable_rule(self, rule_id: str):
        """Enable an alert rule"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            if self.running:
                self._start_rule_evaluation(self.rules[rule_id])
            self.save_configuration()
    
    def disable_rule(self, rule_id: str):
        """Disable an alert rule"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            if rule_id in self.evaluation_tasks:
                self.evaluation_tasks[rule_id].cancel()
                del self.evaluation_tasks[rule_id]
            self.save_configuration()
    
    async def start(self):
        """Start the alert manager"""
        self.running = True
        
        # Start evaluation tasks for enabled rules
        for rule in self.rules.values():
            if rule.enabled:
                self._start_rule_evaluation(rule)
        
        logger.info(f"Alert manager started with {len(self.evaluation_tasks)} active rules")
    
    async def stop(self):
        """Stop the alert manager"""
        self.running = False
        
        # Cancel all evaluation tasks
        for task in self.evaluation_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.evaluation_tasks:
            await asyncio.gather(*self.evaluation_tasks.values(), return_exceptions=True)
        
        self.evaluation_tasks.clear()
        logger.info("Alert manager stopped")
    
    def _start_rule_evaluation(self, rule: AlertRule):
        """Start evaluation task for a rule"""
        if rule.rule_id in self.evaluation_tasks:
            self.evaluation_tasks[rule.rule_id].cancel()
        
        task = asyncio.create_task(self._evaluate_rule_loop(rule))
        self.evaluation_tasks[rule.rule_id] = task
    
    async def _evaluate_rule_loop(self, rule: AlertRule):
        """Continuous evaluation loop for a rule"""
        while self.running and rule.enabled:
            try:
                await self._evaluate_single_rule(rule)
                await asyncio.sleep(rule.evaluation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
                await asyncio.sleep(rule.evaluation_interval)
    
    async def _evaluate_single_rule(self, rule: AlertRule):
        """Evaluate a single rule"""
        # Check if rule is suppressed
        if self._is_suppressed(rule.rule_id):
            return
        
        # Check hourly rate limit
        if self._is_rate_limited(rule.rule_id, rule.max_alerts_per_hour):
            return
        
        # Get current data from data source
        current_data = await self._get_data_for_rule(rule)
        if not current_data:
            return
        
        # Get historical data if needed
        historical_data = await self._get_historical_data_for_rule(rule, lookback_periods=30)
        
        # Evaluate condition
        alert = await self.condition_evaluator.evaluate(rule, current_data, historical_data)
        
        if alert:
            await self._handle_triggered_alert(alert, rule)
    
    async def _get_data_for_rule(self, rule: AlertRule) -> Optional[Dict[str, Any]]:
        """Get current data for rule evaluation"""
        try:
            # This would typically connect to data sources
            # For now, we'll simulate data based on the data source type
            if rule.data_source == 'productivity':
                from ..dashboard.advanced_dashboard import ProductivityDataSource
                source = ProductivityDataSource('productivity', {})
                return await source.get_data(rule.filters)
            elif rule.data_source == 'health':
                from ..dashboard.advanced_dashboard import HealthDataSource
                source = HealthDataSource('health', {})
                return await source.get_data(rule.filters)
            elif rule.data_source == 'tasks':
                from ..dashboard.advanced_dashboard import TaskDataSource
                source = TaskDataSource('tasks', {})
                return await source.get_data(rule.filters)
            else:
                logger.warning(f"Unknown data source: {rule.data_source}")
                return None
        except Exception as e:
            logger.error(f"Error getting data for rule {rule.rule_id}: {e}")
            return None
    
    async def _get_historical_data_for_rule(self, rule: AlertRule, lookback_periods: int = 30) -> List[Dict[str, Any]]:
        """Get historical data for rule evaluation"""
        # This would typically query historical data
        # For now, we'll return empty list
        return []
    
    async def _handle_triggered_alert(self, alert: Alert, rule: AlertRule):
        """Handle a triggered alert"""
        # Check if this alert already exists (deduplication)
        existing_alert = self._find_existing_alert(alert)
        if existing_alert:
            logger.debug(f"Alert {alert.alert_id} already exists, skipping")
            return
        
        # Add to active alerts
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        
        # Increment alert count for rate limiting
        self._increment_alert_count(rule.rule_id)
        
        # Suppress future alerts for this rule
        self.suppressed_alerts[rule.rule_id] = datetime.now() + timedelta(seconds=rule.suppress_duration)
        
        # Deliver alert
        await self._deliver_alert(alert, rule)
        
        logger.info(f"Alert triggered: {alert.title} (ID: {alert.alert_id})")
    
    async def _deliver_alert(self, alert: Alert, rule: AlertRule):
        """Deliver alert using configured methods"""
        delivery_tasks = []
        
        for method in rule.delivery_methods:
            recipients = rule.delivery_config.get(method.value, {}).get('recipients', [])
            
            for recipient in recipients:
                delivery_config = rule.delivery_config.get(method.value, {})
                task = self.delivery_service.deliver_alert(alert, method, recipient, delivery_config)
                delivery_tasks.append(task)
        
        # Execute deliveries concurrently
        if delivery_tasks:
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if isinstance(r, AlertDelivery) and r.status == "sent")
            logger.info(f"Alert {alert.alert_id} delivered via {successful}/{len(delivery_tasks)} methods")
    
    def _find_existing_alert(self, alert: Alert) -> Optional[Alert]:
        """Find existing alert with same characteristics"""
        for existing_alert in self.active_alerts.values():
            if (existing_alert.rule_id == alert.rule_id and
                existing_alert.status == AlertStatus.ACTIVE and
                existing_alert.metric_key == alert.metric_key):
                return existing_alert
        return None
    
    def _is_suppressed(self, rule_id: str) -> bool:
        """Check if rule is currently suppressed"""
        if rule_id not in self.suppressed_alerts:
            return False
        
        suppressed_until = self.suppressed_alerts[rule_id]
        if datetime.now() > suppressed_until:
            del self.suppressed_alerts[rule_id]
            return False
        
        return True
    
    def _is_rate_limited(self, rule_id: str, max_per_hour: int) -> bool:
        """Check if rule has exceeded rate limit"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        count_key = f"{rule_id}_{current_hour.isoformat()}"
        
        current_count = self.alert_counts.get(count_key, 0)
        return current_count >= max_per_hour
    
    def _increment_alert_count(self, rule_id: str):
        """Increment alert count for rate limiting"""
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        count_key = f"{rule_id}_{current_hour.isoformat()}"
        
        self.alert_counts[count_key] = self.alert_counts.get(count_key, 0) + 1
        
        # Clean old counts (keep only last 24 hours)
        cutoff = current_hour - timedelta(hours=24)
        self.alert_counts = {
            k: v for k, v in self.alert_counts.items()
            if datetime.fromisoformat(k.split('_', 1)[1]) > cutoff
        }
    
    def acknowledge_alert(self, alert_id: str, user: str, note: str = None):
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now()
            alert.acknowledged_by = user
            
            if note:
                alert.notes.append(f"[{datetime.now().isoformat()}] {user}: {note}")
            
            logger.info(f"Alert {alert_id} acknowledged by {user}")
    
    def resolve_alert(self, alert_id: str, user: str, note: str = None):
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.resolved_by = user
            
            if note:
                alert.notes.append(f"[{datetime.now().isoformat()}] {user}: {note}")
            
            # Remove from active alerts
            del self.active_alerts[alert_id]
            
            logger.info(f"Alert {alert_id} resolved by {user}")
    
    def suppress_alert(self, alert_id: str, duration_minutes: int = 60):
        """Suppress an alert temporarily"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.SUPPRESSED
            
            # Also suppress the rule
            suppressed_until = datetime.now() + timedelta(minutes=duration_minutes)
            self.suppressed_alerts[alert.rule_id] = suppressed_until
            
            logger.info(f"Alert {alert_id} suppressed for {duration_minutes} minutes")
    
    def get_active_alerts(self, severity: AlertSeverity = None) -> List[Alert]:
        """Get active alerts, optionally filtered by severity"""
        alerts = list(self.active_alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)
    
    def get_alert_history(self, limit: int = 100, rule_id: str = None) -> List[Alert]:
        """Get alert history"""
        history = self.alert_history
        if rule_id:
            history = [a for a in history if a.rule_id == rule_id]
        return sorted(history, key=lambda a: a.triggered_at, reverse=True)[:limit]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics"""
        active_count = len(self.active_alerts)
        total_count = len(self.alert_history)
        
        # Count by severity
        severity_counts = {}
        for severity in AlertSeverity:
            severity_counts[severity.value] = len([
                a for a in self.active_alerts.values() 
                if a.severity == severity
            ])
        
        # Count by rule
        rule_counts = {}
        for alert in self.alert_history:
            rule_counts[alert.rule_id] = rule_counts.get(alert.rule_id, 0) + 1
        
        # Recent activity (last 24 hours)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_alerts = [a for a in self.alert_history if a.triggered_at > recent_cutoff]
        
        return {
            'active_alerts': active_count,
            'total_alerts': total_count,
            'recent_alerts_24h': len(recent_alerts),
            'severity_breakdown': severity_counts,
            'top_rules': dict(sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'enabled_rules': len([r for r in self.rules.values() if r.enabled]),
            'total_rules': len(self.rules)
        }
    
    def save_configuration(self):
        """Save alert configuration to file"""
        try:
            config_data = {
                'rules': {}
            }
            
            for rule_id, rule in self.rules.items():
                config_data['rules'][rule_id] = {
                    'rule_id': rule.rule_id,
                    'name': rule.name,
                    'description': rule.description,
                    'condition_type': rule.condition_type.value,
                    'data_source': rule.data_source,
                    'metric_key': rule.metric_key,
                    'condition_config': rule.condition_config,
                    'severity': rule.severity.value,
                    'enabled': rule.enabled,
                    'delivery_methods': [m.value for m in rule.delivery_methods],
                    'delivery_config': rule.delivery_config,
                    'evaluation_interval': rule.evaluation_interval,
                    'suppress_duration': rule.suppress_duration,
                    'max_alerts_per_hour': rule.max_alerts_per_hour,
                    'tags': rule.tags,
                    'filters': rule.filters,
                    'created_at': rule.created_at.isoformat(),
                    'updated_at': rule.updated_at.isoformat(),
                    'created_by': rule.created_by
                }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving alert configuration: {e}")
    
    def load_configuration(self):
        """Load alert configuration from file"""
        try:
            if not self.config_path.exists():
                self._create_default_rules()
                return
            
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load rules
            for rule_id, rule_data in config_data.get('rules', {}).items():
                rule = AlertRule(
                    rule_id=rule_data['rule_id'],
                    name=rule_data['name'],
                    description=rule_data['description'],
                    condition_type=AlertCondition(rule_data['condition_type']),
                    data_source=rule_data['data_source'],
                    metric_key=rule_data['metric_key'],
                    condition_config=rule_data['condition_config'],
                    severity=AlertSeverity(rule_data['severity']),
                    enabled=rule_data.get('enabled', True),
                    delivery_methods=[DeliveryMethod(m) for m in rule_data.get('delivery_methods', [])],
                    delivery_config=rule_data.get('delivery_config', {}),
                    evaluation_interval=rule_data.get('evaluation_interval', 60),
                    suppress_duration=rule_data.get('suppress_duration', 300),
                    max_alerts_per_hour=rule_data.get('max_alerts_per_hour', 10),
                    tags=rule_data.get('tags', []),
                    filters=rule_data.get('filters', {}),
                    created_at=datetime.fromisoformat(rule_data.get('created_at', datetime.now().isoformat())),
                    updated_at=datetime.fromisoformat(rule_data.get('updated_at', datetime.now().isoformat())),
                    created_by=rule_data.get('created_by', 'system')
                )
                self.rules[rule_id] = rule
                
        except Exception as e:
            logger.error(f"Error loading alert configuration: {e}")
            self._create_default_rules()
    
    def _create_default_rules(self):
        """Create default alert rules"""
        # Low productivity alert
        low_productivity_rule = AlertRule(
            rule_id="low_productivity",
            name="Low Productivity Alert",
            description="Alert when productivity score drops below threshold",
            condition_type=AlertCondition.THRESHOLD,
            data_source="productivity",
            metric_key="productivity_score",
            condition_config={
                "operator": "lt",
                "threshold": 50
            },
            severity=AlertSeverity.MEDIUM,
            delivery_methods=[DeliveryMethod.IN_APP],
            delivery_config={
                "in_app": {"recipients": ["user@example.com"]}
            }
        )
        
        # High stress alert
        high_stress_rule = AlertRule(
            rule_id="high_stress",
            name="High Stress Level Alert", 
            description="Alert when stress level is consistently high",
            condition_type=AlertCondition.PATTERN,
            data_source="health",
            metric_key="average_stress_level",
            condition_config={
                "pattern_type": "consecutive",
                "window_size": 3,
                "operator": "gt",
                "threshold": 7
            },
            severity=AlertSeverity.HIGH,
            delivery_methods=[DeliveryMethod.IN_APP],
            delivery_config={
                "in_app": {"recipients": ["user@example.com"]}
            }
        )
        
        # Task completion trend alert
        task_trend_rule = AlertRule(
            rule_id="declining_task_completion",
            name="Declining Task Completion",
            description="Alert when task completion rate is decreasing",
            condition_type=AlertCondition.TREND,
            data_source="tasks",
            metric_key="completion_rate",
            condition_config={
                "trend_direction": "decreasing",
                "trend_window": 7,
                "trend_threshold": 0.1
            },
            severity=AlertSeverity.MEDIUM,
            delivery_methods=[DeliveryMethod.IN_APP],
            delivery_config={
                "in_app": {"recipients": ["user@example.com"]}
            }
        )
        
        self.add_rule(low_productivity_rule)
        self.add_rule(high_stress_rule)
        self.add_rule(task_trend_rule)


# Example usage and testing functions
async def example_usage():
    """Example usage of the alert management system"""
    
    # Create alert manager
    manager = AlertManager()
    
    # Create a custom threshold rule
    custom_rule = AlertRule(
        rule_id="custom_focus_time",
        name="Low Focus Time Alert",
        description="Alert when daily focus time is below 4 hours",
        condition_type=AlertCondition.THRESHOLD,
        data_source="productivity",
        metric_key="focus_time_hours",
        condition_config={
            "operator": "lt",
            "threshold": 4.0
        },
        severity=AlertSeverity.MEDIUM,
        delivery_methods=[DeliveryMethod.EMAIL, DeliveryMethod.IN_APP],
        delivery_config={
            "email": {
                "recipients": ["user@example.com"],
                "smtp_host": "smtp.example.com",
                "from_address": "alerts@example.com"
            },
            "in_app": {
                "recipients": ["user@example.com"]
            }
        }
    )
    
    manager.add_rule(custom_rule)
    
    # Start the alert manager
    await manager.start()
    
    # Let it run for a short time to demonstrate
    await asyncio.sleep(5)
    
    # Check statistics
    stats = manager.get_alert_statistics()
    print(f"Alert Statistics: {stats}")
    
    # List active alerts
    active_alerts = manager.get_active_alerts()
    print(f"Active Alerts: {len(active_alerts)}")
    
    # Stop the alert manager
    await manager.stop()


if __name__ == "__main__":
    asyncio.run(example_usage())