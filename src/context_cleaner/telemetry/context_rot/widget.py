"""Context Rot Meter Widget for Dashboard Integration."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from ..dashboard.widgets import WidgetData, TelemetryWidgetType
from ..clients.clickhouse_client import ClickHouseClient
from .analyzer import ContextRotAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ContextRotMeterData:
    """Context Rot Meter widget data structure."""
    current_rot_score: float  # 0.0 to 1.0
    confidence_level: float   # 0.0 to 1.0
    session_health_status: str  # "healthy", "degraded", "critical"
    trend_direction: str        # "improving", "stable", "degrading" 
    measurements_count: int     # Number of recent measurements
    attention_alerts: int       # Number of attention-requiring events
    time_window_minutes: int    # Analysis time window
    
    # Detailed breakdown
    repetition_score: float = 0.0
    efficiency_score: float = 0.0
    health_score: float = 0.0
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    # Performance metrics
    analysis_latency_ms: float = 0.0
    memory_usage_mb: float = 0.0
    
    # Historical data for trending
    hourly_averages: List[Dict[str, Any]] = field(default_factory=list)


class ContextRotWidget:
    """Context Rot Meter widget for real-time conversation quality monitoring."""
    
    widget_type = TelemetryWidgetType.CONTEXT_ROT_METER
    
    def __init__(self, clickhouse_client: ClickHouseClient, context_rot_analyzer: ContextRotAnalyzer):
        """
        Initialize Context Rot Widget.
        
        Args:
            clickhouse_client: ClickHouse client for data queries
            context_rot_analyzer: Context rot analyzer instance
        """
        self.clickhouse_client = clickhouse_client
        self.analyzer = context_rot_analyzer
        self.last_update = None
        self._cache = {}
        self._cache_ttl = 30  # seconds
        
    async def get_widget_data(self, session_id: Optional[str] = None, time_window_minutes: int = 30) -> WidgetData:
        """
        Get context rot widget data for dashboard display.
        
        Args:
            session_id: Specific session to analyze (optional)
            time_window_minutes: Time window for analysis
            
        Returns:
            WidgetData formatted for dashboard consumption
        """
        start_time = datetime.now()
        
        try:
            # Check cache first
            cache_key = f"{session_id}:{time_window_minutes}"
            if self._is_cache_valid(cache_key):
                cached_data = self._cache[cache_key]
                logger.debug(f"Using cached context rot data for {cache_key}")
                return cached_data
            
            # Get context rot metrics
            if session_id:
                # Session-specific analysis
                context_rot_data = await self._get_session_context_rot(session_id, time_window_minutes)
                title = f"Context Rot - Session {session_id[:8]}..."
            else:
                # Global analysis across all recent sessions
                context_rot_data = await self._get_global_context_rot(time_window_minutes)
                title = "Context Rot - Global Overview"
            
            # Get system metrics
            system_metrics = await self.analyzer.get_analyzer_status()
            
            # Calculate analysis latency
            analysis_latency = (datetime.now() - start_time).total_seconds() * 1000
            
            # Determine overall status
            status = self._determine_status(context_rot_data)
            
            # Generate alerts
            alerts = self._generate_alerts(context_rot_data)
            
            # Create widget data
            widget_data = WidgetData(
                widget_type=self.widget_type,
                title=title,
                status=status,
                data={
                    'context_rot': context_rot_data,
                    'system_metrics': system_metrics,
                    'analysis_latency_ms': analysis_latency,
                    'session_id': session_id,
                    'time_window_minutes': time_window_minutes
                },
                alerts=alerts
            )
            
            # Cache the result
            self._cache[cache_key] = widget_data
            self._cache[f"{cache_key}:timestamp"] = datetime.now()
            
            logger.info(f"Context rot widget data generated in {analysis_latency:.1f}ms")
            return widget_data
            
        except Exception as e:
            logger.error(f"Error generating context rot widget data: {e}")
            return self._get_error_widget_data(str(e), session_id)
    
    async def _get_session_context_rot(self, session_id: str, time_window_minutes: int) -> ContextRotMeterData:
        """Get context rot data for a specific session."""
        try:
            # Get session health analysis
            health_analysis = await self.analyzer.analyze_session_health(session_id, time_window_minutes)
            
            if health_analysis.get('status') == 'no_data':
                return ContextRotMeterData(
                    current_rot_score=0.0,
                    confidence_level=0.0,
                    session_health_status="no_data",
                    trend_direction="stable",
                    measurements_count=0,
                    attention_alerts=0,
                    time_window_minutes=time_window_minutes,
                    recommendations=["No recent activity detected for this session"]
                )
            
            # Extract metrics
            metrics = health_analysis.get('metrics', {})
            system_metrics = health_analysis.get('system_health', {})
            
            # Get trending data
            trends = await self.analyzer.get_recent_trends(session_id, hours=24)
            trend_analysis = trends.get('trend_analysis', {})
            
            return ContextRotMeterData(
                current_rot_score=float(metrics.get('average_rot_score', 0.0)),
                confidence_level=float(metrics.get('average_confidence', 0.0)),
                session_health_status=health_analysis.get('status', 'unknown'),
                trend_direction=trend_analysis.get('direction', 'stable'),
                measurements_count=int(metrics.get('measurement_count', 0)),
                attention_alerts=int(metrics.get('attention_alerts', 0)),
                time_window_minutes=time_window_minutes,
                recommendations=health_analysis.get('recommendations', []),
                analysis_latency_ms=float(system_metrics.get('memory_usage_mb', 0.0)),
                memory_usage_mb=float(system_metrics.get('memory_usage_mb', 0.0)),
                hourly_averages=trends.get('hourly_trends', [])
            )
            
        except Exception as e:
            logger.error(f"Error getting session context rot data: {e}")
            return ContextRotMeterData(
                current_rot_score=0.0,
                confidence_level=0.0,
                session_health_status="error",
                trend_direction="unknown",
                measurements_count=0,
                attention_alerts=0,
                time_window_minutes=time_window_minutes,
                recommendations=[f"Analysis error: {str(e)}"]
            )
    
    async def _get_global_context_rot(self, time_window_minutes: int) -> ContextRotMeterData:
        """Get global context rot data across all sessions."""
        try:
            # Query global context rot metrics
            query = """
            SELECT 
                avg(rot_score) as avg_rot_score,
                max(rot_score) as max_rot_score,
                count() as total_measurements,
                uniq(session_id) as active_sessions,
                sum(requires_attention) as total_alerts,
                avg(confidence_score) as avg_confidence
            FROM otel.context_rot_metrics
            WHERE timestamp >= now() - INTERVAL {time_window:Int32} MINUTE
            """
            
            params = {'time_window': time_window_minutes}
            results = await self.clickhouse_client.execute_query(query, params)
            
            if not results or not results[0]['total_measurements']:
                return ContextRotMeterData(
                    current_rot_score=0.0,
                    confidence_level=0.0,
                    session_health_status="no_data",
                    trend_direction="stable",
                    measurements_count=0,
                    attention_alerts=0,
                    time_window_minutes=time_window_minutes,
                    recommendations=["No recent context rot data available"]
                )
            
            data = results[0]
            
            # Calculate global health status
            avg_rot = float(data['avg_rot_score'])
            health_status = "healthy" if avg_rot < 0.3 else "degraded" if avg_rot < 0.7 else "critical"
            
            # Get hourly trends for global view
            hourly_query = """
            SELECT 
                toHour(timestamp) as hour,
                avg(rot_score) as avg_rot,
                count() as measurements
            FROM otel.context_rot_metrics
            WHERE timestamp >= now() - INTERVAL 24 HOUR
            GROUP BY hour
            ORDER BY hour
            """
            
            hourly_results = await self.clickhouse_client.execute_query(hourly_query)
            
            # Simple trend calculation
            if len(hourly_results) >= 3:
                recent_avg = sum(float(row['avg_rot']) for row in hourly_results[-3:]) / 3
                earlier_avg = sum(float(row['avg_rot']) for row in hourly_results[:3]) / 3
                trend = "improving" if recent_avg < earlier_avg else "degrading" if recent_avg > earlier_avg else "stable"
            else:
                trend = "stable"
            
            return ContextRotMeterData(
                current_rot_score=avg_rot,
                confidence_level=float(data['avg_confidence'] or 0.0),
                session_health_status=health_status,
                trend_direction=trend,
                measurements_count=int(data['total_measurements']),
                attention_alerts=int(data['total_alerts']),
                time_window_minutes=time_window_minutes,
                recommendations=self._generate_global_recommendations(data),
                hourly_averages=hourly_results
            )
            
        except Exception as e:
            logger.error(f"Error getting global context rot data: {e}")
            return ContextRotMeterData(
                current_rot_score=0.0,
                confidence_level=0.0,
                session_health_status="error",
                trend_direction="unknown",
                measurements_count=0,
                attention_alerts=0,
                time_window_minutes=time_window_minutes,
                recommendations=[f"Global analysis error: {str(e)}"]
            )
    
    def _generate_global_recommendations(self, data: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on global metrics."""
        recommendations = []
        
        avg_rot = float(data['avg_rot_score'])
        max_rot = float(data['max_rot_score'])
        total_alerts = int(data['total_alerts'])
        active_sessions = int(data['active_sessions'])
        
        if avg_rot > 0.7:
            recommendations.append("High global context rot detected - consider session management best practices")
        elif avg_rot > 0.5:
            recommendations.append("Moderate global context rot - monitor active sessions closely")
        
        if max_rot > 0.8:
            recommendations.append(f"Some sessions showing critical rot levels (max: {max_rot:.2f})")
        
        if total_alerts > 10:
            recommendations.append(f"Multiple attention alerts ({total_alerts}) - review session patterns")
        
        if active_sessions > 50:
            recommendations.append(f"High session volume ({active_sessions}) may impact analysis accuracy")
        
        if not recommendations:
            recommendations.append("Global context rot levels are within healthy ranges")
        
        return recommendations
    
    def _determine_status(self, context_rot_data: ContextRotMeterData) -> str:
        """Determine widget status based on context rot data."""
        if context_rot_data.session_health_status == "error":
            return "critical"
        elif context_rot_data.session_health_status == "no_data":
            return "warning"
        elif context_rot_data.current_rot_score >= 0.7:
            return "critical"
        elif context_rot_data.current_rot_score >= 0.5:
            return "warning"
        else:
            return "healthy"
    
    def _generate_alerts(self, context_rot_data: ContextRotMeterData) -> List[str]:
        """Generate alerts based on context rot data."""
        alerts = []
        
        if context_rot_data.current_rot_score >= 0.8:
            alerts.append(f"CRITICAL: High context rot detected ({context_rot_data.current_rot_score:.2f})")
        elif context_rot_data.current_rot_score >= 0.6:
            alerts.append(f"WARNING: Elevated context rot ({context_rot_data.current_rot_score:.2f})")
        
        if context_rot_data.attention_alerts > 5:
            alerts.append(f"Multiple attention events ({context_rot_data.attention_alerts})")
        
        if context_rot_data.confidence_level < 0.3 and context_rot_data.measurements_count > 5:
            alerts.append("Low confidence in analysis - may need more data")
        
        if context_rot_data.trend_direction == "degrading":
            alerts.append("Context quality is degrading over time")
        
        return alerts
    
    def _get_error_widget_data(self, error_message: str, session_id: Optional[str]) -> WidgetData:
        """Create error widget data when analysis fails."""
        title = f"Context Rot - Error"
        if session_id:
            title = f"Context Rot - Session {session_id[:8]}... (Error)"
        
        return WidgetData(
            widget_type=self.widget_type,
            title=title,
            status="critical",
            data={
                'error': error_message,
                'context_rot': ContextRotMeterData(
                    current_rot_score=0.0,
                    confidence_level=0.0,
                    session_health_status="error",
                    trend_direction="unknown",
                    measurements_count=0,
                    attention_alerts=0,
                    time_window_minutes=30,
                    recommendations=[f"Analysis failed: {error_message}"]
                )
            },
            alerts=[f"Context rot analysis error: {error_message}"]
        )
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        
        timestamp_key = f"{cache_key}:timestamp"
        if timestamp_key not in self._cache:
            return False
        
        cached_time = self._cache[timestamp_key]
        return (datetime.now() - cached_time).total_seconds() < self._cache_ttl
    
    def clear_cache(self):
        """Clear widget cache."""
        self._cache.clear()
        logger.debug("Context rot widget cache cleared")
    
    async def get_widget_status_summary(self) -> Dict[str, Any]:
        """Get a quick status summary for monitoring."""
        try:
            analyzer_status = await self.analyzer.get_analyzer_status()
            
            return {
                'widget_type': self.widget_type.value,
                'status': analyzer_status.get('status', 'unknown'),
                'clickhouse_healthy': analyzer_status.get('clickhouse_connection') == 'healthy',
                'cache_entries': len([k for k in self._cache.keys() if ':timestamp' not in k]),
                'last_update': self.last_update,
                'version': analyzer_status.get('version', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error getting widget status summary: {e}")
            return {
                'widget_type': self.widget_type.value,
                'status': 'error',
                'error': str(e)
            }