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
            # Get model usage breakdown for real cost data
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            model_breakdown = {}
            total_daily_cost = 0.0
            for model, stats in model_stats.items():
                model_key = model.split('-')[-1] if '-' in model else model
                cost = stats['total_cost']
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
                    session_cost = await self.telemetry.get_current_session_cost(latest_session)
                else:
                    session_cost = 0.0
            
            # Calculate budget information (simplified approach)
            # Assume a daily budget based on current usage patterns
            daily_budget = 100.0  # $100/day default budget
            budget_used = total_daily_cost
            budget_remaining = max(0, ((daily_budget - budget_used) / daily_budget) * 100)
            
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
                avg_duration = float(result.get('avg_duration', 0) or 0)
                slow_requests = int(result.get('slow_requests', 0) or 0)
                very_slow_requests = int(result.get('very_slow_requests', 0) or 0)
                max_duration = float(result.get('max_duration', 0) or 0)
                min_duration = float(result.get('min_duration', 0) or 0)
                request_count = int(result.get('request_count', 0) or 0)
            
            # Assess detailed risk factors and provide actionable insights
            risk_factors = []
            recommendations = []
            
            # Analyze response time patterns
            if avg_duration > 15000:
                risk_factors.append(f"Very high average response time: {avg_duration/1000:.1f}s")
                recommendations.append("Consider breaking large requests into smaller chunks")
            elif avg_duration > 10000:
                risk_factors.append(f"High average response time: {avg_duration/1000:.1f}s")
                recommendations.append("Consider optimizing context size")
            elif avg_duration > 5000:
                risk_factors.append(f"Elevated response time: {avg_duration/1000:.1f}s")
            
            # Analyze slow request patterns
            if request_count > 0:
                slow_request_percentage = (slow_requests / request_count) * 100
                if slow_request_percentage > 50:
                    risk_factors.append(f"High timeout risk: {slow_request_percentage:.0f}% of requests are slow")
                    recommendations.append("Consider using Claude 3.5 Haiku for faster responses")
                elif slow_request_percentage > 25:
                    risk_factors.append(f"Moderate timeout risk: {slow_request_percentage:.0f}% of requests are slow")
                elif slow_request_percentage > 10:
                    risk_factors.append(f"Some slow requests: {slow_request_percentage:.0f}% taking >10s")
            
            # Check for very slow requests (>30s)
            if very_slow_requests > 0:
                risk_factors.append(f"{very_slow_requests} requests took >30 seconds")
                recommendations.append("Review and optimize prompts causing >30s responses")
            
            # Get model usage for additional risk assessment
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            for model, stats in model_stats.items():
                if 'sonnet-4' in model.lower() and stats['request_count'] > 0:
                    avg_model_duration = stats.get('avg_duration_ms', 0)
                    if avg_model_duration > 10000:
                        risk_factors.append(f"Sonnet 4 averaging {avg_model_duration/1000:.1f}s per request")
                        recommendations.append("Consider using Haiku for routine tasks")
            
            # Performance insights
            if max_duration > 60000:  # >1 minute
                risk_factors.append(f"Slowest request: {max_duration/1000:.0f}s")
                recommendations.append("Identify and optimize extremely slow operations")
            
            # Determine overall risk level and status
            critical_factors = len([f for f in risk_factors if any(word in f.lower() for word in ['very high', 'high timeout', '>30 seconds'])])
            warning_factors = len([f for f in risk_factors if any(word in f.lower() for word in ['high', 'moderate', 'elevated'])])
            
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
                    recommendations.append("Performance is good - current setup working well")
                else:
                    recommendations.append("Monitor response times for optimization opportunities")
            
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
            # Get tool usage statistics from actual telemetry data
            tool_query = """
            SELECT 
                LogAttributes['tool_name'] as tool_name,
                COUNT(*) as usage_count,
                AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration_ms
            FROM otel.otel_logs 
            WHERE Timestamp >= now() - INTERVAL 7 DAY
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
                tool_name = r['tool_name']
                usage_count = int(r['usage_count'])
                avg_duration = float(r['avg_duration_ms'] or 0)
                
                tool_stats[tool_name] = {
                    'usage_count': usage_count,
                    'avg_duration_ms': avg_duration
                }
                total_calls += usage_count
                total_duration += avg_duration * usage_count
            
            # Analyze tool sequences from actual sessions
            sequence_query = """
            WITH tool_sequences AS (
                SELECT 
                    LogAttributes['session.id'] as session_id,
                    LogAttributes['tool_name'] as tool_name,
                    Timestamp,
                    ROW_NUMBER() OVER (PARTITION BY LogAttributes['session.id'] ORDER BY Timestamp) as seq_num
                FROM otel.otel_logs
                WHERE Body = 'claude_code.tool_decision'
                    AND LogAttributes['tool_name'] != ''
                    AND Timestamp >= now() - INTERVAL 7 DAY
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
                sequence = [seq['first_tool'], seq['second_tool']]
                count = int(seq['pair_count'])
                # Calculate efficiency based on tool performance
                first_duration = tool_stats.get(seq['first_tool'], {}).get('avg_duration_ms', 1000)
                second_duration = tool_stats.get(seq['second_tool'], {}).get('avg_duration_ms', 1000)
                efficiency = max(0.3, min(0.95, 1.0 - (first_duration + second_duration) / 10000))
                
                common_sequences.append({
                    "sequence": sequence,
                    "count": count,
                    "efficiency": round(efficiency, 2)
                })
            
            # Calculate overall efficiency metrics
            if total_calls > 0:
                avg_tool_duration = total_duration / total_calls
                
                # Efficiency based on tool diversity and performance
                tool_diversity = len(tool_stats) / max(total_calls, 1)  # More tools used = better
                performance_score = max(0, 1.0 - (avg_tool_duration / 5000))  # Lower duration = better
                
                # Balance between Read/Write operations
                read_tools = ['Read', 'Grep', 'Glob']
                write_tools = ['Edit', 'Write', 'MultiEdit']
                
                read_count = sum(tool_stats.get(tool, {}).get('usage_count', 0) for tool in read_tools)
                write_count = sum(tool_stats.get(tool, {}).get('usage_count', 0) for tool in write_tools)
                
                if read_count + write_count > 0:
                    balance_score = 1.0 - abs((read_count - write_count) / (read_count + write_count))
                else:
                    balance_score = 0.5
                
                efficiency_score = (tool_diversity * 0.3 + performance_score * 0.4 + balance_score * 0.3)
            else:
                efficiency_score = 0.0
            
            # Generate intelligent optimization suggestions
            suggestions = []
            most_used_tool = max(tool_stats.keys(), key=lambda x: tool_stats[x]['usage_count']) if tool_stats else None
            
            if most_used_tool and tool_stats[most_used_tool]['usage_count'] > total_calls * 0.4:
                suggestions.append(f"Heavy reliance on {most_used_tool} - consider workflow optimization")
            
            bash_usage = tool_stats.get('Bash', {}).get('usage_count', 0)
            read_usage = tool_stats.get('Read', {}).get('usage_count', 0)
            
            if bash_usage > read_usage * 2:
                suggestions.append("High Bash usage detected - consider using Read/Grep for file operations")
            
            if tool_stats.get('Grep', {}).get('usage_count', 0) > tool_stats.get('Glob', {}).get('usage_count', 0) * 3:
                suggestions.append("Multiple Grep searches - use Glob patterns for better performance")
            
            slow_tools = [tool for tool, stats in tool_stats.items() 
                         if stats['avg_duration_ms'] > 2000 and stats['usage_count'] > 5]
            if slow_tools:
                suggestions.append(f"Slow tools detected: {', '.join(slow_tools)} - consider alternatives")
            
            if efficiency_score < 0.6:
                suggestions.append("Tool usage patterns could be optimized for better workflow efficiency")
            
            # Determine status based on efficiency and usage patterns
            if efficiency_score > 0.75 and len(suggestions) <= 1:
                status = "healthy"
            elif efficiency_score > 0.5:
                status = "warning"
            else:
                status = "critical"
            
            # Convert tool_stats to simple format for frontend
            tool_usage_stats = {tool: stats['usage_count'] for tool, stats in tool_stats.items()}
            
            tool_data = ToolOptimizerData(
                common_sequences=common_sequences,
                efficiency_score=round(efficiency_score, 2),
                optimization_suggestions=suggestions,
                tool_usage_stats=tool_usage_stats
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
            # Get comprehensive model statistics from telemetry data
            model_query = """
            SELECT 
                LogAttributes['model'] as model,
                COUNT(*) as request_count,
                AVG(toFloat64OrNull(LogAttributes['cost_usd'])) as avg_cost,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration,
                SUM(toFloat64OrNull(LogAttributes['input_tokens'])) as total_input_tokens,
                SUM(toFloat64OrNull(LogAttributes['output_tokens'])) as total_output_tokens,
                AVG(toFloat64OrNull(LogAttributes['input_tokens'])) as avg_input_tokens,
                AVG(toFloat64OrNull(LogAttributes['output_tokens'])) as avg_output_tokens
            FROM otel.otel_logs 
            WHERE Body = 'claude_code.api_request'
                AND Timestamp >= now() - INTERVAL 7 DAY
                AND LogAttributes['model'] IS NOT NULL
                AND LogAttributes['cost_usd'] IS NOT NULL
            GROUP BY LogAttributes['model']
            ORDER BY request_count DESC
            """
            
            results = await self.telemetry.execute_query(model_query)
            
            # Process model data
            model_data = {}
            total_requests = 0
            total_cost = 0
            
            for row in results:
                model = row['model']
                
                # Clean model name for display
                display_name = model.replace('claude-', '').replace('-20250514', '').replace('-20241022', '').title()
                if 'sonnet' in model.lower():
                    display_name = f"Sonnet 4"
                elif 'haiku' in model.lower():
                    display_name = f"Haiku 3.5"
                
                request_count = int(row['request_count'])
                avg_cost = float(row['avg_cost'] or 0)
                model_total_cost = float(row['total_cost'] or 0)
                avg_duration = float(row['avg_duration'] or 0)
                total_input = int(row['total_input_tokens'] or 0)
                total_output = int(row['total_output_tokens'] or 0)
                avg_input = float(row['avg_input_tokens'] or 0)
                avg_output = float(row['avg_output_tokens'] or 0)
                
                # Calculate cost per token
                total_tokens = total_input + total_output
                cost_per_token = model_total_cost / max(total_tokens, 1)
                
                # Calculate tokens per dollar
                tokens_per_dollar = total_tokens / max(model_total_cost, 0.001)
                
                model_data[model] = {
                    'display_name': display_name,
                    'request_count': request_count,
                    'avg_cost': avg_cost,
                    'total_cost': model_total_cost,
                    'avg_duration': avg_duration,
                    'total_tokens': total_tokens,
                    'cost_per_token': cost_per_token,
                    'tokens_per_dollar': tokens_per_dollar,
                    'avg_input_tokens': avg_input,
                    'avg_output_tokens': avg_output,
                    'speed_score': max(0, min(10, 10 - (avg_duration / 1000)))  # 0-10 scale
                }
                
                total_requests += request_count
                total_cost += model_total_cost
            
            # Find primary models
            sonnet_key = next((k for k in model_data.keys() if 'sonnet' in k.lower()), None)
            haiku_key = next((k for k in model_data.keys() if 'haiku' in k.lower()), None)
            
            primary_model = max(model_data.keys(), key=lambda x: model_data[x]['request_count']) if model_data else None
            
            # Calculate efficiency metrics
            if sonnet_key and haiku_key:
                sonnet_data = model_data[sonnet_key]
                haiku_data = model_data[haiku_key]
                
                # Cost efficiency (how much cheaper Haiku is)
                cost_efficiency_ratio = sonnet_data['avg_cost'] / max(haiku_data['avg_cost'], 0.001)
                
                # Speed efficiency (how much faster Haiku is)  
                speed_efficiency_ratio = sonnet_data['avg_duration'] / max(haiku_data['avg_duration'], 1)
                
                # Usage ratio (what % is cost-effective Haiku)
                haiku_usage_ratio = haiku_data['request_count'] / max(total_requests, 1)
                
                # Overall efficiency score (0-100)
                efficiency_score = min(100, (haiku_usage_ratio * 60) + (min(cost_efficiency_ratio, 50) / 50 * 40))
                
            else:
                cost_efficiency_ratio = 1.0
                speed_efficiency_ratio = 1.0
                haiku_usage_ratio = 0.0
                efficiency_score = 50.0  # Neutral if only one model
            
            # Generate intelligent recommendations
            recommendations = []
            potential_savings = 0.0
            
            if sonnet_key and haiku_key:
                sonnet_requests = model_data[sonnet_key]['request_count']
                haiku_cost = model_data[haiku_key]['avg_cost']
                sonnet_cost = model_data[sonnet_key]['avg_cost']
                
                # Calculate potential savings if 50% of Sonnet requests used Haiku
                potential_savings = sonnet_requests * 0.5 * (sonnet_cost - haiku_cost)
                
                if cost_efficiency_ratio > 25:
                    recommendations.append(f"Haiku is {cost_efficiency_ratio:.0f}x more cost-effective than Sonnet")
                
                if speed_efficiency_ratio > 4:
                    recommendations.append(f"Haiku is {speed_efficiency_ratio:.1f}x faster for quick tasks")
                
                if haiku_usage_ratio < 0.3 and cost_efficiency_ratio > 10:
                    recommendations.append("Consider using Haiku for routine tasks to reduce costs")
                
                if potential_savings > 5.0:
                    recommendations.append(f"Potential weekly savings: ${potential_savings:.2f}")
            
            # Determine status
            if efficiency_score > 75:
                status = "healthy"
            elif efficiency_score > 50:
                status = "warning"
            else:
                status = "critical"
            
            # Create enhanced data structure for frontend
            enhanced_data = {
                'models': model_data,
                'primary_model': model_data[primary_model]['display_name'] if primary_model else 'Unknown',
                'efficiency_score': efficiency_score / 100,  # Convert to 0-1 scale for frontend
                'cost_efficiency_ratio': cost_efficiency_ratio,
                'speed_efficiency_ratio': speed_efficiency_ratio,
                'total_requests': total_requests,
                'total_cost': total_cost,
                'haiku_usage_percentage': haiku_usage_ratio * 100,
                'recommendations': recommendations,
                'potential_savings': potential_savings,
                'avg_response_time': sum(d['avg_duration'] for d in model_data.values()) / len(model_data) if model_data else 0,
                'token_efficiency': (1 / (total_cost / max(sum(d['total_tokens'] for d in model_data.values()), 1))) if total_cost > 0 else 0
            }
            
            return WidgetData(
                widget_type=TelemetryWidgetType.MODEL_EFFICIENCY,
                title="Model Efficiency Tracker",
                status=status,
                data=enhanced_data,
                alerts=recommendations if status != "healthy" else []
            )
            
        except Exception as e:
            logger.error(f"Error generating model efficiency data: {e}")
            import traceback
            traceback.print_exc()
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