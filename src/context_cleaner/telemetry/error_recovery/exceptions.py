"""Exceptions for error recovery system using standardized HTTPException pattern."""

from fastapi import HTTPException
from context_cleaner.api.models import create_error_response


def create_max_retries_exceeded_error(attempts: int, strategies_tried: list) -> HTTPException:
    """Create standardized error for when all recovery strategies have been exhausted."""
    return create_error_response(
        message=f"Recovery failed after {attempts} attempts with strategies: {strategies_tried}",
        error_code="MAX_RETRIES_EXCEEDED",
        status_code=503,
        details={
            "attempts": attempts,
            "strategies_tried": strategies_tried,
            "recovery_type": "error_recovery"
        }
    )


def create_no_viable_strategy_error(error_type: str) -> HTTPException:
    """Create standardized error for when no recovery strategy is applicable."""
    return create_error_response(
        message=f"No recovery strategy available for error type: {error_type}",
        error_code="NO_VIABLE_STRATEGY",
        status_code=422,
        details={
            "error_type": error_type,
            "recovery_type": "error_recovery"
        }
    )


def create_strategy_execution_error(strategy_name: str, reason: str) -> HTTPException:
    """Create standardized error for when a recovery strategy fails to execute."""
    return create_error_response(
        message=f"Strategy {strategy_name} failed: {reason}",
        error_code="STRATEGY_EXECUTION_FAILED",
        status_code=500,
        details={
            "strategy_name": strategy_name,
            "reason": reason,
            "recovery_type": "error_recovery"
        }
    )


# Legacy compatibility - deprecated but kept for backwards compatibility
class RecoveryError(Exception):
    """Base exception for recovery system errors. DEPRECATED: Use create_*_error functions instead."""
    pass


class MaxRetriesExceeded(RecoveryError):
    """DEPRECATED: Use create_max_retries_exceeded_error() instead."""

    def __init__(self, attempts: int, strategies_tried: list):
        self.attempts = attempts
        self.strategies_tried = strategies_tried
        super().__init__(f"Recovery failed after {attempts} attempts with strategies: {strategies_tried}")


class NoViableStrategyError(RecoveryError):
    """DEPRECATED: Use create_no_viable_strategy_error() instead."""

    def __init__(self, error_type: str):
        self.error_type = error_type
        super().__init__(f"No recovery strategy available for error type: {error_type}")


class StrategyExecutionError(RecoveryError):
    """DEPRECATED: Use create_strategy_execution_error() instead."""

    def __init__(self, strategy_name: str, reason: str):
        self.strategy_name = strategy_name
        self.reason = reason
        super().__init__(f"Strategy {strategy_name} failed: {reason}")