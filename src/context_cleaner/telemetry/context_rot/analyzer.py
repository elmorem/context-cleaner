"""Core Context Rot Analyzer with statistical analysis."""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .monitor import ProductionReadyContextRotMonitor, QuickAssessment
from .security import PrivacyConfig
from ..clients.clickhouse_client import ClickHouseClient
from ..error_recovery.manager import ErrorRecoveryManager

logger = logging.getLogger(__name__)


@dataclass
class ContextRotMetric:
    """Structured context rot metric for storage."""
    session_id: str
    timestamp: datetime
    rot_score: float
    confidence_score: float
    indicator_breakdown: Dict[str, float]
    analysis_version: int = 1  # For future compatibility
    requires_attention: bool = False


class StatisticalContextAnalyzer:
    """Statistical context analysis replacing naive pattern matching."""
    
    def __init__(self):
        self.repetition_detector = None  # Will be initialized by monitor
        self.efficiency_tracker = None   # Will be initialized by monitor
        self.session_health = None       # Will be initialized by monitor
    
    def set_components(self, repetition_detector, efficiency_tracker, session_health):
        """Set analysis components from the monitor."""
        self.repetition_detector = repetition_detector
        self.efficiency_tracker = efficiency_tracker
        self.session_health = session_health
    
    async def analyze_sequence(self, event_data: Dict[str, Any]) -> float:
        """Analyze sequence for repetition patterns."""
        if not self.repetition_detector:
            return 0.0
        
        content = event_data.get('content', '')
        return self.repetition_detector.analyze_sequence(content)
    
    async def calculate_trend(self, event_data: Dict[str, Any]) -> float:
        """Calculate efficiency trend."""
        if not self.efficiency_tracker:
            return 0.5  # Neutral
        
        return self.efficiency_tracker.calculate_trend(event_data)


class ContextRotAnalyzer:
    """Main Context Rot Analyzer orchestrating all components."""
    
    def __init__(self, clickhouse_client: ClickHouseClient, error_manager: ErrorRecoveryManager):
        """Initialize with existing infrastructure components."""
        self.clickhouse_client = clickhouse_client
        self.error_manager = error_manager
        
        # Initialize production monitor
        self.monitor = ProductionReadyContextRotMonitor(clickhouse_client, error_manager)
        
        # Initialize statistical analyzer
        self.statistical_analyzer = StatisticalContextAnalyzer()
        
        # Connect components
        self.statistical_analyzer.set_components(
            self.monitor.repetition_detector,
            self.monitor.efficiency_tracker, 
            self.monitor.session_health
        )
        
        logger.info("Context Rot Analyzer initialized with production components")
    
    async def analyze_realtime(self, session_id: str, content: str) -> Optional[ContextRotMetric]:
        """
        Perform real-time context rot analysis.
        
        Args:
            session_id: Current session identifier
            content: Content to analyze
            
        Returns:
            ContextRotMetric if analysis successful, None otherwise
        """
        try:
            # Lightweight real-time analysis
            assessment = await self.monitor.analyze_lightweight(session_id, content)
            
            if not assessment:
                logger.warning("Real-time context rot analysis failed")
                return None
            
            # Convert to structured metric
            metric = ContextRotMetric(
                session_id=session_id,
                timestamp=assessment.timestamp,
                rot_score=assessment.rot_estimate,
                confidence_score=assessment.confidence,
                indicator_breakdown=assessment.indicators.copy(),
                requires_attention=assessment.requires_attention
            )
            
            # Store in ClickHouse if configured
            await self._store_metric(metric)
            
            return metric
            
        except Exception as e:
            logger.error(f"Context rot analysis error for session {session_id}: {e}")
            return None
    
    async def analyze_session_health(self, session_id: str, time_window_minutes: int = 30) -> Dict[str, Any]:
        """
        Analyze overall session health over a time window.
        
        Args:
            session_id: Session to analyze
            time_window_minutes: Time window for analysis
            
        Returns:
            Dict containing session health metrics
        """
        try:
            # Get recent metrics from ClickHouse
            query = """
            SELECT 
                avg(rot_score) as avg_rot_score,
                max(rot_score) as max_rot_score,
                count() as measurement_count,
                sum(case when requires_attention then 1 else 0 end) as attention_alerts,
                avg(confidence_score) as avg_confidence
            FROM otel.context_rot_metrics
            WHERE session_id = {session_id:String}
                AND timestamp >= now() - INTERVAL {time_window:Int32} MINUTE
            """
            
            params = {
                'session_id': session_id,
                'time_window': time_window_minutes
            }
            
            results = await self.clickhouse_client.execute_query(query, params)
            
            if not results or not results[0]['measurement_count']:
                return {
                    'session_id': session_id,
                    'status': 'no_data',
                    'message': f'No context rot data available for the last {time_window_minutes} minutes'
                }
            
            data = results[0]
            
            # System metrics
            system_metrics = await self.monitor.get_system_metrics()
            
            return {
                'session_id': session_id,
                'time_window_minutes': time_window_minutes,
                'status': 'healthy' if float(data['avg_rot_score']) < 0.5 else 'degraded',
                'metrics': {
                    'average_rot_score': float(data['avg_rot_score']),
                    'maximum_rot_score': float(data['max_rot_score']),
                    'measurement_count': int(data['measurement_count']),
                    'attention_alerts': int(data['attention_alerts']),
                    'average_confidence': float(data['avg_confidence'] or 0.0)
                },
                'system_health': system_metrics,
                'recommendations': self._generate_recommendations(data)
            }
            
        except Exception as e:
            logger.error(f"Session health analysis error: {e}")
            return {
                'session_id': session_id,
                'status': 'error',
                'error': str(e)
            }
    
    def _generate_recommendations(self, metrics_data: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on metrics."""
        recommendations = []
        avg_rot = float(metrics_data['avg_rot_score'])
        max_rot = float(metrics_data['max_rot_score'])
        alerts = int(metrics_data['attention_alerts'])
        
        if avg_rot > 0.7:
            recommendations.append("High context rot detected. Consider starting a fresh session.")
        elif avg_rot > 0.5:
            recommendations.append("Moderate context rot detected. Review recent conversation for repetitive patterns.")
        
        if max_rot > 0.8:
            recommendations.append("Context rot spike detected. Check for circular conversation patterns.")
        
        if alerts > 3:
            recommendations.append(f"Multiple attention alerts ({alerts}). Session may benefit from refocusing or restart.")
        
        if not recommendations:
            recommendations.append("Session health looks good. Continue with current approach.")
        
        return recommendations
    
    async def _store_metric(self, metric: ContextRotMetric) -> bool:
        """Store context rot metric in ClickHouse."""
        try:
            # Prepare record for insertion
            record = {
                'timestamp': metric.timestamp,
                'session_id': metric.session_id,
                'rot_score': metric.rot_score,
                'confidence_score': metric.confidence_score,
                'indicator_breakdown': metric.indicator_breakdown,
                'analysis_version': metric.analysis_version,
                'requires_attention': metric.requires_attention
            }
            
            # Use bulk insert for efficiency
            success = await self.clickhouse_client.bulk_insert('context_rot_metrics', [record])
            
            if not success:
                logger.warning("Failed to store context rot metric")
            
            return success
            
        except Exception as e:
            logger.error(f"Error storing context rot metric: {e}")
            return False
    
    async def get_recent_trends(self, session_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get recent context rot trends for a session."""
        try:
            query = """
            SELECT 
                toHour(timestamp) as hour,
                avg(rot_score) as avg_rot,
                max(rot_score) as max_rot,
                count() as measurements
            FROM otel.context_rot_metrics
            WHERE session_id = {session_id:String}
                AND timestamp >= now() - INTERVAL {hours:Int32} HOUR
            GROUP BY hour
            ORDER BY hour
            """
            
            params = {'session_id': session_id, 'hours': hours}
            results = await self.clickhouse_client.execute_query(query, params)
            
            return {
                'session_id': session_id,
                'time_range_hours': hours,
                'hourly_trends': results,
                'trend_analysis': self._analyze_trends(results)
            }
            
        except Exception as e:
            logger.error(f"Error getting context rot trends: {e}")
            return {'error': str(e)}
    
    def _analyze_trends(self, hourly_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trend patterns in hourly data."""
        if not hourly_data or len(hourly_data) < 2:
            return {'status': 'insufficient_data'}
        
        # Simple trend analysis
        rot_values = [float(row['avg_rot']) for row in hourly_data]
        
        # Calculate trend direction
        recent_avg = sum(rot_values[-3:]) / min(3, len(rot_values))  # Last 3 hours
        earlier_avg = sum(rot_values[:3]) / min(3, len(rot_values))  # First 3 hours
        
        trend_direction = 'improving' if recent_avg < earlier_avg else 'degrading'
        trend_magnitude = abs(recent_avg - earlier_avg)
        
        return {
            'status': 'analyzed',
            'direction': trend_direction,
            'magnitude': round(trend_magnitude, 3),
            'recent_average': round(recent_avg, 3),
            'earlier_average': round(earlier_avg, 3),
            'volatility': round(max(rot_values) - min(rot_values), 3)
        }
    
    async def reset_session(self, session_id: str) -> Dict[str, Any]:
        """Reset context rot tracking for a session."""
        try:
            # Reset monitor data
            self.monitor.reset_session_data(session_id)
            
            return {
                'session_id': session_id,
                'status': 'reset',
                'message': 'Context rot tracking has been reset for this session',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting session {session_id}: {e}")
            return {
                'session_id': session_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def get_analyzer_status(self) -> Dict[str, Any]:
        """Get overall analyzer status and health metrics."""
        try:
            system_metrics = await self.monitor.get_system_metrics()
            
            # Check ClickHouse health
            clickhouse_healthy = await self.clickhouse_client.health_check()
            
            return {
                'status': 'healthy' if clickhouse_healthy and system_metrics.get('circuit_breaker', {}).get('uptime_ok', False) else 'degraded',
                'clickhouse_connection': 'healthy' if clickhouse_healthy else 'unavailable',
                'system_metrics': system_metrics,
                'components': {
                    'security_analyzer': 'active',
                    'statistical_analyzer': 'active',
                    'production_monitor': 'active',
                    'error_recovery': 'integrated'
                },
                'version': '1.0.0-phase0',
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting analyzer status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }