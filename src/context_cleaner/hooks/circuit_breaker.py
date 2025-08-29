"""
Circuit Breaker Pattern Implementation

Provides protection against cascading failures and ensures hook operations
never block Claude Code execution for more than the specified timeout.
"""

import time
from enum import Enum
from typing import Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable failure thresholds.
    
    Designed to protect Claude Code from hook execution failures:
    - Fails fast when hooks are consistently failing
    - Automatic recovery testing after timeout period
    - Performance guarantees: <50ms execution timeout
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: float = 0.050,  # 50ms max execution time
        recovery_timeout: float = 30.0,  # 30s before attempting recovery
        name: str = "hook_circuit_breaker"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Maximum execution time in seconds (50ms default)
            recovery_timeout: Time to wait before attempting recovery
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker protection."""
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result or None if circuit is open
            
        Raises:
            TimeoutError: If function exceeds timeout (caught internally)
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} attempting recovery")
            else:
                logger.debug(f"Circuit breaker {self.name} is open, failing fast")
                return None
        
        try:
            result = self._execute_with_timeout(func, *args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure(e)
            return None
    
    def _execute_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with strict timeout enforcement.
        
        This is critical for Claude Code performance - hooks must never
        block execution beyond the specified timeout period.
        """
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function execution exceeded {self.timeout}s timeout")
        
        # Set timeout signal (Unix/Linux/macOS only)
        try:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                signal.alarm(0)  # Cancel the alarm
                signal.signal(signal.SIGALRM, old_handler)
                
        except AttributeError:
            # Windows doesn't support SIGALRM, use threading approach
            import threading
            import queue
            
            result_queue = queue.Queue()
            exception_queue = queue.Queue()
            
            def target():
                try:
                    result = func(*args, **kwargs)
                    result_queue.put(result)
                except Exception as e:
                    exception_queue.put(e)
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=self.timeout)
            
            if thread.is_alive():
                # Thread is still running - timeout occurred
                raise TimeoutError(f"Function execution exceeded {self.timeout}s timeout")
            
            # Check for exceptions
            if not exception_queue.empty():
                raise exception_queue.get()
            
            # Return result if available
            if not result_queue.empty():
                return result_queue.get()
            
            # No result and no exception - unexpected
            raise RuntimeError("Function completed but returned no result")
    
    def _on_success(self):
        """Handle successful function execution."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker {self.name} recovered, closing circuit")
            self.state = CircuitState.CLOSED
        
        self.failure_count = 0
    
    def _on_failure(self, exception: Exception):
        """Handle function execution failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.warning(
            f"Circuit breaker {self.name} failure {self.failure_count}/{self.failure_threshold}: {exception}"
        )
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker {self.name} opened after {self.failure_count} failures"
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt circuit recovery."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout_ms": self.timeout * 1000,
            "last_failure_time": self.last_failure_time,
            "uptime_ok": self.state == CircuitState.CLOSED
        }
    
    def reset(self):
        """Manually reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker {self.name} manually reset")