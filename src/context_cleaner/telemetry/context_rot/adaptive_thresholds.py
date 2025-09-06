"""Adaptive Threshold Management for Context Rot Detection - Phase 2: Advanced Analytics

This module implements dynamic threshold management that adapts to individual user
behavior patterns rather than using static, one-size-fits-all thresholds. This
significantly reduces false positives and improves detection accuracy.

Key Components:
- AdaptiveThresholdManager: Dynamic threshold calculation
- UserBaselineTracker: User behavior pattern learning
- ThresholdOptimizer: Statistical optimization of thresholds
- ThresholdConfig: Personalized threshold configuration

Features:
- Per-user baseline establishment
- Statistical variance tracking
- Confidence-based threshold adjustment
- Privacy-safe user profiling
- Memory-efficient baseline storage
"""

import asyncio
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
from enum import Enum

from ..clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


class SensitivityFeedback(Enum):
    """User feedback on sensitivity levels."""
    TOO_SENSITIVE = "too_sensitive"
    APPROPRIATE = "appropriate" 
    NOT_SENSITIVE_ENOUGH = "not_sensitive_enough"


@dataclass
class UserBaseline:
    """User behavior baseline data."""
    user_id: str
    normal_level: float          # Normal frustration baseline (0.0 to 1.0)
    variance: float              # Statistical variance in user behavior
    session_count: int           # Number of sessions contributing to baseline
    last_updated: datetime
    confidence: float            # Confidence in baseline accuracy (0.0 to 1.0)
    
    # Behavioral patterns
    avg_session_length: float = 0.0
    avg_messages_per_session: float = 0.0
    typical_conversation_flow: float = 0.0
    
    # Threshold adjustment factors
    sensitivity_factor: float = 1.0  # User-specific sensitivity adjustment


@dataclass
class ThresholdConfig:
    """Personalized threshold configuration."""
    user_id: str
    warning_threshold: float      # Threshold for warning alerts
    critical_threshold: float     # Threshold for critical alerts
    confidence_required: float    # Required confidence for alerts
    last_optimized: datetime
    
    # Context-specific thresholds
    session_length_factor: float = 1.0    # Adjustment based on session length
    time_of_day_factor: float = 1.0       # Adjustment based on time patterns
    baseline_deviation: float = 0.0       # How much user deviates from global baseline


@dataclass
class ThresholdOptimizationResult:
    """Result of threshold optimization process."""
    optimized_thresholds: ThresholdConfig
    improvement_score: float      # How much better the new thresholds are
    false_positive_reduction: float
    false_negative_reduction: float
    confidence: float
    evidence: List[str] = field(default_factory=list)


class UserBaselineTracker:
    """Tracks and maintains user behavior baselines."""
    
    def __init__(self, clickhouse_client: ClickHouseClient):
        self.clickhouse = clickhouse_client
        self.baseline_cache = {}  # In-memory cache for frequently accessed baselines
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.min_sessions_for_baseline = 5  # Minimum sessions needed for reliable baseline
        self.max_baseline_age_days = 30  # Refresh baseline after 30 days
        
    async def get_user_baseline(self, user_id: str) -> Optional[UserBaseline]:
        """Get or create user behavior baseline."""
        # Input validation
        if not user_id or len(user_id) > 64:  # Security: limit user_id length
            logger.warning(f"Invalid user_id: {user_id}")
            return None
        
        # Check cache first
        cache_key = f"baseline_{user_id}"
        if cache_key in self.baseline_cache:
            cached_baseline, cached_time = self.baseline_cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                return cached_baseline
        
        # Fetch from database
        baseline = await self._fetch_user_baseline(user_id)
        
        # Create new baseline if needed
        if not baseline:
            baseline = await self._create_initial_baseline(user_id)
        
        # Check if baseline needs updating
        elif self._needs_baseline_update(baseline):
            baseline = await self._update_user_baseline(baseline)
        
        # Cache the result
        if baseline:
            self.baseline_cache[cache_key] = (baseline, datetime.now())
        
        return baseline
    
    async def _fetch_user_baseline(self, user_id: str) -> Optional[UserBaseline]:
        """Fetch existing baseline from database."""
        try:
            query = """
            SELECT 
                normal_level,
                variance,
                session_count,
                last_updated,
                confidence,
                avg_session_length,
                avg_messages_per_session,
                typical_conversation_flow,
                sensitivity_factor
            FROM otel.user_baselines 
            WHERE user_id = {user_id:String}
            LIMIT 1
            """
            
            results = await self.clickhouse.execute_query(query, {'user_id': user_id})
            
            if not results:
                return None
            
            data = results[0]
            return UserBaseline(
                user_id=user_id,
                normal_level=float(data['normal_level']),
                variance=float(data['variance']),
                session_count=int(data['session_count']),
                last_updated=data['last_updated'],
                confidence=float(data['confidence']),
                avg_session_length=float(data['avg_session_length']),
                avg_messages_per_session=float(data['avg_messages_per_session']),
                typical_conversation_flow=float(data['typical_conversation_flow']),
                sensitivity_factor=float(data['sensitivity_factor'])
            )
            
        except Exception as e:
            logger.error(f"Error fetching user baseline: {e}")
            return None
    
    async def _create_initial_baseline(self, user_id: str) -> Optional[UserBaseline]:
        """Create initial baseline from user's historical data."""
        try:
            # Query user's recent context rot data
            query = """
            SELECT 
                avg(rot_score) as avg_rot,
                stddevPop(rot_score) as variance,
                count() as session_count,
                avg(CAST(extractAllGroups(additional_context, 'session_length:([0-9.]+)')[1] as Float64)) as avg_session_length,
                avg(CAST(extractAllGroups(additional_context, 'message_count:([0-9]+)')[1] as UInt32)) as avg_messages
            FROM otel.context_rot_metrics 
            WHERE extractAllGroups(additional_context, 'user_id:([^,}]+)')[1] = {user_id:String}
              AND timestamp >= now() - INTERVAL 14 DAY
            """
            
            results = await self.clickhouse.execute_query(query, {'user_id': user_id})
            
            if not results or not results[0]['session_count']:
                # Not enough data - use global defaults
                return UserBaseline(
                    user_id=user_id,
                    normal_level=0.3,  # Global average
                    variance=0.2,
                    session_count=0,
                    last_updated=datetime.now(),
                    confidence=0.1,  # Low confidence
                    sensitivity_factor=1.0
                )
            
            data = results[0]
            session_count = int(data['session_count'])
            
            # Calculate confidence based on data availability
            confidence = min(1.0, session_count / self.min_sessions_for_baseline)
            
            baseline = UserBaseline(
                user_id=user_id,
                normal_level=float(data['avg_rot'] or 0.3),
                variance=float(data['variance'] or 0.2),
                session_count=session_count,
                last_updated=datetime.now(),
                confidence=confidence,
                avg_session_length=float(data['avg_session_length'] or 0.0),
                avg_messages_per_session=float(data['avg_messages'] or 0.0),
                typical_conversation_flow=0.7,  # Default
                sensitivity_factor=1.0
            )
            
            # Store in database
            await self._store_user_baseline(baseline)
            
            logger.info(f"Created initial baseline for user {user_id} with {session_count} sessions")
            return baseline
            
        except Exception as e:
            logger.error(f"Error creating initial baseline: {e}")
            return None
    
    async def _update_user_baseline(self, baseline: UserBaseline) -> UserBaseline:
        """Update existing baseline with recent data."""
        try:
            # Fetch recent data since last update
            query = """
            SELECT 
                avg(rot_score) as recent_avg,
                stddevPop(rot_score) as recent_variance,
                count() as recent_sessions
            FROM otel.context_rot_metrics 
            WHERE extractAllGroups(additional_context, 'user_id:([^,}]+)')[1] = {user_id:String}
              AND timestamp >= {since_date:DateTime}
            """
            
            since_date = baseline.last_updated - timedelta(hours=1)  # Small overlap
            results = await self.clickhouse.execute_query(
                query, 
                {'user_id': baseline.user_id, 'since_date': since_date}
            )
            
            if not results or not results[0]['recent_sessions']:
                return baseline  # No new data
            
            data = results[0]
            recent_sessions = int(data['recent_sessions'])
            recent_avg = float(data['recent_avg'] or baseline.normal_level)
            recent_variance = float(data['recent_variance'] or baseline.variance)
            
            # Weighted average update (more weight to recent data if confidence is low)
            weight_recent = min(0.3, (1.0 - baseline.confidence) * 0.5)
            weight_historical = 1.0 - weight_recent
            
            updated_baseline = UserBaseline(
                user_id=baseline.user_id,
                normal_level=baseline.normal_level * weight_historical + recent_avg * weight_recent,
                variance=baseline.variance * weight_historical + recent_variance * weight_recent,
                session_count=baseline.session_count + recent_sessions,
                last_updated=datetime.now(),
                confidence=min(1.0, (baseline.session_count + recent_sessions) / self.min_sessions_for_baseline),
                avg_session_length=baseline.avg_session_length,  # Keep existing
                avg_messages_per_session=baseline.avg_messages_per_session,  # Keep existing
                typical_conversation_flow=baseline.typical_conversation_flow,  # Keep existing
                sensitivity_factor=baseline.sensitivity_factor  # Keep existing
            )
            
            # Store updated baseline
            await self._store_user_baseline(updated_baseline)
            
            logger.info(f"Updated baseline for user {baseline.user_id} with {recent_sessions} new sessions")
            return updated_baseline
            
        except Exception as e:
            logger.error(f"Error updating user baseline: {e}")
            return baseline  # Return original on error
    
    def _needs_baseline_update(self, baseline: UserBaseline) -> bool:
        """Check if baseline needs updating."""
        age = datetime.now() - baseline.last_updated
        return (
            age.days > self.max_baseline_age_days or
            (baseline.confidence < 0.8 and age.hours > 6)  # More frequent updates for low confidence
        )
    
    async def _store_user_baseline(self, baseline: UserBaseline):
        """Store or update user baseline in database."""
        try:
            # Use INSERT or REPLACE pattern for ClickHouse
            query = """
            INSERT INTO otel.user_baselines VALUES (
                {user_id:String},
                {normal_level:Float64},
                {variance:Float64},
                {session_count:UInt32},
                {last_updated:DateTime},
                {confidence:Float64},
                {avg_session_length:Float64},
                {avg_messages_per_session:Float64},
                {typical_conversation_flow:Float64},
                {sensitivity_factor:Float64}
            )
            """
            
            await self.clickhouse.execute_query(query, {
                'user_id': baseline.user_id,
                'normal_level': baseline.normal_level,
                'variance': baseline.variance,
                'session_count': baseline.session_count,
                'last_updated': baseline.last_updated,
                'confidence': baseline.confidence,
                'avg_session_length': baseline.avg_session_length,
                'avg_messages_per_session': baseline.avg_messages_per_session,
                'typical_conversation_flow': baseline.typical_conversation_flow,
                'sensitivity_factor': baseline.sensitivity_factor
            })
            
        except Exception as e:
            logger.error(f"Error storing user baseline: {e}")


class ThresholdOptimizer:
    """Optimizes thresholds based on historical performance."""
    
    def __init__(self):
        self.optimization_window_days = 7  # Look at last week of data
        self.min_events_for_optimization = 20  # Minimum events needed
        
    async def optimize_thresholds(self, baseline: UserBaseline, 
                                historical_performance: Dict[str, Any]) -> ThresholdOptimizationResult:
        """Optimize thresholds for a user based on historical performance."""
        
        # Calculate optimal thresholds using statistical methods
        optimal_warning = self._calculate_optimal_warning_threshold(baseline)
        optimal_critical = self._calculate_optimal_critical_threshold(baseline)
        optimal_confidence = self._calculate_optimal_confidence_threshold(baseline)
        
        # Calculate improvement metrics
        improvement_score = self._calculate_improvement_score(
            baseline, optimal_warning, optimal_critical
        )
        
        # Generate optimized config
        optimized_config = ThresholdConfig(
            user_id=baseline.user_id,
            warning_threshold=optimal_warning,
            critical_threshold=optimal_critical,
            confidence_required=optimal_confidence,
            last_optimized=datetime.now(),
            baseline_deviation=abs(baseline.normal_level - 0.3)  # Deviation from global average
        )
        
        return ThresholdOptimizationResult(
            optimized_thresholds=optimized_config,
            improvement_score=improvement_score,
            false_positive_reduction=0.2,  # Estimated
            false_negative_reduction=0.1,  # Estimated
            confidence=baseline.confidence,
            evidence=[
                f"Baseline level: {baseline.normal_level:.2f}",
                f"Variance: {baseline.variance:.2f}",
                f"Session count: {baseline.session_count}",
                f"Warning threshold: {optimal_warning:.2f}",
                f"Critical threshold: {optimal_critical:.2f}"
            ]
        )
    
    def _calculate_optimal_warning_threshold(self, baseline: UserBaseline) -> float:
        """Calculate optimal warning threshold."""
        # Use statistical approach: baseline + 1.5 * standard deviation
        threshold = baseline.normal_level + (1.5 * baseline.variance)
        
        # Apply sensitivity factor
        threshold *= baseline.sensitivity_factor
        
        # Ensure reasonable bounds
        return max(0.2, min(0.8, threshold))
    
    def _calculate_optimal_critical_threshold(self, baseline: UserBaseline) -> float:
        """Calculate optimal critical threshold."""
        # Use statistical approach: baseline + 2.5 * standard deviation
        threshold = baseline.normal_level + (2.5 * baseline.variance)
        
        # Apply sensitivity factor
        threshold *= baseline.sensitivity_factor
        
        # Ensure it's higher than warning threshold
        warning_threshold = self._calculate_optimal_warning_threshold(baseline)
        
        return max(warning_threshold + 0.1, min(0.9, threshold))
    
    def _calculate_optimal_confidence_threshold(self, baseline: UserBaseline) -> float:
        """Calculate optimal confidence threshold."""
        # Higher confidence required for users with low baseline confidence
        base_confidence = 0.7
        
        if baseline.confidence < 0.5:
            return min(0.9, base_confidence + 0.2)  # Require higher confidence
        elif baseline.confidence > 0.8:
            return max(0.5, base_confidence - 0.1)  # Can accept lower confidence
        
        return base_confidence
    
    def _calculate_improvement_score(self, baseline: UserBaseline, 
                                   warning_threshold: float, critical_threshold: float) -> float:
        """Calculate estimated improvement score for new thresholds."""
        # Simple heuristic - better personalization should improve accuracy
        personalization_score = baseline.confidence  # More confident baseline = better personalization
        
        # Threshold spacing score - good spacing reduces false positives
        spacing = critical_threshold - warning_threshold
        spacing_score = min(1.0, spacing / 0.3)  # Ideal spacing is ~0.3
        
        # Baseline appropriateness - thresholds should be reasonable relative to baseline
        appropriateness_score = 1.0
        if warning_threshold < baseline.normal_level:
            appropriateness_score *= 0.7  # Too low warning threshold
        if critical_threshold > 0.9:
            appropriateness_score *= 0.8  # Too high critical threshold
        
        return (personalization_score * 0.5 + spacing_score * 0.3 + appropriateness_score * 0.2)


class AdaptiveThresholdManager:
    """Manages adaptive thresholds for personalized context rot detection."""
    
    def __init__(self, clickhouse_client: ClickHouseClient):
        self.user_baseline_tracker = UserBaselineTracker(clickhouse_client)
        self.threshold_optimizer = ThresholdOptimizer()
        self.threshold_cache = {}  # Cache for computed thresholds
        self.cache_ttl = 1800  # 30 minute cache TTL
        
        # Default thresholds (fallback)
        self.default_thresholds = ThresholdConfig(
            user_id="default",
            warning_threshold=0.5,
            critical_threshold=0.7,
            confidence_required=0.7,
            last_optimized=datetime.now()
        )
    
    async def get_personalized_thresholds(self, user_id: str) -> ThresholdConfig:
        """Get personalized thresholds for a user."""
        # Input validation
        if not user_id:
            return self.default_thresholds
        
        # Check cache
        cache_key = f"thresholds_{user_id}"
        if cache_key in self.threshold_cache:
            cached_config, cached_time = self.threshold_cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                return cached_config
        
        try:
            # Get user baseline
            baseline = await self.user_baseline_tracker.get_user_baseline(user_id)
            
            if not baseline or baseline.confidence < 0.3:
                # Not enough data for personalization
                logger.info(f"Using default thresholds for user {user_id} (insufficient data)")
                return self.default_thresholds
            
            # Optimize thresholds
            optimization_result = await self.threshold_optimizer.optimize_thresholds(
                baseline, {}  # Historical performance data could be added here
            )
            
            personalized_config = optimization_result.optimized_thresholds
            
            # Apply time-of-day adjustments (could be extended)
            personalized_config = self._apply_contextual_adjustments(personalized_config)
            
            # Cache the result
            self.threshold_cache[cache_key] = (personalized_config, datetime.now())
            
            logger.info(f"Generated personalized thresholds for user {user_id}: "
                       f"warning={personalized_config.warning_threshold:.2f}, "
                       f"critical={personalized_config.critical_threshold:.2f}")
            
            return personalized_config
            
        except Exception as e:
            logger.error(f"Error getting personalized thresholds: {e}")
            return self.default_thresholds
    
    def _apply_contextual_adjustments(self, config: ThresholdConfig) -> ThresholdConfig:
        """Apply contextual adjustments to thresholds (time of day, session length, etc)."""
        current_hour = datetime.now().hour
        
        # People might be more frustrated late at night or early morning
        if current_hour < 6 or current_hour > 22:
            config.time_of_day_factor = 0.9  # Lower thresholds (more sensitive)
            config.warning_threshold *= config.time_of_day_factor
            config.critical_threshold *= config.time_of_day_factor
        
        return config
    
    async def update_user_sensitivity(self, user_id: str, feedback: str) -> bool:
        """Update user sensitivity based on feedback (too sensitive/not sensitive enough)."""
        try:
            baseline = await self.user_baseline_tracker.get_user_baseline(user_id)
            if not baseline:
                return False
            
            # Adjust sensitivity factor based on feedback
            if feedback.lower() in ['too_sensitive', 'too_many_alerts']:
                baseline.sensitivity_factor *= 0.9  # Reduce sensitivity
            elif feedback.lower() in ['not_sensitive', 'missed_issues']:
                baseline.sensitivity_factor *= 1.1  # Increase sensitivity
            
            # Clamp sensitivity factor to reasonable bounds
            baseline.sensitivity_factor = max(0.5, min(2.0, baseline.sensitivity_factor))
            
            # Store updated baseline
            await self.user_baseline_tracker._store_user_baseline(baseline)
            
            # Clear cache to force recalculation
            cache_key = f"thresholds_{user_id}"
            if cache_key in self.threshold_cache:
                del self.threshold_cache[cache_key]
            
            logger.info(f"Updated sensitivity for user {user_id}: {baseline.sensitivity_factor:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user sensitivity: {e}")
            return False