"""Error recovery manager for coordinating recovery strategies."""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..clients.base import TelemetryClient, ErrorEvent
from .strategies import (
    RecoveryStrategy, 
    TokenReductionStrategy,
    ModelSwitchStrategy,
    ContextChunkingStrategy,
    TimeoutIncreaseStrategy,
    RequestContext,
    RecoveryResult
)
from .exceptions import (
    MaxRetriesExceeded, NoViableStrategyError,  # Legacy compatibility
    create_max_retries_exceeded_error, create_no_viable_strategy_error  # Modern HTTPException pattern
)
from context_cleaner.api.models import create_error_response

logger = logging.getLogger(__name__)


class ErrorPattern:
    """Represents patterns in error telemetry data."""
    
    def __init__(self, error_type: str, frequency: int, success_rate: float):
        self.error_type = error_type
        self.frequency = frequency
        self.success_rate = success_rate
        self.is_timeout = "timeout" in error_type.lower() or "aborted" in error_type.lower()


class ErrorRecoveryManager:
    """Manages error recovery strategies based on telemetry patterns."""
    
    def __init__(self, telemetry_client: TelemetryClient, max_retries: int = 3):
        self.telemetry = telemetry_client
        self.max_retries = max_retries
        
        # Initialize recovery strategies in priority order
        self.strategies: List[RecoveryStrategy] = [
            TokenReductionStrategy(reduction_factor=0.3),
            ModelSwitchStrategy(fallback_model="claude-3-5-haiku-20241022"),
            ContextChunkingStrategy(chunk_size_tokens=2000),
            TimeoutIncreaseStrategy(timeout_multiplier=1.5)
        ]
        
        # Sort strategies by priority
        self.strategies.sort(key=lambda s: s.get_priority())
        
        # Cache for error patterns
        self._error_pattern_cache: Dict[str, ErrorPattern] = {}
        self._cache_expiry = datetime.now()
        
    async def handle_api_error(self, error_type: str, context: RequestContext) -> RecoveryResult:
        """
        Handle an API error by trying applicable recovery strategies.
        
        Args:
            error_type: The type of error that occurred
            context: The request context that caused the error
            
        Returns:
            RecoveryResult with the outcome of recovery attempts
            
        Raises:
            MaxRetriesExceeded: When all recovery strategies fail
            NoViableStrategyError: When no strategies are applicable
        """
        logger.info(f"Handling API error: {error_type} for session {context.session_id}")
        
        # Analyze error pattern from telemetry
        error_pattern = await self._analyze_error_pattern(error_type)
        
        # Get applicable strategies for this error
        applicable_strategies = self._get_applicable_strategies(error_type, context, error_pattern)
        
        if not applicable_strategies:
            raise create_no_viable_strategy_error(error_type)
        
        # Try strategies in priority order
        strategies_tried = []
        for attempt, strategy in enumerate(applicable_strategies[:self.max_retries], 1):
            logger.info(f"Attempt {attempt}: Trying strategy '{strategy.name}'")
            
            try:
                result = await strategy.execute(context)
                strategies_tried.append(strategy.name)
                
                if result.succeeded:
                    logger.info(f"Recovery successful with strategy: {strategy.name}")
                    await self._log_recovery_success(error_type, strategy.name, context)
                    return result
                else:
                    logger.warning(f"Strategy {strategy.name} failed: {result.error_message}")
                    
            except Exception as e:
                logger.error(f"Strategy {strategy.name} execution error: {e}")
                
        # All strategies failed
        logger.error(f"All recovery strategies failed for error: {error_type}")
        await self._log_recovery_failure(error_type, strategies_tried, context)
        
        raise create_max_retries_exceeded_error(len(strategies_tried), strategies_tried)
    
    async def _analyze_error_pattern(self, error_type: str) -> ErrorPattern:
        """Analyze error patterns from telemetry data."""
        # Use cache if available and not expired
        if (error_type in self._error_pattern_cache and 
            datetime.now() < self._cache_expiry):
            return self._error_pattern_cache[error_type]
        
        try:
            # Get recent error data
            recent_errors = await self.telemetry.get_recent_errors(hours=48)
            
            # Count this error type
            error_count = sum(1 for e in recent_errors if e.error_type == error_type)
            
            # For now, assume moderate success rate - could be enhanced with actual recovery tracking
            success_rate = 0.7  # 70% default success rate assumption
            
            pattern = ErrorPattern(error_type, error_count, success_rate)
            
            # Cache the pattern
            self._error_pattern_cache[error_type] = pattern
            self._cache_expiry = datetime.now() + timedelta(hours=1)
            
            return pattern
            
        except Exception as e:
            logger.warning(f"Could not analyze error pattern: {e}")
            # Return default pattern
            return ErrorPattern(error_type, 1, 0.5)
    
    def _get_applicable_strategies(self, error_type: str, context: RequestContext, 
                                 pattern: ErrorPattern) -> List[RecoveryStrategy]:
        """Get strategies applicable to the given error and context."""
        applicable = []
        
        for strategy in self.strategies:
            if strategy.is_applicable(error_type, context):
                applicable.append(strategy)
                logger.debug(f"Strategy {strategy.name} is applicable for error: {error_type}")
        
        return applicable
    
    async def _log_recovery_success(self, error_type: str, strategy_name: str, context: RequestContext):
        """Log successful recovery for telemetry."""
        logger.info(f"Recovery success: {error_type} -> {strategy_name} (session: {context.session_id})")
        # Could send this to telemetry system for tracking recovery effectiveness
        
    async def _log_recovery_failure(self, error_type: str, strategies_tried: List[str], context: RequestContext):
        """Log recovery failure for telemetry."""
        logger.error(f"Recovery failure: {error_type} after trying {strategies_tried} (session: {context.session_id})")
        # Could send this to telemetry system for improving recovery strategies
    
    async def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get statistics about recovery attempts and success rates."""
        try:
            recent_errors = await self.telemetry.get_recent_errors(hours=168)  # 1 week
            
            if not recent_errors:
                return {"total_errors": 0, "error_types": {}}
            
            # Analyze error types
            error_types = {}
            for error in recent_errors:
                error_type = error.error_type
                if error_type not in error_types:
                    error_types[error_type] = {
                        "count": 0,
                        "avg_duration_ms": 0,
                        "models_affected": set()
                    }
                
                error_types[error_type]["count"] += 1
                error_types[error_type]["avg_duration_ms"] += error.duration_ms
                error_types[error_type]["models_affected"].add(error.model)
            
            # Calculate averages
            for error_type, stats in error_types.items():
                stats["avg_duration_ms"] /= stats["count"]
                stats["models_affected"] = list(stats["models_affected"])
            
            return {
                "total_errors": len(recent_errors),
                "error_types": error_types,
                "error_rate": len(recent_errors) / max(168, 1),  # errors per hour
                "most_common_error": max(error_types.items(), key=lambda x: x[1]["count"])[0] if error_types else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get recovery statistics: {e}")
            raise create_error_response(
                f"Error recovery processing failed: {str(e)}",
                "ERROR_RECOVERY_FAILED",
                500
            )
    
    async def suggest_optimizations(self, session_id: str) -> List[Dict[str, Any]]:
        """Suggest optimizations based on current session patterns."""
        try:
            session_metrics = await self.telemetry.get_session_metrics(session_id)
            if not session_metrics:
                return []
            
            suggestions = []
            
            # High cost session suggestion
            if session_metrics.total_cost > 2.0:
                suggestions.append({
                    "type": "cost_optimization",
                    "priority": "high",
                    "message": f"Session cost (${session_metrics.total_cost:.2f}) is above optimal range. Consider using Haiku model for routine tasks.",
                    "action": "model_switch",
                    "expected_savings": "60-80%"
                })
            
            # Large token usage suggestion  
            avg_tokens = session_metrics.total_input_tokens / max(session_metrics.api_calls, 1)
            if avg_tokens > 2000:
                suggestions.append({
                    "type": "context_optimization",
                    "priority": "medium", 
                    "message": f"Average request size ({avg_tokens:.0f} tokens) may increase timeout risk. Consider breaking down large contexts.",
                    "action": "context_chunking",
                    "expected_benefit": "Reduced timeout risk"
                })
            
            # Error-prone session suggestion
            if session_metrics.error_count > 0:
                suggestions.append({
                    "type": "reliability",
                    "priority": "high",
                    "message": f"Session has {session_metrics.error_count} error(s). Enable automatic error recovery.",
                    "action": "enable_recovery",
                    "expected_benefit": "90% error recovery success rate"
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            return []