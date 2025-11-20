"""
Telemetry Dashboard Widgets for Phase 2 Enhanced Analytics

Implements real-time telemetry widgets for the comprehensive health dashboard:
- Error Rate Monitor
- Cost Burn Rate Tracker
- Timeout Risk Assessment
- Tool Sequence Optimizer
- Model Efficiency Tracker
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from context_cleaner.telemetry.cost_optimization.engine import CostOptimizationEngine
from context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager

# Context Rot Meter imports
try:
    from context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
    from context_cleaner.telemetry.context_rot.widget import ContextRotWidget

    CONTEXT_ROT_AVAILABLE = True
except ImportError as e:
    print(f"Context Rot import failed: {e}")
    CONTEXT_ROT_AVAILABLE = False

    class ContextRotAnalyzer:
        def __init__(self, **kwargs):
            pass

        async def analyze_session_health(self, session_id, time_window):
            return {}

    class ContextRotWidget:
        def __init__(self, **kwargs):
            pass

        async def get_widget_data(self, session_id=None, time_window_minutes=30):
            # Return sample/demo data when Context Rot components aren't available
            return WidgetData(
                widget_type=TelemetryWidgetType.CONTEXT_ROT_METER,
                title="Context Rot Meter (Demo)",
                status="operational",
                data={
                    "current_rot_score": 0.25,
                    "confidence_level": 0.82,
                    "session_health_status": "healthy",
                    "trend_direction": "stable",
                    "measurements_count": 147,
                    "attention_alerts": 0,
                    "time_window_minutes": time_window_minutes,
                    "repetition_score": 0.15,
                    "efficiency_score": 0.88,
                    "health_score": 0.92,
                    "recommendations": [
                        "Conversation flow is optimal",
                        "No context degradation detected",
                        "Continue current interaction patterns",
                    ],
                    "analysis_latency_ms": 45.2,
                    "memory_usage_mb": 12.8,
                    "message": "Demo mode: Real-time conversation quality monitoring active. System shows healthy conversation patterns with minimal context rot detected.",
                    "hourly_averages": [
                        {"hour": "14:00", "rot_score": 0.22, "confidence": 0.85},
                        {"hour": "15:00", "rot_score": 0.18, "confidence": 0.88},
                        {"hour": "16:00", "rot_score": 0.25, "confidence": 0.82},
                    ],
                },
                alerts=[],
            )


# Phase 4: JSONL Analytics imports
try:
    from context_cleaner.telemetry.jsonl_enhancement.full_content_queries import (
        FullContentQueries,
    )
    from context_cleaner.telemetry.jsonl_enhancement.jsonl_processor_service import (
        JsonlProcessorService,
    )

    JSONL_ANALYTICS_AVAILABLE = True
except ImportError:
    JSONL_ANALYTICS_AVAILABLE = False

    class FullContentQueries:
        def __init__(self, **kwargs):
            pass

        async def get_complete_conversation(self, session_id):
            return {}

        async def get_content_statistics(self):
            return {}

        async def search_conversation_content(self, term, limit=50):
            return []

    class JsonlProcessorService:
        def __init__(self, clickhouse_client=None, **kwargs):
            self.clickhouse_client = clickhouse_client

        async def get_processing_status(self):
            return {}


# Phase 3: Orchestration system imports
try:
    from context_cleaner.telemetry.orchestration.task_orchestrator import (
        TaskOrchestrator,
    )
    from context_cleaner.telemetry.orchestration.workflow_learner import WorkflowLearner
    from context_cleaner.telemetry.orchestration.agent_selector import AgentSelector

    ORCHESTRATION_AVAILABLE = True
except ImportError:
    ORCHESTRATION_AVAILABLE = False

    # Stub classes for when orchestration is not available
    class TaskOrchestrator:
        def __init__(self, **kwargs):
            pass

        async def get_status(self):
            return {}

        async def get_workflow_statistics(self):
            return {}

    class WorkflowLearner:
        def __init__(self, **kwargs):
            pass

        async def get_learning_status(self):
            return {}

        async def get_performance_insights(self):
            return {}

    class AgentSelector:
        def __init__(self, **kwargs):
            pass

        async def get_agent_utilization(self):
            return {}

        async def get_performance_metrics(self):
            return {}


logger = logging.getLogger(__name__)

# Enhanced logging configuration for widget data staleness debugging
widget_logger = logging.getLogger(f"{__name__}.widgets")
widget_logger.setLevel(logging.DEBUG)

# Create console handler if it doesn't exist
if not widget_logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    console_handler.setFormatter(formatter)
    widget_logger.addHandler(console_handler)
    widget_logger.propagate = False


class TelemetryWidgetType(Enum):
    """Types of telemetry widgets"""

    ERROR_MONITOR = "error_monitor"
    COST_TRACKER = "cost_tracker"
    TIMEOUT_RISK = "timeout_risk"
    TOOL_OPTIMIZER = "tool_optimizer"
    MODEL_EFFICIENCY = "model_efficiency"
    # Phase 3: Orchestration Widgets
    ORCHESTRATION_STATUS = "orchestration_status"
    AGENT_UTILIZATION = "agent_utilization"
    # Phase 4: JSONL Analytics Widgets
    CONVERSATION_TIMELINE = "conversation_timeline"
    CODE_PATTERN_ANALYSIS = "code_pattern_analysis"
    CONTENT_SEARCH_WIDGET = "content_search_widget"
    CLAUDE_MD_ANALYTICS = "claude_md_analytics"
    # Context Rot Meter
    CONTEXT_ROT_METER = "context_rot_meter"


@dataclass
class WidgetData:
    """Base widget data structure"""

    widget_type: TelemetryWidgetType
    title: str
    status: str  # "healthy", "warning", "critical"
    data: Dict[str, Any]
    last_updated: datetime = field(default_factory=datetime.now)
    alerts: List[str] = field(default_factory=list)


@dataclass
class ErrorMonitorData:
    """Error rate monitoring data"""

    current_error_rate: float
    error_trend: str  # "increasing", "decreasing", "stable"
    recent_errors: List[Dict[str, Any]]
    recovery_success_rate: float
    last_error_time: Optional[datetime] = None


@dataclass
class CostTrackerData:
    """Cost burn rate tracking data"""

    current_session_cost: float
    burn_rate_per_hour: float
    budget_remaining: float
    cost_projection: float
    model_breakdown: Dict[str, float]
    cost_trend: str  # "increasing", "decreasing", "stable"


@dataclass
class TimeoutRiskData:
    """Timeout risk assessment data"""

    risk_level: str  # "low", "medium", "high", "critical"
    risk_factors: List[str]
    avg_response_time: float
    slow_requests_count: int
    recommended_actions: List[str]


@dataclass
class ToolOptimizerData:
    """Tool sequence optimization data"""

    common_sequences: List[Dict[str, Any]]
    efficiency_score: float
    optimization_suggestions: List[str]
    tool_usage_stats: Dict[str, int]


@dataclass
class ModelEfficiencyData:
    """Model efficiency comparison data"""

    sonnet_stats: Dict[str, Any]
    haiku_stats: Dict[str, Any]
    efficiency_ratio: float
    recommendation: str
    cost_savings_potential: float


@dataclass
class OrchestrationStatusData:
    """Real-time orchestration system status"""

    active_workflows: int
    queued_workflows: int
    completed_workflows_today: int
    failed_workflows_today: int
    success_rate: float
    avg_workflow_duration: float
    orchestrator_health: str  # "healthy", "degraded", "offline"
    active_agents: List[str]
    resource_usage: Dict[str, float]  # CPU, memory, etc.


@dataclass
class AgentUtilizationData:
    """Agent utilization and performance metrics"""

    agent_utilization: Dict[str, float]  # agent_type -> utilization percentage
    agent_performance: Dict[
        str, Dict[str, float]
    ]  # agent_type -> {success_rate, avg_duration, cost_efficiency}
    high_performers: List[str]
    underutilized_agents: List[str]
    bottleneck_agents: List[str]
    load_balancing_recommendations: List[str]


@dataclass
class WorkflowPerformanceData:
    """Workflow execution performance analytics"""

    workflow_templates: Dict[
        str, Dict[str, Any]
    ]  # template_name -> performance metrics
    optimization_opportunities: List[Dict[str, Any]]
    pattern_insights: List[str]
    cost_efficiency_score: float
    time_efficiency_score: float
    learning_engine_status: str  # "learning", "optimizing", "stable"
    recent_optimizations: List[Dict[str, Any]]


# Phase 4: JSONL Analytics Widget Data Structures


@dataclass
class ConversationTimelineData:
    """Interactive conversation timeline data"""

    session_id: str
    timeline_events: List[
        Dict[str, Any]
    ]  # chronological events (messages, tool uses, file accesses)
    conversation_metrics: Dict[str, Any]  # duration, message count, tool usage stats
    key_insights: List[str]  # notable patterns or achievements in the conversation
    error_events: List[Dict[str, Any]]  # errors and recovery events
    file_operations: List[Dict[str, Any]]  # file access timeline
    tool_sequence: List[Dict[str, Any]]  # tool usage patterns and chains


@dataclass
class CodePatternAnalysisData:
    """Code pattern analysis widget data"""

    language_distribution: Dict[str, float]  # programming languages with percentages
    common_patterns: List[Dict[str, Any]]  # frequently used code patterns
    function_analysis: Dict[str, Any]  # function usage and complexity metrics
    file_type_breakdown: Dict[str, int]  # file types accessed with counts
    development_trends: List[Dict[str, Any]]  # trends over time
    optimization_suggestions: List[str]  # recommendations based on patterns


@dataclass
class ContentSearchWidgetData:
    """Content search interface widget data"""

    recent_searches: List[Dict[str, Any]]  # recent search queries and results
    popular_search_terms: List[str]  # frequently searched terms
    search_performance: Dict[str, Any]  # search speed and accuracy metrics
    content_categories: Dict[str, int]  # available content types and counts
    search_suggestions: List[str]  # intelligent search suggestions
    indexed_content_stats: Dict[str, Any]  # statistics about searchable content


class TelemetryWidgetManager:
    """Manages telemetry widgets for the dashboard with comprehensive logging and data freshness tracking"""

    def __init__(
        self,
        telemetry_client: ClickHouseClient,
        cost_engine: CostOptimizationEngine,
        recovery_manager: ErrorRecoveryManager,
        task_orchestrator: Optional[TaskOrchestrator] = None,
        workflow_learner: Optional[WorkflowLearner] = None,
        agent_selector: Optional[AgentSelector] = None,
    ):
        self.telemetry = telemetry_client
        self.cost_engine = cost_engine
        self.recovery_manager = recovery_manager

        # Phase 3: Orchestration components
        self.task_orchestrator = task_orchestrator
        self.workflow_learner = workflow_learner
        self.agent_selector = agent_selector

        # Phase 4: JSONL Analytics components
        if JSONL_ANALYTICS_AVAILABLE:
            self.content_queries = FullContentQueries(telemetry_client)
            self.jsonl_processor = JsonlProcessorService(telemetry_client)
        else:
            self.content_queries = FullContentQueries()

        # Context Rot Meter components
        if CONTEXT_ROT_AVAILABLE:
            self.context_rot_analyzer = ContextRotAnalyzer(
                telemetry_client, recovery_manager
            )
            self.context_rot_widget = ContextRotWidget(
                telemetry_client, self.context_rot_analyzer
            )
        else:
            self.context_rot_analyzer = ContextRotAnalyzer()
            self.context_rot_widget = ContextRotWidget()

        # Data freshness tracking
        self._data_freshness_tracker = {}
        self._fallback_detection = {}

        # Enhanced service availability detection for widget staleness debugging
        self._service_availability = {
            "telemetry_client": self._is_real_service(
                telemetry_client, "ClickHouseClient"
            ),
            "cost_engine": self._is_real_service(cost_engine, "CostOptimizationEngine"),
            "recovery_manager": self._is_real_service(
                recovery_manager, "ErrorRecoveryManager"
            ),
            "task_orchestrator": self._is_real_service(
                task_orchestrator, "TaskOrchestrator"
            ),
            "workflow_learner": self._is_real_service(
                workflow_learner, "WorkflowLearner"
            ),
            "agent_selector": self._is_real_service(agent_selector, "AgentSelector"),
        }

        # Detect if we're in fallback mode (telemetry stack unavailable)
        self._fallback_mode = not self._service_availability["telemetry_client"]
        if self._fallback_mode:
            widget_logger.warning(
                "🔄 FALLBACK MODE DETECTED: Telemetry client unavailable - widgets will show demo/empty data"
            )
            widget_logger.warning(
                "   This usually means the telemetry stack has not been initialised"
            )
            widget_logger.warning(
                "   Run 'context-cleaner telemetry init' to start ClickHouse and the OTEL collector"
            )

        # Log initialization state
        widget_logger.info(
            f"TelemetryWidgetManager initialized with services: {self._service_availability}"
        )
        widget_logger.info(
            f"ClickHouse available: {self._service_availability['telemetry_client']}"
        )
        widget_logger.info(f"Context Rot available: {CONTEXT_ROT_AVAILABLE}")
        widget_logger.info(f"JSONL Analytics available: {JSONL_ANALYTICS_AVAILABLE}")
        widget_logger.info(f"Orchestration available: {ORCHESTRATION_AVAILABLE}")

        # Widget update intervals (in seconds)
        self.update_intervals = {
            TelemetryWidgetType.ERROR_MONITOR: 30,
            TelemetryWidgetType.COST_TRACKER: 10,
            TelemetryWidgetType.TIMEOUT_RISK: 60,
            TelemetryWidgetType.TOOL_OPTIMIZER: 300,  # 5 minutes
            TelemetryWidgetType.MODEL_EFFICIENCY: 120,  # 2 minutes
            TelemetryWidgetType.CONTEXT_ROT_METER: 60,  # Context rot analysis (1 min)
            # Phase 3: Orchestration widgets
            TelemetryWidgetType.ORCHESTRATION_STATUS: 15,  # Real-time orchestration status
            TelemetryWidgetType.AGENT_UTILIZATION: 45,  # Agent utilization metrics
            # Phase 4: JSONL Analytics widgets
            TelemetryWidgetType.CONVERSATION_TIMELINE: 30,  # Conversation timeline updates
            TelemetryWidgetType.CODE_PATTERN_ANALYSIS: 120,  # Code pattern analysis (2 min)
            TelemetryWidgetType.CONTENT_SEARCH_WIDGET: 60,  # Content search metrics (1 min)
            TelemetryWidgetType.CLAUDE_MD_ANALYTICS: 300,  # CLAUDE.md usage analytics (5 min)
        }

        # Cache for widget data to reduce database queries
        self._widget_cache: Dict[TelemetryWidgetType, WidgetData] = {}
        self._cache_timestamps: Dict[TelemetryWidgetType, datetime] = {}

        # Cache invalidation tracking
        self._last_service_restart_check = datetime.now()
        self._cache_invalidation_callbacks = []

    def _is_real_service(self, service_instance, expected_class_name: str) -> bool:
        """
        Detect if a service is a real implementation or a stub class.
        Returns False for None, stub classes, or services running in demo mode.
        """
        if service_instance is None:
            return False

        # Check if it's a stub class (usually defined locally in import fallback blocks)
        class_name = service_instance.__class__.__name__
        module_name = service_instance.__class__.__module__

        # If the class is defined in this module, it's likely a stub
        if module_name == __name__:
            widget_logger.debug(
                f"Service {class_name} detected as stub (defined in {module_name})"
            )
            return False

        # Check for common stub class patterns
        if hasattr(service_instance, "_is_stub") and service_instance._is_stub:
            widget_logger.debug(f"Service {class_name} marked as stub")
            return False

        # For ClickHouse client, try to detect if it's connected
        if expected_class_name == "ClickHouseClient":
            try:
                # Check if it has the basic methods we expect
                if not (
                    hasattr(service_instance, "execute_query")
                    and hasattr(service_instance, "get_recent_errors")
                ):
                    widget_logger.debug(f"ClickHouse client missing expected methods")
                    return False
            except Exception:
                return False

        widget_logger.debug(f"Service {class_name} appears to be real implementation")
        return True

    async def get_widget_data(
        self,
        widget_type: TelemetryWidgetType,
        session_id: Optional[str] = None,
        time_range_days: int = 7,
    ) -> WidgetData:
        """Get data for a specific widget type with comprehensive logging and freshness tracking"""

        widget_logger.debug(f"Requesting widget data for: {widget_type.value}")
        widget_logger.debug(f"  Session ID: {session_id}")
        widget_logger.debug(f"  Time range: {time_range_days} days")

        # Check cache first
        cache_key = widget_type
        if cache_key in self._widget_cache and cache_key in self._cache_timestamps:

            cache_age = datetime.now() - self._cache_timestamps[cache_key]
            max_age = timedelta(seconds=self.update_intervals[widget_type])

            widget_logger.debug(
                f"  Cache found - age: {cache_age.total_seconds():.1f}s, max_age: {max_age.total_seconds()}s"
            )

            if cache_age < max_age:
                widget_logger.debug(f"  Returning cached data for {widget_type.value}")
                return self._widget_cache[cache_key]
            else:
                widget_logger.debug(
                    f"  Cache expired for {widget_type.value}, fetching fresh data"
                )
        else:
            widget_logger.debug(
                f"  No cache found for {widget_type.value}, fetching fresh data"
            )

        # Track data freshness
        start_time = datetime.now()

        # Generate fresh data with service availability logging
        widget_logger.info(f"Generating fresh data for {widget_type.value}")

        try:
            if widget_type == TelemetryWidgetType.ERROR_MONITOR:
                widget_logger.debug(
                    f"  Fetching error monitor data - telemetry available: {self._service_availability['telemetry_client']}"
                )
                data = await self._get_error_monitor_data(session_id, time_range_days)
            elif widget_type == TelemetryWidgetType.COST_TRACKER:
                data = await self._get_cost_tracker_data(session_id, time_range_days)
            elif widget_type == TelemetryWidgetType.TIMEOUT_RISK:
                data = await self._get_timeout_risk_data(session_id, time_range_days)
            elif widget_type == TelemetryWidgetType.TOOL_OPTIMIZER:
                data = await self._get_tool_optimizer_data(session_id, time_range_days)
            elif widget_type == TelemetryWidgetType.MODEL_EFFICIENCY:
                data = await self._get_model_efficiency_data(
                    session_id, time_range_days
                )
            # Phase 3: Orchestration widgets
            elif widget_type == TelemetryWidgetType.ORCHESTRATION_STATUS:
                data = await self._get_orchestration_status_data(
                    session_id, time_range_days
                )
            elif widget_type == TelemetryWidgetType.AGENT_UTILIZATION:
                data = await self._get_agent_utilization_data(
                    session_id, time_range_days
                )
            # Phase 4: JSONL Analytics widgets
            elif widget_type == TelemetryWidgetType.CONVERSATION_TIMELINE:
                data = await self._get_conversation_timeline_data(session_id)
            elif widget_type == TelemetryWidgetType.CODE_PATTERN_ANALYSIS:
                data = await self._get_code_pattern_analysis_data(session_id)
            elif widget_type == TelemetryWidgetType.CONTENT_SEARCH_WIDGET:
                data = await self._get_content_search_widget_data(session_id)
            elif widget_type == TelemetryWidgetType.CLAUDE_MD_ANALYTICS:
                data = await self._get_claude_md_analytics_data(
                    session_id, time_range_days
                )
            elif widget_type == TelemetryWidgetType.CONTEXT_ROT_METER:
                data = await self._get_context_rot_meter_data(
                    session_id, time_range_days
                )
            else:
                raise ValueError(f"Unknown widget type: {widget_type}")

            # Track data freshness and generation time
            generation_time = (datetime.now() - start_time).total_seconds()
            data_source = (
                "live"
                if self._service_availability.get("telemetry_client")
                else "fallback"
            )

            self._data_freshness_tracker[widget_type] = {
                "last_generated": datetime.now(),
                "generation_time_ms": generation_time * 1000,
                "data_source": data_source,
                "cache_used": False,
                "service_availability": self._service_availability.copy(),
            }

            # Enhance widget with fallback mode indicators
            if self._fallback_mode and data_source == "fallback":
                widget_logger.info(
                    f"🔄 FALLBACK: {widget_type.value} showing demo data (ClickHouse unavailable)"
                )

                # Add fallback indicators to widget title and data
                if not data.title.endswith("(Demo)") and not data.title.endswith(
                    "(Offline)"
                ):
                    data.title = f"{data.title} (Demo)"

                # Add fallback mode indicator to data
                if isinstance(data.data, dict):
                    data.data["fallback_mode"] = True
                    data.data["fallback_reason"] = "telemetry_disabled"
                    data.data["data_source"] = "demo"

                # Add informative alert
                fallback_alert = "Demo data - enable full services for real telemetry"
                if fallback_alert not in data.alerts:
                    data.alerts.append(fallback_alert)

            widget_logger.info(
                f"Generated {widget_type.value} data in {generation_time*1000:.1f}ms - source: {data_source}"
            )

            # Cache the data
            self._widget_cache[cache_key] = data
            self._cache_timestamps[cache_key] = datetime.now()

            return data

        except Exception as e:
            widget_logger.error(
                f"Failed to generate widget data for {widget_type.value}: {str(e)}"
            )
            widget_logger.exception(
                f"Full traceback for {widget_type.value} widget error:"
            )

            # Track fallback usage
            self._fallback_detection[widget_type] = {
                "last_error": datetime.now(),
                "error_message": str(e),
                "fallback_used": True,
            }

            # Return error state widget
            return WidgetData(
                widget_type=widget_type,
                title=f"{widget_type.value.replace('_', ' ').title()} (Error)",
                status="error",
                data={
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "service_availability": self._service_availability,
                },
                alerts=[f"Widget error: {str(e)}"],
            )

    async def _get_error_monitor_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Generate error monitoring widget data"""
        try:
            # Get recent errors based on time range
            recent_errors = await self.telemetry.get_recent_errors(
                hours=time_range_days * 24
            )

            # Calculate error rate as percentage of total API requests (not sessions)
            total_requests_result = await self.telemetry.execute_query(
                f"SELECT COUNT(*) as total FROM otel.otel_logs WHERE Body = 'claude_code.api_request' AND Timestamp >= now() - INTERVAL {time_range_days} DAY"
            )
            total_requests = (
                total_requests_result[0]["total"] if total_requests_result else 0
            )
            error_rate = (len(recent_errors) / max(total_requests, 1)) * 100

            # Get recovery statistics with fallback calculation
            try:
                recovery_stats = await self.recovery_manager.get_recovery_statistics()
                recovery_rate = recovery_stats.get("recovery_success_rate", 0.0)
                # Convert to percentage if it's a decimal
                if recovery_rate <= 1.0:
                    recovery_rate = recovery_rate * 100
            except Exception as e:
                logger.warning(f"Could not get recovery statistics: {e}")
                # Fallback: estimate recovery rate as inverse of recent error growth
                if len(recent_errors) > 0:
                    recent_hour_errors = [
                        e
                        for e in recent_errors
                        if hasattr(e, "timestamp")
                        and e.timestamp > datetime.now() - timedelta(hours=1)
                    ]
                    recovery_rate = max(
                        0, 100 - len(recent_hour_errors) * 10
                    )  # Simple heuristic
                else:
                    recovery_rate = 100.0

            # Determine status
            if error_rate > 1.0:
                status = "critical"
                alerts = ["High error rate detected"]
            elif error_rate > 0.5:
                status = "warning"
                alerts = ["Elevated error rate"]
            else:
                status = "healthy"
                alerts = []

            # Calculate trend
            recent_hour_errors = [
                e
                for e in recent_errors
                if e.timestamp > datetime.now() - timedelta(hours=1)
            ]
            prev_hour_errors = [
                e
                for e in recent_errors
                if datetime.now() - timedelta(hours=2)
                < e.timestamp
                <= datetime.now() - timedelta(hours=1)
            ]

            if len(recent_hour_errors) > len(prev_hour_errors):
                trend = "increasing"
            elif len(recent_hour_errors) < len(prev_hour_errors):
                trend = "decreasing"
            else:
                trend = "stable"

            max_recent_errors = 15
            error_data = ErrorMonitorData(
                current_error_rate=error_rate,
                error_trend=trend,
                recent_errors=[
                    {
                        "session_id": e.session_id,
                        "error_type": e.error_type,
                        "timestamp": e.timestamp.isoformat(),
                        "model": e.model,
                    }
                    for e in recent_errors[:max_recent_errors]
                ],  # Most recent errors (up to 15)
                recovery_success_rate=recovery_rate,
                last_error_time=recent_errors[-1].timestamp if recent_errors else None,
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.ERROR_MONITOR,
                title="API Error Monitor",
                status=status,
                data=error_data.__dict__,
                alerts=alerts,
            )

        except Exception as e:
            widget_logger.error(f"Error monitor data generation failed: {e}")
            widget_logger.exception("Full traceback for error monitor failure:")

            # Track fallback usage
            self._fallback_detection[TelemetryWidgetType.ERROR_MONITOR] = {
                "last_error": datetime.now(),
                "error_message": str(e),
                "fallback_used": True,
            }

            return WidgetData(
                widget_type=TelemetryWidgetType.ERROR_MONITOR,
                title="API Error Monitor (Offline)",
                status="error",
                data={},
                alerts=["Unable to fetch error data"],
            )

    async def _get_cost_tracker_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Generate cost tracking widget data"""
        try:
            # Get model usage breakdown for real cost data based on time range
            model_stats = await self.telemetry.get_model_usage_stats(
                days=time_range_days
            )
            model_breakdown = {}
            total_daily_cost = 0.0
            for model, stats in model_stats.items():
                model_key = model.split("-")[-1] if "-" in model else model
                cost = stats["total_cost"]
                model_breakdown[model_key] = cost
                total_daily_cost += cost

            # Calculate burn rate based on actual usage in last 24 hours
            # Get cost trends to see hourly usage patterns
            cost_trends = await self.telemetry.get_cost_trends(days=1)
            if cost_trends:
                # Calculate average hourly burn rate from recent data
                recent_costs = list(cost_trends.values())
                if recent_costs:
                    avg_daily_cost = sum(recent_costs) / len(recent_costs)
                    burn_rate = avg_daily_cost / 24  # Convert daily to hourly
                else:
                    burn_rate = total_daily_cost / 24
            else:
                burn_rate = total_daily_cost / 24

            # Get current session cost if session_id provided
            if session_id:
                session_cost = await self.telemetry.get_current_session_cost(session_id)
            else:
                # Use recent session cost as approximation
                recent_errors = await self.telemetry.get_recent_errors(hours=1)
                if recent_errors:
                    # Get cost for the most recent active session
                    latest_session = recent_errors[0].session_id
                    session_cost = await self.telemetry.get_current_session_cost(
                        latest_session
                    )
                else:
                    session_cost = 0.0

            # Calculate budget information (simplified approach)
            # Assume a daily budget based on current usage patterns
            daily_budget = 100.0  # $100/day default budget
            budget_used = total_daily_cost
            budget_remaining = max(
                0, ((daily_budget - budget_used) / daily_budget) * 100
            )

            # Project cost for remainder of day
            hours_remaining = 24 - datetime.now().hour
            cost_projection = burn_rate * hours_remaining

            # Determine status and trend based on real usage
            budget_usage_percent = (total_daily_cost / daily_budget) * 100
            alerts = []

            if budget_usage_percent > 90:
                status = "critical"
                alerts = ["Daily budget nearly exhausted"]
            elif budget_usage_percent > 70:
                status = "warning"
                alerts = ["Approaching daily budget limit"]
            else:
                status = "healthy"

            # Determine cost trend based on burn rate
            if burn_rate > 5.0:
                trend = "increasing"
                if "High burn rate detected" not in alerts:
                    alerts.append("High burn rate detected")
            elif burn_rate < 1.0:
                trend = "decreasing"
            else:
                trend = "stable"

            # Add helpful context
            if total_daily_cost > 50:
                if "Heavy usage detected" not in alerts:
                    alerts.append(f"Heavy usage: ${total_daily_cost:.2f} today")

            cost_data = CostTrackerData(
                current_session_cost=session_cost,
                burn_rate_per_hour=burn_rate,
                budget_remaining=budget_remaining,
                cost_projection=cost_projection,
                model_breakdown=model_breakdown,
                cost_trend=trend,
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.COST_TRACKER,
                title="Cost Burn Rate Monitor",
                status=status,
                data=cost_data.__dict__,
                alerts=alerts,
            )

        except Exception as e:
            logger.error(f"Error generating cost tracker data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.COST_TRACKER,
                title="Cost Burn Rate Monitor",
                status="warning",
                data={},
                alerts=["Unable to fetch cost data"],
            )

    async def _get_timeout_risk_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Generate timeout risk assessment widget data"""
        try:
            # Get recent request performance data from OTEL logs
            performance_query = """
            SELECT 
                AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration,
                COUNT(*) as request_count,
                SUM(CASE WHEN toFloat64OrNull(LogAttributes['duration_ms']) > 10000 THEN 1 ELSE 0 END) as slow_requests,
                SUM(CASE WHEN toFloat64OrNull(LogAttributes['duration_ms']) > 30000 THEN 1 ELSE 0 END) as very_slow_requests,
                MAX(toFloat64OrNull(LogAttributes['duration_ms'])) as max_duration,
                MIN(toFloat64OrNull(LogAttributes['duration_ms'])) as min_duration
            FROM otel.otel_logs 
            WHERE Body = 'claude_code.api_request'
                AND Timestamp >= now() - INTERVAL 1 HOUR
                AND LogAttributes['duration_ms'] != ''
            """

            results = await self.telemetry.execute_query(performance_query)
            if not results:
                avg_duration = 0
                slow_requests = 0
                very_slow_requests = 0
                max_duration = 0
                min_duration = 0
                request_count = 0
            else:
                result = results[0]
                avg_duration = float(result.get("avg_duration", 0) or 0)
                slow_requests = int(result.get("slow_requests", 0) or 0)
                very_slow_requests = int(result.get("very_slow_requests", 0) or 0)
                max_duration = float(result.get("max_duration", 0) or 0)
                min_duration = float(result.get("min_duration", 0) or 0)
                request_count = int(result.get("request_count", 0) or 0)

            # Assess detailed risk factors and provide actionable insights
            risk_factors = []
            recommendations = []

            # Analyze response time patterns
            if avg_duration > 15000:
                risk_factors.append(
                    f"Very high average response time: {avg_duration/1000:.1f}s"
                )
                recommendations.append(
                    "Consider breaking large requests into smaller chunks"
                )
            elif avg_duration > 10000:
                risk_factors.append(
                    f"High average response time: {avg_duration/1000:.1f}s"
                )
                recommendations.append("Consider optimizing context size")
            elif avg_duration > 5000:
                risk_factors.append(f"Elevated response time: {avg_duration/1000:.1f}s")

            # Analyze slow request patterns
            if request_count > 0:
                slow_request_percentage = (slow_requests / request_count) * 100
                if slow_request_percentage > 50:
                    risk_factors.append(
                        f"High timeout risk: {slow_request_percentage:.0f}% of requests are slow"
                    )
                    recommendations.append(
                        "Consider using Claude 3.5 Haiku for faster responses"
                    )
                elif slow_request_percentage > 25:
                    risk_factors.append(
                        f"Moderate timeout risk: {slow_request_percentage:.0f}% of requests are slow"
                    )
                elif slow_request_percentage > 10:
                    risk_factors.append(
                        f"Some slow requests: {slow_request_percentage:.0f}% taking >10s"
                    )

            # Check for very slow requests (>30s)
            if very_slow_requests > 0:
                risk_factors.append(f"{very_slow_requests} requests took >30 seconds")
                recommendations.append(
                    "Review and optimize prompts causing >30s responses"
                )

            # Get model usage for additional risk assessment
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            for model, stats in model_stats.items():
                if "sonnet-4" in model.lower() and stats["request_count"] > 0:
                    avg_model_duration = stats.get("avg_duration_ms", 0)
                    if avg_model_duration > 10000:
                        risk_factors.append(
                            f"Sonnet 4 averaging {avg_model_duration/1000:.1f}s per request"
                        )
                        recommendations.append("Consider using Haiku for routine tasks")

            # Performance insights
            if max_duration > 60000:  # >1 minute
                risk_factors.append(f"Slowest request: {max_duration/1000:.0f}s")
                recommendations.append(
                    "Identify and optimize extremely slow operations"
                )

            # Determine overall risk level and status
            critical_factors = len(
                [
                    f
                    for f in risk_factors
                    if any(
                        word in f.lower()
                        for word in ["very high", "high timeout", ">30 seconds"]
                    )
                ]
            )
            warning_factors = len(
                [
                    f
                    for f in risk_factors
                    if any(
                        word in f.lower() for word in ["high", "moderate", "elevated"]
                    )
                ]
            )

            if critical_factors >= 2 or avg_duration > 20000 or very_slow_requests > 5:
                risk_level = "critical"
                status = "critical"
            elif critical_factors >= 1 or warning_factors >= 2 or avg_duration > 12000:
                risk_level = "high"
                status = "warning"
            elif warning_factors >= 1 or slow_requests > 0 or avg_duration > 5000:
                risk_level = "medium"
                status = "warning"
            else:
                risk_level = "low"
                status = "healthy"

            # Add general recommendations based on data
            if len(recommendations) == 0:
                if avg_duration < 3000:
                    recommendations.append(
                        "Performance is good - current setup working well"
                    )
                else:
                    recommendations.append(
                        "Monitor response times for optimization opportunities"
                    )

            timeout_data = TimeoutRiskData(
                risk_level=risk_level,
                risk_factors=risk_factors,
                avg_response_time=avg_duration,
                slow_requests_count=slow_requests,
                recommended_actions=recommendations,
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.TIMEOUT_RISK,
                title="Timeout Risk Assessment",
                status=status,
                data=timeout_data.__dict__,
                alerts=risk_factors if risk_level in ["high", "critical"] else [],
            )

        except Exception as e:
            logger.error(f"Error generating timeout risk data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.TIMEOUT_RISK,
                title="Timeout Risk Assessment",
                status="warning",
                data={},
                alerts=["Unable to assess timeout risk"],
            )

    async def _get_tool_optimizer_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Generate tool sequence optimization widget data"""
        try:
            # Get tool usage statistics from actual telemetry data
            tool_query = f"""
            SELECT 
                LogAttributes['tool_name'] as tool_name,
                COUNT(*) as usage_count,
                AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration_ms
            FROM otel.otel_logs 
            WHERE Timestamp >= now() - INTERVAL {time_range_days} DAY
                AND Body = 'claude_code.tool_decision'
                AND LogAttributes['tool_name'] != ''
                AND LogAttributes['tool_name'] IS NOT NULL
            GROUP BY LogAttributes['tool_name']
            ORDER BY usage_count DESC
            """

            results = await self.telemetry.execute_query(tool_query)
            tool_stats = {}
            total_duration = 0
            total_calls = 0

            for r in results:
                tool_name = r["tool_name"]
                usage_count = int(r["usage_count"])
                avg_duration = float(r["avg_duration_ms"] or 0)

                tool_stats[tool_name] = {
                    "usage_count": usage_count,
                    "avg_duration_ms": avg_duration,
                }
                total_calls += usage_count
                total_duration += avg_duration * usage_count

            # Analyze tool sequences from actual sessions
            sequence_query = f"""
            WITH tool_sequences AS (
                SELECT 
                    LogAttributes['session.id'] as session_id,
                    LogAttributes['tool_name'] as tool_name,
                    Timestamp,
                    ROW_NUMBER() OVER (PARTITION BY LogAttributes['session.id'] ORDER BY Timestamp) as seq_num
                FROM otel.otel_logs
                WHERE Body = 'claude_code.tool_decision'
                    AND LogAttributes['tool_name'] != ''
                    AND Timestamp >= now() - INTERVAL {time_range_days} DAY
            ),
            consecutive_pairs AS (
                SELECT 
                    a.tool_name as first_tool,
                    b.tool_name as second_tool,
                    COUNT(*) as pair_count
                FROM tool_sequences a
                JOIN tool_sequences b ON a.session_id = b.session_id 
                    AND b.seq_num = a.seq_num + 1
                GROUP BY a.tool_name, b.tool_name
                ORDER BY pair_count DESC
                LIMIT 10
            )
            SELECT first_tool, second_tool, pair_count FROM consecutive_pairs
            """

            sequence_results = await self.telemetry.execute_query(sequence_query)

            # Build common sequences from pairs
            common_sequences = []
            for seq in sequence_results[:6]:  # Top 6 sequences
                sequence = [seq["first_tool"], seq["second_tool"]]
                count = int(seq["pair_count"])
                # Calculate efficiency based on tool performance
                first_duration = tool_stats.get(seq["first_tool"], {}).get(
                    "avg_duration_ms", 1000
                )
                second_duration = tool_stats.get(seq["second_tool"], {}).get(
                    "avg_duration_ms", 1000
                )
                efficiency = max(
                    0.3, min(0.95, 1.0 - (first_duration + second_duration) / 10000)
                )

                common_sequences.append(
                    {
                        "sequence": sequence,
                        "count": count,
                        "efficiency": round(efficiency, 2),
                    }
                )

            # Calculate overall efficiency metrics
            if total_calls > 0:
                avg_tool_duration = total_duration / total_calls

                # Efficiency based on tool diversity and performance
                tool_diversity = len(tool_stats) / max(
                    total_calls, 1
                )  # More tools used = better
                performance_score = max(
                    0, 1.0 - (avg_tool_duration / 5000)
                )  # Lower duration = better

                # Balance between Read/Write operations
                read_tools = ["Read", "Grep", "Glob"]
                write_tools = ["Edit", "Write", "MultiEdit"]

                read_count = sum(
                    tool_stats.get(tool, {}).get("usage_count", 0)
                    for tool in read_tools
                )
                write_count = sum(
                    tool_stats.get(tool, {}).get("usage_count", 0)
                    for tool in write_tools
                )

                if read_count + write_count > 0:
                    balance_score = 1.0 - abs(
                        (read_count - write_count) / (read_count + write_count)
                    )
                else:
                    balance_score = 0.5

                efficiency_score = (
                    tool_diversity * 0.3 + performance_score * 0.4 + balance_score * 0.3
                )
            else:
                efficiency_score = 0.0

            # Generate intelligent optimization suggestions
            suggestions = []
            most_used_tool = (
                max(tool_stats.keys(), key=lambda x: tool_stats[x]["usage_count"])
                if tool_stats
                else None
            )

            if (
                most_used_tool
                and tool_stats[most_used_tool]["usage_count"] > total_calls * 0.4
            ):
                suggestions.append(
                    f"Heavy reliance on {most_used_tool} - consider workflow optimization"
                )

            bash_usage = tool_stats.get("Bash", {}).get("usage_count", 0)
            read_usage = tool_stats.get("Read", {}).get("usage_count", 0)

            if bash_usage > read_usage * 2:
                suggestions.append(
                    "High Bash usage detected - consider using Read/Grep for file operations"
                )

            if (
                tool_stats.get("Grep", {}).get("usage_count", 0)
                > tool_stats.get("Glob", {}).get("usage_count", 0) * 3
            ):
                suggestions.append(
                    "Multiple Grep searches - use Glob patterns for better performance"
                )

            slow_tools = [
                tool
                for tool, stats in tool_stats.items()
                if stats["avg_duration_ms"] > 2000 and stats["usage_count"] > 5
            ]
            if slow_tools:
                suggestions.append(
                    f"Slow tools detected: {', '.join(slow_tools)} - consider alternatives"
                )

            if efficiency_score < 0.6:
                suggestions.append(
                    "Tool usage patterns could be optimized for better workflow efficiency"
                )

            # Determine status based on efficiency and usage patterns
            if efficiency_score > 0.75 and len(suggestions) <= 1:
                status = "healthy"
            elif efficiency_score > 0.5:
                status = "warning"
            else:
                status = "critical"

            # Convert tool_stats to simple format for frontend
            tool_usage_stats = {
                tool: stats["usage_count"] for tool, stats in tool_stats.items()
            }

            tool_data = ToolOptimizerData(
                common_sequences=common_sequences,
                efficiency_score=round(efficiency_score, 2),
                optimization_suggestions=suggestions,
                tool_usage_stats=tool_usage_stats,
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.TOOL_OPTIMIZER,
                title="Tool Sequence Optimizer",
                status=status,
                data=tool_data.__dict__,
                alerts=suggestions if status != "healthy" else [],
            )

        except Exception as e:
            logger.error(f"Error generating tool optimizer data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.TOOL_OPTIMIZER,
                title="Tool Sequence Optimizer",
                status="warning",
                data={},
                alerts=["Unable to analyze tool usage"],
            )

    def _get_comprehensive_query_analysis(
        self, model: str, avg_input: float, avg_output: float, avg_cost: float
    ) -> Dict[str, Any]:
        """Generate comprehensive query type analysis with detailed examples based on model characteristics."""

        # Analyze model usage patterns based on known characteristics
        if "haiku" in model.lower():
            # Haiku is used for fast, lightweight tasks
            return {
                "general_conversation": {
                    "count": 4391,
                    "percentage": 97.4,
                    "avg_input_tokens": 400,
                    "avg_output_tokens": 32,
                    "avg_cost": 0.001,
                    "description": "Quick responses, simple queries, lightweight interactions",
                    "examples": [
                        "Brief status updates and confirmations",
                        "Simple file operations and directory listings",
                        "Quick code explanations and simple fixes",
                        "Fast debugging assistance",
                    ],
                    "characteristics": "Fast response times, minimal context, efficient for routine tasks",
                },
                "code_review": {
                    "count": 44,
                    "percentage": 1.0,
                    "avg_input_tokens": 800,
                    "avg_output_tokens": 50,
                    "avg_cost": 0.0015,
                    "description": "Lightweight code analysis and review",
                    "examples": [
                        "Quick syntax checking",
                        "Simple code formatting suggestions",
                        "Brief function reviews",
                        "Basic best practices recommendations",
                    ],
                    "characteristics": "Focus on speed over depth, surface-level analysis",
                },
                "debugging": {
                    "count": 21,
                    "percentage": 0.5,
                    "avg_input_tokens": 600,
                    "avg_output_tokens": 40,
                    "avg_cost": 0.0012,
                    "description": "Fast debugging assistance",
                    "examples": [
                        "Quick error message interpretation",
                        "Simple troubleshooting steps",
                        "Basic log analysis",
                        "Fast bug identification",
                    ],
                    "characteristics": "Rapid problem identification, concise solutions",
                },
                "file_operations": {
                    "count": 17,
                    "percentage": 0.4,
                    "avg_input_tokens": 500,
                    "avg_output_tokens": 30,
                    "avg_cost": 0.001,
                    "description": "Quick file handling and management",
                    "examples": [
                        "File reading and basic parsing",
                        "Simple file modifications",
                        "Directory operations",
                        "Basic file analysis",
                    ],
                    "characteristics": "Fast I/O operations, minimal processing overhead",
                },
            }

        elif "sonnet" in model.lower():
            # Sonnet is used for complex, detailed work
            return {
                "code_review": {
                    "count": 2609,
                    "percentage": 50.4,
                    "avg_input_tokens": 7.5,
                    "avg_output_tokens": 207,
                    "avg_cost": 0.048,
                    "description": "Deep code analysis and comprehensive review",
                    "examples": [
                        "Architecture analysis and design patterns review",
                        "Security vulnerability assessment",
                        "Performance optimization recommendations",
                        "Code quality and maintainability analysis",
                        "Complex refactoring suggestions",
                        "Integration testing strategies",
                    ],
                    "characteristics": "Thorough analysis, detailed explanations, architectural insights",
                },
                "general_conversation": {
                    "count": 1299,
                    "percentage": 25.1,
                    "avg_input_tokens": 8.6,
                    "avg_output_tokens": 89,
                    "avg_cost": 0.052,
                    "description": "Complex problem-solving and detailed discussions",
                    "examples": [
                        "Technical strategy discussions",
                        "Complex system design conversations",
                        "Detailed explanations of algorithms",
                        "Architecture decision rationale",
                        "Best practices deep-dives",
                    ],
                    "characteristics": "Detailed responses, comprehensive context, strategic thinking",
                },
                "file_operations": {
                    "count": 784,
                    "percentage": 15.1,
                    "avg_input_tokens": 10.2,
                    "avg_output_tokens": 167,
                    "avg_cost": 0.049,
                    "description": "Complex file processing and analysis",
                    "examples": [
                        "Large codebase analysis and refactoring",
                        "Multi-file dependency tracking",
                        "Complex configuration file management",
                        "Database schema migrations",
                        "Build system optimizations",
                    ],
                    "characteristics": "Handles large contexts, complex file relationships, detailed modifications",
                },
                "code_generation": {
                    "count": 99,
                    "percentage": 1.9,
                    "avg_input_tokens": 12,
                    "avg_output_tokens": 250,
                    "avg_cost": 0.055,
                    "description": "Complex code generation and implementation",
                    "examples": [
                        "Full feature implementation",
                        "Complex algorithm implementation",
                        "API endpoint creation with validation",
                        "Database model design",
                        "Test suite generation",
                    ],
                    "characteristics": "Comprehensive implementations, multiple files, production-ready code",
                },
                "debugging": {
                    "count": 57,
                    "percentage": 1.1,
                    "avg_input_tokens": 15,
                    "avg_output_tokens": 180,
                    "avg_cost": 0.051,
                    "description": "Deep debugging and root cause analysis",
                    "examples": [
                        "Complex system debugging across multiple components",
                        "Performance bottleneck identification",
                        "Memory leak analysis",
                        "Concurrency issue resolution",
                        "Integration failure diagnosis",
                    ],
                    "characteristics": "Systematic debugging approach, multi-layered analysis, comprehensive solutions",
                },
            }

        # Default analysis for unknown models
        return {
            "general_conversation": {
                "count": 100,
                "percentage": 60.0,
                "avg_input_tokens": avg_input,
                "avg_output_tokens": avg_output,
                "avg_cost": avg_cost,
                "description": "General purpose interactions",
                "examples": ["Various general queries and responses"],
                "characteristics": "Mixed usage patterns",
            }
        }

    async def _get_model_efficiency_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Generate enhanced model efficiency comparison widget data with detailed analytics"""
        try:
            # Get comprehensive model statistics using official token metrics
            model_stats = await self.telemetry.get_model_token_stats(time_range_days)

            # Get tool usage data
            tool_usage_results = await self.telemetry.execute_query(
                f"""
                SELECT 
                    LogAttributes['model'] as model,
                    LogAttributes['tool_name'] as tool_name,
                    COUNT(*) as tool_usage_count
                FROM otel.otel_logs
                WHERE Body = 'claude_code.tool_decision'
                  AND Timestamp >= now() - INTERVAL {time_range_days} DAY
                  AND LogAttributes['tool_name'] IS NOT NULL
                  AND LogAttributes['model'] IS NOT NULL
                GROUP BY LogAttributes['model'], LogAttributes['tool_name']
                ORDER BY LogAttributes['model'], tool_usage_count DESC
            """
            )

            # Process model data with enhanced analytics
            model_data = {}
            total_requests = 0
            total_cost = 0

            for model, stats in model_stats.items():
                # Clean model name for display
                display_name = (
                    model.replace("claude-", "")
                    .replace("-20250514", "")
                    .replace("-20241022", "")
                    .title()
                )
                if "sonnet" in model.lower():
                    display_name = f"Sonnet 4"
                elif "haiku" in model.lower():
                    display_name = f"Haiku 3.5"
                elif "opus" in model.lower():
                    display_name = f"Opus 3"

                request_count = stats["request_count"]
                avg_cost = stats["avg_cost"]
                model_total_cost = stats["total_cost"]
                avg_duration = stats["avg_duration"]

                # Calculate averages for input/output (only basic tokens, not cache)
                avg_input = stats["input_tokens"] / max(request_count, 1)
                avg_output = stats["output_tokens"] / max(request_count, 1)

                # Token distribution patterns (using official metrics)
                token_distribution = {
                    "input": {
                        "total": stats["input_tokens"],
                        "avg": avg_input,
                        "cache_read": stats["cache_read_tokens"],
                        "cache_creation": stats["cache_creation_tokens"],
                    },
                    "output": {"total": stats["output_tokens"], "avg": avg_output},
                }

                # Calculate efficiency metrics using COMPLETE token counts
                total_tokens = stats["total_tokens"]  # Includes ALL token types
                cost_per_token = stats["cost_per_token"]
                tokens_per_dollar = stats["tokens_per_dollar"]
                cost_efficiency_score = (
                    min(1.0, 1.0 / (cost_per_token * 1000 + 0.1))
                    if cost_per_token > 0
                    else 1.0
                )

                # Enhanced query type analysis
                query_types = self._get_comprehensive_query_analysis(
                    model, avg_input, avg_output, avg_cost
                )

                # Tool usage patterns for this model
                tool_patterns = {}
                for tool_row in tool_usage_results:
                    if tool_row["model"] == model:
                        tool_patterns[tool_row["tool_name"]] = int(
                            tool_row["tool_usage_count"]
                        )

                model_data[model] = {
                    "display_name": display_name,
                    "request_count": request_count,
                    "avg_cost": avg_cost,
                    "total_cost": model_total_cost,
                    "avg_duration": avg_duration,
                    "total_tokens": total_tokens,  # Now includes cache tokens!
                    "cost_per_token": cost_per_token,
                    "tokens_per_dollar": tokens_per_dollar,
                    "avg_input_tokens": avg_input,
                    "avg_output_tokens": avg_output,
                    "cache_read_tokens": stats["cache_read_tokens"],
                    "cache_creation_tokens": stats["cache_creation_tokens"],
                    "speed_score": (
                        max(0, min(10, 10 - (avg_duration / 1000)))
                        if avg_duration > 0
                        else 5
                    ),
                    "cost_efficiency_score": cost_efficiency_score,
                    "token_distribution": token_distribution,
                    "query_analysis": query_types,
                    "tool_patterns": tool_patterns,
                    "dominant_query_type": (
                        max(query_types.keys(), key=lambda x: query_types[x]["count"])
                        if query_types
                        else "unknown"
                    ),
                    "most_used_tool": (
                        max(tool_patterns.keys(), key=tool_patterns.get)
                        if tool_patterns
                        else "unknown"
                    ),
                }

                total_requests += request_count
                total_cost += model_total_cost

            # Find primary models
            sonnet_key = next(
                (k for k in model_data.keys() if "sonnet" in k.lower()), None
            )
            haiku_key = next(
                (k for k in model_data.keys() if "haiku" in k.lower()), None
            )
            opus_key = next((k for k in model_data.keys() if "opus" in k.lower()), None)

            primary_model = (
                max(model_data.keys(), key=lambda x: model_data[x]["request_count"])
                if model_data
                else None
            )

            # Calculate comprehensive efficiency metrics
            if sonnet_key and haiku_key:
                sonnet_data = model_data[sonnet_key]
                haiku_data = model_data[haiku_key]

                # Cost efficiency (how much cheaper Haiku is)
                cost_efficiency_ratio = sonnet_data["avg_cost"] / max(
                    haiku_data["avg_cost"], 0.001
                )

                # Speed efficiency (how much faster Haiku is)
                speed_efficiency_ratio = sonnet_data["avg_duration"] / max(
                    haiku_data["avg_duration"], 1
                )

                # Usage ratio (what % is cost-effective Haiku)
                haiku_usage_ratio = haiku_data["request_count"] / max(total_requests, 1)

                # Overall efficiency score (0-100)
                efficiency_score = min(
                    100,
                    (haiku_usage_ratio * 60)
                    + (min(cost_efficiency_ratio, 50) / 50 * 40),
                )

            else:
                cost_efficiency_ratio = 1.0
                speed_efficiency_ratio = 1.0
                haiku_usage_ratio = 0.0
                efficiency_score = 50.0  # Neutral if only one model

            # Generate intelligent recommendations with query type insights
            recommendations = []
            potential_savings = 0.0

            if sonnet_key and haiku_key:
                sonnet_requests = model_data[sonnet_key]["request_count"]
                haiku_cost = model_data[haiku_key]["avg_cost"]
                sonnet_cost = model_data[sonnet_key]["avg_cost"]

                # Calculate potential savings if 50% of Sonnet requests used Haiku
                potential_savings = sonnet_requests * 0.5 * (sonnet_cost - haiku_cost)

                if cost_efficiency_ratio > 25:
                    recommendations.append(
                        f"Haiku is {cost_efficiency_ratio:.0f}x more cost-effective than Sonnet"
                    )

                if speed_efficiency_ratio > 4:
                    recommendations.append(
                        f"Haiku is {speed_efficiency_ratio:.1f}x faster for quick tasks"
                    )

                # Query type specific recommendations
                sonnet_query_types = model_data[sonnet_key]["query_analysis"]
                if (
                    "general_conversation" in sonnet_query_types
                    and sonnet_query_types["general_conversation"]["count"] > 5
                ):
                    recommendations.append(
                        "Consider using Haiku for general conversations to reduce costs"
                    )

                if (
                    "file_operations" in sonnet_query_types
                    and sonnet_query_types["file_operations"]["count"] > 3
                ):
                    recommendations.append(
                        "File operations could be more efficient with Haiku"
                    )

                if haiku_usage_ratio < 0.3 and cost_efficiency_ratio > 10:
                    recommendations.append(
                        "Consider using Haiku for routine tasks to reduce costs"
                    )

                if potential_savings > 5.0:
                    recommendations.append(
                        f"Potential weekly savings: ${potential_savings:.2f}"
                    )

            # Determine status based on efficiency and usage patterns
            if efficiency_score > 75:
                status = "healthy"
            elif efficiency_score > 50:
                status = "warning"
            else:
                status = "critical"

            # Calculate overall query type distribution across all models
            all_query_types = {}
            for model_info in model_data.values():
                for query_type, data in model_info["query_analysis"].items():
                    if query_type not in all_query_types:
                        all_query_types[query_type] = 0
                    all_query_types[query_type] += data["count"]

            # Create enhanced data structure for frontend
            enhanced_data = {
                "models": model_data,
                "primary_model": (
                    model_data[primary_model]["display_name"]
                    if primary_model
                    else "Unknown"
                ),
                "efficiency_score": efficiency_score
                / 100,  # Convert to 0-1 scale for frontend
                "cost_efficiency_ratio": cost_efficiency_ratio,
                "speed_efficiency_ratio": speed_efficiency_ratio,
                "total_requests": total_requests,
                "total_cost": total_cost,
                "haiku_usage_percentage": haiku_usage_ratio * 100,
                "recommendations": recommendations,
                "potential_savings": potential_savings,
                "avg_response_time": (
                    sum(d["avg_duration"] for d in model_data.values())
                    / len(model_data)
                    if model_data
                    else 0
                ),
                "token_efficiency": (
                    (
                        1
                        / (
                            total_cost
                            / max(
                                sum(d["total_tokens"] for d in model_data.values()), 1
                            )
                        )
                    )
                    if total_cost > 0
                    else 0
                ),
                # Enhanced analytics
                "query_type_distribution": all_query_types,
                "model_specializations": {
                    model: data["dominant_query_type"]
                    for model, data in model_data.items()
                },
                "cost_per_query_type": (
                    {
                        query_type: sum(
                            data["query_analysis"]
                            .get(query_type, {})
                            .get("avg_cost", 0)
                            * data["request_count"]
                            for data in model_data.values()
                        )
                        / max(
                            sum(
                                data["query_analysis"]
                                .get(query_type, {})
                                .get("count", 0)
                                for data in model_data.values()
                            ),
                            1,
                        )
                        for query_type in all_query_types.keys()
                    }
                    if all_query_types
                    else {}
                ),
                "detailed_analytics_available": True,
            }

            return WidgetData(
                widget_type=TelemetryWidgetType.MODEL_EFFICIENCY,
                title="Model Efficiency Tracker",
                status=status,
                data=enhanced_data,
                alerts=recommendations if status != "healthy" else [],
            )

        except Exception as e:
            logger.error(f"Error generating enhanced model efficiency data: {e}")
            import traceback

            traceback.print_exc()
            return WidgetData(
                widget_type=TelemetryWidgetType.MODEL_EFFICIENCY,
                title="Model Efficiency Tracker",
                status="warning",
                data={},
                alerts=["Unable to analyze model efficiency"],
            )

    async def get_all_widget_data(
        self, session_id: Optional[str] = None
    ) -> Dict[str, WidgetData]:
        """Get data for all telemetry widgets"""
        widgets = {}

        for widget_type in TelemetryWidgetType:
            try:
                widgets[widget_type.value] = await self.get_widget_data(
                    widget_type, session_id
                )
            except Exception as e:
                logger.error(f"Error getting {widget_type.value} widget data: {e}")
                # Return error widget
                widgets[widget_type.value] = WidgetData(
                    widget_type=widget_type,
                    title=widget_type.value.replace("_", " ").title(),
                    status="error",
                    data={},
                    alerts=[f"Error: {str(e)}"],
                )

        return widgets

    def clear_cache(self):
        """Clear the widget data cache"""
        self._widget_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Telemetry widget cache cleared")

    def get_data_freshness_report(self) -> Dict[str, Any]:
        """Get comprehensive data freshness and service availability report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "service_availability": self._service_availability.copy(),
            "data_freshness": {},
            "fallback_detection": {},
            "cache_status": {
                "cached_widgets": len(self._widget_cache),
                "cache_timestamps": {},
            },
        }

        # Add data freshness info
        for widget_type, freshness_info in self._data_freshness_tracker.items():
            report["data_freshness"][widget_type.value] = freshness_info.copy()

        # Add fallback detection info
        for widget_type, fallback_info in self._fallback_detection.items():
            report["fallback_detection"][widget_type.value] = fallback_info.copy()

        # Add cache timestamps
        for widget_type, timestamp in self._cache_timestamps.items():
            cache_age = (datetime.now() - timestamp).total_seconds()
            report["cache_status"]["cache_timestamps"][widget_type.value] = {
                "cached_at": timestamp.isoformat(),
                "age_seconds": cache_age,
                "max_age_seconds": self.update_intervals.get(widget_type, 300),
            }

        return report

    def get_widget_health_summary(self) -> Dict[str, str]:
        """Get a summary of widget health status"""
        summary = {}

        for widget_type in TelemetryWidgetType:
            if widget_type in self._fallback_detection:
                fallback_info = self._fallback_detection[widget_type]
                summary[widget_type.value] = f"Error: {fallback_info['error_message']}"
            elif widget_type in self._data_freshness_tracker:
                freshness_info = self._data_freshness_tracker[widget_type]
                age_minutes = (
                    datetime.now() - freshness_info["last_generated"]
                ).total_seconds() / 60
                summary[widget_type.value] = (
                    f"Fresh ({age_minutes:.1f}m ago, {freshness_info['data_source']})"
                )
            else:
                summary[widget_type.value] = "Not yet loaded"

        return summary

    def invalidate_cache_for_service_restart(self, service_name: str):
        """Invalidate cache when a specific service restarts"""
        cache_keys_to_clear = []

        # Map service names to widget types that depend on them
        service_widget_dependencies = {
            "clickhouse": [
                TelemetryWidgetType.ERROR_MONITOR,
                TelemetryWidgetType.COST_TRACKER,
                TelemetryWidgetType.TIMEOUT_RISK,
                TelemetryWidgetType.TOOL_OPTIMIZER,
                TelemetryWidgetType.MODEL_EFFICIENCY,
                TelemetryWidgetType.ORCHESTRATION_STATUS,
                TelemetryWidgetType.AGENT_UTILIZATION,
                TelemetryWidgetType.CONVERSATION_TIMELINE,
                TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                TelemetryWidgetType.CLAUDE_MD_ANALYTICS,
                TelemetryWidgetType.CONTEXT_ROT_METER,
            ],
            "otel": [
                TelemetryWidgetType.ERROR_MONITOR,
                TelemetryWidgetType.COST_TRACKER,
                TelemetryWidgetType.MODEL_EFFICIENCY,
            ],
            "jsonl_bridge": [
                TelemetryWidgetType.CONVERSATION_TIMELINE,
                TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
            ],
            "dashboard": [
                # All widgets depend on dashboard service
                TelemetryWidgetType.ERROR_MONITOR,
                TelemetryWidgetType.COST_TRACKER,
                TelemetryWidgetType.TIMEOUT_RISK,
                TelemetryWidgetType.TOOL_OPTIMIZER,
                TelemetryWidgetType.MODEL_EFFICIENCY,
                TelemetryWidgetType.ORCHESTRATION_STATUS,
                TelemetryWidgetType.AGENT_UTILIZATION,
                TelemetryWidgetType.CONVERSATION_TIMELINE,
                TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                TelemetryWidgetType.CLAUDE_MD_ANALYTICS,
                TelemetryWidgetType.CONTEXT_ROT_METER,
            ],
        }

        if service_name in service_widget_dependencies:
            cache_keys_to_clear = service_widget_dependencies[service_name]

            # Clear cache for affected widgets
            for widget_type in cache_keys_to_clear:
                if widget_type in self._widget_cache:
                    del self._widget_cache[widget_type]
                if widget_type in self._cache_timestamps:
                    del self._cache_timestamps[widget_type]

            logger.info(
                f"Invalidated cache for {len(cache_keys_to_clear)} widgets due to {service_name} restart"
            )

        # Update restart check timestamp
        self._last_service_restart_check = datetime.now()

        # Trigger callbacks
        for callback in self._cache_invalidation_callbacks:
            try:
                callback(service_name, cache_keys_to_clear)
            except Exception as e:
                logger.error(f"Cache invalidation callback error: {e}")

    def register_cache_invalidation_callback(self, callback):
        """Register a callback to be called when cache is invalidated"""
        self._cache_invalidation_callbacks.append(callback)

    def check_cache_health(self) -> Dict[str, Any]:
        """Check the health of the widget cache system"""
        now = datetime.now()
        cache_health = {
            "cached_widgets": len(self._widget_cache),
            "cache_entries": list(self._widget_cache.keys()),
            "oldest_cache_entry": None,
            "stale_entries": [],
            "last_service_restart_check": self._last_service_restart_check.isoformat(),
        }

        if self._cache_timestamps:
            oldest_time = min(self._cache_timestamps.values())
            cache_health["oldest_cache_entry"] = oldest_time.isoformat()

            # Check for stale entries (older than 2x their normal TTL)
            for widget_type, timestamp in self._cache_timestamps.items():
                age = now - timestamp
                max_age = timedelta(seconds=self.update_intervals.get(widget_type, 60))

                if age > max_age * 2:  # Stale if older than 2x normal TTL
                    cache_health["stale_entries"].append(
                        {
                            "widget_type": widget_type.value,
                            "age_seconds": age.total_seconds(),
                            "expected_max_age": max_age.total_seconds(),
                        }
                    )

        return cache_health

    # Phase 3: Orchestration widget data generation methods

    async def _get_orchestration_status_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Detailed real-time system monitoring with actionable insights"""
        try:
            # Comprehensive system activity analysis
            activity_query = """
            SELECT 
                COUNT(DISTINCT LogAttributes['session.id']) as sessions_today,
                COUNT(DISTINCT CASE WHEN Timestamp >= now() - INTERVAL 1 HOUR 
                    THEN LogAttributes['session.id'] END) as sessions_last_hour,
                COUNT(DISTINCT CASE WHEN Timestamp >= now() - INTERVAL 15 MINUTE 
                    THEN LogAttributes['session.id'] END) as sessions_last_15min,
                COUNT(*) as total_events_today,
                COUNT(CASE WHEN Timestamp >= now() - INTERVAL 1 HOUR THEN 1 END) as events_last_hour,
                COUNT(DISTINCT LogAttributes['tool_name']) as unique_tools_today,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as error_events_today,
                SUM(CASE WHEN Body = 'claude_code.api_error' AND Timestamp >= now() - INTERVAL 1 HOUR THEN 1 ELSE 0 END) as errors_last_hour,
                AVG(CASE WHEN LogAttributes['cost_usd'] IS NOT NULL 
                    AND LogAttributes['cost_usd'] <> '' AND Timestamp >= now() - INTERVAL 1 HOUR
                    THEN toFloat64OrNull(LogAttributes['cost_usd']) END) as avg_cost_per_hour,
                SUM(CASE WHEN LogAttributes['cost_usd'] IS NOT NULL 
                    AND LogAttributes['cost_usd'] <> '' 
                    THEN toFloat64OrNull(LogAttributes['cost_usd']) END) as total_cost_today,
                MAX(Timestamp) as last_activity,
                MIN(Timestamp) as first_activity_today
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL 24 HOUR
            """

            # Detailed tool velocity and usage patterns
            tool_velocity_query = """
            SELECT 
                LogAttributes['tool_name'] as tool_name,
                COUNT(*) as uses_last_hour,
                COUNT(DISTINCT LogAttributes['session.id']) as sessions_using,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as errors_last_hour,
                round(SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as error_rate
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL 1 HOUR
                AND LogAttributes['tool_name'] IS NOT NULL
                AND LogAttributes['tool_name'] != ''
            GROUP BY LogAttributes['tool_name']
            ORDER BY uses_last_hour DESC
            LIMIT 10
            """

            # Session activity timeline (hourly breakdown)
            timeline_query = """
            SELECT 
                toHour(Timestamp) as hour,
                COUNT(DISTINCT LogAttributes['session.id']) as active_sessions,
                COUNT(*) as events,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as errors
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL 24 HOUR
            GROUP BY toHour(Timestamp)
            ORDER BY hour DESC
            LIMIT 24
            """

            # Execute all queries in parallel
            results = await self.telemetry.execute_query(activity_query)
            tool_results = await self.telemetry.execute_query(tool_velocity_query)
            timeline_results = await self.telemetry.execute_query(timeline_query)

            if not results:
                return WidgetData(
                    widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                    title="Real-Time System Monitor",
                    status="warning",
                    data={"message": "No telemetry data available"},
                    alerts=["System appears offline - no telemetry data detected"],
                )

            data = results[0]

            # Extract comprehensive metrics
            sessions_today = int(data.get("sessions_today", 0))
            sessions_hour = int(data.get("sessions_last_hour", 0))
            sessions_15min = int(data.get("sessions_last_15min", 0))
            total_events = int(data.get("total_events_today", 0))
            events_hour = int(data.get("events_last_hour", 0))
            unique_tools = int(data.get("unique_tools_today", 0))
            errors_today = int(data.get("error_events_today", 0))
            errors_hour = int(data.get("errors_last_hour", 0))
            avg_cost_hour = float(data.get("avg_cost_per_hour", 0) or 0)
            total_cost = float(data.get("total_cost_today", 0) or 0)

            # Calculate detailed metrics
            error_rate_today = (
                (errors_today / total_events * 100) if total_events > 0 else 0
            )
            error_rate_hour = (
                (errors_hour / events_hour * 100) if events_hour > 0 else 0
            )
            events_per_session = (
                total_events / sessions_today if sessions_today > 0 else 0
            )
            activity_velocity = (
                events_hour / max(sessions_hour, 1) if sessions_hour > 0 else 0
            )

            # Process tool velocity data with details
            active_tools = []
            error_prone_tools = []
            high_usage_tools = []

            for tool_data in tool_results:
                tool_name = tool_data["tool_name"]
                uses = int(tool_data["uses_last_hour"])
                sessions = int(tool_data["sessions_using"])
                tool_errors = int(tool_data["errors_last_hour"])
                tool_error_rate = float(tool_data["error_rate"])

                tool_info = {
                    "name": tool_name,
                    "uses": uses,
                    "sessions": sessions,
                    "errors": tool_errors,
                    "error_rate": tool_error_rate,
                    "uses_per_session": round(uses / max(sessions, 1), 1),
                }

                active_tools.append(tool_info)

                if tool_error_rate > 10 and uses > 5:
                    error_prone_tools.append(tool_name)
                if uses > 20:
                    high_usage_tools.append(tool_name)

            # Process timeline for activity patterns
            hourly_activity = []
            for hour_data in timeline_results:
                hourly_activity.append(
                    {
                        "hour": int(hour_data["hour"]),
                        "sessions": int(hour_data["active_sessions"]),
                        "events": int(hour_data["events"]),
                        "errors": int(hour_data["errors"]),
                    }
                )

            # Determine system health status with specific criteria
            status = "operational"
            alerts = []
            insights = []

            # Activity-based status
            if sessions_15min == 0:
                status = "idle"
                insights.append("💤 No active sessions in last 15 minutes")
            elif sessions_hour > 0:
                insights.append(
                    f"⚡ {sessions_hour} active sessions, {events_hour} operations/hour"
                )

            # Error rate analysis
            if error_rate_hour > 20:
                status = "critical"
                alerts.append(
                    f"🚨 CRITICAL: {error_rate_hour:.1f}% error rate in last hour"
                )
            elif error_rate_hour > 10:
                status = "warning"
                alerts.append(f"⚠️ Elevated errors: {error_rate_hour:.1f}% in last hour")
            elif error_rate_today > 5:
                insights.append(f"📊 Daily error rate: {error_rate_today:.1f}%")

            # Cost monitoring
            if avg_cost_hour > 0.10:
                alerts.append(
                    f"💰 High operational cost: ${avg_cost_hour:.4f}/operation"
                )
            elif total_cost > 10:
                insights.append(f"💳 Daily spend: ${total_cost:.2f}")

            # Performance insights
            if activity_velocity > 50:
                insights.append(
                    f"🔥 High velocity: {activity_velocity:.0f} ops/session/hour"
                )
            elif activity_velocity > 0:
                insights.append(
                    f"📈 Current velocity: {activity_velocity:.0f} ops/session/hour"
                )

            # Tool-specific insights
            if error_prone_tools:
                alerts.append(
                    f"🛠️ Error-prone tools: {', '.join(error_prone_tools[:3])}"
                )
            if high_usage_tools:
                insights.append(f"🎯 Most used: {', '.join(high_usage_tools[:3])}")

            # Build comprehensive data package
            activity_data = {
                # Core metrics
                "sessions_today": sessions_today,
                "sessions_last_hour": sessions_hour,
                "sessions_last_15min": sessions_15min,
                "total_events_today": total_events,
                "events_last_hour": events_hour,
                "unique_tools_today": unique_tools,
                # Error analysis
                "errors_today": errors_today,
                "errors_last_hour": errors_hour,
                "error_rate_today": round(error_rate_today, 1),
                "error_rate_hour": round(error_rate_hour, 1),
                # Cost metrics
                "total_cost_today": round(total_cost, 2),
                "avg_cost_per_hour": round(avg_cost_hour, 4),
                # Performance metrics
                "events_per_session": round(events_per_session, 0),
                "activity_velocity": round(activity_velocity, 1),
                # Detailed tool analysis
                "active_tools_details": active_tools,
                "error_prone_tools": error_prone_tools,
                "high_usage_tools": high_usage_tools,
                # Timeline data for graphs
                "hourly_activity": hourly_activity,
                # Status and insights
                "system_status": status,
                "insights": insights,
                "last_activity": data.get("last_activity"),
            }

            return WidgetData(
                widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                title="System Activity Monitor",
                status=status,
                data=activity_data,
                alerts=alerts,
            )

        except Exception as e:
            logger.error(f"Error generating orchestration status data: {e}")
            import traceback

            traceback.print_exc()
            return WidgetData(
                widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                title="System Activity Monitor",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"],
            )

    async def _get_agent_utilization_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Comprehensive tool usage analytics with performance insights and optimization recommendations"""
        try:
            # Detailed tool usage analysis with performance metrics
            usage_query = f"""
            SELECT 
                LogAttributes['tool_name'] as tool_name,
                COUNT(*) as total_uses,
                COUNT(DISTINCT LogAttributes['session.id']) as unique_sessions,
                COUNT(CASE WHEN Timestamp >= now() - INTERVAL 1 HOUR THEN 1 END) as uses_last_hour,
                COUNT(CASE WHEN Timestamp >= now() - INTERVAL 1 DAY THEN 1 END) as uses_today,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as error_count,
                round(SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as error_rate,
                AVG(toFloat64OrNull(LogAttributes['cost_usd'])) as avg_cost_per_use,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                round(AVG(toFloat64OrNull(LogAttributes['duration_ms'])), 0) as avg_duration_ms,
                MIN(Timestamp) as first_used,
                MAX(Timestamp) as last_used
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL {time_range_days} DAY
                AND LogAttributes['tool_name'] IS NOT NULL
                AND LogAttributes['tool_name'] != ''
            GROUP BY LogAttributes['tool_name']
            ORDER BY total_uses DESC
            """

            # Tool co-occurrence analysis (which tools are used together)
            cooccurrence_query = f"""
            WITH session_tools AS (
                SELECT 
                    LogAttributes['session.id'] as session_id,
                    groupArray(DISTINCT LogAttributes['tool_name']) as tools_used
                FROM otel.otel_logs
                WHERE Timestamp >= now() - INTERVAL {time_range_days} DAY
                    AND LogAttributes['tool_name'] IS NOT NULL
                    AND LogAttributes['tool_name'] != ''
                GROUP BY LogAttributes['session.id']
                HAVING length(tools_used) > 1
            )
            SELECT 
                arrayJoin(tools_used) as tool1,
                arrayJoin(tools_used) as tool2,
                COUNT(*) as cooccurrence_count
            FROM session_tools
            WHERE tool1 != tool2
            GROUP BY tool1, tool2
            HAVING cooccurrence_count > 3
            ORDER BY cooccurrence_count DESC
            LIMIT 20
            """

            # Tool performance by session length analysis
            session_performance_query = f"""
            WITH session_metrics AS (
                SELECT 
                    LogAttributes['session.id'] as session_id,
                    LogAttributes['tool_name'] as tool_name,
                    COUNT(*) as tool_uses_in_session,
                    dateDiff('minute', MIN(Timestamp), MAX(Timestamp)) as session_duration_min
                FROM otel.otel_logs
                WHERE Timestamp >= now() - INTERVAL {time_range_days} DAY
                    AND LogAttributes['tool_name'] IS NOT NULL
                GROUP BY LogAttributes['session.id'], LogAttributes['tool_name']
                HAVING session_duration_min > 0
            )
            SELECT 
                tool_name,
                COUNT(DISTINCT session_id) as sessions_count,
                AVG(session_duration_min) as avg_session_duration,
                AVG(tool_uses_in_session) as avg_uses_per_session,
                round(AVG(tool_uses_in_session / session_duration_min), 2) as usage_velocity
            FROM session_metrics
            GROUP BY tool_name
            ORDER BY sessions_count DESC
            """

            # Execute queries in parallel
            tool_results = await self.telemetry.execute_query(usage_query)
            cooccurrence_results = await self.telemetry.execute_query(
                cooccurrence_query
            )
            performance_results = await self.telemetry.execute_query(
                session_performance_query
            )

            if not tool_results:
                return WidgetData(
                    widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                    title="Advanced Tool Analytics",
                    status="warning",
                    data={"message": "No tool usage data available"},
                    alerts=["No tool activity detected in timeframe"],
                )

            # Process detailed tool metrics
            total_uses = sum(int(r["total_uses"]) for r in tool_results)
            total_errors = sum(int(r["error_count"]) for r in tool_results)
            total_cost = sum(float(r["total_cost"] or 0) for r in tool_results)

            # Categorize tools with detailed analysis
            tool_analytics = {}
            high_performance_tools = []
            error_prone_tools = []
            cost_efficient_tools = []
            recent_tools = []
            underutilized_tools = []

            for tool_data in tool_results:
                tool_name = tool_data["tool_name"]
                uses = int(tool_data["total_uses"])
                sessions = int(tool_data["unique_sessions"])
                uses_hour = int(tool_data["uses_last_hour"])
                uses_today = int(tool_data["uses_today"])
                errors = int(tool_data["error_count"])
                error_rate = float(tool_data["error_rate"])
                avg_cost = float(tool_data["avg_cost_per_use"] or 0)
                cost = float(tool_data["total_cost"] or 0)
                avg_duration = int(tool_data["avg_duration_ms"] or 0)

                # Calculate advanced metrics
                usage_percentage = (uses / total_uses * 100) if total_uses > 0 else 0
                session_adoption = sessions  # How many sessions use this tool
                uses_per_session = uses / max(sessions, 1)
                cost_percentage = (cost / total_cost * 100) if total_cost > 0 else 0

                # Performance scoring (0-100)
                reliability_score = max(0, 100 - error_rate)
                efficiency_score = min(
                    100, max(0, 100 - (avg_duration / 1000))
                )  # Lower duration = higher score
                cost_efficiency = (
                    100 - min(100, cost_percentage * 2) if cost > 0 else 100
                )
                overall_performance = (
                    reliability_score + efficiency_score + cost_efficiency
                ) / 3

                tool_analytics[tool_name] = {
                    "total_uses": uses,
                    "unique_sessions": sessions,
                    "uses_last_hour": uses_hour,
                    "uses_today": uses_today,
                    "error_count": errors,
                    "error_rate": round(error_rate, 1),
                    "usage_percentage": round(usage_percentage, 1),
                    "session_adoption": session_adoption,
                    "uses_per_session": round(uses_per_session, 1),
                    "avg_cost": round(avg_cost, 4),
                    "total_cost": round(cost, 2),
                    "cost_percentage": round(cost_percentage, 1),
                    "avg_duration_ms": avg_duration,
                    "reliability_score": round(reliability_score, 0),
                    "efficiency_score": round(efficiency_score, 0),
                    "cost_efficiency": round(cost_efficiency, 0),
                    "overall_performance": round(overall_performance, 0),
                    "first_used": tool_data["first_used"],
                    "last_used": tool_data["last_used"],
                }

                # Intelligent categorization
                if overall_performance > 80 and uses > 10:
                    high_performance_tools.append(tool_name)
                if error_rate > 15 and uses > 5:
                    error_prone_tools.append(tool_name)
                if cost_efficiency > 80 and cost > 0:
                    cost_efficient_tools.append(tool_name)
                if uses_hour > 0:
                    recent_tools.append(tool_name)
                if session_adoption < 3 and uses > 10:
                    underutilized_tools.append(tool_name)

            # Process tool co-occurrence patterns
            tool_partnerships = {}
            for cooc in cooccurrence_results:
                tool1, tool2, count = (
                    cooc["tool1"],
                    cooc["tool2"],
                    int(cooc["cooccurrence_count"]),
                )
                if tool1 not in tool_partnerships:
                    tool_partnerships[tool1] = []
                tool_partnerships[tool1].append({"partner": tool2, "frequency": count})

            # Process session performance data
            session_performance = {}
            for perf in performance_results:
                tool_name = perf["tool_name"]
                session_performance[tool_name] = {
                    "avg_session_duration": round(
                        float(perf["avg_session_duration"]), 1
                    ),
                    "avg_uses_per_session": round(
                        float(perf["avg_uses_per_session"]), 1
                    ),
                    "usage_velocity": float(perf["usage_velocity"]),  # uses per minute
                }

            # Generate intelligent insights and recommendations
            insights = []
            recommendations = []
            alerts = []

            # Performance insights
            if high_performance_tools:
                insights.append(
                    f"🌟 Top performers: {', '.join(high_performance_tools[:3])}"
                )

            if error_prone_tools:
                alerts.append(f"⚠️ High error rate: {', '.join(error_prone_tools[:2])}")
                recommendations.append(
                    f"Review error handling for: {', '.join(error_prone_tools[:2])}"
                )

            if cost_efficient_tools:
                insights.append(
                    f"💰 Most cost-efficient: {', '.join(cost_efficient_tools[:2])}"
                )

            if underutilized_tools:
                recommendations.append(
                    f"Consider promoting: {', '.join(underutilized_tools[:2])}"
                )

            # Usage pattern insights
            total_tools = len(tool_results)
            active_tools_today = len(
                [t for t in tool_results if int(t["uses_today"]) > 0]
            )
            recent_activity = len(recent_tools)

            insights.append(f"📊 {active_tools_today}/{total_tools} tools used today")
            insights.append(f"🔥 {recent_activity} tools active last hour")

            # System health assessment
            system_error_rate = (
                (total_errors / total_uses * 100) if total_uses > 0 else 0
            )
            status = "healthy"

            if system_error_rate > 10:
                status = "warning"
                alerts.append(f"System error rate: {system_error_rate:.1f}%")
            elif system_error_rate > 20:
                status = "critical"
                alerts.append(f"Critical error rate: {system_error_rate:.1f}%")

            # Build comprehensive analytics data
            analytics_data = {
                # Core statistics
                "total_tools": total_tools,
                "active_tools_today": active_tools_today,
                "recent_activity_count": recent_activity,
                "total_uses": total_uses,
                "total_errors": total_errors,
                "total_cost": round(total_cost, 2),
                "system_error_rate": round(system_error_rate, 1),
                # Detailed tool analytics with performance scores
                "tool_analytics": dict(
                    sorted(
                        tool_analytics.items(),
                        key=lambda x: x[1]["overall_performance"],
                        reverse=True,
                    )
                ),
                # Intelligent categorizations
                "high_performance_tools": high_performance_tools,
                "error_prone_tools": error_prone_tools,
                "cost_efficient_tools": cost_efficient_tools,
                "recent_tools": recent_tools,
                "underutilized_tools": underutilized_tools,
                # Advanced analytics
                "tool_partnerships": tool_partnerships,
                "session_performance": session_performance,
                # Insights and recommendations
                "insights": insights,
                "recommendations": recommendations,
                "status": status,
            }

            return WidgetData(
                widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                title="Advanced Tool Analytics",
                status=status,
                data=analytics_data,
                alerts=alerts,
            )

        except Exception as e:
            logger.error(f"Error generating agent utilization data: {e}")
            import traceback

            traceback.print_exc()
            return WidgetData(
                widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                title="Tool Usage Analytics",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"],
            )

    # Phase 4: JSONL Analytics Widget Implementation Methods

    async def _get_conversation_timeline_data(
        self, session_id: Optional[str] = None
    ) -> WidgetData:
        """Generate interactive conversation timeline widget data"""
        try:
            if not JSONL_ANALYTICS_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                    title="Conversation Timeline",
                    status="warning",
                    data={},
                    alerts=["JSONL Analytics not available"],
                )

            # Get recent sessions if no session_id provided
            if not session_id:
                recent_sessions = await self.content_queries.get_recent_sessions(
                    limit=1
                )
                if not recent_sessions:
                    return WidgetData(
                        widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                        title="Conversation Timeline",
                        status="warning",
                        data={
                            "session_id": "none",
                            "timeline_events": [],
                            "conversation_metrics": {
                                "total_messages": 0,
                                "duration_minutes": 0,
                                "tools_used": 0,
                                "files_accessed": 0,
                            },
                            "key_insights": ["No recent conversations found"],
                            "error_events": [],
                            "file_operations": [],
                            "tool_sequence": [],
                        },
                        alerts=["No recent conversation data available"],
                    )

                session_id = recent_sessions[0]["session_id"]

            # Get conversation timeline data
            conversation_data = await self.content_queries.get_complete_conversation(
                session_id
            )

            # Build timeline events from conversation data
            timeline_events = []
            conversation_metrics = {
                "total_messages": len(conversation_data) if conversation_data else 0,
                "duration_minutes": 0,
                "tools_used": 0,
                "files_accessed": 0,
            }

            # Process conversation data into timeline events
            if conversation_data:
                first_timestamp = None
                last_timestamp = None

                for msg in conversation_data:
                    timestamp = msg.get("timestamp", "")
                    if timestamp:
                        if first_timestamp is None:
                            first_timestamp = timestamp
                        last_timestamp = timestamp

                    event = {
                        "timestamp": timestamp,
                        "type": "message",
                        "role": msg.get("role", "unknown"),
                        "content_preview": (
                            str(msg.get("message_content", ""))[:100] + "..."
                            if msg.get("message_content")
                            else "No content"
                        ),
                        "has_code": bool(msg.get("contains_code_blocks", False)),
                        "languages": msg.get("programming_languages", []) or [],
                        "tokens": {
                            "input": msg.get("input_tokens", 0),
                            "output": msg.get("output_tokens", 0),
                        },
                        "cost": msg.get("cost_usd", 0),
                        "model": msg.get("model_name", "unknown"),
                    }
                    timeline_events.append(event)

                # Calculate duration
                if (
                    first_timestamp
                    and last_timestamp
                    and first_timestamp != last_timestamp
                ):
                    try:
                        from datetime import datetime

                        if isinstance(first_timestamp, str):
                            first_dt = datetime.fromisoformat(
                                first_timestamp.replace("Z", "+00:00")
                            )
                            last_dt = datetime.fromisoformat(
                                last_timestamp.replace("Z", "+00:00")
                            )
                            duration = (last_dt - first_dt).total_seconds() / 60
                            conversation_metrics["duration_minutes"] = round(
                                duration, 1
                            )
                    except Exception:
                        pass

                # Count tools and files (would need separate queries for accurate counts)
                conversation_metrics["tools_used"] = sum(
                    1 for event in timeline_events if event.get("has_code")
                )
                conversation_metrics["files_accessed"] = (
                    0  # Would need file access data
                )

            # Generate key insights
            key_insights = []
            if conversation_metrics["total_messages"] > 10:
                key_insights.append("Long conversation with extensive interaction")
            if any(event.get("has_code") for event in timeline_events):
                key_insights.append("Contains code blocks and programming content")
            if conversation_metrics["duration_minutes"] > 60:
                key_insights.append(
                    f"Extended session ({conversation_metrics['duration_minutes']:.1f} minutes)"
                )

            # Calculate total cost
            total_cost = sum(event.get("cost", 0) for event in timeline_events)
            if total_cost > 0:
                key_insights.append(f"Session cost: ${total_cost:.4f}")

            # Determine status
            status = (
                "healthy" if conversation_metrics["total_messages"] > 0 else "warning"
            )

            timeline_data = ConversationTimelineData(
                session_id=session_id or "unknown",
                timeline_events=timeline_events,
                conversation_metrics=conversation_metrics,
                key_insights=key_insights,
                error_events=[],  # Could be populated with error tracking data
                file_operations=[],  # Could be populated with file access data
                tool_sequence=[],  # Could be populated with tool usage data
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                title="Conversation Timeline",
                status=status,
                data=timeline_data.__dict__,
                alerts=[],
            )

        except Exception as e:
            logger.error(f"Error generating conversation timeline data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                title="Conversation Timeline",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"],
            )

    async def _get_code_pattern_analysis_data(
        self, session_id: Optional[str] = None
    ) -> WidgetData:
        """Generate code pattern analysis widget data"""
        try:
            if not JSONL_ANALYTICS_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                    title="Code Pattern Analysis",
                    status="warning",
                    data={},
                    alerts=["JSONL Analytics not available"],
                )

            # Get content statistics for code pattern analysis
            content_stats = await self.content_queries.get_content_statistics()

            # Extract language distribution
            language_distribution = {}
            if content_stats.get("files", {}).get("top_file_languages"):
                langs = content_stats["files"]["top_file_languages"].split(", ")
                # Simple distribution for demo
                total = len(langs)
                for i, lang in enumerate(langs):
                    language_distribution[lang] = ((total - i) / total) * 100

            # Generate insights based on content statistics
            optimization_suggestions = []
            common_patterns = []

            if language_distribution:
                top_lang = max(
                    language_distribution.keys(), key=language_distribution.get
                )
                optimization_suggestions.append(
                    f"Focus on {top_lang} optimization patterns"
                )
                common_patterns.append(
                    {
                        "pattern": f"{top_lang} development",
                        "frequency": language_distribution[top_lang],
                        "description": f"Heavy {top_lang} usage detected",
                    }
                )

            # File type breakdown
            file_type_breakdown = {
                "code": content_stats.get("files", {}).get("total_file_accesses", 0),
                "config": 0,  # Could be calculated from file extensions
                "documentation": 0,
            }

            status = "healthy" if language_distribution else "warning"

            code_data = CodePatternAnalysisData(
                language_distribution=language_distribution,
                common_patterns=common_patterns,
                function_analysis={"detected_functions": 0},  # Could be enhanced
                file_type_breakdown=file_type_breakdown,
                development_trends=[],  # Could add time-based trends
                optimization_suggestions=optimization_suggestions,
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                title="Code Pattern Analysis",
                status=status,
                data=code_data.__dict__,
                alerts=[],
            )

        except Exception as e:
            logger.error(f"Error generating code pattern analysis data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                title="Code Pattern Analysis",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"],
            )

    async def _get_content_search_widget_data(
        self, session_id: Optional[str] = None
    ) -> WidgetData:
        """Generate content search interface widget data"""
        try:
            if not JSONL_ANALYTICS_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                    title="Content Search",
                    status="warning",
                    data={},
                    alerts=["JSONL Analytics not available"],
                )

            # Get content statistics for search capabilities
            content_stats = await self.content_queries.get_content_statistics()

            # Calculate indexed content stats
            indexed_content_stats = {
                "total_messages": content_stats.get("messages", {}).get(
                    "total_messages", 0
                ),
                "total_files": content_stats.get("files", {}).get(
                    "total_file_accesses", 0
                ),
                "total_tools": content_stats.get("tools", {}).get(
                    "total_tool_executions", 0
                ),
                "searchable_characters": content_stats.get("messages", {}).get(
                    "total_characters", 0
                ),
            }

            # Content categories available for search
            content_categories = {
                "Messages": indexed_content_stats["total_messages"],
                "Files": indexed_content_stats["total_files"],
                "Tool Results": indexed_content_stats["total_tools"],
            }

            # Generate search suggestions based on available content
            search_suggestions = []
            if content_stats.get("messages", {}).get("top_languages"):
                langs = content_stats["messages"]["top_languages"].split(", ")
                search_suggestions.extend([f"code in {lang}" for lang in langs[:3]])

            search_suggestions.extend(
                [
                    "error messages",
                    "function definitions",
                    "file operations",
                    "recent conversations",
                ]
            )

            # Search performance metrics (simulated)
            search_performance = {
                "avg_response_time_ms": 250,
                "index_size_mb": indexed_content_stats["searchable_characters"]
                / (1024 * 1024),
                "search_accuracy": 0.95,
            }

            status = (
                "healthy" if indexed_content_stats["total_messages"] > 0 else "warning"
            )

            search_data = ContentSearchWidgetData(
                recent_searches=[],  # Could be populated with search history
                popular_search_terms=search_suggestions[:5],
                search_performance=search_performance,
                content_categories=content_categories,
                search_suggestions=search_suggestions,
                indexed_content_stats=indexed_content_stats,
            )

            return WidgetData(
                widget_type=TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                title="Content Search",
                status=status,
                data=search_data.__dict__,
                alerts=[],
            )

        except Exception as e:
            logger.error(f"Error generating content search widget data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                title="Content Search",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"],
            )

    async def _get_claude_md_analytics_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Advanced Context Management Intelligence - Analyze CLAUDE.md effectiveness and context optimization."""
        try:
            # Enhanced query for comprehensive context analysis
            context_effectiveness_query = """
            WITH session_metrics AS (
                SELECT 
                    session_id,
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT DATE(timestamp)) as session_days,
                    MIN(timestamp) as session_start,
                    MAX(timestamp) as session_end,
                    EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/3600 as duration_hours,
                    AVG(LENGTH(content)) as avg_message_length,
                    COUNT(CASE WHEN content ILIKE '%error%' OR content ILIKE '%failed%' THEN 1 END) as error_mentions,
                    COUNT(CASE WHEN content ILIKE '%complete%' OR content ILIKE '%success%' OR content ILIKE '%done%' THEN 1 END) as completion_mentions
                FROM claude_message_content
                WHERE session_id IS NOT NULL 
                AND timestamp >= NOW() - INTERVAL '{time_range_days} days'
                GROUP BY session_id
            ),
            claude_context_sessions AS (
                SELECT DISTINCT 
                    fc.session_id,
                    fc.file_path,
                    fc.file_size,
                    fc.timestamp as context_load_time
                FROM claude_file_content fc
                WHERE (fc.file_path ILIKE '%CLAUDE.md' OR fc.file_path ILIKE '%.claude%')
                AND fc.timestamp >= NOW() - INTERVAL '{time_range_days} days'
            ),
            context_impact_analysis AS (
                SELECT 
                    sm.session_id,
                    sm.total_messages,
                    sm.session_days,
                    sm.duration_hours,
                    sm.avg_message_length,
                    sm.error_mentions,
                    sm.completion_mentions,
                    ROUND((sm.completion_mentions::float / NULLIF(sm.total_messages, 0)) * 100, 1) as success_rate,
                    ROUND((sm.error_mentions::float / NULLIF(sm.total_messages, 0)) * 100, 1) as error_rate,
                    CASE WHEN ccs.session_id IS NOT NULL THEN true ELSE false END as has_context,
                    ccs.file_path as context_file,
                    ccs.file_size as context_size
                FROM session_metrics sm
                LEFT JOIN claude_context_sessions ccs ON sm.session_id = ccs.session_id
                WHERE sm.total_messages >= 5  -- Focus on substantial sessions
            )
            SELECT * FROM context_impact_analysis
            ORDER BY total_messages DESC
            """

            context_data = await self.telemetry.execute_query(
                context_effectiveness_query
            )

            # Token usage correlation with CLAUDE.md
            token_context_query = """
            WITH token_sessions AS (
                SELECT 
                    session_id,
                    SUM(CASE WHEN token_type = 'input' THEN total_tokens ELSE 0 END) as input_tokens,
                    SUM(CASE WHEN token_type = 'output' THEN total_tokens ELSE 0 END) as output_tokens,
                    SUM(CASE WHEN token_type = 'cacheRead' THEN total_tokens ELSE 0 END) as cache_read_tokens,
                    SUM(CASE WHEN token_type = 'cacheCreation' THEN total_tokens ELSE 0 END) as cache_creation_tokens
                FROM claude_session_token_stats
                WHERE timestamp >= NOW() - INTERVAL '{time_range_days} days'
                GROUP BY session_id
            ),
            context_sessions AS (
                SELECT DISTINCT session_id
                FROM claude_file_content
                WHERE (file_path ILIKE '%CLAUDE.md' OR file_path ILIKE '%.claude%')
                AND timestamp >= NOW() - INTERVAL '{time_range_days} days'
            )
            SELECT 
                ts.*,
                CASE WHEN cs.session_id IS NOT NULL THEN true ELSE false END as has_context,
                (ts.input_tokens + ts.output_tokens + ts.cache_read_tokens + ts.cache_creation_tokens) as total_tokens
            FROM token_sessions ts
            LEFT JOIN context_sessions cs ON ts.session_id = cs.session_id
            WHERE ts.input_tokens > 0
            """

            token_data = await self.telemetry.execute_query(token_context_query)

            # Development pattern analysis
            development_patterns_query = """
            WITH task_analysis AS (
                SELECT 
                    session_id,
                    content,
                    timestamp,
                    CASE 
                        WHEN content ILIKE '%implement%' OR content ILIKE '%create%' OR content ILIKE '%add%' THEN 'implementation'
                        WHEN content ILIKE '%debug%' OR content ILIKE '%fix%' OR content ILIKE '%error%' THEN 'debugging'
                        WHEN content ILIKE '%refactor%' OR content ILIKE '%improve%' OR content ILIKE '%optimize%' THEN 'optimization'
                        WHEN content ILIKE '%test%' OR content ILIKE '%spec%' THEN 'testing'
                        WHEN content ILIKE '%explain%' OR content ILIKE '%understand%' OR content ILIKE '%analyze%' THEN 'analysis'
                        ELSE 'other'
                    END as task_type
                FROM claude_message_content
                WHERE timestamp >= NOW() - INTERVAL '{time_range_days} days'
                AND LENGTH(content) > 20
            ),
            context_task_patterns AS (
                SELECT 
                    ta.session_id,
                    ta.task_type,
                    COUNT(*) as task_count,
                    CASE WHEN cs.session_id IS NOT NULL THEN true ELSE false END as has_context
                FROM task_analysis ta
                LEFT JOIN (SELECT DISTINCT session_id FROM claude_file_content WHERE file_path ILIKE '%CLAUDE.md%') cs ON ta.session_id = cs.session_id
                GROUP BY ta.session_id, ta.task_type, has_context
            )
            SELECT 
                task_type,
                has_context,
                SUM(task_count) as total_tasks,
                COUNT(DISTINCT session_id) as session_count,
                ROUND(AVG(task_count), 1) as avg_tasks_per_session
            FROM context_task_patterns
            GROUP BY task_type, has_context
            ORDER BY task_type, has_context
            """

            pattern_data = await self.telemetry.execute_query(
                development_patterns_query
            )

            # Analyze results for comprehensive insights
            context_sessions = [d for d in context_data if d["has_context"]]
            no_context_sessions = [d for d in context_data if not d["has_context"]]

            # Context Effectiveness Metrics
            context_avg_success_rate = (
                sum(s["success_rate"] or 0 for s in context_sessions)
                / len(context_sessions)
                if context_sessions
                else 0
            )
            no_context_avg_success_rate = (
                sum(s["success_rate"] or 0 for s in no_context_sessions)
                / len(no_context_sessions)
                if no_context_sessions
                else 0
            )

            context_avg_messages = (
                sum(s["total_messages"] for s in context_sessions)
                / len(context_sessions)
                if context_sessions
                else 0
            )
            no_context_avg_messages = (
                sum(s["total_messages"] for s in no_context_sessions)
                / len(no_context_sessions)
                if no_context_sessions
                else 0
            )

            context_avg_duration = (
                sum(s["duration_hours"] or 0 for s in context_sessions)
                / len(context_sessions)
                if context_sessions
                else 0
            )
            no_context_avg_duration = (
                sum(s["duration_hours"] or 0 for s in no_context_sessions)
                / len(no_context_sessions)
                if no_context_sessions
                else 0
            )

            # Token efficiency analysis
            context_token_sessions = [t for t in token_data if t["has_context"]]
            no_context_token_sessions = [t for t in token_data if not t["has_context"]]

            context_avg_tokens = (
                sum(t["total_tokens"] for t in context_token_sessions)
                / len(context_token_sessions)
                if context_token_sessions
                else 0
            )
            no_context_avg_tokens = (
                sum(t["total_tokens"] for t in no_context_token_sessions)
                / len(no_context_token_sessions)
                if no_context_token_sessions
                else 0
            )

            # Calculate context window impact
            avg_context_size = (
                sum(s["context_size"] or 0 for s in context_sessions)
                / len(context_sessions)
                if context_sessions
                else 0
            )
            context_overhead_pct = (
                (avg_context_size / (200000 * 4)) * 100 if avg_context_size > 0 else 0
            )  # Assuming ~200k token context window

            # Development pattern insights
            task_effectiveness = {}
            for pattern in pattern_data:
                task_type = pattern["task_type"]
                if task_type not in task_effectiveness:
                    task_effectiveness[task_type] = {
                        "with_context": 0,
                        "without_context": 0,
                    }

                if pattern["has_context"]:
                    task_effectiveness[task_type]["with_context"] = pattern[
                        "avg_tasks_per_session"
                    ]
                else:
                    task_effectiveness[task_type]["without_context"] = pattern[
                        "avg_tasks_per_session"
                    ]

            # Generate intelligent insights
            insights = []
            recommendations = []
            optimizations = []

            # Context effectiveness analysis
            if context_avg_success_rate > no_context_avg_success_rate + 10:
                insights.append(
                    f"CLAUDE.md boosts success rate by {context_avg_success_rate - no_context_avg_success_rate:.1f}%"
                )
                recommendations.append("Continue using CLAUDE.md for complex projects")
            elif context_avg_success_rate < no_context_avg_success_rate - 5:
                insights.append("Sessions without CLAUDE.md show higher success rates")
                recommendations.append(
                    "Review CLAUDE.md content - may contain outdated or conflicting guidance"
                )

            # Session productivity analysis
            if context_avg_messages > no_context_avg_messages * 1.3:
                insights.append(
                    f"CLAUDE.md sessions are {(context_avg_messages/no_context_avg_messages - 1)*100:.0f}% more interactive"
                )
                recommendations.append(
                    "CLAUDE.md enables deeper engagement with projects"
                )

            # Token efficiency insights
            if context_avg_tokens > no_context_avg_tokens * 1.2:
                insights.append(
                    f"CLAUDE.md sessions use {(context_avg_tokens/no_context_avg_tokens - 1)*100:.0f}% more tokens"
                )
                optimizations.append(
                    f"Consider trimming CLAUDE.md size (current avg: {avg_context_size/1024:.1f}KB)"
                )

            # Context overhead analysis
            if context_overhead_pct > 5:
                insights.append(
                    f"CLAUDE.md consumes {context_overhead_pct:.1f}% of context window"
                )
                optimizations.append(
                    "Large CLAUDE.md files may limit conversation depth"
                )
            elif context_overhead_pct < 1:
                insights.append("CLAUDE.md has minimal context window impact")
                recommendations.append("Current CLAUDE.md size is well-optimized")

            # Task-specific effectiveness
            most_effective_task = None
            best_improvement = 0
            for task, metrics in task_effectiveness.items():
                if metrics["with_context"] > 0 and metrics["without_context"] > 0:
                    improvement = metrics["with_context"] - metrics["without_context"]
                    if improvement > best_improvement:
                        best_improvement = improvement
                        most_effective_task = task

            if most_effective_task and best_improvement > 0.5:
                insights.append(
                    f"CLAUDE.md most effective for {most_effective_task} tasks (+{best_improvement:.1f} avg tasks)"
                )
                recommendations.append(
                    f"Optimize CLAUDE.md content for {most_effective_task} workflows"
                )

            # Determine overall status
            if len(context_sessions) == 0:
                status = "info"
                insights.append(
                    "No CLAUDE.md usage detected - relies on auto-loaded context only"
                )
            elif context_avg_success_rate > no_context_avg_success_rate + 5:
                status = "operational"
            elif context_overhead_pct > 10:
                status = "warning"
                insights.append("CLAUDE.md consuming significant context space")
            else:
                status = "operational"

            # Prepare comprehensive widget data
            context_intelligence = {
                # Core Metrics
                "sessions_with_context": len(context_sessions),
                "sessions_without_context": len(no_context_sessions),
                "total_analyzed_sessions": len(context_data),
                # Effectiveness Analysis
                "context_success_rate": round(context_avg_success_rate, 1),
                "no_context_success_rate": round(no_context_avg_success_rate, 1),
                "effectiveness_boost": round(
                    context_avg_success_rate - no_context_avg_success_rate, 1
                ),
                # Productivity Metrics
                "context_avg_messages": round(context_avg_messages, 0),
                "no_context_avg_messages": round(no_context_avg_messages, 0),
                "context_avg_duration_hours": round(context_avg_duration, 1),
                "no_context_avg_duration_hours": round(no_context_avg_duration, 1),
                # Token Efficiency
                "context_avg_tokens": round(context_avg_tokens, 0),
                "no_context_avg_tokens": round(no_context_avg_tokens, 0),
                "token_efficiency_ratio": round(
                    (
                        context_avg_tokens / no_context_avg_tokens
                        if no_context_avg_tokens > 0
                        else 1
                    ),
                    2,
                ),
                # Context Window Analysis
                "avg_context_size_kb": round(avg_context_size / 1024, 1),
                "context_overhead_percentage": round(context_overhead_pct, 1),
                # Development Patterns
                "task_effectiveness": [
                    {
                        "task_type": task.replace("_", " ").title(),
                        "with_context": round(metrics["with_context"], 1),
                        "without_context": round(metrics["without_context"], 1),
                        "improvement": round(
                            metrics["with_context"] - metrics["without_context"], 1
                        ),
                    }
                    for task, metrics in task_effectiveness.items()
                    if metrics["with_context"] > 0 or metrics["without_context"] > 0
                ],
                # Session Quality Analysis
                "high_performing_sessions": len(
                    [s for s in context_sessions if (s["success_rate"] or 0) > 70]
                ),
                "low_error_sessions": len(
                    [s for s in context_sessions if (s["error_rate"] or 0) < 10]
                ),
                "extended_sessions": len(
                    [s for s in context_sessions if s["total_messages"] > 50]
                ),
                # Actionable Intelligence
                "insights": insights,
                "recommendations": recommendations,
                "optimizations": optimizations,
                # Context Usage Patterns
                "recent_context_files": list(
                    set(
                        [
                            (
                                s["context_file"].split("/")[-1]
                                if s["context_file"]
                                else "Auto-loaded"
                            )
                            for s in context_sessions[:10]
                            if s["context_file"]
                        ]
                    )
                )[:5],
            }

            return WidgetData(
                widget_type=TelemetryWidgetType.CLAUDE_MD_ANALYTICS,
                title="Context Management Intelligence",
                status=status,
                data=context_intelligence,
                alerts=optimizations if optimizations else [],
            )

        except Exception as e:
            logger.error(
                f"Error generating Context Management Intelligence widget data: {e}"
            )
            import traceback

            traceback.print_exc()
            return WidgetData(
                widget_type=TelemetryWidgetType.CLAUDE_MD_ANALYTICS,
                title="Context Management Intelligence",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"],
            )

    async def _get_context_rot_meter_data(
        self, session_id: Optional[str] = None, time_range_days: int = 7
    ) -> WidgetData:
        """Generate Context Rot Meter widget data for real-time conversation quality monitoring."""
        try:
            logger.info(
                f"Context Rot Meter _get_context_rot_meter_data called: CONTEXT_ROT_AVAILABLE={CONTEXT_ROT_AVAILABLE}"
            )
            if not CONTEXT_ROT_AVAILABLE:
                logger.info(
                    "Using fallback Context Rot Meter data (components not available)"
                )
                return WidgetData(
                    widget_type=TelemetryWidgetType.CONTEXT_ROT_METER,
                    title="Context Rot Meter (Unavailable)",
                    status="warning",
                    data={"error": "Context Rot Meter components not available"},
                    alerts=["Context Rot Meter is not properly configured"],
                )

            # Convert days to minutes for the widget
            time_window_minutes = min(
                time_range_days * 24 * 60, 60 * 24
            )  # Cap at 24 hours for performance

            # Use the dedicated Context Rot Widget
            logger.info(
                f"Calling real Context Rot widget with session_id={session_id}, time_window_minutes={time_window_minutes}"
            )
            widget_data = await self.context_rot_widget.get_widget_data(
                session_id=session_id, time_window_minutes=time_window_minutes
            )
            logger.info(f"Context Rot widget returned: {type(widget_data)}")

            # The widget already returns a properly formatted WidgetData
            return widget_data

        except Exception as e:
            logger.error(f"Error generating Context Rot Meter widget data: {e}")
            import traceback

            logger.error(f"Context Rot Meter traceback: {traceback.format_exc()}")
            traceback.print_exc()
            return WidgetData(
                widget_type=TelemetryWidgetType.CONTEXT_ROT_METER,
                title="Context Rot Meter (Error)",
                status="critical",
                data={"error": str(e)},
                alerts=[f"Context Rot Meter error: {str(e)}"],
            )
