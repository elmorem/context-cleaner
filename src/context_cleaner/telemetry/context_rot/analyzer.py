"""Core Context Rot Analyzer with ML-enhanced statistical analysis - Phase 2: Advanced Analytics

Enhanced with machine learning capabilities for improved accuracy:
- ML-based frustration detection replacing naive pattern matching
- Adaptive thresholds personalized per user
- Conversation flow analysis with confidence scoring
- User behavior baseline tracking for false positive reduction
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .monitor import ProductionReadyContextRotMonitor, QuickAssessment
from .security import PrivacyConfig
from ..clients.clickhouse_client import ClickHouseClient
from ..error_recovery.manager import ErrorRecoveryManager

# Phase 2: ML Enhancement Imports
try:
    from .ml_analysis import MLFrustrationDetector, FrustrationAnalysis, SentimentScore
    from .adaptive_thresholds import AdaptiveThresholdManager, ThresholdConfig
    ML_CAPABILITIES_AVAILABLE = True
except ImportError:
    # Fallback when ML components are not available
    ML_CAPABILITIES_AVAILABLE = False
    
    class MLFrustrationDetector:
        async def analyze_user_sentiment(self, messages): return None
    
    class AdaptiveThresholdManager:
        async def get_personalized_thresholds(self, user_id): return None

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
        """Initialize with existing infrastructure components and Phase 2 ML enhancements."""
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
        
        # Phase 2: Initialize ML components
        self.ml_enabled = ML_CAPABILITIES_AVAILABLE
        if self.ml_enabled:
            self.ml_frustration_detector = MLFrustrationDetector(confidence_threshold=0.8)
            self.adaptive_threshold_manager = AdaptiveThresholdManager(clickhouse_client)
            logger.info("Context Rot Analyzer initialized with ML capabilities enabled")
        else:
            self.ml_frustration_detector = MLFrustrationDetector()
            self.adaptive_threshold_manager = AdaptiveThresholdManager()
            logger.warning("Context Rot Analyzer initialized with ML capabilities disabled (fallback mode)")
        
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
                    'error_recovery': 'integrated',
                    'ml_frustration_detector': 'active' if self.ml_enabled else 'fallback',
                    'adaptive_thresholds': 'active' if self.ml_enabled else 'fallback'
                },
                'version': '1.0.0-phase2' if self.ml_enabled else '1.0.0-phase1',
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting analyzer status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    # Phase 2: ML-Enhanced Analysis Methods
    
    async def analyze_conversation_sentiment(self, user_id: str, messages: List[str]) -> Dict[str, Any]:
        """
        Analyze conversation sentiment using ML-based frustration detection.
        
        Args:
            user_id: User identifier for personalized analysis
            messages: List of conversation messages to analyze
            
        Returns:
            Dict containing detailed sentiment analysis with confidence scoring
        """
        try:
            if not self.ml_enabled or not messages:
                return {'status': 'ml_unavailable', 'fallback_used': True}
            
            # Perform ML-based frustration analysis
            frustration_analysis = await self.ml_frustration_detector.analyze_user_sentiment(messages)
            
            if not frustration_analysis:
                return {'status': 'analysis_failed'}
            
            # Get personalized thresholds for this user
            thresholds = await self.adaptive_threshold_manager.get_personalized_thresholds(user_id)
            
            # Determine alert level based on personalized thresholds
            alert_level = self._determine_alert_level(
                frustration_analysis.frustration_level, 
                frustration_analysis.confidence,
                thresholds
            )
            
            return {
                'status': 'success',
                'user_id': user_id,
                'analysis': {
                    'frustration_level': frustration_analysis.frustration_level,
                    'confidence': frustration_analysis.confidence,
                    'sentiment_breakdown': {
                        str(k): v for k, v in frustration_analysis.sentiment_breakdown.items()
                    },
                    'conversation_patterns': frustration_analysis.conversation_patterns,
                    'evidence': frustration_analysis.evidence,
                    'processing_time_ms': frustration_analysis.processing_time_ms
                },
                'personalization': {
                    'warning_threshold': thresholds.warning_threshold if thresholds else 0.5,
                    'critical_threshold': thresholds.critical_threshold if thresholds else 0.7,
                    'confidence_required': thresholds.confidence_required if thresholds else 0.7
                },
                'alert_level': alert_level,
                'recommendations': self._generate_ml_recommendations(frustration_analysis, alert_level),
                'version': '2.0.0-ml'
            }
            
        except Exception as e:
            logger.error(f"Error in ML conversation sentiment analysis: {e}")
            return {'status': 'error', 'error': str(e), 'fallback_used': True}
    
    async def get_personalized_insights(self, user_id: str) -> Dict[str, Any]:
        """
        Get personalized insights for a user based on their behavior patterns.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict containing personalized insights and recommendations
        """
        try:
            if not self.ml_enabled:
                return {'status': 'ml_unavailable'}
            
            # Get user's personalized thresholds
            thresholds = await self.adaptive_threshold_manager.get_personalized_thresholds(user_id)
            
            if not thresholds:
                return {
                    'status': 'insufficient_data',
                    'message': 'Not enough user data for personalized insights',
                    'recommendation': 'Continue using the system to build personalized profile'
                }
            
            # Get user baseline from threshold manager
            baseline = await self.adaptive_threshold_manager.user_baseline_tracker.get_user_baseline(user_id)
            
            insights = {
                'status': 'success',
                'user_id': user_id,
                'personalization_level': baseline.confidence if baseline else 0.0,
                'thresholds': {
                    'warning': thresholds.warning_threshold,
                    'critical': thresholds.critical_threshold,
                    'confidence_required': thresholds.confidence_required
                },
                'behavioral_profile': {},
                'recommendations': [],
                'last_updated': datetime.now().isoformat()
            }
            
            if baseline:
                insights['behavioral_profile'] = {
                    'normal_frustration_level': baseline.normal_level,
                    'variability': baseline.variance,
                    'session_count': baseline.session_count,
                    'avg_session_length': baseline.avg_session_length,
                    'typical_message_count': baseline.avg_messages_per_session,
                    'sensitivity_factor': baseline.sensitivity_factor
                }
                
                # Generate personalized recommendations
                insights['recommendations'] = self._generate_personalized_recommendations(baseline, thresholds)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting personalized insights: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def update_user_feedback(self, user_id: str, feedback_type: str, session_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Update user's personalization based on feedback.
        
        Args:
            user_id: User identifier
            feedback_type: Type of feedback ('too_sensitive', 'not_sensitive', 'accurate')
            session_context: Optional context about the session
            
        Returns:
            Dict containing update status and new personalization info
        """
        try:
            if not self.ml_enabled:
                return {'status': 'ml_unavailable'}
            
            # Update user sensitivity based on feedback
            update_success = await self.adaptive_threshold_manager.update_user_sensitivity(
                user_id, feedback_type
            )
            
            if not update_success:
                return {'status': 'update_failed', 'message': 'Could not update user preferences'}
            
            # Get updated personalized insights
            updated_insights = await self.get_personalized_insights(user_id)
            
            return {
                'status': 'success',
                'feedback_processed': feedback_type,
                'user_id': user_id,
                'updated_insights': updated_insights,
                'message': f'Successfully updated sensitivity based on {feedback_type} feedback'
            }
            
        except Exception as e:
            logger.error(f"Error updating user feedback: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _determine_alert_level(self, frustration_level: float, confidence: float, 
                              thresholds: Optional[ThresholdConfig]) -> str:
        """Determine alert level using personalized thresholds."""
        if not thresholds:
            # Use default thresholds
            if frustration_level >= 0.7 and confidence >= 0.7:
                return 'critical'
            elif frustration_level >= 0.5 and confidence >= 0.6:
                return 'warning'
            else:
                return 'normal'
        
        # Use personalized thresholds
        if (frustration_level >= thresholds.critical_threshold and 
            confidence >= thresholds.confidence_required):
            return 'critical'
        elif (frustration_level >= thresholds.warning_threshold and 
              confidence >= thresholds.confidence_required):
            return 'warning'
        else:
            return 'normal'
    
    def _generate_ml_recommendations(self, analysis: FrustrationAnalysis, alert_level: str) -> List[str]:
        """Generate recommendations based on ML analysis."""
        recommendations = []
        
        if alert_level == 'critical':
            recommendations.append("High frustration detected - consider taking a break or trying a different approach")
            
            if analysis.conversation_patterns.get('escalation_detected'):
                recommendations.append("Conversation escalation pattern identified - session restart may help")
            
            if analysis.conversation_patterns.get('repetition_ratio', 0) > 0.4:
                recommendations.append("High repetition detected - try rephrasing your questions or approach")
        
        elif alert_level == 'warning':
            recommendations.append("Elevated frustration detected - monitoring situation")
            
            if analysis.conversation_patterns.get('flow_quality_score', 1.0) < 0.5:
                recommendations.append("Poor conversation flow - try being more specific with questions")
        
        # Add conversation flow recommendations
        question_ratio = analysis.conversation_patterns.get('question_ratio', 0)
        if question_ratio > 0.5:
            recommendations.append("Many questions detected - you might benefit from more direct statements")
        elif question_ratio < 0.1:
            recommendations.append("Few questions asked - asking clarifying questions might help")
        
        if not recommendations:
            recommendations.append("Conversation quality looks good - continue with current approach")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _generate_personalized_recommendations(self, baseline: 'UserBaseline', 
                                             thresholds: ThresholdConfig) -> List[str]:
        """Generate personalized recommendations based on user profile."""
        recommendations = []
        
        # Recommendations based on baseline patterns
        if baseline.normal_level > 0.4:
            recommendations.append("You tend to experience higher frustration - consider shorter sessions")
        elif baseline.normal_level < 0.2:
            recommendations.append("Your frustration levels are typically low - current approach is working well")
        
        if baseline.variance > 0.3:
            recommendations.append("Your frustration levels vary significantly - adaptive thresholds are especially beneficial for you")
        
        if baseline.avg_session_length > 60:
            recommendations.append("You prefer longer sessions - consider periodic breaks to maintain effectiveness")
        elif baseline.avg_session_length < 20:
            recommendations.append("You prefer shorter sessions - this focused approach seems to work well for you")
        
        # Threshold-based recommendations
        if thresholds.warning_threshold < 0.3:
            recommendations.append("You have sensitive frustration detection - this helps catch issues early")
        elif thresholds.warning_threshold > 0.6:
            recommendations.append("You have higher frustration tolerance - alerts focus on significant issues")
        
        if baseline.session_count < 10:
            recommendations.append(f"Building your profile ({baseline.session_count} sessions) - accuracy will improve with more usage")
        
        return recommendations[:4]  # Limit to top 4 recommendations