import asyncio
import time
import logging
from typing import Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    expected_exception: type = Exception
    name: str = "default"

class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open."""
    pass

class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.success_count = 0
        
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to a function."""
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        return wrapper
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.config.name} attempting reset")
            else:
                raise CircuitBreakerOpenException(
                    f"Circuit breaker {self.config.name} is open"
                )
                
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            self._on_success()
            return result
            
        except self.config.expected_exception as e:
            self._on_failure()
            raise e
            
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.config.recovery_timeout
        
    def _on_success(self):
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:  # Require 3 successes to close
                self._reset()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
            
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.config.name} failed during half-open, returning to open")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.config.name} opened after {self.failure_count} failures")
            
    def _reset(self):
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info(f"Circuit breaker {self.config.name} reset to closed state")
        
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
        
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN
        
    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring."""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "success_count": self.success_count
        }