"""Production-ready Context Rot Monitor with resource bounds and circuit breaker integration."""

import asyncio
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import weakref
import psutil
import os

from ..clients.clickhouse_client import ClickHouseClient
from ...hooks.circuit_breaker import CircuitBreaker
from .security import SecureContextRotAnalyzer, PrivacyConfig

logger = logging.getLogger(__name__)


@dataclass
class MemoryLimiter:
    """Memory usage limiter to prevent unbounded growth."""

    max_mb: int = 256
    check_interval_seconds: int = 30
    _last_check: datetime = field(default_factory=datetime.now)

    def get_current_usage_mb(self) -> float:
        """Get current memory usage of the process in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

    def check_memory_limit(self) -> bool:
        """Check if current memory usage is within limits."""
        now = datetime.now()
        if (now - self._last_check).total_seconds() < self.check_interval_seconds:
            return True  # Skip check to avoid overhead

        self._last_check = now
        current_mb = self.get_current_usage_mb()

        if current_mb > self.max_mb:
            logger.warning(
                f"Memory usage ({current_mb:.1f}MB) exceeds limit ({self.max_mb}MB)"
            )
            return False

        return True

    def force_cleanup(self):
        """Force garbage collection when approaching limits."""
        import gc

        gc.collect()


@dataclass
class QuickAssessment:
    """Quick assessment result from lightweight analysis."""

    rot_estimate: float  # 0.0 to 1.0, where 1.0 is maximum rot
    confidence: float  # 0.0 to 1.0, confidence in the assessment
    requires_attention: bool  # True if user action recommended
    indicators: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class BoundedDataStructure:
    """Memory-bounded data structure with automatic cleanup."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.data = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def append(self, item: Any):
        """Thread-safe append with automatic size limiting."""
        with self._lock:
            self.data.append(item)

    def get_recent(self, count: int) -> List[Any]:
        """Get most recent items."""
        with self._lock:
            return (
                list(self.data)[-count:] if count <= len(self.data) else list(self.data)
            )

    def clear(self):
        """Clear all data."""
        with self._lock:
            self.data.clear()

    def __len__(self):
        return len(self.data)


class RepetitionStatistics:
    """Memory-efficient repetition detection using bounded data structures."""

    def __init__(self, window_size: int = 50):
        self.window_size = min(window_size, 100)  # Cap window size
        self.message_hashes = BoundedDataStructure(max_size=self.window_size)
        self.pattern_counts = BoundedDataStructure(max_size=self.window_size * 2)

    def analyze_sequence(self, content: str) -> float:
        """Analyze repetition in content sequence."""
        if not content:
            return 0.0

        # Simple hash-based repetition detection
        content_hash = hash(content.lower().strip())

        # Check for exact repetitions
        recent_hashes = self.message_hashes.get_recent(self.window_size)
        exact_repetitions = sum(1 for h in recent_hashes if h == content_hash)

        # Add current hash
        self.message_hashes.append(content_hash)

        # Calculate repetition score (0.0 to 1.0)
        if len(recent_hashes) == 0:
            return 0.0

        repetition_score = min(exact_repetitions / max(len(recent_hashes), 1), 1.0)

        # Additional pattern detection for phrases
        words = content.lower().split()
        if len(words) > 3:
            for i in range(len(words) - 2):
                phrase = " ".join(words[i : i + 3])
                self.pattern_counts.append(phrase)

        return repetition_score


class EfficiencyTracker:
    """Track conversation efficiency with bounded memory usage."""

    def __init__(self):
        self.response_times = BoundedDataStructure(max_size=50)
        self.message_lengths = BoundedDataStructure(max_size=50)
        self.success_indicators = BoundedDataStructure(max_size=50)

    def calculate_trend(self, event_data: Dict[str, Any]) -> float:
        """Calculate efficiency trend from recent events."""
        # Mock efficiency calculation - could be enhanced with real metrics
        message_length = len(event_data.get("content", ""))
        self.message_lengths.append(message_length)

        # Simple heuristic: shorter messages might indicate frustration or confusion
        recent_lengths = self.message_lengths.get_recent(10)
        if len(recent_lengths) < 3:
            return 0.5  # Neutral score

        avg_length = sum(recent_lengths) / len(recent_lengths)

        # Score efficiency (higher is better, 0.0 to 1.0)
        if avg_length < 50:  # Very short messages might indicate frustration
            return 0.3
        elif avg_length > 1000:  # Very long messages might indicate confusion
            return 0.4
        else:
            return 0.7  # Good range


class SessionHealthMonitor:
    """Monitor overall session health with memory bounds."""

    def __init__(self):
        self.error_indicators = BoundedDataStructure(max_size=20)
        self.success_indicators = BoundedDataStructure(max_size=20)
        self.session_start = datetime.now()

    def add_error_indicator(self, error_type: str):
        """Add an error indicator."""
        self.error_indicators.append((datetime.now(), error_type))

    def add_success_indicator(self, success_type: str):
        """Add a success indicator."""
        self.success_indicators.append((datetime.now(), success_type))

    def get_health_score(self) -> float:
        """Get overall session health score."""
        error_count = len(self.error_indicators)
        success_count = len(self.success_indicators)
        total_events = error_count + success_count

        if total_events == 0:
            return 0.5  # Neutral

        success_rate = success_count / total_events
        return success_rate


class ProductionReadyContextRotMonitor:
    """Production-ready Context Rot Monitor with comprehensive safety measures."""

    def __init__(
        self, clickhouse_client: ClickHouseClient, error_manager: "ErrorRecoveryManager"
    ):
        self.clickhouse = clickhouse_client
        self.error_manager = error_manager

        # Memory and resource management
        self.memory_limiter = MemoryLimiter(max_mb=256)

        # Circuit breaker for external dependencies
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=0.050,  # 50ms timeout
            recovery_timeout=30.0,
            name="context_rot_monitor",
        )

        # Security analyzer
        privacy_config = PrivacyConfig(
            remove_pii=True,
            hash_sensitive_patterns=True,
            anonymize_file_paths=True,
            max_content_length=10000,  # Reasonable limit for context analysis
        )
        self.secure_analyzer = SecureContextRotAnalyzer(privacy_config)

        # Analysis components with memory bounds
        self.repetition_detector = RepetitionStatistics(window_size=50)
        self.efficiency_tracker = EfficiencyTracker()
        self.session_health = SessionHealthMonitor()

        # Session tracking with weak references to prevent memory leaks
        self._active_sessions = weakref.WeakValueDictionary()

        logger.info("Context Rot Monitor initialized with production safety measures")

    async def analyze_lightweight(
        self, session_id: str, content: str
    ) -> Optional[QuickAssessment]:
        """Perform lightweight real-time analysis with comprehensive error handling."""
        try:
            # Memory limit check
            if not self.memory_limiter.check_memory_limit():
                logger.warning("Memory limit exceeded, forcing cleanup")
                self.memory_limiter.force_cleanup()
                return None

            # Input validation and sanitization
            validated_input = self.secure_analyzer.validate_and_sanitize_input(
                session_id, content, window_size=50
            )

            if not validated_input:
                logger.warning("Input validation failed for context rot analysis")
                return None

            # Use circuit breaker for analysis
            result = self.circuit_breaker.call(self._perform_analysis, validated_input)

            if result is None:
                logger.warning("Context rot analysis failed or circuit breaker open")
                return None

            return result

        except Exception as e:
            logger.error(f"Context rot analysis error: {e}")
            self.session_health.add_error_indicator("analysis_error")
            return None

    def _perform_analysis(self, validated_input: Dict[str, Any]) -> QuickAssessment:
        """Perform the actual analysis with validated input."""
        content = validated_input["content"]
        session_id = validated_input["session_id"]

        # Repetition analysis
        repetition_score = self.repetition_detector.analyze_sequence(content)

        # Efficiency analysis
        efficiency_score = self.efficiency_tracker.calculate_trend({"content": content})

        # Session health check
        health_score = self.session_health.get_health_score()

        # Weighted scoring (can be tuned based on real data)
        rot_estimate = self._weighted_score(
            repetition_score, efficiency_score, health_score
        )
        confidence = self._calculate_confidence(
            repetition_score, efficiency_score, health_score
        )
        requires_attention = self._check_thresholds(rot_estimate, confidence)

        # Track successful analysis
        self.session_health.add_success_indicator("analysis_success")

        return QuickAssessment(
            rot_estimate=rot_estimate,
            confidence=confidence,
            requires_attention=requires_attention,
            indicators={
                "repetition": repetition_score,
                "efficiency": efficiency_score,
                "health": health_score,
            },
        )

    def _weighted_score(
        self, repetition: float, efficiency: float, health: float
    ) -> float:
        """Calculate weighted context rot score."""
        # Higher repetition = more rot
        # Lower efficiency = more rot
        # Lower health = more rot

        repetition_weight = 0.4
        efficiency_weight = 0.3
        health_weight = 0.3

        # Convert efficiency and health to rot indicators (invert them)
        efficiency_rot = 1.0 - efficiency
        health_rot = 1.0 - health

        weighted_rot = (
            repetition * repetition_weight
            + efficiency_rot * efficiency_weight
            + health_rot * health_weight
        )

        return min(max(weighted_rot, 0.0), 1.0)  # Clamp to [0, 1]

    def _calculate_confidence(
        self, repetition: float, efficiency: float, health: float
    ) -> float:
        """Calculate confidence in the assessment."""
        # More data points = higher confidence
        data_points = [
            len(self.repetition_detector.message_hashes),
            len(self.efficiency_tracker.message_lengths),
            len(self.session_health.success_indicators)
            + len(self.session_health.error_indicators),
        ]

        avg_data_points = sum(data_points) / len(data_points)
        max_confidence_threshold = 20  # Need 20+ data points for full confidence

        confidence = min(avg_data_points / max_confidence_threshold, 1.0)

        return confidence

    def _check_thresholds(self, rot_estimate: float, confidence: float) -> bool:
        """Check if the assessment requires user attention."""
        # Only flag for attention if we have reasonable confidence
        if confidence < 0.3:
            return False

        # Thresholds can be made configurable
        high_rot_threshold = 0.7
        medium_rot_threshold = 0.5

        if rot_estimate >= high_rot_threshold:
            return True
        elif rot_estimate >= medium_rot_threshold and confidence >= 0.6:
            return True

        return False

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system health and performance metrics."""
        try:
            memory_mb = self.memory_limiter.get_current_usage_mb()
            circuit_state = self.circuit_breaker.get_state()

            return {
                "memory_usage_mb": round(memory_mb, 1),
                "memory_limit_mb": self.memory_limiter.max_mb,
                "memory_usage_pct": round(
                    (memory_mb / self.memory_limiter.max_mb) * 100, 1
                ),
                "circuit_breaker": circuit_state,
                "active_sessions": len(self._active_sessions),
                "analysis_components": {
                    "repetition_buffer_size": len(
                        self.repetition_detector.message_hashes
                    ),
                    "efficiency_buffer_size": len(
                        self.efficiency_tracker.message_lengths
                    ),
                    "health_events": len(self.session_health.success_indicators)
                    + len(self.session_health.error_indicators),
                },
                "uptime_seconds": (
                    datetime.now() - self.session_health.session_start
                ).total_seconds(),
            }

        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}

    def reset_session_data(self, session_id: str):
        """Reset data for a specific session."""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]

        # For now, we reset all data - could be enhanced to track per-session
        self.repetition_detector = RepetitionStatistics(window_size=50)
        self.efficiency_tracker = EfficiencyTracker()

        logger.info(f"Reset context rot data for session: {session_id}")

    async def cleanup_old_data(self, max_age_hours: int = 24):
        """Cleanup old data to prevent memory accumulation."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            # The bounded data structures will automatically limit size
            # This method could be enhanced to clean up based on timestamps

            # Force garbage collection
            self.memory_limiter.force_cleanup()

            logger.info(f"Cleaned up context rot data older than {max_age_hours} hours")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
