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

# Phase 4: JSONL Analytics imports
try:
    from ..jsonl_enhancement.full_content_queries import FullContentQueries
    from ..jsonl_enhancement.jsonl_processor_service import JsonlProcessorService
    JSONL_ANALYTICS_AVAILABLE = True
except ImportError:
    JSONL_ANALYTICS_AVAILABLE = False
    
    class FullContentQueries:
        def __init__(self, **kwargs): pass
        async def get_complete_conversation(self, session_id): return {}
        async def get_content_statistics(self): return {}
        async def search_conversation_content(self, term, limit=50): return []
    
    class JsonlProcessorService:
        def __init__(self, **kwargs): pass
        async def get_processing_status(self): return {}

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
    # Phase 4: JSONL Analytics Widgets
    CONVERSATION_TIMELINE = "conversation_timeline"
    CODE_PATTERN_ANALYSIS = "code_pattern_analysis"
    CONTENT_SEARCH_WIDGET = "content_search_widget"


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


# Phase 4: JSONL Analytics Widget Data Structures

@dataclass
class ConversationTimelineData:
    """Interactive conversation timeline data"""
    session_id: str
    timeline_events: List[Dict[str, Any]]  # chronological events (messages, tool uses, file accesses)
    conversation_metrics: Dict[str, Any]   # duration, message count, tool usage stats
    key_insights: List[str]                # notable patterns or achievements in the conversation
    error_events: List[Dict[str, Any]]     # errors and recovery events
    file_operations: List[Dict[str, Any]]  # file access timeline
    tool_sequence: List[Dict[str, Any]]    # tool usage patterns and chains


@dataclass
class CodePatternAnalysisData:
    """Code pattern analysis widget data"""
    language_distribution: Dict[str, float]  # programming languages with percentages
    common_patterns: List[Dict[str, Any]]    # frequently used code patterns
    function_analysis: Dict[str, Any]        # function usage and complexity metrics
    file_type_breakdown: Dict[str, int]      # file types accessed with counts
    development_trends: List[Dict[str, Any]] # trends over time
    optimization_suggestions: List[str]     # recommendations based on patterns


@dataclass
class ContentSearchWidgetData:
    """Content search interface widget data"""
    recent_searches: List[Dict[str, Any]]    # recent search queries and results
    popular_search_terms: List[str]         # frequently searched terms
    search_performance: Dict[str, Any]      # search speed and accuracy metrics
    content_categories: Dict[str, int]      # available content types and counts
    search_suggestions: List[str]           # intelligent search suggestions
    indexed_content_stats: Dict[str, Any]   # statistics about searchable content


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
        
        # Phase 4: JSONL Analytics components
        if JSONL_ANALYTICS_AVAILABLE:
            self.content_queries = FullContentQueries(telemetry_client)
            self.jsonl_processor = JsonlProcessorService(telemetry_client)
        else:
            self.content_queries = FullContentQueries()
            self.jsonl_processor = JsonlProcessorService()
        
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
            TelemetryWidgetType.WORKFLOW_PERFORMANCE: 180,  # Workflow performance analytics (3 min)
            # Phase 4: JSONL Analytics widgets
            TelemetryWidgetType.CONVERSATION_TIMELINE: 30,   # Conversation timeline updates
            TelemetryWidgetType.CODE_PATTERN_ANALYSIS: 120, # Code pattern analysis (2 min)
            TelemetryWidgetType.CONTENT_SEARCH_WIDGET: 60   # Content search metrics (1 min)
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
        # Phase 4: JSONL Analytics widgets
        elif widget_type == TelemetryWidgetType.CONVERSATION_TIMELINE:
            data = await self._get_conversation_timeline_data(session_id)
        elif widget_type == TelemetryWidgetType.CODE_PATTERN_ANALYSIS:
            data = await self._get_code_pattern_analysis_data(session_id)
        elif widget_type == TelemetryWidgetType.CONTENT_SEARCH_WIDGET:
            data = await self._get_content_search_widget_data(session_id)
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
        """Show real-time session activity and system performance insights"""
        try:
            # Get current session activity and performance metrics
            activity_query = """
            SELECT 
                COUNT(DISTINCT LogAttributes['session.id']) as active_sessions_today,
                COUNT(DISTINCT CASE WHEN Timestamp >= now() - INTERVAL 1 HOUR 
                    THEN LogAttributes['session.id'] END) as sessions_last_hour,
                COUNT(*) as total_events_today,
                COUNT(DISTINCT LogAttributes['tool_name']) as unique_tools_used,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as error_events,
                AVG(CASE WHEN LogAttributes['cost_usd'] IS NOT NULL 
                    AND LogAttributes['cost_usd'] <> '' 
                    THEN toFloat64OrNull(LogAttributes['cost_usd']) END) as avg_cost_per_event,
                MAX(Timestamp) as last_activity
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL 24 HOUR
            """
            
            # Get tool usage velocity for real-time insights
            velocity_query = """
            SELECT 
                LogAttributes['tool_name'] as tool_name,
                COUNT(*) as uses_last_hour
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL 1 HOUR
                AND LogAttributes['tool_name'] IS NOT NULL
            GROUP BY LogAttributes['tool_name']
            ORDER BY uses_last_hour DESC
            LIMIT 3
            """
            
            results = await self.telemetry.execute_query(activity_query)
            velocity_results = await self.telemetry.execute_query(velocity_query)
            
            if not results:
                return WidgetData(
                    widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                    title="System Activity Monitor",
                    status="warning",
                    data={'message': 'No activity data available'},
                    alerts=["System appears offline - no telemetry data"]
                )
            
            data = results[0]
            sessions_today = int(data.get('active_sessions_today', 0))
            sessions_hour = int(data.get('sessions_last_hour', 0))
            total_events = int(data.get('total_events_today', 0))
            unique_tools = int(data.get('unique_tools_used', 0))
            error_events = int(data.get('error_events', 0))
            avg_cost = float(data.get('avg_cost_per_event', 0) or 0)
            
            # Calculate key metrics
            error_rate = (error_events / total_events * 100) if total_events > 0 else 0
            events_per_session = total_events / sessions_today if sessions_today > 0 else 0
            
            # Get top active tools
            top_tools = [f"{r['tool_name']} ({r['uses_last_hour']}x)" 
                        for r in velocity_results] if velocity_results else []
            
            # Determine system status and generate insights
            status = "operational"
            alerts = []
            
            if sessions_hour == 0:
                status = "idle"
                alerts.append("No active sessions in the last hour")
            elif error_rate > 15:
                status = "error"
                alerts.append(f"High error rate: {error_rate:.1f}% - System needs attention")
            elif error_rate > 8:
                status = "warning"
                alerts.append(f"Elevated error rate: {error_rate:.1f}% - Monitor closely")
            
            if avg_cost > 0.05:
                alerts.append(f"High cost per operation: ${avg_cost:.4f}")
            
            if events_per_session > 1000:
                alerts.append(f"Heavy session load: {events_per_session:.0f} events/session")
                
            # Add performance insights
            insights = []
            if sessions_hour > 0:
                insights.append(f"Current velocity: {sessions_hour} sessions/hour")
            if top_tools:
                insights.append(f"Most active tools: {', '.join(top_tools[:2])}")
                
            activity_data = {
                # Template expects these field names
                'active_workflows': sessions_hour,
                'queue_depth': 0,  # We don't have queued concept in telemetry  
                'success_rate': (100 - error_rate) / 100,  # Convert to decimal for template
                
                # Rich data for insights
                'sessions_today': sessions_today,
                'sessions_active_hour': sessions_hour,
                'total_events_today': total_events,
                'unique_tools_today': unique_tools,
                'error_rate_today': f"{error_rate:.1f}%",
                'avg_events_per_session': f"{events_per_session:.0f}",
                'avg_cost_per_event': f"${avg_cost:.4f}",
                'top_active_tools': top_tools,
                'performance_insights': insights,
                'system_load_indicator': min(100, sessions_hour * 10)
            }
            
            return WidgetData(
                widget_type=TelemetryWidgetType.ORCHESTRATION_STATUS,
                title="System Activity Monitor",
                status=status,
                data=activity_data,
                alerts=alerts
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
                alerts=[f"Error: {str(e)}"]
            )
    
    async def _get_agent_utilization_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Show tool usage patterns and identify optimization opportunities"""
        try:
            # Get tool usage patterns to identify optimization opportunities
            usage_query = """
            SELECT 
                LogAttributes['tool_name'] as tool_name,
                COUNT(*) as total_uses_today,
                COUNT(DISTINCT LogAttributes['session.id']) as sessions_using,
                COUNT(CASE WHEN Timestamp >= now() - INTERVAL 1 HOUR THEN 1 END) as uses_last_hour,
                SUM(CASE WHEN Body = 'claude_code.api_error' 
                    AND LogAttributes['tool_name'] IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM otel.otel_logs
            WHERE Timestamp >= now() - INTERVAL 24 HOUR
                AND LogAttributes['tool_name'] IS NOT NULL
                AND LogAttributes['tool_name'] != ''
            GROUP BY LogAttributes['tool_name']
            ORDER BY total_uses_today DESC
            """

            
            results = await self.telemetry.execute_query(usage_query)
            
            if not results:
                return WidgetData(
                    widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                    title="Tool Usage Analytics",
                    status="warning",
                    data={'message': 'No tool usage data available'},
                    alerts=["No tool activity detected"]
                )
            
            # Process tool usage data to extract meaningful insights
            total_uses = sum(int(r['total_uses_today']) for r in results)
            total_errors = sum(int(r['error_count']) for r in results)
            
            # Categorize tools by usage and performance patterns
            heavy_usage_tools = []
            error_prone_tools = []
            recent_activity_tools = []
            
            tool_details = {}
            
            for tool_data in results:
                tool_name = tool_data['tool_name'] 
                uses_today = int(tool_data['total_uses_today'])
                sessions = int(tool_data['sessions_using'])
                recent_uses = int(tool_data['uses_last_hour'])
                errors = int(tool_data['error_count'])
                
                usage_percentage = (uses_today / total_uses * 100) if total_uses > 0 else 0
                error_rate = (errors / uses_today * 100) if uses_today > 0 else 0
                
                tool_details[tool_name] = {
                    'uses_today': uses_today,
                    'sessions_using': sessions,
                    'recent_activity': recent_uses,
                    'error_count': errors,
                    'usage_percentage': round(usage_percentage, 1),
                    'error_rate': round(error_rate, 1)
                }
                
                # Categorize tools for insights
                if usage_percentage > 15:
                    heavy_usage_tools.append(tool_name)
                if error_rate > 10 and uses_today > 10:
                    error_prone_tools.append(tool_name)
                if recent_uses > 0:
                    recent_activity_tools.append(tool_name)
            
            # Generate actionable insights
            system_error_rate = (total_errors / total_uses * 100) if total_uses > 0 else 0
            
            insights = []
            if heavy_usage_tools:
                insights.append(f"Heavy usage: {', '.join(heavy_usage_tools[:3])}")
            if error_prone_tools:
                insights.append(f"Error-prone tools: {', '.join(error_prone_tools[:2])}")
            if len(recent_activity_tools) > 0:
                insights.append(f"{len(recent_activity_tools)} tools active in last hour")
                
            # Determine status
            status = "operational"
            alerts = []
            
            if system_error_rate > 15:
                status = "error"
                alerts.append(f"High system error rate: {system_error_rate:.1f}%")
            elif system_error_rate > 8:
                status = "warning"
                alerts.append(f"Elevated error rate: {system_error_rate:.1f}%")
                
            if len(error_prone_tools) > 2:
                alerts.append(f"Multiple error-prone tools detected")
                
            # Top 5 tools summary
            top_5_tools = sorted(results[:5], key=lambda x: int(x['total_uses_today']), reverse=True)
            top_tools_summary = [
                f"{tool['tool_name']}: {tool['total_uses_today']} uses"
                for tool in top_5_tools
            ]
            
            usage_data = {
                # Template expects these field names
                'active_agents': len(recent_activity_tools),
                'utilization_rate': min(100, len(heavy_usage_tools) * 20) / 100,  # Percentage as decimal  
                'avg_response_time': 45 if heavy_usage_tools else 0,  # Estimate based on activity
                
                # Rich data for insights
                'total_tools_active': len(results),
                'total_uses_today': total_uses,
                'system_error_rate': f"{system_error_rate:.1f}%",
                'tools_with_recent_activity': len(recent_activity_tools),
                'heavy_usage_tools': heavy_usage_tools[:5],
                'error_prone_tools': error_prone_tools[:5], 
                'top_tools_summary': top_tools_summary,
                'insights': insights,
                'tool_breakdown': dict(sorted(tool_details.items(), 
                                           key=lambda x: x[1]['uses_today'], reverse=True)[:8])
            }
            
            return WidgetData(
                widget_type=TelemetryWidgetType.AGENT_UTILIZATION,
                title="Tool Usage Analytics",
                status=status,
                data=usage_data,
                alerts=alerts
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
                alerts=[f"Error: {str(e)}"]
            )
    
    async def _get_workflow_performance_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Show session performance patterns and optimization insights"""
        try:
            # Get workflow (session) performance patterns from telemetry - simplified
            performance_query = """
            WITH session_analysis AS (
                SELECT 
                    LogAttributes['session.id'] as session_id,
                    COUNT(DISTINCT LogAttributes['tool_name']) as unique_tools,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as error_count,
                    SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as session_cost,
                    dateDiff('minute', MIN(Timestamp), MAX(Timestamp)) as duration_minutes
                FROM otel.otel_logs
                WHERE Timestamp >= now() - INTERVAL 7 DAY
                    AND LogAttributes['session.id'] IS NOT NULL
                GROUP BY LogAttributes['session.id']
                HAVING total_events > 5  -- Only sessions with meaningful activity
            )
            SELECT 
                'all_workflows' as workflow_type,
                COUNT(*) as execution_count,
                ROUND(AVG(duration_minutes), 1) as avg_duration,
                ROUND(AVG(session_cost), 4) as avg_cost,
                ROUND(AVG(unique_tools), 1) as avg_tools,
                ROUND((COUNT(*) - SUM(CASE WHEN error_count > 0 THEN 1 ELSE 0 END)) * 100.0 / COUNT(*), 1) as success_rate,
                SUM(CASE WHEN error_count > 0 THEN 1 ELSE 0 END) as failed_workflows,
                ROUND(AVG(CASE WHEN duration_minutes > 0 THEN unique_tools / duration_minutes ELSE 0 END), 2) as efficiency_score
            FROM session_analysis
            """
            
            results = await self.telemetry.execute_query(performance_query)
            
            if not results:
                return WidgetData(
                    widget_type=TelemetryWidgetType.WORKFLOW_PERFORMANCE,
                    title="Workflow Performance",
                    status="warning", 
                    data={
                        'workflow_templates': {},
                        'optimization_opportunities': [],
                        'performance_trends': {},
                        'total_workflows': 0
                    },
                    alerts=["No workflow data available"]
                )
            
            # Process workflow performance data
            workflow_templates = {}
            total_workflows = 0
            total_success_rate = 0
            optimization_opportunities = []
            
            for workflow in results:
                workflow_type = workflow['workflow_type']
                execution_count = int(workflow['execution_count'])
                avg_duration = float(workflow['avg_duration'])
                avg_cost = float(workflow['avg_cost'])
                success_rate = float(workflow['success_rate'])
                failed_count = int(workflow['failed_workflows'])
                efficiency_score = float(workflow['efficiency_score'])
                
                # Calculate cost efficiency (higher efficiency = lower cost per tool per minute)
                cost_efficiency = min(1.0, max(0.1, 1.0 / (avg_cost + 0.01)))
                
                workflow_templates[workflow_type] = {
                    'success_rate': success_rate,
                    'avg_duration': avg_duration,
                    'cost_efficiency': cost_efficiency,
                    'execution_count': execution_count,
                    'avg_cost': avg_cost,
                    'failed_count': failed_count,
                    'efficiency_score': efficiency_score
                }
                
                total_workflows += execution_count
                total_success_rate += success_rate * execution_count
                
                # Generate optimization opportunities
                if success_rate < 85:
                    optimization_opportunities.append({
                        'workflow': workflow_type,
                        'opportunity': f'Improve error handling (success rate: {success_rate:.1f}%)',
                        'potential_improvement': f'{100 - success_rate:.0f}% failure reduction',
                        'priority': 'high' if success_rate < 75 else 'medium'
                    })
                
                if avg_duration > 30:
                    optimization_opportunities.append({
                        'workflow': workflow_type,
                        'opportunity': f'Reduce workflow duration ({avg_duration:.1f} min average)',
                        'potential_improvement': f'{(avg_duration - 15):.0f} min time savings potential',
                        'priority': 'medium'
                    })
                
                if efficiency_score < 0.5:
                    optimization_opportunities.append({
                        'workflow': workflow_type,
                        'opportunity': 'Optimize tool usage patterns',
                        'potential_improvement': f'{(1 - efficiency_score) * 100:.0f}% efficiency improvement',
                        'priority': 'low'
                    })
            
            # Calculate overall performance metrics
            avg_success_rate = (total_success_rate / total_workflows) if total_workflows > 0 else 0
            cost_scores = [w.get('cost_efficiency', 0) for w in workflow_templates.values()]
            avg_cost_efficiency = sum(cost_scores) / len(cost_scores) if cost_scores else 0.0
            
            # Generate pattern insights from the data
            pattern_insights = []
            if workflow_templates:
                # Find best performing workflow
                best_workflow = max(workflow_templates.items(), key=lambda x: x[1]['success_rate'])
                pattern_insights.append(f"{best_workflow[0]} workflows show best success rate: {best_workflow[1]['success_rate']:.1f}%")
                
                # Find most cost-efficient workflow
                best_cost = max(workflow_templates.items(), key=lambda x: x[1]['cost_efficiency'])
                pattern_insights.append(f"{best_cost[0]} workflows are most cost-efficient")
                
                # Add general insight about tool usage
                pattern_insights.append("Workflows with balanced tool usage show better efficiency scores")
            
            # Sort optimization opportunities by priority
            priority_order = {'high': 3, 'medium': 2, 'low': 1}
            optimization_opportunities.sort(key=lambda x: priority_order.get(x['priority'], 0), reverse=True)
            
            # Determine overall status and create detailed alerts
            alerts = []
            if avg_success_rate < 80:
                status = "critical"
                alerts.append(f"Low overall success rate: {avg_success_rate:.1f}%")
            elif avg_success_rate < 90 or len(optimization_opportunities) > 3:
                status = "warning"
                # Add specific optimization opportunities to alerts
                if optimization_opportunities:
                    alerts.append(f"{len(optimization_opportunities)} optimization opportunities:")
                    for opt in optimization_opportunities[:2]:  # Show top 2 in alerts
                        alerts.append(f"• {opt['opportunity']} → {opt['potential_improvement']}")
                else:
                    alerts.append("Performance optimization opportunities available")
            else:
                status = "healthy"
            
            # Calculate template-expected fields from workflow data
            completed_today = total_workflows  
            durations = [w.get('avg_duration', 0) for w in workflow_templates.values()]
            avg_duration_minutes = sum(durations) / len(durations) if durations else 0
            avg_duration_seconds = round(avg_duration_minutes * 60)  # Convert minutes to seconds
            efficiency_decimal = avg_cost_efficiency
            
            workflow_data = {
                # Template expects these field names
                'completed_today': completed_today,
                'avg_duration': avg_duration_seconds,
                'efficiency_score': efficiency_decimal,
                
                # Rich data for insights
                'workflow_templates': workflow_templates,
                'optimization_opportunities': optimization_opportunities[:10],  # Limit to top 10
                'pattern_insights': pattern_insights,
                'performance_summary': {
                    'total_workflows': total_workflows,
                    'avg_success_rate': round(avg_success_rate, 1),
                    'avg_cost_efficiency': round(avg_cost_efficiency, 2),
                    'top_performing_workflow': best_workflow[0] if workflow_templates else 'None'
                }
            }
            
            return WidgetData(
                widget_type=TelemetryWidgetType.WORKFLOW_PERFORMANCE,
                title="Workflow Performance Analytics",
                status=status,
                data=workflow_data,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"Error generating workflow performance data: {e}")
            import traceback
            traceback.print_exc()
            return WidgetData(
                widget_type=TelemetryWidgetType.WORKFLOW_PERFORMANCE,
                title="Workflow Performance Analytics",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )

    # Phase 4: JSONL Analytics Widget Implementation Methods
    
    async def _get_conversation_timeline_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate interactive conversation timeline widget data"""
        try:
            if not JSONL_ANALYTICS_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                    title="Conversation Timeline",
                    status="warning",
                    data={},
                    alerts=["JSONL Analytics not available"]
                )
            
            # Get recent sessions if no session_id provided
            if not session_id:
                recent_sessions = await self.content_queries.get_recent_sessions(limit=1)
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
                                "files_accessed": 0
                            },
                            "key_insights": ["No recent conversations found"],
                            "error_events": [],
                            "file_operations": [],
                            "tool_sequence": []
                        },
                        alerts=["No recent conversation data available"]
                    )
                
                session_id = recent_sessions[0]['session_id']
            
            # Get conversation timeline data
            conversation_data = await self.content_queries.get_complete_conversation(session_id)
            
            # Build timeline events from conversation data
            timeline_events = []
            conversation_metrics = {
                'total_messages': len(conversation_data) if conversation_data else 0,
                'duration_minutes': 0,
                'tools_used': 0,
                'files_accessed': 0
            }
            
            # Process conversation data into timeline events
            if conversation_data:
                first_timestamp = None
                last_timestamp = None
                
                for msg in conversation_data:
                    timestamp = msg.get('timestamp', '')
                    if timestamp:
                        if first_timestamp is None:
                            first_timestamp = timestamp
                        last_timestamp = timestamp
                    
                    event = {
                        'timestamp': timestamp,
                        'type': 'message',
                        'role': msg.get('role', 'unknown'),
                        'content_preview': str(msg.get('message_content', ''))[:100] + '...' if msg.get('message_content') else 'No content',
                        'has_code': bool(msg.get('contains_code_blocks', False)),
                        'languages': msg.get('programming_languages', []) or [],
                        'tokens': {
                            'input': msg.get('input_tokens', 0),
                            'output': msg.get('output_tokens', 0)
                        },
                        'cost': msg.get('cost_usd', 0),
                        'model': msg.get('model_name', 'unknown')
                    }
                    timeline_events.append(event)
                
                # Calculate duration
                if first_timestamp and last_timestamp and first_timestamp != last_timestamp:
                    try:
                        from datetime import datetime
                        if isinstance(first_timestamp, str):
                            first_dt = datetime.fromisoformat(first_timestamp.replace('Z', '+00:00'))
                            last_dt = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                            duration = (last_dt - first_dt).total_seconds() / 60
                            conversation_metrics['duration_minutes'] = round(duration, 1)
                    except Exception:
                        pass
                
                # Count tools and files (would need separate queries for accurate counts)
                conversation_metrics['tools_used'] = sum(1 for event in timeline_events if event.get('has_code'))
                conversation_metrics['files_accessed'] = 0  # Would need file access data
            
            # Generate key insights
            key_insights = []
            if conversation_metrics['total_messages'] > 10:
                key_insights.append("Long conversation with extensive interaction")
            if any(event.get('has_code') for event in timeline_events):
                key_insights.append("Contains code blocks and programming content")
            if conversation_metrics['duration_minutes'] > 60:
                key_insights.append(f"Extended session ({conversation_metrics['duration_minutes']:.1f} minutes)")
            
            # Calculate total cost
            total_cost = sum(event.get('cost', 0) for event in timeline_events)
            if total_cost > 0:
                key_insights.append(f"Session cost: ${total_cost:.4f}")
            
            # Determine status
            status = "healthy" if conversation_metrics['total_messages'] > 0 else "warning"
            
            timeline_data = ConversationTimelineData(
                session_id=session_id or "unknown",
                timeline_events=timeline_events,
                conversation_metrics=conversation_metrics,
                key_insights=key_insights,
                error_events=[],  # Could be populated with error tracking data
                file_operations=[],  # Could be populated with file access data
                tool_sequence=[]  # Could be populated with tool usage data
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                title="Conversation Timeline",
                status=status,
                data=timeline_data.__dict__,
                alerts=[]
            )
            
        except Exception as e:
            logger.error(f"Error generating conversation timeline data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.CONVERSATION_TIMELINE,
                title="Conversation Timeline",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )
    
    async def _get_code_pattern_analysis_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate code pattern analysis widget data"""
        try:
            if not JSONL_ANALYTICS_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                    title="Code Pattern Analysis",
                    status="warning",
                    data={},
                    alerts=["JSONL Analytics not available"]
                )
            
            # Get content statistics for code pattern analysis
            content_stats = await self.content_queries.get_content_statistics()
            
            # Extract language distribution
            language_distribution = {}
            if content_stats.get('files', {}).get('top_file_languages'):
                langs = content_stats['files']['top_file_languages'].split(', ')
                # Simple distribution for demo
                total = len(langs)
                for i, lang in enumerate(langs):
                    language_distribution[lang] = ((total - i) / total) * 100
            
            # Generate insights based on content statistics
            optimization_suggestions = []
            common_patterns = []
            
            if language_distribution:
                top_lang = max(language_distribution.keys(), key=language_distribution.get)
                optimization_suggestions.append(f"Focus on {top_lang} optimization patterns")
                common_patterns.append({
                    'pattern': f'{top_lang} development',
                    'frequency': language_distribution[top_lang],
                    'description': f'Heavy {top_lang} usage detected'
                })
            
            # File type breakdown
            file_type_breakdown = {
                'code': content_stats.get('files', {}).get('total_file_accesses', 0),
                'config': 0,  # Could be calculated from file extensions
                'documentation': 0
            }
            
            status = "healthy" if language_distribution else "warning"
            
            code_data = CodePatternAnalysisData(
                language_distribution=language_distribution,
                common_patterns=common_patterns,
                function_analysis={'detected_functions': 0},  # Could be enhanced
                file_type_breakdown=file_type_breakdown,
                development_trends=[],  # Could add time-based trends
                optimization_suggestions=optimization_suggestions
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                title="Code Pattern Analysis",
                status=status,
                data=code_data.__dict__,
                alerts=[]
            )
            
        except Exception as e:
            logger.error(f"Error generating code pattern analysis data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.CODE_PATTERN_ANALYSIS,
                title="Code Pattern Analysis",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )
    
    async def _get_content_search_widget_data(self, session_id: Optional[str] = None) -> WidgetData:
        """Generate content search interface widget data"""
        try:
            if not JSONL_ANALYTICS_AVAILABLE:
                return WidgetData(
                    widget_type=TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                    title="Content Search",
                    status="warning",
                    data={},
                    alerts=["JSONL Analytics not available"]
                )
            
            # Get content statistics for search capabilities
            content_stats = await self.content_queries.get_content_statistics()
            
            # Calculate indexed content stats
            indexed_content_stats = {
                'total_messages': content_stats.get('messages', {}).get('total_messages', 0),
                'total_files': content_stats.get('files', {}).get('total_file_accesses', 0),
                'total_tools': content_stats.get('tools', {}).get('total_tool_executions', 0),
                'searchable_characters': content_stats.get('messages', {}).get('total_characters', 0)
            }
            
            # Content categories available for search
            content_categories = {
                'Messages': indexed_content_stats['total_messages'],
                'Files': indexed_content_stats['total_files'],
                'Tool Results': indexed_content_stats['total_tools']
            }
            
            # Generate search suggestions based on available content
            search_suggestions = []
            if content_stats.get('messages', {}).get('top_languages'):
                langs = content_stats['messages']['top_languages'].split(', ')
                search_suggestions.extend([f"code in {lang}" for lang in langs[:3]])
            
            search_suggestions.extend([
                "error messages",
                "function definitions",
                "file operations",
                "recent conversations"
            ])
            
            # Search performance metrics (simulated)
            search_performance = {
                'avg_response_time_ms': 250,
                'index_size_mb': indexed_content_stats['searchable_characters'] / (1024 * 1024),
                'search_accuracy': 0.95
            }
            
            status = "healthy" if indexed_content_stats['total_messages'] > 0 else "warning"
            
            search_data = ContentSearchWidgetData(
                recent_searches=[],  # Could be populated with search history
                popular_search_terms=search_suggestions[:5],
                search_performance=search_performance,
                content_categories=content_categories,
                search_suggestions=search_suggestions,
                indexed_content_stats=indexed_content_stats
            )
            
            return WidgetData(
                widget_type=TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                title="Content Search",
                status=status,
                data=search_data.__dict__,
                alerts=[]
            )
            
        except Exception as e:
            logger.error(f"Error generating content search widget data: {e}")
            return WidgetData(
                widget_type=TelemetryWidgetType.CONTENT_SEARCH_WIDGET,
                title="Content Search",
                status="error",
                data={},
                alerts=[f"Error: {str(e)}"]
            )