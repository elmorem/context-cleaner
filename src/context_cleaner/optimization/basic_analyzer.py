#!/usr/bin/env python3
"""
Basic Context Analyzer - Performance-first implementation
Provides safe context analysis with comprehensive error handling and performance limits.
"""

import asyncio
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass


# Configure logging to be silent by default
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Structured result from context analysis."""

    health_score: int
    size_category: str
    estimated_tokens: int
    total_chars: int
    top_level_keys: int
    session_length_category: str
    analysis_timestamp: str
    analysis_duration: float
    circuit_breaker_active: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "health_score": self.health_score,
            "size_category": self.size_category,
            "estimated_tokens": self.estimated_tokens,
            "total_chars": self.total_chars,
            "top_level_keys": self.top_level_keys,
            "session_length_category": self.session_length_category,
            "analysis_timestamp": self.analysis_timestamp,
            "analysis_duration": self.analysis_duration,
            "circuit_breaker_active": self.circuit_breaker_active,
        }


class CircuitBreaker:
    """Circuit breaker for protecting against repeated failures."""

    def __init__(self, failure_threshold: int = 3, timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self._lock = threading.Lock()

    def can_proceed(self) -> bool:
        """Check if operation can proceed."""
        with self._lock:
            if self.failure_count < self.failure_threshold:
                return True

            if self.last_failure_time is None:
                return False  # Should not proceed if we have failures but no timestamp

            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout:
                self.failure_count = 0
                self.last_failure_time = None
                return True

            return False

    def record_failure(self):
        """Record a failure."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

    def record_success(self):
        """Record a successful operation."""
        with self._lock:
            if self.failure_count > 0:
                self.failure_count = max(0, self.failure_count - 1)


class SimpleCache:
    """Simple in-memory cache with TTL."""

    def __init__(self, ttl: int = 300):  # 5 minutes default
        self.ttl = ttl
        self._cache = {}
        self._timestamps = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        with self._lock:
            if key not in self._cache:
                return None

            if time.time() - self._timestamps[key] > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            return self._cache[key]

    def set(self, key: str, value: Any):
        """Set cached value with timestamp."""
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()

    def clear_expired(self):
        """Clear expired cache entries."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, timestamp in self._timestamps.items()
                if current_time - timestamp > self.ttl
            ]
            for key in expired_keys:
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)


class SafeContextAnalyzer:
    """Safe context analyzer with performance limits and error handling."""

    # Performance constants
    MAX_ANALYSIS_TIME = 5.0  # seconds
    MAX_MEMORY_MB = 50
    CACHE_TTL = 300  # 5 minutes
    SIZE_ANALYSIS_TIMEOUT = 2.0  # seconds

    def __init__(self):
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
        self.cache = SimpleCache(ttl=self.CACHE_TTL)
        self._start_time = time.time()

    def _get_accurate_token_count(self, content_str: str) -> int:
        """Get accurate token count using ccusage approach."""
        try:
            from ..analysis.enhanced_token_counter import get_accurate_token_count

            return get_accurate_token_count(content_str)
        except ImportError:
            return 0

    def _get_cache_key(self, data: Dict[str, Any]) -> str:
        """Generate cache key from data hash."""
        try:
            data_str = json.dumps(data, sort_keys=True, default=str)
            return str(hash(data_str))
        except Exception:
            return str(time.time())  # Fallback to timestamp

    def _get_fallback_result(self) -> AnalysisResult:
        """Get fallback analysis result for error cases."""
        return AnalysisResult(
            health_score=50,  # Neutral score
            size_category="unknown",
            estimated_tokens=0,
            total_chars=0,
            top_level_keys=0,
            session_length_category="unknown",
            analysis_timestamp=datetime.now().isoformat(),
            analysis_duration=0.0,
            circuit_breaker_active=True,
        )

    def _check_memory_usage(self) -> bool:
        """Check if memory usage is within limits."""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            if memory_mb > self.MAX_MEMORY_MB:
                logger.warning(
                    f"Memory usage {memory_mb:.1f}MB exceeds limit {self.MAX_MEMORY_MB}MB"
                )
                return False
            return True
        except ImportError:
            # psutil not available - assume OK
            return True
        except Exception:
            # Error checking memory - assume OK but log
            logger.warning("Memory usage check failed")
            return True

    def _analyze_context_size(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze context size with timeout protection."""
        start_time = time.time()

        try:
            # Basic size calculation
            json_str = json.dumps(data, default=str)
            total_chars = len(json_str)
            estimated_tokens = self._get_accurate_token_count(json_str)
            top_level_keys = len(data.keys()) if isinstance(data, dict) else 0

            # Size categorization
            if total_chars < 10000:
                size_category = "small"
            elif total_chars < 50000:
                size_category = "medium"
            elif total_chars < 100000:
                size_category = "large"
            else:
                size_category = "very_large"

            result = {
                "total_chars": total_chars,
                "estimated_tokens": estimated_tokens,
                "top_level_keys": top_level_keys,
                "size_category": size_category,
            }

            # Check execution time
            elapsed = time.time() - start_time
            if elapsed > self.SIZE_ANALYSIS_TIMEOUT:
                logger.warning(
                    f"Size analysis took {elapsed:.3f}s (limit: {self.SIZE_ANALYSIS_TIMEOUT}s)"
                )

            return result

        except Exception as e:
            logger.error(f"Size analysis failed: {e}")
            return {
                "total_chars": 0,
                "estimated_tokens": 0,
                "top_level_keys": 0,
                "size_category": "unknown",
                "error": str(e),
            }

    def _calculate_health_score(
        self, size_info: Dict[str, Any], session_duration: float = 0
    ) -> Dict[str, Any]:
        """Calculate basic health score."""
        try:
            estimated_tokens = size_info.get("estimated_tokens", 0)
            size_info.get("total_chars", 0)

            # Basic health score calculation
            # Score decreases as context size increases
            base_score = 100

            # Penalize large context sizes
            if estimated_tokens > 0:
                token_penalty = min(
                    50, estimated_tokens // 1000
                )  # 1 point per 1000 tokens, max 50
                base_score -= token_penalty

            # Bonus for well-structured data
            top_level_keys = size_info.get("top_level_keys", 0)
            if 3 <= top_level_keys <= 10:  # Sweet spot for structure
                base_score += 5

            health_score = min(100, max(0, base_score))

            # Session length categorization
            if session_duration < 1800:  # 30 minutes
                session_length_category = "short"
            elif session_duration < 7200:  # 2 hours
                session_length_category = "medium"
            else:
                session_length_category = "long"

            return {
                "health_score": health_score,
                "session_length_category": session_length_category,
                "token_penalty": (
                    min(50, estimated_tokens // 1000) if estimated_tokens > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Health score calculation failed: {e}")
            return {
                "health_score": 50,
                "session_length_category": "unknown",
                "token_penalty": 0,
                "error": str(e),
            }

    async def _perform_analysis(self, data: Dict[str, Any]) -> AnalysisResult:
        """Perform the actual analysis with timeout protection."""
        analysis_start = time.time()

        # Check memory before starting
        if not self._check_memory_usage():
            raise MemoryError("Memory usage exceeds limits")

        # Analyze context size
        size_info = self._analyze_context_size(data)

        # Calculate session duration
        current_time = time.time()
        session_duration = current_time - self._start_time

        # Calculate health metrics
        health_info = self._calculate_health_score(size_info, session_duration)

        analysis_duration = time.time() - analysis_start

        # Create result object
        result = AnalysisResult(
            health_score=health_info["health_score"],
            size_category=size_info["size_category"],
            estimated_tokens=size_info["estimated_tokens"],
            total_chars=size_info["total_chars"],
            top_level_keys=size_info["top_level_keys"],
            session_length_category=health_info["session_length_category"],
            analysis_timestamp=datetime.now().isoformat(),
            analysis_duration=analysis_duration,
            circuit_breaker_active=not self.circuit_breaker.can_proceed(),
        )

        return result

    async def analyze_context_safely(
        self, data: Dict[str, Any]
    ) -> Optional[AnalysisResult]:
        """Main analysis method with comprehensive safety measures."""
        # Generate cache key
        cache_key = self._get_cache_key(data)

        # Check cache first
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Returning cached analysis result")
            return cached_result

        # Circuit breaker check
        if not self.circuit_breaker.can_proceed():
            logger.warning("Circuit breaker active, returning fallback result")
            return self._get_fallback_result()

        try:
            # Perform analysis with timeout
            result = await asyncio.wait_for(
                self._perform_analysis(data), timeout=self.MAX_ANALYSIS_TIME
            )

            # Cache successful result
            self.cache.set(cache_key, result)

            # Record success for circuit breaker
            self.circuit_breaker.record_success()

            return result

        except asyncio.TimeoutError:
            logger.error(f"Analysis timed out after {self.MAX_ANALYSIS_TIME}s")
            self.circuit_breaker.record_failure()
            return self._get_fallback_result()

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            self.circuit_breaker.record_failure()
            return self._get_fallback_result()

    def analyze_context_sync(self, data: Dict[str, Any]) -> Optional[AnalysisResult]:
        """Synchronous wrapper for analysis."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.analyze_context_safely(data))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Synchronous analysis failed: {e}")
            return self._get_fallback_result()

    def get_basic_health_summary(self, result: AnalysisResult) -> Dict[str, str]:
        """Get human-readable health summary."""
        if result is None:
            return {
                "status": "Analysis unavailable",
                "summary": "Context analysis could not be completed",
            }

        # Health status
        if result.health_score >= 80:
            status = "Excellent"
        elif result.health_score >= 60:
            status = "Good"
        elif result.health_score >= 40:
            status = "Fair"
        else:
            status = "Needs attention"

        # Create summary
        summary = f"Context health: {status} (Score: {result.health_score}/100)"
        if result.size_category != "unknown":
            summary += f", Size: {result.size_category}"
        if result.estimated_tokens > 0:
            summary += f", ~{result.estimated_tokens} tokens"

        return {
            "status": status,
            "summary": summary,
            "health_score": result.health_score,
            "size_category": result.size_category,
            "estimated_tokens": result.estimated_tokens,
        }


# Global analyzer instance for reuse
_global_analyzer = None


def get_analyzer() -> SafeContextAnalyzer:
    """Get global analyzer instance (singleton pattern)."""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = SafeContextAnalyzer()
    return _global_analyzer


# Convenience functions for easy usage
async def analyze_context(data: Dict[str, Any]) -> Optional[AnalysisResult]:
    """Analyze context data safely."""
    analyzer = get_analyzer()
    return await analyzer.analyze_context_safely(data)


def analyze_context_sync(data: Dict[str, Any]) -> Optional[AnalysisResult]:
    """Analyze context data synchronously."""
    analyzer = get_analyzer()
    return analyzer.analyze_context_sync(data)


def get_health_summary(data: Dict[str, Any]) -> Dict[str, str]:
    """Get basic health summary for context data."""
    result = analyze_context_sync(data)
    analyzer = get_analyzer()
    return analyzer.get_basic_health_summary(result)


# Main function for testing
if __name__ == "__main__":
    # Test with sample data
    test_data = {
        "session_id": "test-123",
        "messages": ["msg1", "msg2", "msg3"],
        "files": ["file1.py", "file2.py"],
        "timestamp": datetime.now().isoformat(),
    }

    print("Testing Basic Context Analyzer...")

    # Test synchronous analysis
    result = analyze_context_sync(test_data)
    if result:
        print(f"Analysis completed successfully!")
        print(f"Health Score: {result.health_score}")
        print(f"Size Category: {result.size_category}")
        print(f"Estimated Tokens: {result.estimated_tokens}")
        print(f"Analysis Duration: {result.analysis_duration:.3f}s")

        # Test health summary
        summary = get_health_summary(test_data)
        print(f"Summary: {summary['summary']}")
    else:
        print("Analysis failed!")
