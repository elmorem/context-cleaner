"""Exceptions for error recovery system."""


class RecoveryError(Exception):
    """Base exception for recovery system errors."""
    pass


class MaxRetriesExceeded(RecoveryError):
    """Raised when all recovery strategies have been exhausted."""
    
    def __init__(self, attempts: int, strategies_tried: list):
        self.attempts = attempts
        self.strategies_tried = strategies_tried
        super().__init__(f"Recovery failed after {attempts} attempts with strategies: {strategies_tried}")


class NoViableStrategyError(RecoveryError):
    """Raised when no recovery strategy is applicable to the error."""
    
    def __init__(self, error_type: str):
        self.error_type = error_type
        super().__init__(f"No recovery strategy available for error type: {error_type}")


class StrategyExecutionError(RecoveryError):
    """Raised when a recovery strategy fails to execute."""
    
    def __init__(self, strategy_name: str, reason: str):
        self.strategy_name = strategy_name
        self.reason = reason
        super().__init__(f"Strategy {strategy_name} failed: {reason}")