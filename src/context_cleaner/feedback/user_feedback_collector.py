"""
Privacy-First User Feedback Collector

Anonymous feedback collection system for Context Cleaner that respects user privacy
while gathering insights about real-world performance and usage patterns.

Key Privacy Principles:
- Zero external data transmission
- Local-only processing and storage
- Anonymous usage patterns (no personal data)
- User consent and opt-out mechanisms
- GDPR/CCPA compliant data handling
"""

import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import psutil

from ..config.settings import ContextCleanerConfig
from ..optimization.memory_optimizer import MemoryOptimizer
from ..optimization.cpu_optimizer import CPUOptimizer

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEvent:
    """Anonymous feedback event with privacy protection."""
    event_type: str  # 'performance', 'usage', 'satisfaction', 'error'
    timestamp: datetime
    session_id: str  # Anonymous session identifier
    data: Dict[str, Any] = field(default_factory=dict)
    privacy_level: str = "anonymous"  # anonymous, aggregated_only
    
    def to_anonymous_dict(self) -> Dict[str, Any]:
        """Convert to anonymous dictionary for storage."""
        return {
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'session_hash': hashlib.sha256(self.session_id.encode()).hexdigest()[:16],
            'data': self._sanitize_data(self.data),
            'privacy_level': self.privacy_level
        }
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove any potentially identifying information."""
        sanitized = {}
        
        # Allow list of safe metrics
        safe_keys = {
            'memory_mb', 'cpu_percent', 'duration_ms', 'optimization_count',
            'cache_hits', 'cache_misses', 'task_count', 'error_type',
            'performance_score', 'improvement_percent', 'feature_used',
            'system_type', 'python_version', 'package_version'
        }
        
        for key, value in data.items():
            if key in safe_keys:
                # Additional sanitization for numeric values
                if isinstance(value, (int, float)):
                    # Round to reasonable precision
                    sanitized[key] = round(float(value), 2)
                elif isinstance(value, str) and len(value) < 100:
                    # Allow short strings (like version numbers)
                    sanitized[key] = value[:50]  # Truncate to be safe
                elif isinstance(value, bool):
                    sanitized[key] = value
        
        return sanitized


@dataclass
class UserPreferences:
    """User preferences for feedback collection."""
    feedback_enabled: bool = True
    anonymous_usage_stats: bool = True
    performance_tracking: bool = True
    error_reporting: bool = True
    satisfaction_surveys: bool = False  # Opt-in only
    
    # Frequency controls
    max_events_per_hour: int = 10
    max_events_per_day: int = 50
    
    # Data retention
    retention_days: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPreferences':
        """Create from dictionary."""
        return cls(**data)


class FeedbackStorage:
    """Local-only feedback storage with automatic cleanup."""
    
    def __init__(self, storage_dir: Path):
        """Initialize feedback storage."""
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage files
        self.events_file = self.storage_dir / "feedback_events.jsonl"
        self.preferences_file = self.storage_dir / "user_preferences.json"
        self.session_file = self.storage_dir / "session_info.json"
        
        # In-memory cache
        self._events_cache: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
    
    def store_event(self, event: FeedbackEvent):
        """Store feedback event locally."""
        with self._lock:
            try:
                # Add to cache
                self._events_cache.append(event.to_anonymous_dict())
                
                # Append to file
                with open(self.events_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event.to_anonymous_dict()) + '\n')
                
                logger.debug(f"Stored feedback event: {event.event_type}")
                
            except Exception as e:
                logger.warning(f"Failed to store feedback event: {e}")
    
    def load_preferences(self) -> UserPreferences:
        """Load user preferences."""
        try:
            if self.preferences_file.exists():
                with open(self.preferences_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return UserPreferences.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load preferences: {e}")
        
        return UserPreferences()  # Default preferences
    
    def save_preferences(self, preferences: UserPreferences):
        """Save user preferences."""
        try:
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(preferences.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save preferences: {e}")
    
    def get_recent_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent events from cache and file."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_events = []
        
        with self._lock:
            # Check cache first
            for event_dict in self._events_cache:
                try:
                    event_time = datetime.fromisoformat(event_dict['timestamp'])
                    if event_time >= cutoff:
                        recent_events.append(event_dict)
                except Exception:
                    continue
            
            # If cache doesn't have enough, read from file
            if len(recent_events) < 10 and self.events_file.exists():
                try:
                    with open(self.events_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                event_dict = json.loads(line.strip())
                                event_time = datetime.fromisoformat(event_dict['timestamp'])
                                if event_time >= cutoff:
                                    recent_events.append(event_dict)
                            except Exception:
                                continue
                except Exception as e:
                    logger.warning(f"Failed to read events file: {e}")
        
        return recent_events
    
    def cleanup_old_data(self, retention_days: int = 30):
        """Remove old feedback data."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        try:
            if not self.events_file.exists():
                return
            
            # Read all events and keep only recent ones
            kept_events = []
            with open(self.events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event_dict = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event_dict['timestamp'])
                        if event_time >= cutoff:
                            kept_events.append(event_dict)
                    except Exception:
                        continue
            
            # Rewrite file with kept events
            with open(self.events_file, 'w', encoding='utf-8') as f:
                for event_dict in kept_events:
                    f.write(json.dumps(event_dict) + '\n')
            
            logger.info(f"Cleaned up feedback data: kept {len(kept_events)} recent events")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup old data: {e}")


class UserFeedbackCollector:
    """
    Privacy-first user feedback collection system.
    
    Collects anonymous usage patterns and performance metrics to improve
    Context Cleaner while respecting user privacy and regulatory requirements.
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize user feedback collector."""
        self.config = config or ContextCleanerConfig.from_env()
        
        # Storage setup
        feedback_dir = Path.home() / '.context-cleaner' / 'feedback'
        self.storage = FeedbackStorage(feedback_dir)
        
        # User preferences
        self.preferences = self.storage.load_preferences()
        
        # Session tracking
        self.session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        
        # Rate limiting
        self._event_counts = defaultdict(int)  # events per hour
        self._last_reset = datetime.now()
        
        # Monitoring state
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Performance baselines
        self._baseline_metrics: Dict[str, Any] = {}
        self._performance_samples: deque = deque(maxlen=100)
        
        logger.info("User feedback collector initialized")
        
        # Show privacy notice on first run
        self._show_privacy_notice_if_needed()
    
    def _show_privacy_notice_if_needed(self):
        """Show privacy notice to user on first run."""
        session_file = self.storage.session_file
        
        if not session_file.exists():
            logger.info("""
╭─ Context Cleaner Privacy Notice ─────────────────────────────────────╮
│                                                                       │
│  Context Cleaner collects anonymous usage data to improve            │
│  performance and user experience. This data:                         │
│                                                                       │
│  ✓ Stays local on your machine (never transmitted)                   │
│  ✓ Contains no personal or identifying information                    │
│  ✓ Helps optimize performance for all users                          │
│  ✓ Can be disabled anytime with: context-cleaner feedback --disable  │
│                                                                       │
│  Learn more: https://github.com/elmorem/context-cleaner#privacy      │
│                                                                       │
╰───────────────────────────────────────────────────────────────────────╯
            """)
            
            # Create session file to track first run
            try:
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'first_run': self.session_start.isoformat(),
                        'privacy_notice_shown': True
                    }, f)
            except Exception as e:
                logger.warning(f"Failed to create session file: {e}")
    
    def start_monitoring(self):
        """Start background feedback monitoring."""
        if not self.preferences.feedback_enabled:
            logger.debug("Feedback collection disabled by user preferences")
            return
        
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._stop_monitoring.clear()
        
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="FeedbackCollector"
        )
        self._monitor_thread.start()
        
        # Record session start
        self._record_event('usage', {
            'action': 'session_start',
            'system_type': self._get_system_type(),
            'python_version': self._get_python_version(),
            'package_version': self._get_package_version()
        })
        
        logger.debug("Feedback monitoring started")
    
    def stop_monitoring(self):
        """Stop feedback monitoring."""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        self._stop_monitoring.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        
        # Record session end
        session_duration = (datetime.now() - self.session_start).total_seconds()
        self._record_event('usage', {
            'action': 'session_end',
            'duration_ms': int(session_duration * 1000)
        })
        
        # Cleanup old data
        self.storage.cleanup_old_data(self.preferences.retention_days)
        
        logger.debug("Feedback monitoring stopped")
    
    def _monitoring_loop(self):
        """Background monitoring loop for automatic feedback collection."""
        while not self._stop_monitoring.is_set():
            try:
                # Reset hourly rate limits
                now = datetime.now()
                if now - self._last_reset > timedelta(hours=1):
                    self._event_counts.clear()
                    self._last_reset = now
                
                # Collect performance metrics
                if self.preferences.performance_tracking:
                    self._collect_performance_metrics()
                
                # Sleep until next collection (every 5 minutes)
                self._stop_monitoring.wait(timeout=300)
                
            except Exception as e:
                logger.warning(f"Feedback monitoring error: {e}")
                self._stop_monitoring.wait(timeout=600)  # Longer wait on error
    
    def _collect_performance_metrics(self):
        """Collect current performance metrics."""
        try:
            # Get system metrics
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent()
            
            metrics = {
                'memory_mb': memory_mb,
                'cpu_percent': cpu_percent,
                'timestamp': datetime.now().isoformat()
            }
            
            self._performance_samples.append(metrics)
            
            # Calculate improvement if we have baseline
            if self._baseline_metrics:
                baseline_memory = self._baseline_metrics.get('memory_mb', memory_mb)
                baseline_cpu = self._baseline_metrics.get('cpu_percent', cpu_percent)
                
                memory_improvement = max(0, baseline_memory - memory_mb)
                cpu_improvement = max(0, baseline_cpu - cpu_percent)
                
                if memory_improvement > 5 or cpu_improvement > 1:  # Significant improvement
                    self._record_event('performance', {
                        'memory_improvement_mb': memory_improvement,
                        'cpu_improvement_percent': cpu_improvement,
                        'current_memory_mb': memory_mb,
                        'current_cpu_percent': cpu_percent
                    })
            else:
                # Set baseline on first measurement
                self._baseline_metrics = {
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu_percent
                }
        
        except Exception as e:
            logger.debug(f"Performance metrics collection failed: {e}")
    
    def record_feature_usage(self, feature: str, success: bool = True, **kwargs):
        """Record usage of a specific feature."""
        if not self.preferences.anonymous_usage_stats:
            return
        
        data = {
            'feature_used': feature,
            'success': success,
            **kwargs
        }
        
        self._record_event('usage', data)
    
    def record_optimization_impact(self, optimization_type: str, before_metrics: Dict[str, Any], 
                                  after_metrics: Dict[str, Any]):
        """Record the impact of an optimization."""
        if not self.preferences.performance_tracking:
            return
        
        # Calculate improvements
        memory_before = before_metrics.get('memory_mb', 0)
        memory_after = after_metrics.get('memory_mb', 0)
        memory_saved = max(0, memory_before - memory_after)
        
        cpu_before = before_metrics.get('cpu_percent', 0)
        cpu_after = after_metrics.get('cpu_percent', 0)
        cpu_improvement = max(0, cpu_before - cpu_after)
        
        data = {
            'optimization_type': optimization_type,
            'memory_saved_mb': memory_saved,
            'cpu_improvement_percent': cpu_improvement,
            'memory_before_mb': memory_before,
            'memory_after_mb': memory_after,
            'cpu_before_percent': cpu_before,
            'cpu_after_percent': cpu_after
        }
        
        self._record_event('performance', data)
    
    def record_error(self, error_type: str, error_context: str = None):
        """Record an error event (if user opted in)."""
        if not self.preferences.error_reporting:
            return
        
        data = {
            'error_type': error_type[:50],  # Truncate error types
        }
        
        if error_context:
            data['error_context'] = error_context[:100]  # Limited context
        
        self._record_event('error', data)
    
    def _record_event(self, event_type: str, data: Dict[str, Any]):
        """Record a feedback event with rate limiting."""
        # Check rate limits
        hour_key = datetime.now().strftime('%Y-%m-%d-%H')
        if self._event_counts[hour_key] >= self.preferences.max_events_per_hour:
            logger.debug(f"Rate limit exceeded for feedback events")
            return
        
        # Check daily limits
        today = datetime.now().strftime('%Y-%m-%d')
        day_count = sum(count for key, count in self._event_counts.items() 
                       if key.startswith(today))
        
        if day_count >= self.preferences.max_events_per_day:
            logger.debug(f"Daily limit exceeded for feedback events")
            return
        
        # Create and store event
        event = FeedbackEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            session_id=self.session_id,
            data=data
        )
        
        self.storage.store_event(event)
        self._event_counts[hour_key] += 1
        
        logger.debug(f"Recorded {event_type} feedback event")
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of collected feedback data."""
        recent_events = self.storage.get_recent_events(24)
        
        # Analyze events by type
        event_types = defaultdict(int)
        performance_metrics = []
        feature_usage = defaultdict(int)
        
        for event in recent_events:
            event_types[event['event_type']] += 1
            
            if event['event_type'] == 'performance':
                performance_metrics.append(event['data'])
            elif event['event_type'] == 'usage':
                feature = event['data'].get('feature_used')
                if feature:
                    feature_usage[feature] += 1
        
        # Calculate performance trends
        if performance_metrics:
            avg_memory_saved = sum(m.get('memory_saved_mb', 0) for m in performance_metrics)
            avg_cpu_improvement = sum(m.get('cpu_improvement_percent', 0) for m in performance_metrics)
        else:
            avg_memory_saved = 0
            avg_cpu_improvement = 0
        
        return {
            'session_id_hash': hashlib.sha256(self.session_id.encode()).hexdigest()[:16],
            'session_duration_hours': (datetime.now() - self.session_start).total_seconds() / 3600,
            'events_last_24h': len(recent_events),
            'event_types': dict(event_types),
            'top_features': dict(sorted(feature_usage.items(), key=lambda x: x[1], reverse=True)[:5]),
            'performance_impact': {
                'avg_memory_saved_mb': round(avg_memory_saved, 1),
                'avg_cpu_improvement_percent': round(avg_cpu_improvement, 1),
                'measurements_count': len(performance_metrics)
            },
            'preferences': self.preferences.to_dict()
        }
    
    def update_preferences(self, **kwargs):
        """Update user preferences."""
        for key, value in kwargs.items():
            if hasattr(self.preferences, key):
                setattr(self.preferences, key, value)
        
        self.storage.save_preferences(self.preferences)
        logger.info("Updated user feedback preferences")
    
    def disable_feedback(self):
        """Completely disable feedback collection."""
        self.update_preferences(
            feedback_enabled=False,
            anonymous_usage_stats=False,
            performance_tracking=False,
            error_reporting=False,
            satisfaction_surveys=False
        )
        
        if self._is_monitoring:
            self.stop_monitoring()
        
        logger.info("Feedback collection disabled")
    
    def _get_system_type(self) -> str:
        """Get anonymous system type."""
        import platform
        system = platform.system()
        # Return generic categories only
        if system in ['Darwin', 'Linux', 'Windows']:
            return system
        return 'Other'
    
    def _get_python_version(self) -> str:
        """Get Python version."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}"
    
    def _get_package_version(self) -> str:
        """Get Context Cleaner package version."""
        try:
            from .. import __version__
            return __version__
        except ImportError:
            return "unknown"


def main():
    """CLI interface for feedback management."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Context Cleaner Feedback Management')
    parser.add_argument('--status', action='store_true', help='Show feedback status')
    parser.add_argument('--disable', action='store_true', help='Disable feedback collection')
    parser.add_argument('--enable', action='store_true', help='Enable feedback collection')
    parser.add_argument('--summary', action='store_true', help='Show feedback summary')
    
    args = parser.parse_args()
    
    collector = UserFeedbackCollector()
    
    if args.disable:
        collector.disable_feedback()
        print("✓ Feedback collection disabled")
    
    elif args.enable:
        collector.update_preferences(feedback_enabled=True, anonymous_usage_stats=True)
        print("✓ Feedback collection enabled")
    
    elif args.summary:
        summary = collector.get_feedback_summary()
        print("\n📊 Feedback Summary")
        print("═" * 40)
        print(f"Session Duration: {summary['session_duration_hours']:.1f} hours")
        print(f"Events (24h): {summary['events_last_24h']}")
        print(f"Event Types: {summary['event_types']}")
        print(f"Top Features: {summary['top_features']}")
        print(f"Performance Impact:")
        perf = summary['performance_impact']
        print(f"  Memory Saved: {perf['avg_memory_saved_mb']:.1f} MB avg")
        print(f"  CPU Improvement: {perf['avg_cpu_improvement_percent']:.1f}% avg")
        print(f"  Measurements: {perf['measurements_count']}")
    
    else:
        # Show status
        prefs = collector.preferences
        print(f"\n📊 Context Cleaner Feedback Status")
        print("═" * 40)
        print(f"Feedback Enabled: {'✓' if prefs.feedback_enabled else '✗'}")
        print(f"Usage Stats: {'✓' if prefs.anonymous_usage_stats else '✗'}")
        print(f"Performance Tracking: {'✓' if prefs.performance_tracking else '✗'}")
        print(f"Error Reporting: {'✓' if prefs.error_reporting else '✗'}")
        print(f"Data Retention: {prefs.retention_days} days")
        print(f"Rate Limits: {prefs.max_events_per_hour}/hour, {prefs.max_events_per_day}/day")
        print("\nAll data stays local on your machine. No external transmission.")


if __name__ == '__main__':
    main()