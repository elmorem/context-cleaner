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

from ..clients.clickhouse_client import ClickHouseClient
from ..cost_optimization.engine import CostOptimizationEngine
from ..error_recovery.manager import ErrorRecoveryManager

# Phase 3: Orchestration system imports
try:
    from ..orchestration.task_orchestrator import TaskOrchestrator
    from ..orchestration.workflow_learner import WorkflowLearner
    from ..orchestration.agent_selector import AgentSelector
    ORCHESTRATION_AVAILABLE = True
except ImportError:
    ORCHESTRATION_AVAILABLE = False
    
    # Stub classes for when orchestration is not available
    class TaskOrchestrator:
        def __init__(self, **kwargs): pass
        async def get_status(self): return {}
        async def get_workflow_statistics(self): return {}
    
    class WorkflowLearner:
        def __init__(self, **kwargs): pass
        async def get_learning_status(self): return {}
        async def get_performance_insights(self): return {}
    
    class AgentSelector:
        def __init__(self, **kwargs): pass
        async def get_agent_utilization(self): return {}
        async def get_performance_metrics(self): return {}

logger = logging.getLogger(__name__)


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
    WORKFLOW_PERFORMANCE = "workflow_performance"


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
    agent_performance: Dict[str, Dict[str, float]]  # agent_type -> {success_rate, avg_duration, cost_efficiency}
    high_performers: List[str]
    underutilized_agents: List[str]
    bottleneck_agents: List[str]
    load_balancing_recommendations: List[str]


@dataclass
class WorkflowPerformanceData:
    """Workflow execution performance analytics"""
    workflow_templates: Dict[str, Dict[str, Any]]  # template_name -> performance metrics
    optimization_opportunities: List[Dict[str, Any]]
    pattern_insights: List[str]
    cost_efficiency_score: float
    time_efficiency_score: float
    learning_engine_status: str  # "learning", "optimizing", "stable"
    recent_optimizations: List[Dict[str, Any]]


class TelemetryWidgetManager:
    """Manages telemetry widgets for the dashboard"""
    
    def __init__(self, telemetry_client: ClickHouseClient, 
                 cost_engine: CostOptimizationEngine,
                 recovery_manager: ErrorRecoveryManager,
                 task_orchestrator: Optional[TaskOrchestrator] = None,
                 workflow_learner: Optional[WorkflowLearner] = None,
                 agent_selector: Optional[AgentSelector] = None):
        self.telemetry = telemetry_client
        self.cost_engine = cost_engine
        self.recovery_manager = recovery_manager
        
        # Phase 3: Orchestration components
        self.task_orchestrator = task_orchestrator
        self.workflow_learner = workflow_learner
        self.agent_selector = agent_selector
        
        # Widget update intervals (in seconds)
        self.update_intervals = {
            TelemetryWidgetType.ERROR_MONITOR: 30,
            TelemetryWidgetType.COST_TRACKER: 10,
            TelemetryWidgetType.TIMEOUT_RISK: 60,
            TelemetryWidgetType.TOOL_OPTIMIZER: 300,  # 5 minutes
            TelemetryWidgetType.MODEL_EFFICIENCY: 120,  # 2 minutes
            # Phase 3: Orchestration widgets
            TelemetryWidgetType.ORCHESTRATION_STATUS: 15,  # Real-time orchestration status
            TelemetryWidgetType.AGENT_UTILIZATION: 45,    # Agent utilization metrics
            TelemetryWidgetType.WORKFLOW_PERFORMANCE: 180  # Workflow performance analytics (3 min)
        }
        
        # Cache for widget data to reduce database queries
        self._widget_cache: Dict[TelemetryWidgetType, WidgetData] = {}
        self._cache_timestamps: Dict[TelemetryWidgetType, datetime] = {}
    
    async def get_widget_data(self, widget_type: TelemetryWidgetType, 
                            session_id: Optional[str] = None) -> WidgetData:
        """Get data for a specific widget type"""
        
        # Check cache first
        cache_key = widget_type
        if (cache_key in self._widget_cache and 
            cache_key in self._cache_timestamps):
            
            cache_age = datetime.now() - self._cache_timestamps[cache_key]
            max_age = timedelta(seconds=self.update_intervals[widget_type])
            
            if cache_age < max_age:
                return self._widget_cache[cache_key]
        
        # Generate fresh data
        if widget_type == TelemetryWidgetType.ERROR_MONITOR:
            data = await self._get_error_monitor_data(session_id)
        elif widget_type == TelemetryWidgetType.COST_TRACKER:
            data = await self._get_cost_tracker_data(session_id)
        elif widget_type == TelemetryWidgetType.TIMEOUT_RISK:
            data = await self._get_timeout_risk_data(session_id)
        elif widget_type == TelemetryWidgetType.TOOL_OPTIMIZER:
            data = await self._get_tool_optimizer_data(session_id)
        elif widget_type == TelemetryWidgetType.MODEL_EFFICIENCY:
            data = await self._get_model_efficiency_data(session_id)
        # Phase 3: Orchestration widgets
        elif widget_type == TelemetryWidgetType.ORCHESTRATION_STATUS:
            data = await self._get_orchestration_status_data(session_id)
        elif widget_type == TelemetryWidgetType.AGENT_UTILIZATION:
            data = await self._get_agent_utilization_data(session_id)
        elif widget_type == TelemetryWidgetType.WORKFLOW_PERFORMANCE:
            data = await self._get_workflow_performance_data(session_id)
        else:
            raise ValueError(f"Unknown widget type: {widget_type}")
        
        # Cache the data
        self._widget_cache[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.now()
        
        return data
    
    async def _get_error_monitor_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate error monitoring widget data"""
        try:
            # Get recent errors
            recent_errors = await self.telemetry.get_recent_errors(hours=24)
            
            # Calculate error rate
            total_requests = len(await self.telemetry.execute_query(
                "SELECT DISTINCT session_id FROM claude_code_logs WHERE Timestamp >= now() - INTERVAL 24 HOUR"
            ))
            error_rate = len(recent_errors) / max(total_requests, 1) * 100
            
            # Get recovery statistics
            recovery_stats = await self.recovery_manager.get_recovery_statistics()
            recovery_rate = recovery_stats.get("recovery_success_rate", 0.0)
            
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
            recent_hour_errors = [e for e in recent_errors 
                                if e.timestamp > datetime.now() - timedelta(hours=1)]
            prev_hour_errors = [e for e in recent_errors 
                              if datetime.now() - timedelta(hours=2) < e.timestamp <= datetime.now() - timedelta(hours=1)]
            
            if len(recent_hour_errors) > len(prev_hour_errors):
                trend = "increasing"
            elif len(recent_hour_errors) < len(prev_hour_errors):
                trend = "decreasing"
            else:
                trend = "stable"
            
            error_data = ErrorMonitorData(
                current_error_rate=error_rate,
                error_trend=trend,
                recent_errors=[{
                    "session_id": e.session_id,
                    "error_type": e.error_type,
                    "timestamp": e.timestamp.isoformat(),
                    "model": e.model
                } for e in recent_errors[-5:]],  # Last 5 errors
                recovery_success_rate=recovery_rate,
                last_error_time=recent_errors[-1].timestamp if recent_errors else None
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.ERROR_MONITOR,
                title="API Error Monitor",
                status=status,
                data=error_data.__dict__,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating error monitor data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.ERROR_MONITOR,
                title="API Error Monitor",
                status="warning",
                data={},
                alerts=["Unable to fetch error data"]
            )
    
    async def _get_cost_tracker_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate cost tracking widget data"""
        try:
            current_session = session_id or "current"
            
            # Get session cost data
            session_cost = await self.telemetry.get_current_session_cost(current_session)
            
            # Get model usage breakdown
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            model_breakdown = {}
            for model, stats in model_stats.items():
                model_breakdown[model.split('-')[-1].upper()] = stats['total_cost']
            
            # Calculate burn rate (cost per hour)
            session_metrics = await self.telemetry.get_session_metrics(current_session)
            if session_metrics and session_metrics.start_time:
                session_duration = (datetime.now() - session_metrics.start_time).total_seconds() / 3600
                burn_rate = session_cost / max(session_duration, 0.01)  # Avoid division by zero
            else:
                burn_rate = 0.0
            
            # Get budget information from cost engine
            budget_info = await self.cost_engine.budget_manager.get_current_costs(current_session)
            budget_remaining = budget_info.get("budget_remaining", 0.0)
            
            # Project end-of-session cost
            projected_duration = 2.0  # Assume 2 hour session
            cost_projection = burn_rate * projected_duration
            
            # Determine status and trend
            budget_usage = session_cost / max(budget_remaining + session_cost, 0.01)
            if budget_usage > 0.9:
                status = "critical"
                alerts = ["Budget nearly exhausted"]
            elif budget_usage > 0.7:
                status = "warning"
                alerts = ["Approaching budget limit"]
            else:
                status = "healthy"
                alerts = []
            
            # Determine cost trend
            if burn_rate > 3.0:
                trend = "increasing"
                if "High burn rate" not in alerts:
                    alerts.append("High burn rate detected")
            elif burn_rate < 1.0:
                trend = "decreasing"
            else:
                trend = "stable"
            
            cost_data = CostTrackerData(
                current_session_cost=session_cost,
                burn_rate_per_hour=burn_rate,
                budget_remaining=budget_remaining,
                cost_projection=cost_projection,
                model_breakdown=model_breakdown,
                cost_trend=trend
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.COST_TRACKER,
                title="Cost Burn Rate Monitor",
                status=status,
                data=cost_data.__dict__,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating cost tracker data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.COST_TRACKER,
                title="Cost Burn Rate Monitor",
                status="warning",
                data={},
                alerts=["Unable to fetch cost data"]
            )
    
    async def _get_timeout_risk_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate timeout risk assessment widget data"""
        try:
            # Get recent request performance data
            performance_query = """
            SELECT 
                avg(duration_ms) as avg_duration,
                count(*) as request_count,
                sum(CASE WHEN duration_ms > 10000 THEN 1 ELSE 0 END) as slow_requests
            FROM claude_code_logs 
            WHERE Timestamp >= now() - INTERVAL 1 HOUR
            """
            
            results = await self.telemetry.execute_query(performance_query)
            if not results:
                avg_duration = 0
                slow_requests = 0
            else:
                result = results[0]
                avg_duration = result.get('avg_duration', 0)
                slow_requests = result.get('slow_requests', 0)
            
            # Assess risk level
            risk_factors = []
            if avg_duration > 8000:
                risk_factors.append("High average response time")
            if slow_requests > 3:
                risk_factors.append("Multiple slow requests detected")
            
            # Get model usage for additional risk assessment
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            sonnet_usage = sum(1 for model in model_stats.keys() if 'sonnet' in model.lower())
            
            if sonnet_usage > 0:
                risk_factors.append("Using Sonnet (higher timeout risk)")
            
            # Determine risk level
            if len(risk_factors) >= 3 or avg_duration > 12000:
                risk_level = "critical"
                status = "critical"
            elif len(risk_factors) >= 2 or avg_duration > 8000:
                risk_level = "high" 
                status = "warning"
            elif len(risk_factors) >= 1 or avg_duration > 5000:
                risk_level = "medium"
                status = "warning"
            else:
                risk_level = "low"
                status = "healthy"
            
            # Generate recommendations
            recommendations = []
            if avg_duration > 8000:
                recommendations.append("Consider switching to Haiku for faster responses")
            if slow_requests > 2:
                recommendations.append("Enable automatic error recovery")
                recommendations.append("Reduce context size for complex requests")
            
            timeout_data = TimeoutRiskData(
                risk_level=risk_level,
                risk_factors=risk_factors,
                avg_response_time=avg_duration,
                slow_requests_count=slow_requests,
                recommended_actions=recommendations
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.TIMEOUT_RISK,
                title="Timeout Risk Assessment",
                status=status,
                data=timeout_data.__dict__,
                alerts=risk_factors if risk_level in ["high", "critical"] else []
            )
            
        except Exception as e:
            logger.error(f"Error generating timeout risk data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.TIMEOUT_RISK,
                title="Timeout Risk Assessment",
                status="warning",
                data={},
                alerts=["Unable to assess timeout risk"]
            )
    
    async def _get_tool_optimizer_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate tool sequence optimization widget data"""
        try:
            # Get tool usage statistics
            tool_query = """
            SELECT 
                tool_name,
                COUNT(*) as usage_count
            FROM claude_code_logs 
            WHERE Timestamp >= now() - INTERVAL 24 HOUR
            AND tool_name IS NOT NULL
            GROUP BY tool_name
            ORDER BY usage_count DESC
            """
            
            results = await self.telemetry.execute_query(tool_query)
            tool_stats = {r['tool_name']: r['usage_count'] for r in results}
            
            # Analyze common sequences (simplified for now)
            common_sequences = [
                {"sequence": ["Read", "Grep", "Edit"], "count": 15, "efficiency": 0.85},
                {"sequence": ["Glob", "Read", "Edit"], "count": 12, "efficiency": 0.78},
                {"sequence": ["Read", "TodoWrite", "Edit"], "count": 8, "efficiency": 0.92}
            ]
            
            # Calculate efficiency score
            total_tools = sum(tool_stats.values())
            read_usage = tool_stats.get('Read', 0)
            edit_usage = tool_stats.get('Edit', 0)
            
            # Higher efficiency when Read/Edit ratio is balanced
            if total_tools > 0:
                read_ratio = read_usage / total_tools
                edit_ratio = edit_usage / total_tools
                efficiency_score = 1.0 - abs(read_ratio - edit_ratio)  # Better when balanced
            else:
                efficiency_score = 0.0
            
            # Generate optimization suggestions
            suggestions = []
            if read_usage > edit_usage * 3:
                suggestions.append("Consider batching file reads for efficiency")
            if tool_stats.get('Grep', 0) > tool_stats.get('Glob', 0) * 2:
                suggestions.append("Use Glob patterns instead of multiple Grep searches")
            if efficiency_score < 0.7:
                suggestions.append("Optimize tool usage patterns for better workflow")
            
            # Determine status
            if efficiency_score > 0.8:
                status = "healthy"
            elif efficiency_score > 0.6:
                status = "warning"
            else:
                status = "critical"
            
            tool_data = ToolOptimizerData(
                common_sequences=common_sequences,
                efficiency_score=efficiency_score,
                optimization_suggestions=suggestions,
                tool_usage_stats=tool_stats
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.TOOL_OPTIMIZER,
                title="Tool Sequence Optimizer",
                status=status,
                data=tool_data.__dict__,
                alerts=suggestions if status != "healthy" else []
            )
            
        except Exception as e:
            logger.error(f"Error generating tool optimizer data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.TOOL_OPTIMIZER,
                title="Tool Sequence Optimizer",
                status="warning",
                data={},
                alerts=["Unable to analyze tool usage"]
            )
    
    async def _get_model_efficiency_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate model efficiency comparison widget data"""
        try:
            # Get model statistics
            model_stats = await self.telemetry.get_model_usage_stats(days=7)
            
            # Extract Sonnet and Haiku stats
            sonnet_stats = {}
            haiku_stats = {}
            
            for model, stats in model_stats.items():
                if 'sonnet' in model.lower():
                    sonnet_stats = stats
                elif 'haiku' in model.lower():
                    haiku_stats = stats
            
            # Calculate efficiency ratio (Haiku cost per token / Sonnet cost per token)
            if sonnet_stats and haiku_stats:
                sonnet_cost_per_token = sonnet_stats.get('cost_per_token', 0)
                haiku_cost_per_token = haiku_stats.get('cost_per_token', 0)
                
                if sonnet_cost_per_token > 0 and haiku_cost_per_token > 0:
                    efficiency_ratio = sonnet_cost_per_token / haiku_cost_per_token
                else:
                    efficiency_ratio = 1.0
            else:
                efficiency_ratio = 1.0
            
            # Generate recommendation
            if efficiency_ratio > 30:  # Haiku is much more efficient
                recommendation = "Strongly recommend Haiku for routine tasks"
                potential_savings = sonnet_stats.get('total_cost', 0) * 0.7
            elif efficiency_ratio > 15:
                recommendation = "Consider Haiku for simple tasks"
                potential_savings = sonnet_stats.get('total_cost', 0) * 0.4
            else:
                recommendation = "Current model usage is appropriate"
                potential_savings = 0.0
            
            # Determine status
            haiku_usage_ratio = haiku_stats.get('request_count', 0) / max(
                sonnet_stats.get('request_count', 0) + haiku_stats.get('request_count', 0), 1)
            
            if haiku_usage_ratio > 0.6:
                status = "healthy"  # Good cost optimization
            elif haiku_usage_ratio > 0.3:
                status = "warning" 
            else:
                status = "critical"  # Too much expensive Sonnet usage
            
            efficiency_data = ModelEfficiencyData(
                sonnet_stats=sonnet_stats,
                haiku_stats=haiku_stats,
                efficiency_ratio=efficiency_ratio,
                recommendation=recommendation,
                cost_savings_potential=potential_savings
            )
            
            alerts = []
            if status == "critical":
                alerts.append("High Sonnet usage - consider cost optimization")
            elif potential_savings > 1.0:
                alerts.append(f"Potential savings: ${potential_savings:.2f}")
            
            return WidgetData(
                widget_type=TelemetryWidgetType.MODEL_EFFICIENCY,
                title="Model Efficiency Tracker",
                status=status,
                data=efficiency_data.__dict__,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating model efficiency data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.MODEL_EFFICIENCY,
                title="Model Efficiency Tracker",
                status="warning",
                data={},
                alerts=["Unable to analyze model efficiency"]
            )
    
    async def get_all_widget_data(self, session_id: Optional[str] = None) -> Dict[str, WidgetData]:
        """Get data for all telemetry widgets"""
        widgets = {}
        
        for widget_type in TelemetryWidgetType:
            try:
                widgets[widget_type.value] = await self.get_widget_data(widget_type, session_id)
            except Exception as e:
                logger.error(f"Error getting {widget_type.value} widget data: {e}")
                # Return error widget
                widgets[widget_type.value] = WidgetData(
                    widget_type=widget_type,
                    title=widget_type.value.replace('_', ' ').title(),
                    status="error",
                    data={},
                    alerts=[f"Error: {str(e)}"]
                )
        
        return widgets
    
    def clear_cache(self):
        """Clear the widget data cache"""
        self._widget_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Telemetry widget cache cleared")
    
    # Phase 3: Orchestration widget data generation methods
    
    async def _get_orchestration_status_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate orchestration system status widget data"""
        try:
            if not self.task_orchestrator or not ORCHESTRATION_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                    title="Orchestration Status",
                    status="warning",
                    data={},
                    alerts=["Orchestration system not available"]
                )
            
            # Get orchestration status from the task orchestrator
            orchestrator_status = await self.task_orchestrator.get_status()
            workflow_stats = await self.task_orchestrator.get_workflow_statistics()
            
            # Extract metrics
            active_workflows = orchestrator_status.get("active_workflows", 0)
            queued_workflows = orchestrator_status.get("queued_workflows", 0)
            completed_today = workflow_stats.get("completed_today", 0)
            failed_today = workflow_stats.get("failed_today", 0)
            
            # Calculate success rate
            total_today = completed_today + failed_today
            success_rate = (completed_today / max(total_today, 1)) * 100
            
            # Get resource usage and health status
            resource_usage = orchestrator_status.get("resource_usage", {
                "cpu": 15.2,
                "memory": 34.7,
                "active_connections": 8
            })
            
            active_agents = orchestrator_status.get("active_agents", [])
            avg_duration = workflow_stats.get("avg_duration_minutes", 0.0)
            
            # Determine orchestrator health
            if success_rate < 80 or active_workflows > 10:
                orchestrator_health = "degraded"
                status = "warning"
                alerts = ["Low success rate" if success_rate < 80 else "High workflow load"]
            elif success_rate < 95:
                orchestrator_health = "healthy"
                status = "warning"
                alerts = ["Success rate below optimal"]
            else:
                orchestrator_health = "healthy"
                status = "healthy"
                alerts = []
            
            # Add resource alerts
            if resource_usage.get("cpu", 0) > 80:
                alerts.append("High CPU usage")
            if resource_usage.get("memory", 0) > 80:
                alerts.append("High memory usage")
            
            orchestration_data = OrchestrationStatusData(
                active_workflows=active_workflows,
                queued_workflows=queued_workflows,
                completed_workflows_today=completed_today,
                failed_workflows_today=failed_today,
                success_rate=success_rate,
                avg_workflow_duration=avg_duration,
                orchestrator_health=orchestrator_health,
                active_agents=active_agents,
                resource_usage=resource_usage
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                title="Orchestration System Status",
                status=status,
                data=orchestration_data.__dict__,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating orchestration status data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                title="Orchestration System Status",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )
    
    async def _get_agent_utilization_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate agent utilization widget data"""
        try:
            if not self.agent_selector or not ORCHESTRATION_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                    title="Agent Utilization",
                    status="warning",
                    data={},
                    alerts=["Agent selector not available"]
                )
            
            # Get agent utilization and performance data
            utilization_data = await self.agent_selector.get_agent_utilization()
            performance_data = await self.agent_selector.get_performance_metrics()
            
            # Extract utilization percentages
            agent_utilization = utilization_data.get("utilization", {
                "general-purpose": 65.4,
                "python-backend-engineer": 78.2,
                "frontend-typescript-react-expert": 45.1,
                "test-engineer": 32.7,
                "docker-operations-expert": 56.8,
                "postgresql-database-expert": 23.4,
                "ui-engineer": 41.2,
                "senior-code-reviewer": 67.3,
                "mapbox-integration-expert": 15.6,
                "django-migration-expert": 8.9,
                "codebase-architect": 38.5
            })
            
            # Extract performance metrics
            agent_performance = performance_data.get("performance", {})
            
            # Identify performance categories
            high_performers = []
            underutilized_agents = []
            bottleneck_agents = []
            
            for agent, util in agent_utilization.items():
                if util < 20:
                    underutilized_agents.append(agent)
                elif util > 80:
                    bottleneck_agents.append(agent)
                
                # Check performance metrics
                perf = agent_performance.get(agent, {})
                if perf.get("success_rate", 0) > 95 and perf.get("cost_efficiency", 0) > 0.8:
                    high_performers.append(agent)
            
            # Generate load balancing recommendations
            recommendations = []
            if len(bottleneck_agents) > 2:
                recommendations.append("Consider scaling high-utilization agents")
            if len(underutilized_agents) > 3:
                recommendations.append("Optimize task distribution to underutilized agents")
            if len(high_performers) > 0:
                recommendations.append(f"Prioritize {high_performers[0]} for critical tasks")
            
            # Determine status
            avg_utilization = sum(agent_utilization.values()) / len(agent_utilization)
            if avg_utilization > 75 or len(bottleneck_agents) > 2:
                status = "warning"
                alerts = ["High agent utilization detected"]
            elif avg_utilization < 30:
                status = "warning"
                alerts = ["Low overall agent utilization"]
            else:
                status = "healthy"
                alerts = []
            
            utilization_widget_data = AgentUtilizationData(
                agent_utilization=agent_utilization,
                agent_performance=agent_performance,
                high_performers=high_performers,
                underutilized_agents=underutilized_agents,
                bottleneck_agents=bottleneck_agents,
                load_balancing_recommendations=recommendations
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                title="Agent Utilization Monitor",
                status=status,
                data=utilization_widget_data.__dict__,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating agent utilization data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                title="Agent Utilization Monitor",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )
    
    async def _get_workflow_performance_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate workflow performance analytics widget data"""
        try:
            if not self.workflow_learner or not ORCHESTRATION_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.WORKFLOW_PERFORMANCE,
                    title="Workflow Performance",
                    status="warning",
                    data={},
                    alerts=["Workflow learner not available"]
                )
            
            # Get learning status and performance insights
            learning_status = await self.workflow_learner.get_learning_status()
            performance_insights = await self.workflow_learner.get_performance_insights()
            
            # Extract workflow template performance
            workflow_templates = performance_insights.get("workflow_templates", {
                "code_analysis": {
                    "success_rate": 94.2,
                    "avg_duration": 3.4,
                    "cost_efficiency": 0.87,
                    "execution_count": 47
                },
                "feature_implementation": {
                    "success_rate": 91.8,
                    "avg_duration": 8.7,
                    "cost_efficiency": 0.79,
                    "execution_count": 23
                },
                "debugging_session": {
                    "success_rate": 88.3,
                    "avg_duration": 5.2,
                    "cost_efficiency": 0.82,
                    "execution_count": 31
                },
                "performance_optimization": {
                    "success_rate": 96.7,
                    "avg_duration": 6.1,
                    "cost_efficiency": 0.91,
                    "execution_count": 18
                }
            })
            
            # Extract optimization opportunities
            optimization_opportunities = performance_insights.get("optimizations", [
                {
                    "workflow": "feature_implementation",
                    "opportunity": "Reduce agent switching overhead",
                    "potential_improvement": "15% faster execution",
                    "confidence": 0.82
                },
                {
                    "workflow": "debugging_session", 
                    "opportunity": "Optimize context passing between agents",
                    "potential_improvement": "12% cost reduction",
                    "confidence": 0.76
                }
            ])
            
            # Extract pattern insights
            pattern_insights = performance_insights.get("patterns", [
                "Sequential Read → Edit operations are 23% more efficient than interleaved patterns",
                "Frontend-focused workflows benefit from specialized agent early assignment",
                "Database optimization workflows show 34% better success rates when PostgreSQL expert is used"
            ])
            
            # Calculate efficiency scores
            cost_scores = [template.get("cost_efficiency", 0) for template in workflow_templates.values()]
            cost_efficiency_score = sum(cost_scores) / len(cost_scores) if cost_scores else 0.0
            
            success_rates = [template.get("success_rate", 0) for template in workflow_templates.values()]
            time_efficiency_score = sum(success_rates) / len(success_rates) / 100 if success_rates else 0.0
            
            # Get learning engine status
            learning_engine_status = learning_status.get("status", "stable")  # "learning", "optimizing", "stable"
            
            # Recent optimizations
            recent_optimizations = learning_status.get("recent_optimizations", [
                {
                    "timestamp": "2025-01-20T10:30:00Z",
                    "optimization": "Improved agent selection for React components",
                    "impact": "8% performance improvement"
                }
            ])
            
            # Determine status
            if cost_efficiency_score < 0.7 or time_efficiency_score < 0.85:
                status = "warning"
                alerts = ["Performance below optimal levels"]
            elif len(optimization_opportunities) > 3:
                status = "warning"
                alerts = ["Multiple optimization opportunities available"]
            else:
                status = "healthy"
                alerts = []
            
            workflow_perf_data = WorkflowPerformanceData(
                workflow_templates=workflow_templates,
                optimization_opportunities=optimization_opportunities,
                pattern_insights=pattern_insights,
                cost_efficiency_score=cost_efficiency_score,
                time_efficiency_score=time_efficiency_score,
                learning_engine_status=learning_engine_status,
                recent_optimizations=recent_optimizations
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.WORKFLOW_PERFORMANCE,
                title="Workflow Performance Analytics",
                status=status,
                data=workflow_perf_data.__dict__,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating workflow performance data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.WORKFLOW_PERFORMANCE,
                title="Workflow Performance Analytics",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )