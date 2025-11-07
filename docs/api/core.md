# Core API Reference

This document provides comprehensive API documentation for Context Cleaner's core components.

## Overview

The Context Cleaner core API provides the foundational classes and functions for productivity tracking, context analysis, and system management.

## Main Classes

### `ContextCleanerConfig`

Configuration management for Context Cleaner settings.

```python
from context_cleaner.config import ContextCleanerConfig

# Load configuration from environment
config = ContextCleanerConfig.from_env()

# Create with custom settings
config = ContextCleanerConfig(
    data_directory="./my_data",
    tracking_enabled=True,
    performance_monitoring=True
)
```

#### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `from_env()` | Load configuration from environment variables | `ContextCleanerConfig` |
| `get(key, default=None)` | Get configuration value | `Any` |
| `set(key, value)` | Set configuration value | `None` |
| `save()` | Save configuration to file | `None` |
| `reset()` | Reset to default configuration | `None` |

#### Configuration Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `data_directory` | `str` | `~/.context_cleaner` | Data storage directory |
| `tracking.enabled` | `bool` | `True` | Enable productivity tracking |
| `tracking.session_timeout` | `int` | `1800` | Session timeout in seconds |
| `privacy.data_retention_days` | `int` | `90` | Data retention period |
| `performance.max_memory_mb` | `int` | `50` | Maximum memory usage |
| `dashboard.port` | `int` | `8110` | Dashboard server port |
| `dashboard.theme` | `str` | `dark` | Dashboard theme |

### `SessionTracker`

Core session tracking and productivity monitoring.

```python
from context_cleaner.tracking import SessionTracker

# Initialize tracker
tracker = SessionTracker()

# Start tracking session
session_id = tracker.start_session()

# Track events
tracker.track_event("context_optimization", {
    "context_size": 1500,
    "optimization_type": "quick"
})

# End session
tracker.end_session(session_id)
```

#### Methods

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `start_session()` | Begin new tracking session | None | `str` (session_id) |
| `end_session(session_id)` | End tracking session | `session_id: str` | `None` |
| `track_event(event_type, data)` | Track productivity event | `event_type: str`, `data: dict` | `None` |
| `get_session_data(session_id)` | Get session statistics | `session_id: str` | `dict` |
| `get_recent_sessions(hours)` | Get recent sessions | `hours: int` | `List[dict]` |

#### Event Types

| Event Type | Description | Data Fields |
|------------|-------------|-------------|
| `session_start` | Session initialization | `timestamp`, `user_id` |
| `context_optimization` | Context optimization performed | `context_size`, `optimization_type`, `duration` |
| `productivity_analysis` | Analysis operation | `analysis_type`, `data_points`, `insights` |
| `dashboard_access` | Dashboard viewed | `page`, `duration`, `interactions` |
| `performance_issue` | Performance problem detected | `operation`, `duration_ms`, `severity` |

### `ProductivityAnalyzer`

Advanced productivity analysis and insights generation.

```python
from context_cleaner.analytics import ProductivityAnalyzer

# Initialize analyzer
analyzer = ProductivityAnalyzer()

# Analyze recent productivity
analysis = analyzer.analyze_period(days=7)

# Get productivity score
score = analyzer.calculate_productivity_score(session_data)

# Generate recommendations
recommendations = analyzer.generate_recommendations(analysis)
```

#### Methods

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `analyze_period(days)` | Analyze productivity over time period | `days: int` | `ProductivityReport` |
| `calculate_productivity_score(data)` | Calculate 0-100 productivity score | `data: dict` | `float` |
| `generate_recommendations(analysis)` | Generate improvement suggestions | `analysis: ProductivityReport` | `List[str]` |
| `detect_patterns(sessions)` | Identify productivity patterns | `sessions: List[dict]` | `PatternAnalysis` |
| `forecast_trends(history)` | Predict future productivity trends | `history: List[float]` | `TrendForecast` |

#### ProductivityReport

```python
@dataclass
class ProductivityReport:
    period_days: int
    total_sessions: int
    avg_productivity_score: float
    productivity_trend: str  # "increasing", "stable", "decreasing"
    peak_hours: List[int]
    optimization_impact: float
    recommendations: List[str]
    insights: List[str]
```

### `ContextOptimizer`

Context analysis and optimization engine.

```python
from context_cleaner.optimization import ContextOptimizer

# Initialize optimizer
optimizer = ContextOptimizer()

# Analyze context health
health = optimizer.analyze_context_health(context_data)

# Get optimization suggestions
suggestions = optimizer.get_optimization_suggestions(context_data)

# Apply optimizations
result = optimizer.apply_optimizations(suggestions, preview=False)
```

#### Methods

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `analyze_context_health(data)` | Assess context health | `data: dict` | `ContextHealth` |
| `get_optimization_suggestions(data)` | Generate optimization recommendations | `data: dict` | `List[OptimizationSuggestion]` |
| `apply_optimizations(suggestions, preview)` | Apply optimization changes | `suggestions: List`, `preview: bool` | `OptimizationResult` |
| `estimate_impact(suggestions)` | Estimate optimization impact | `suggestions: List` | `ImpactEstimate` |

## Data Models

### `SessionData`

```python
@dataclass
class SessionData:
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    events: List[dict]
    productivity_score: float
    context_optimizations: int
    performance_metrics: dict
```

### `ContextHealth`

```python
@dataclass
class ContextHealth:
    score: int  # 0-100
    size_category: str  # "small", "medium", "large", "very_large"
    token_count: int
    complexity_score: float
    recommendations: List[str]
    performance_impact: str  # "low", "medium", "high"
```

### `OptimizationSuggestion`

```python
@dataclass
class OptimizationSuggestion:
    type: str  # "remove_redundancy", "prioritize", "summarize"
    description: str
    impact_estimate: float  # 0-1 scale
    risk_level: str  # "low", "medium", "high"
    automatic: bool  # Can be applied automatically
```

## Error Handling

### Exception Classes

```python
from context_cleaner.utils.error_handling import (
    ContextCleanerError,
    StorageError,
    AnalysisError,
    IntegrationError,
    PerformanceError
)

try:
    result = analyzer.analyze_period(days=30)
except AnalysisError as e:
    print(f"Analysis failed: {e}")
    print(f"Error category: {e.category}")
    print(f"Severity: {e.severity}")
except ContextCleanerError as e:
    print(f"General error: {e}")
```

### Error Handler

```python
from context_cleaner.utils.error_handling import get_error_handler

# Get global error handler
handler = get_error_handler()

# Handle specific error
success = handler.handle_error(exception, context={"operation": "analysis"})

# Get error summary
summary = handler.get_error_summary(hours=24)
```

## Utilities

### Decorators

```python
from context_cleaner.utils.error_handling import error_handler
from context_cleaner.utils.performance import performance_monitor

# Automatic error handling
@error_handler(category=ErrorCategory.ANALYSIS, severity=ErrorSeverity.MEDIUM)
def analyze_productivity():
    # Function implementation
    pass

# Performance monitoring
@performance_monitor(track_memory=True, track_time=True)
def expensive_operation():
    # Function implementation
    pass
```

### Helper Functions

```python
from context_cleaner.utils import (
    sanitize_sensitive_data,
    format_duration,
    format_bytes,
    generate_session_id
)

# Sanitize data for logging
clean_data = sanitize_sensitive_data(user_data)

# Format durations
readable_time = format_duration(seconds=3661)  # "1h 1m 1s"

# Format byte sizes
readable_size = format_bytes(1024*1024*50)  # "50.0 MB"

# Generate unique session ID
session_id = generate_session_id()  # UUID-based ID
```

## Integration Examples

### Basic Productivity Tracking

```python
from context_cleaner import ContextCleanerConfig, SessionTracker, ProductivityAnalyzer

# Setup
config = ContextCleanerConfig.from_env()
tracker = SessionTracker(config)
analyzer = ProductivityAnalyzer(config)

# Start session
session_id = tracker.start_session()

# Track work activities
tracker.track_event("context_optimization", {
    "context_size": 2000,
    "optimization_type": "quick",
    "duration_ms": 150
})

# End session
tracker.end_session(session_id)

# Analyze productivity
report = analyzer.analyze_period(days=1)
print(f"Productivity Score: {report.avg_productivity_score}")
print(f"Recommendations: {report.recommendations}")
```

### Custom Analysis Pipeline

```python
from context_cleaner.analytics import (
    AdvancedPatterns, 
    AnomalyDetector, 
    CorrelationAnalyzer
)

# Advanced analytics pipeline
patterns = AdvancedPatterns()
anomaly_detector = AnomalyDetector()
correlations = CorrelationAnalyzer()

# Analyze patterns
session_patterns = patterns.detect_temporal_patterns(session_data)
behavioral_patterns = patterns.detect_behavioral_patterns(session_data)

# Detect anomalies
anomalies = anomaly_detector.detect_statistical_anomalies(metrics)

# Find correlations
correlations_result = correlations.analyze_correlations(features)
```

### Performance Monitoring Integration

```python
from context_cleaner.monitoring import PerformanceOptimizer

# Initialize performance monitoring
optimizer = PerformanceOptimizer()
optimizer.start_monitoring()

# Track specific operations
with optimizer.track_operation("context_analysis", context_tokens=1500):
    # Perform context analysis
    result = analyze_context(data)

# Get performance summary
summary = optimizer.get_performance_summary(hours=24)
print(f"Health Score: {summary['performance']['health_score']}")

# Stop monitoring
optimizer.stop_monitoring()
```

## Environment Variables

Context Cleaner can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CONTEXT_CLEANER_DATA_DIR` | Data directory path | `~/.context_cleaner` |
| `CONTEXT_CLEANER_DEBUG` | Enable debug logging | `False` |
| `CONTEXT_CLEANER_TRACKING_ENABLED` | Enable tracking | `True` |
| `CONTEXT_CLEANER_DASHBOARD_PORT` | Dashboard port | `8110` |
| `CONTEXT_CLEANER_RETENTION_DAYS` | Data retention period | `90` |

---

*For more examples and advanced usage, see the [Examples](../examples/) section.*