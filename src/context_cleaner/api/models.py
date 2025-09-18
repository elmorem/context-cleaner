"""
API Models and Response Formats

Defines standardized data models and response formats for the modern
Context Cleaner API, ensuring consistency across all endpoints.
"""

from typing import Generic, TypeVar, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass

T = TypeVar('T')

class APIResponse(BaseModel, Generic[T]):
    """Standardized API response format for all endpoints"""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None

class PaginatedResponse(APIResponse[List[T]]):
    """Paginated response format for list endpoints"""
    page: int = 1
    page_size: int = 20
    total_count: int = 0
    has_next: bool = False
    has_previous: bool = False

class EventType(Enum):
    """WebSocket event types for real-time updates"""
    # Dashboard events
    DASHBOARD_METRICS_UPDATED = "dashboard.metrics.updated"
    WIDGET_DATA_UPDATED = "widget.data.updated"
    WIDGET_STATUS_CHANGED = "widget.status.changed"

    # System events
    HEALTH_STATUS_CHANGED = "system.health.changed"
    ERROR_OCCURRED = "system.error.occurred"
    CONNECTION_STATUS_CHANGED = "system.connection.changed"

    # Session events
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    SESSION_METRICS_UPDATED = "session.metrics.updated"

    # Cost events
    COST_THRESHOLD_EXCEEDED = "cost.threshold.exceeded"
    COST_BURNRATE_ALERT = "cost.burnrate.alert"

class WebSocketMessage(BaseModel):
    """Base WebSocket message format"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    request_id: Optional[str] = None

# Domain Models
@dataclass
class DashboardMetrics:
    """Core dashboard metrics"""
    total_tokens: int
    total_sessions: int
    success_rate: float
    active_agents: int
    cost: Decimal
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_tokens': self.total_tokens,
            'total_sessions': self.total_sessions,
            'success_rate': self.success_rate,
            'active_agents': self.active_agents,
            'cost': float(self.cost),
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class WidgetData:
    """Standardized widget data structure"""
    widget_id: str
    widget_type: str
    title: str
    status: str  # "healthy", "warning", "critical"
    data: Dict[str, Any]
    last_updated: datetime
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'widget_id': self.widget_id,
            'widget_type': self.widget_type,
            'title': self.title,
            'status': self.status,
            'data': self.data,
            'last_updated': self.last_updated.isoformat(),
            'metadata': self.metadata
        }

@dataclass
class SystemHealth:
    """System health status"""
    overall_healthy: bool
    database_status: str
    connection_status: str
    response_time_ms: float
    uptime_seconds: float
    error_rate: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_healthy': self.overall_healthy,
            'database_status': self.database_status,
            'connection_status': self.connection_status,
            'response_time_ms': self.response_time_ms,
            'uptime_seconds': self.uptime_seconds,
            'error_rate': self.error_rate,
            'timestamp': self.timestamp.isoformat()
        }

# Request Models
class WidgetRequest(BaseModel):
    """Request model for widget data"""
    widget_type: str
    session_id: Optional[str] = None
    time_range_days: int = Field(default=7, ge=1, le=30)
    refresh: bool = False

class MetricsRequest(BaseModel):
    """Request model for metrics data"""
    time_range_days: int = Field(default=7, ge=1, le=90)
    include_breakdown: bool = False
    session_id: Optional[str] = None

class CacheInvalidationRequest(BaseModel):
    """Request model for cache invalidation"""
    pattern: str
    scope: str = Field(default="dashboard", regex="^(dashboard|widgets|telemetry|all)$")

# Event-specific models
class DashboardMetricsEvent(BaseModel):
    """Dashboard metrics update event data"""
    total_tokens: int
    total_sessions: int
    success_rate: float
    cost_change: float
    timestamp: datetime

class WidgetUpdateEvent(BaseModel):
    """Widget data update event data"""
    widget_type: str
    widget_id: str
    data: Dict[str, Any]
    status: str
    last_updated: datetime

class ErrorEvent(BaseModel):
    """Error event data"""
    error_type: str
    error_message: str
    severity: str
    component: str
    timestamp: datetime
    context: Dict[str, Any] = Field(default_factory=dict)

# Response Models for specific endpoints
class DashboardOverviewResponse(BaseModel):
    """Dashboard overview response data"""
    metrics: DashboardMetrics
    widgets: List[WidgetData]
    system_health: SystemHealth
    last_updated: datetime

class WidgetListResponse(BaseModel):
    """Widget list response data"""
    widgets: List[WidgetData]
    total_count: int
    healthy_count: int
    warning_count: int
    critical_count: int