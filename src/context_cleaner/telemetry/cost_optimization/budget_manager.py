"""Budget management and monitoring for cost optimization."""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..clients.base import TelemetryClient
from .models import BudgetConfig, OptimizationSuggestion

logger = logging.getLogger(__name__)


class BudgetManager:
    """Manages budget limits, alerts, and cost monitoring."""
    
    def __init__(self, telemetry_client: TelemetryClient, config: BudgetConfig):
        self.telemetry = telemetry_client
        self.config = config
        self._alert_cache: Dict[str, datetime] = {}  # Prevent spam alerts
        
    async def get_current_costs(self, session_id: str) -> Dict[str, float]:
        """Get current costs for session, daily, and weekly periods."""
        try:
            # Session cost
            session_cost = await self.telemetry.get_current_session_cost(session_id)
            
            # Daily cost
            today_costs = await self.telemetry.get_cost_trends(days=1)
            daily_cost = sum(today_costs.values()) if today_costs else 0.0
            
            # Weekly cost
            weekly_costs = await self.telemetry.get_cost_trends(days=7)
            weekly_cost = sum(weekly_costs.values()) if weekly_costs else 0.0
            
            return {
                "session": session_cost,
                "daily": daily_cost,
                "weekly": weekly_cost
            }
            
        except Exception as e:
            logger.error(f"Failed to get current costs: {e}")
            return {"session": 0.0, "daily": 0.0, "weekly": 0.0}
    
    async def check_budget_status(self, session_id: str) -> List[OptimizationSuggestion]:
        """Check current budget status and return alerts/suggestions."""
        current_costs = await self.get_current_costs(session_id)
        suggestions = []
        
        # Check session budget
        session_percentage = current_costs["session"] / self.config.session_limit
        if session_percentage >= self.config.critical_threshold:
            suggestions.append(OptimizationSuggestion(
                type="budget_alert",
                priority="critical", 
                title="Session Budget Nearly Exhausted",
                description=f"Session cost (${current_costs['session']:.2f}) is at {session_percentage:.0%} of budget (${self.config.session_limit:.2f})",
                action_required=True,
                auto_applicable=self.config.auto_switch_haiku
            ))
        elif session_percentage >= self.config.warning_threshold:
            suggestions.append(OptimizationSuggestion(
                type="budget_warning",
                priority="high",
                title="Session Budget Warning", 
                description=f"Session cost (${current_costs['session']:.2f}) is at {session_percentage:.0%} of budget (${self.config.session_limit:.2f})",
                expected_savings_percent=60.0 if self.config.auto_switch_haiku else None
            ))
        
        # Check daily budget
        daily_percentage = current_costs["daily"] / self.config.daily_limit
        if daily_percentage >= self.config.critical_threshold:
            suggestions.append(OptimizationSuggestion(
                type="daily_budget_alert",
                priority="critical",
                title="Daily Budget Nearly Exhausted",
                description=f"Today's cost (${current_costs['daily']:.2f}) is at {daily_percentage:.0%} of daily budget (${self.config.daily_limit:.2f})",
                action_required=True
            ))
        elif daily_percentage >= self.config.warning_threshold:
            suggestions.append(OptimizationSuggestion(
                type="daily_budget_warning", 
                priority="medium",
                title="Daily Budget Warning",
                description=f"Today's cost (${current_costs['daily']:.2f}) is at {daily_percentage:.0%} of daily budget (${self.config.daily_limit:.2f})"
            ))
        
        return suggestions
    
    async def should_force_cost_optimization(self, session_id: str) -> bool:
        """Determine if cost optimization should be forced."""
        current_costs = await self.get_current_costs(session_id)
        
        # Force optimization if over budget
        if current_costs["session"] >= self.config.session_limit:
            return True
        if current_costs["daily"] >= self.config.daily_limit:
            return True
            
        # Force if approaching limits with auto-optimization enabled
        if self.config.auto_switch_haiku:
            session_percentage = current_costs["session"] / self.config.session_limit
            if session_percentage >= self.config.critical_threshold:
                return True
                
        return False
    
    async def get_budget_projections(self, session_id: str) -> Dict[str, float]:
        """Get budget projections based on current usage patterns."""
        try:
            current_costs = await self.get_current_costs(session_id)
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            
            if not session_metrics:
                return {}
            
            # Calculate burn rate
            session_duration_hours = 1.0  # Default
            if session_metrics.start_time and session_metrics.end_time:
                duration = session_metrics.end_time - session_metrics.start_time
                session_duration_hours = duration.total_seconds() / 3600
            
            hourly_burn_rate = current_costs["session"] / max(session_duration_hours, 0.1)
            
            # Project costs
            projections = {
                "hourly_burn_rate": hourly_burn_rate,
                "projected_daily_total": current_costs["daily"] + (hourly_burn_rate * 8),  # Assume 8 more hours
                "projected_session_total": current_costs["session"] + (hourly_burn_rate * 2),  # Assume 2 more hours
                "budget_exhaustion_hours": max(0, (self.config.session_limit - current_costs["session"]) / max(hourly_burn_rate, 0.01))
            }
            
            return projections
            
        except Exception as e:
            logger.error(f"Failed to calculate budget projections: {e}")
            return {}
    
    async def send_alert(self, alert_type: str, message: str, session_id: str):
        """Send budget alert (with rate limiting to prevent spam)."""
        # Rate limiting - don't send same alert type more than once per hour
        alert_key = f"{alert_type}_{session_id}"
        now = datetime.now()
        
        if alert_key in self._alert_cache:
            last_alert = self._alert_cache[alert_key]
            if now - last_alert < timedelta(hours=1):
                return  # Skip duplicate alert
        
        self._alert_cache[alert_key] = now
        
        # Log alert (could be extended to send notifications)
        logger.warning(f"BUDGET ALERT [{alert_type}]: {message} (Session: {session_id})")
        
        # Clean old cache entries
        cutoff = now - timedelta(hours=2)
        self._alert_cache = {k: v for k, v in self._alert_cache.items() if v > cutoff}
    
    async def enable_cost_efficient_mode(self, session_id: str):
        """Enable cost-efficient mode with automatic optimizations."""
        logger.info(f"Enabling cost-efficient mode for session: {session_id}")
        
        # This would integrate with the main Claude Code system to:
        # 1. Prefer Haiku model for new requests
        # 2. Enable automatic context reduction
        # 3. Show cost warnings more prominently
        
        # For now, just log the action
        await self.send_alert(
            "cost_efficient_mode", 
            "Cost-efficient mode enabled due to budget constraints",
            session_id
        )
    
    async def get_cost_efficiency_report(self, session_id: str) -> Dict[str, any]:
        """Generate a comprehensive cost efficiency report."""
        try:
            current_costs = await self.get_current_costs(session_id)
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            model_stats = await self.telemetry.get_model_usage_stats(days=1)
            projections = await self.get_budget_projections(session_id)
            
            if not session_metrics:
                return {"error": "No session data available"}
            
            # Calculate efficiency metrics
            cost_per_api_call = current_costs["session"] / max(session_metrics.api_calls, 1)
            cost_per_token = current_costs["session"] / max(session_metrics.total_input_tokens, 1)
            
            # Model efficiency comparison
            model_efficiency = {}
            for model, stats in model_stats.items():
                if stats["request_count"] > 0:
                    model_efficiency[model] = {
                        "cost_per_token": stats["cost_per_token"],
                        "avg_duration_ms": stats["avg_duration_ms"],
                        "efficiency_score": (1000 / max(stats["avg_duration_ms"], 1)) * (1 / max(stats["cost_per_token"], 0.001))
                    }
            
            return {
                "session_summary": {
                    "total_cost": current_costs["session"],
                    "api_calls": session_metrics.api_calls,
                    "cost_per_call": cost_per_api_call,
                    "cost_per_token": cost_per_token
                },
                "budget_status": {
                    "session_budget_used": (current_costs["session"] / self.config.session_limit) * 100,
                    "daily_budget_used": (current_costs["daily"] / self.config.daily_limit) * 100,
                    "remaining_session_budget": max(0, self.config.session_limit - current_costs["session"]),
                    "remaining_daily_budget": max(0, self.config.daily_limit - current_costs["daily"])
                },
                "model_efficiency": model_efficiency,
                "projections": projections,
                "recommendations": await self._generate_efficiency_recommendations(session_metrics, model_stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate cost efficiency report: {e}")
            return {"error": str(e)}
    
    async def _generate_efficiency_recommendations(self, session_metrics, model_stats) -> List[str]:
        """Generate personalized efficiency recommendations."""
        recommendations = []
        
        # High cost per call recommendation
        if session_metrics.total_cost / max(session_metrics.api_calls, 1) > 0.03:
            recommendations.append("Consider using Haiku model for routine tasks to reduce cost per API call")
        
        # Token efficiency recommendation  
        avg_input_tokens = session_metrics.total_input_tokens / max(session_metrics.api_calls, 1)
        if avg_input_tokens > 2000:
            recommendations.append("Large context sizes detected - consider breaking down requests for better efficiency")
        
        # Model usage recommendation
        sonnet_usage = 0
        haiku_usage = 0
        for model, stats in model_stats.items():
            if "sonnet" in model.lower():
                sonnet_usage += stats["request_count"]
            elif "haiku" in model.lower():
                haiku_usage += stats["request_count"]
        
        total_requests = sonnet_usage + haiku_usage
        if total_requests > 0:
            sonnet_percentage = sonnet_usage / total_requests
            if sonnet_percentage > 0.7:  # More than 70% Sonnet usage
                recommendations.append("High Sonnet usage detected - Haiku could handle many tasks at 60-80% cost savings")
        
        return recommendations