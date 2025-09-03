"""
Real-time Cost Burn Rate Monitoring for Phase 2

Provides live cost tracking, budget alerts, and predictive cost analysis
for Claude Code usage optimization.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..clients.clickhouse_client import ClickHouseClient
from ..cost_optimization.models import BudgetConfig, ModelType

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Cost alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class CostAlert:
    """Cost monitoring alert"""
    level: AlertLevel
    message: str
    current_cost: float
    threshold: float
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    recommended_action: Optional[str] = None


@dataclass
class BurnRateData:
    """Real-time burn rate analysis data"""
    current_cost: float
    burn_rate_per_hour: float
    burn_rate_per_minute: float
    projected_session_cost: float
    projected_daily_cost: float
    time_to_budget_exhaustion: Optional[timedelta]
    cost_acceleration: float  # Change in burn rate
    model_breakdown: Dict[str, float]
    efficiency_score: float


@dataclass
class CostProjection:
    """Cost projection analysis"""
    next_hour_cost: float
    end_of_session_cost: float
    end_of_day_cost: float
    confidence: float
    factors: List[str]


class RealTimeCostMonitor:
    """Real-time cost monitoring and alerting system"""
    
    def __init__(self, telemetry_client: ClickHouseClient, budget_config: BudgetConfig):
        self.telemetry = telemetry_client
        self.budget_config = budget_config
        
        # Alert thresholds
        self.alert_thresholds = {
            "session": {
                AlertLevel.INFO: 0.5,      # 50% of session budget
                AlertLevel.WARNING: 0.75,  # 75% of session budget
                AlertLevel.CRITICAL: 0.9,  # 90% of session budget
                AlertLevel.EMERGENCY: 1.0  # 100% of session budget
            },
            "daily": {
                AlertLevel.INFO: 0.6,      # 60% of daily budget
                AlertLevel.WARNING: 0.8,   # 80% of daily budget
                AlertLevel.CRITICAL: 0.95, # 95% of daily budget
                AlertLevel.EMERGENCY: 1.0  # 100% of daily budget
            }
        }
        
        # Alert cooldown to prevent spam
        self._last_alerts: Dict[str, datetime] = {}
        self._alert_cooldown = timedelta(minutes=5)
        
        # Cost history for trend analysis
        self._cost_history: List[Dict[str, float]] = []
        self._max_history_points = 100
        
        # Registered alert callbacks
        self._alert_callbacks: List[Callable[[CostAlert], None]] = []
    
    def register_alert_callback(self, callback: Callable[[CostAlert], None]):
        """Register callback function for cost alerts"""
        self._alert_callbacks.append(callback)
    
    async def get_current_burn_rate(self, session_id: str) -> BurnRateData:
        """Get current burn rate analysis for a session"""
        try:
            # Get session metrics
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            if not session_metrics:
                raise ValueError(f"Session {session_id} not found")
            
            current_cost = session_metrics.total_cost
            
            # Calculate burn rates
            session_duration = datetime.now() - session_metrics.start_time
            duration_hours = max(session_duration.total_seconds() / 3600, 0.01)  # Prevent division by zero
            duration_minutes = max(session_duration.total_seconds() / 60, 0.01)
            
            burn_rate_hour = current_cost / duration_hours
            burn_rate_minute = current_cost / duration_minutes
            
            # Project costs
            assumed_session_length = 2.0  # hours
            projected_session = burn_rate_hour * assumed_session_length
            projected_daily = burn_rate_hour * 8  # 8 hour workday
            
            # Calculate time to budget exhaustion
            budget_remaining = self.budget_config.session_limit - current_cost
            if burn_rate_hour > 0 and budget_remaining > 0:
                hours_remaining = budget_remaining / burn_rate_hour
                time_to_exhaustion = timedelta(hours=hours_remaining)
            else:
                time_to_exhaustion = None
            
            # Calculate cost acceleration (change in burn rate)
            acceleration = self._calculate_cost_acceleration(session_id, burn_rate_hour)
            
            # Get model breakdown
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            model_breakdown = {}
            for model, stats in model_stats.items():
                model_name = model.split('-')[-1].upper()  # SONNET, HAIKU
                model_breakdown[model_name] = stats.get('total_cost', 0)
            
            # Calculate efficiency score
            efficiency_score = self._calculate_efficiency_score(
                current_cost, session_metrics.api_calls, model_breakdown
            )
            
            return BurnRateData(
                current_cost=current_cost,
                burn_rate_per_hour=burn_rate_hour,
                burn_rate_per_minute=burn_rate_minute,
                projected_session_cost=projected_session,
                projected_daily_cost=projected_daily,
                time_to_budget_exhaustion=time_to_exhaustion,
                cost_acceleration=acceleration,
                model_breakdown=model_breakdown,
                efficiency_score=efficiency_score
            )
            
        except Exception as e:
            logger.error(f"Error calculating burn rate for session {session_id}: {e}")
            # Return safe defaults
            return BurnRateData(
                current_cost=0.0,
                burn_rate_per_hour=0.0,
                burn_rate_per_minute=0.0,
                projected_session_cost=0.0,
                projected_daily_cost=0.0,
                time_to_budget_exhaustion=None,
                cost_acceleration=0.0,
                model_breakdown={},
                efficiency_score=0.0
            )
    
    def _calculate_cost_acceleration(self, session_id: str, current_burn_rate: float) -> float:
        """Calculate change in burn rate (acceleration)"""
        # Store current burn rate in history
        self._cost_history.append({
            'session_id': session_id,
            'burn_rate': current_burn_rate,
            'timestamp': datetime.now().timestamp()
        })
        
        # Limit history size
        if len(self._cost_history) > self._max_history_points:
            self._cost_history.pop(0)
        
        # Calculate acceleration from recent history
        session_history = [h for h in self._cost_history 
                          if h['session_id'] == session_id]
        
        if len(session_history) < 2:
            return 0.0
        
        # Compare with previous burn rate
        previous_rate = session_history[-2]['burn_rate']
        return current_burn_rate - previous_rate
    
    def _calculate_efficiency_score(self, cost: float, api_calls: int, 
                                  model_breakdown: Dict[str, float]) -> float:
        """Calculate cost efficiency score (0-1, higher is better)"""
        if api_calls == 0:
            return 0.0
        
        # Cost per API call
        cost_per_call = cost / api_calls
        
        # Efficiency based on model usage
        haiku_cost = model_breakdown.get('HAIKU', 0)
        sonnet_cost = model_breakdown.get('SONNET', 0)
        total_model_cost = haiku_cost + sonnet_cost
        
        if total_model_cost == 0:
            return 0.5  # Neutral score
        
        # Higher Haiku usage = better efficiency
        haiku_ratio = haiku_cost / total_model_cost
        
        # Base efficiency score from model usage
        base_score = haiku_ratio * 0.8 + 0.2  # Range: 0.2 to 1.0
        
        # Adjust based on cost per call (lower is better)
        if cost_per_call < 0.01:  # Very efficient
            cost_modifier = 1.0
        elif cost_per_call < 0.02:  # Moderately efficient
            cost_modifier = 0.8
        elif cost_per_call < 0.05:  # Less efficient
            cost_modifier = 0.6
        else:  # Inefficient
            cost_modifier = 0.4
        
        return min(base_score * cost_modifier, 1.0)
    
    async def check_budget_alerts(self, session_id: str) -> List[CostAlert]:
        """Check for budget threshold violations and generate alerts"""
        alerts = []
        
        try:
            # Get current costs
            session_cost = await self.telemetry.get_current_session_cost(session_id)
            
            # Get daily cost (approximate)
            daily_cost = session_cost * 3  # Rough estimate based on typical usage
            
            # Check session budget alerts
            session_usage = session_cost / self.budget_config.session_limit
            for alert_level, threshold in self.alert_thresholds["session"].items():
                if session_usage >= threshold:
                    alert_key = f"{session_id}_session_{alert_level.value}"
                    if self._should_send_alert(alert_key):
                        alert = CostAlert(
                            level=alert_level,
                            message=f"Session budget {threshold*100:.0f}% reached: ${session_cost:.2f}",
                            current_cost=session_cost,
                            threshold=self.budget_config.session_limit * threshold,
                            session_id=session_id,
                            recommended_action=self._get_session_recommendation(alert_level, session_usage)
                        )
                        alerts.append(alert)
                        self._mark_alert_sent(alert_key)
            
            # Check daily budget alerts
            daily_usage = daily_cost / self.budget_config.daily_limit
            for alert_level, threshold in self.alert_thresholds["daily"].items():
                if daily_usage >= threshold:
                    alert_key = f"daily_{alert_level.value}"
                    if self._should_send_alert(alert_key):
                        alert = CostAlert(
                            level=alert_level,
                            message=f"Daily budget {threshold*100:.0f}% reached: ${daily_cost:.2f}",
                            current_cost=daily_cost,
                            threshold=self.budget_config.daily_limit * threshold,
                            session_id=session_id,
                            recommended_action=self._get_daily_recommendation(alert_level, daily_usage)
                        )
                        alerts.append(alert)
                        self._mark_alert_sent(alert_key)
            
            # Send alerts to registered callbacks
            for alert in alerts:
                for callback in self._alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking budget alerts for session {session_id}: {e}")
            return []
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if enough time has passed since last alert of this type"""
        if alert_key not in self._last_alerts:
            return True
        
        time_since_last = datetime.now() - self._last_alerts[alert_key]
        return time_since_last >= self._alert_cooldown
    
    def _mark_alert_sent(self, alert_key: str):
        """Mark that an alert was sent"""
        self._last_alerts[alert_key] = datetime.now()
    
    def _get_session_recommendation(self, alert_level: AlertLevel, usage: float) -> str:
        """Get recommendation based on session budget usage"""
        if alert_level == AlertLevel.EMERGENCY:
            return "Switch to Haiku immediately or end session"
        elif alert_level == AlertLevel.CRITICAL:
            return "Consider switching to Haiku for remaining requests"
        elif alert_level == AlertLevel.WARNING:
            return "Monitor usage closely and consider cost optimization"
        else:
            return "Budget tracking active"
    
    def _get_daily_recommendation(self, alert_level: AlertLevel, usage: float) -> str:
        """Get recommendation based on daily budget usage"""
        if alert_level == AlertLevel.EMERGENCY:
            return "Daily budget exceeded - enable strict cost controls"
        elif alert_level == AlertLevel.CRITICAL:
            return "Daily budget nearly exhausted - limit remaining sessions"
        elif alert_level == AlertLevel.WARNING:
            return "High daily usage - consider optimizing remaining sessions"
        else:
            return "Daily budget tracking active"
    
    async def get_cost_projection(self, session_id: str) -> CostProjection:
        """Generate cost projections based on current usage patterns"""
        try:
            burn_rate_data = await self.get_current_burn_rate(session_id)
            
            # Project next hour
            next_hour_cost = burn_rate_data.current_cost + burn_rate_data.burn_rate_per_hour
            
            # Project end of session (assume 2 hours remaining)
            end_session_cost = burn_rate_data.current_cost + (burn_rate_data.burn_rate_per_hour * 2)
            
            # Project end of day (8 hour workday, current session + future sessions)
            end_day_cost = burn_rate_data.projected_daily_cost
            
            # Calculate confidence based on cost stability
            confidence = self._calculate_projection_confidence(burn_rate_data.cost_acceleration)
            
            # Identify projection factors
            factors = []
            if burn_rate_data.cost_acceleration > 0.5:
                factors.append("Cost increasing rapidly")
            elif burn_rate_data.cost_acceleration < -0.2:
                factors.append("Cost decreasing")
            
            if burn_rate_data.efficiency_score < 0.5:
                factors.append("Low efficiency - high Sonnet usage")
            elif burn_rate_data.efficiency_score > 0.8:
                factors.append("High efficiency - optimal model usage")
            
            if burn_rate_data.burn_rate_per_hour > 3.0:
                factors.append("High burn rate detected")
            elif burn_rate_data.burn_rate_per_hour < 1.0:
                factors.append("Moderate burn rate")
            
            return CostProjection(
                next_hour_cost=next_hour_cost,
                end_of_session_cost=end_session_cost,
                end_of_day_cost=end_day_cost,
                confidence=confidence,
                factors=factors
            )
            
        except Exception as e:
            logger.error(f"Error generating cost projection for session {session_id}: {e}")
            return CostProjection(
                next_hour_cost=0.0,
                end_of_session_cost=0.0,
                end_of_day_cost=0.0,
                confidence=0.0,
                factors=["Error calculating projection"]
            )
    
    def _calculate_projection_confidence(self, cost_acceleration: float) -> float:
        """Calculate confidence in cost projections"""
        # Higher confidence when cost acceleration is stable
        if abs(cost_acceleration) < 0.1:
            return 0.9  # Very stable
        elif abs(cost_acceleration) < 0.3:
            return 0.7  # Moderately stable
        elif abs(cost_acceleration) < 0.5:
            return 0.5  # Unstable
        else:
            return 0.3  # Very unstable
    
    async def monitor_session(self, session_id: str, check_interval: int = 30) -> None:
        """Continuously monitor a session for cost issues"""
        logger.info(f"Starting cost monitoring for session {session_id}")
        
        while True:
            try:
                # Check for alerts
                alerts = await self.check_budget_alerts(session_id)
                
                # Log any critical alerts
                for alert in alerts:
                    if alert.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
                        logger.warning(f"Cost alert: {alert.message}")
                
                # Wait for next check
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in cost monitoring for session {session_id}: {e}")
                await asyncio.sleep(check_interval)  # Continue monitoring despite errors