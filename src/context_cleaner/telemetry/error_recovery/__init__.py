"""Error recovery and resilience patterns for Claude Code telemetry."""

from .manager import ErrorRecoveryManager
from .strategies import (
    TokenReductionStrategy,
    ModelSwitchStrategy, 
    ContextChunkingStrategy,
    RecoveryStrategy
)
from .exceptions import (
    RecoveryError,
    MaxRetriesExceeded,
    NoViableStrategyError
)

__all__ = [
    "ErrorRecoveryManager",
    "TokenReductionStrategy", 
    "ModelSwitchStrategy",
    "ContextChunkingStrategy",
    "RecoveryStrategy",
    "RecoveryError",
    "MaxRetriesExceeded", 
    "NoViableStrategyError"
]