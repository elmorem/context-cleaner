"""Recovery strategies for different types of API errors."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Context information for an API request."""

    model: str
    input_tokens: int
    context: str
    session_id: str
    original_request: Dict[str, Any]
    timeout_seconds: Optional[float] = None


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    succeeded: bool
    strategy_used: str
    modified_context: Optional[RequestContext] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None


class RecoveryStrategy(ABC):
    """Abstract base class for recovery strategies."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def is_applicable(self, error_type: str, context: RequestContext) -> bool:
        """Determine if this strategy can handle the given error."""
        pass

    @abstractmethod
    async def execute(self, context: RequestContext) -> RecoveryResult:
        """Execute the recovery strategy."""
        pass

    def get_priority(self) -> int:
        """Get strategy priority (lower number = higher priority)."""
        return 100  # Default priority


class TokenReductionStrategy(RecoveryStrategy):
    """Reduce token count to avoid timeouts and context limits."""

    def __init__(self, reduction_factor: float = 0.3):
        super().__init__("token_reduction")
        self.reduction_factor = reduction_factor  # Reduce by 30% by default

    def is_applicable(self, error_type: str, context: RequestContext) -> bool:
        """Applicable for timeout errors and large contexts."""
        return (
            "timeout" in error_type.lower()
            or "aborted" in error_type.lower()
            or context.input_tokens
            > 3000  # Based on telemetry: >3000 tokens risk timeouts
        )

    async def execute(self, context: RequestContext) -> RecoveryResult:
        """Reduce context size and retry."""
        try:
            # Calculate new token target
            target_tokens = int(context.input_tokens * (1 - self.reduction_factor))

            # Simple truncation strategy (more sophisticated chunking could be added)
            estimated_chars_per_token = len(context.context) / max(
                context.input_tokens, 1
            )
            target_chars = int(target_tokens * estimated_chars_per_token)

            reduced_context = context.context[:target_chars]

            # Add truncation notice
            if len(reduced_context) < len(context.context):
                reduced_context += "\n\n[Context truncated for reliability]"

            modified_context = RequestContext(
                model=context.model,
                input_tokens=target_tokens,
                context=reduced_context,
                session_id=context.session_id,
                original_request=context.original_request,
                timeout_seconds=context.timeout_seconds,
            )

            logger.info(
                f"Token reduction: {context.input_tokens} → {target_tokens} tokens"
            )

            return RecoveryResult(
                succeeded=True,
                strategy_used=self.name,
                modified_context=modified_context,
            )

        except Exception as e:
            return RecoveryResult(
                succeeded=False, strategy_used=self.name, error_message=str(e)
            )

    def get_priority(self) -> int:
        return 10  # High priority


class ModelSwitchStrategy(RecoveryStrategy):
    """Switch to a more reliable/cost-effective model."""

    def __init__(self, fallback_model: str = "claude-3-5-haiku-20241022"):
        super().__init__("model_switch")
        self.fallback_model = fallback_model

    def is_applicable(self, error_type: str, context: RequestContext) -> bool:
        """Applicable when using high-cost models that timeout."""
        return context.model == "claude-sonnet-4-20250514" and (
            "timeout" in error_type.lower() or "aborted" in error_type.lower()
        )

    async def execute(self, context: RequestContext) -> RecoveryResult:
        """Switch to fallback model."""
        try:
            modified_context = RequestContext(
                model=self.fallback_model,
                input_tokens=context.input_tokens,
                context=context.context,
                session_id=context.session_id,
                original_request=context.original_request,
                timeout_seconds=context.timeout_seconds,
            )

            logger.info(f"Model switch: {context.model} → {self.fallback_model}")

            return RecoveryResult(
                succeeded=True,
                strategy_used=self.name,
                modified_context=modified_context,
            )

        except Exception as e:
            return RecoveryResult(
                succeeded=False, strategy_used=self.name, error_message=str(e)
            )

    def get_priority(self) -> int:
        return 20  # Medium priority


class ContextChunkingStrategy(RecoveryStrategy):
    """Break large contexts into smaller chunks."""

    def __init__(self, chunk_size_tokens: int = 2000):
        super().__init__("context_chunking")
        self.chunk_size_tokens = chunk_size_tokens

    def is_applicable(self, error_type: str, context: RequestContext) -> bool:
        """Applicable for very large contexts."""
        return context.input_tokens > 2500  # Chunk contexts larger than 2.5k tokens

    async def execute(self, context: RequestContext) -> RecoveryResult:
        """Break context into manageable chunks."""
        try:
            # For now, just take the first chunk - could be enhanced to be smarter
            estimated_chars_per_token = len(context.context) / max(
                context.input_tokens, 1
            )
            chunk_chars = int(self.chunk_size_tokens * estimated_chars_per_token)

            chunked_context = context.context[:chunk_chars]
            chunked_context += "\n\n[Note: Context chunked for processing efficiency]"

            modified_context = RequestContext(
                model=context.model,
                input_tokens=self.chunk_size_tokens,
                context=chunked_context,
                session_id=context.session_id,
                original_request=context.original_request,
                timeout_seconds=context.timeout_seconds,
            )

            logger.info(
                f"Context chunking: {context.input_tokens} → {self.chunk_size_tokens} tokens"
            )

            return RecoveryResult(
                succeeded=True,
                strategy_used=self.name,
                modified_context=modified_context,
            )

        except Exception as e:
            return RecoveryResult(
                succeeded=False, strategy_used=self.name, error_message=str(e)
            )

    def get_priority(self) -> int:
        return 30  # Lower priority


class TimeoutIncreaseStrategy(RecoveryStrategy):
    """Increase timeout for potentially slow requests."""

    def __init__(self, timeout_multiplier: float = 1.5):
        super().__init__("timeout_increase")
        self.timeout_multiplier = timeout_multiplier

    def is_applicable(self, error_type: str, context: RequestContext) -> bool:
        """Applicable for timeout errors with reasonable context sizes."""
        return (
            "timeout" in error_type.lower()
            and context.input_tokens < 3000  # Don't increase timeout for huge contexts
        )

    async def execute(self, context: RequestContext) -> RecoveryResult:
        """Increase timeout and retry."""
        try:
            new_timeout = None
            if context.timeout_seconds:
                new_timeout = context.timeout_seconds * self.timeout_multiplier
            else:
                new_timeout = 15.0  # Default increased timeout

            modified_context = RequestContext(
                model=context.model,
                input_tokens=context.input_tokens,
                context=context.context,
                session_id=context.session_id,
                original_request=context.original_request,
                timeout_seconds=new_timeout,
            )

            logger.info(
                f"Timeout increase: {context.timeout_seconds}s → {new_timeout}s"
            )

            return RecoveryResult(
                succeeded=True,
                strategy_used=self.name,
                modified_context=modified_context,
            )

        except Exception as e:
            return RecoveryResult(
                succeeded=False, strategy_used=self.name, error_message=str(e)
            )

    def get_priority(self) -> int:
        return 40  # Lowest priority
