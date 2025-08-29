"""
Session Tracking Models

Defines data models for productivity tracking and session analytics.
All models support both in-memory and SQLite storage.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


class SessionStatus(Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class EventType(Enum):
    """Context event types."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    CONTEXT_CHANGE = "context_change"
    OPTIMIZATION_EVENT = "optimization_event"
    TOOL_USE = "tool_use"
    ERROR_EVENT = "error_event"


@dataclass
class MetricsModel:
    """Performance and productivity metrics."""
    
    # Performance metrics
    hook_execution_time_ms: float = 0.0
    context_health_score: Optional[int] = None
    context_size_tokens: Optional[int] = None
    
    # Productivity metrics  
    tools_used: int = 0
    optimizations_applied: int = 0
    errors_encountered: int = 0
    
    # Quality metrics
    completion_rate: float = 0.0
    efficiency_score: Optional[float] = None
    
    # Timestamps
    recorded_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'hook_execution_time_ms': self.hook_execution_time_ms,
            'context_health_score': self.context_health_score,
            'context_size_tokens': self.context_size_tokens,
            'tools_used': self.tools_used,
            'optimizations_applied': self.optimizations_applied,
            'errors_encountered': self.errors_encountered,
            'completion_rate': self.completion_rate,
            'efficiency_score': self.efficiency_score,
            'recorded_at': self.recorded_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetricsModel':
        """Create from dictionary."""
        return cls(
            hook_execution_time_ms=data.get('hook_execution_time_ms', 0.0),
            context_health_score=data.get('context_health_score'),
            context_size_tokens=data.get('context_size_tokens'),
            tools_used=data.get('tools_used', 0),
            optimizations_applied=data.get('optimizations_applied', 0),
            errors_encountered=data.get('errors_encountered', 0),
            completion_rate=data.get('completion_rate', 0.0),
            efficiency_score=data.get('efficiency_score'),
            recorded_at=datetime.fromisoformat(data.get('recorded_at', datetime.now().isoformat()))
        )


@dataclass  
class ContextEventModel:
    """Individual context change or optimization event."""
    
    event_id: str
    session_id: str
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Event details
    context_size: Optional[int] = None
    optimization_type: Optional[str] = None
    tool_name: Optional[str] = None
    duration_ms: Optional[float] = None
    
    # Metadata (sanitized)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Performance impact
    before_health_score: Optional[int] = None
    after_health_score: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'event_id': self.event_id,
            'session_id': self.session_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'context_size': self.context_size,
            'optimization_type': self.optimization_type,
            'tool_name': self.tool_name,
            'duration_ms': self.duration_ms,
            'metadata': self.metadata,
            'before_health_score': self.before_health_score,
            'after_health_score': self.after_health_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextEventModel':
        """Create from dictionary."""
        return cls(
            event_id=data['event_id'],
            session_id=data['session_id'],
            event_type=EventType(data['event_type']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            context_size=data.get('context_size'),
            optimization_type=data.get('optimization_type'),
            tool_name=data.get('tool_name'),
            duration_ms=data.get('duration_ms'),
            metadata=data.get('metadata', {}),
            before_health_score=data.get('before_health_score'),
            after_health_score=data.get('after_health_score')
        )


@dataclass
class SessionModel:
    """Development session tracking model."""
    
    # Core session info
    session_id: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE
    
    # Session context
    project_path: Optional[str] = None
    model_name: Optional[str] = None
    claude_version: Optional[str] = None
    
    # Performance data
    duration_seconds: float = 0.0
    context_events: List[ContextEventModel] = field(default_factory=list)
    metrics: Optional[MetricsModel] = None
    
    # Privacy and metadata
    privacy_level: str = "local_only"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_context_event(self, event: ContextEventModel):
        """Add a context event to the session."""
        self.context_events.append(event)
        self.updated_at = datetime.now()
    
    def complete_session(self, end_time: Optional[datetime] = None):
        """Mark session as completed."""
        self.end_time = end_time or datetime.now()
        self.status = SessionStatus.COMPLETED
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.updated_at = datetime.now()
    
    def calculate_productivity_score(self) -> float:
        """
        Calculate productivity score based on session metrics.
        
        Returns:
            Productivity score from 0.0 to 100.0
        """
        if not self.metrics:
            return 0.0
        
        # Base score from completion and efficiency
        base_score = (self.metrics.completion_rate * 0.4 + 
                     (self.metrics.efficiency_score or 0.5) * 0.3) * 100
        
        # Bonus for optimization usage
        optimization_bonus = min(self.metrics.optimizations_applied * 5, 20)
        
        # Penalty for errors
        error_penalty = min(self.metrics.errors_encountered * 10, 30)
        
        # Context health bonus
        health_bonus = 0
        if self.metrics.context_health_score:
            health_bonus = max(0, (self.metrics.context_health_score - 50) * 0.2)
        
        final_score = max(0, min(100, base_score + optimization_bonus + health_bonus - error_penalty))
        return round(final_score, 1)
    
    def get_context_health_trend(self) -> List[Dict[str, Any]]:
        """Get context health score trend throughout the session."""
        health_events = [
            {
                'timestamp': event.timestamp.isoformat(),
                'before_score': event.before_health_score,
                'after_score': event.after_health_score,
                'event_type': event.event_type.value
            }
            for event in self.context_events 
            if event.before_health_score is not None or event.after_health_score is not None
        ]
        
        return sorted(health_events, key=lambda x: x['timestamp'])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status.value,
            'project_path': self.project_path,
            'model_name': self.model_name,
            'claude_version': self.claude_version,
            'duration_seconds': self.duration_seconds,
            'context_events': [event.to_dict() for event in self.context_events],
            'metrics': self.metrics.to_dict() if self.metrics else None,
            'privacy_level': self.privacy_level,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'productivity_score': self.calculate_productivity_score()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionModel':
        """Create from dictionary."""
        session = cls(
            session_id=data['session_id'],
            start_time=datetime.fromisoformat(data['start_time']),
            end_time=datetime.fromisoformat(data['end_time']) if data.get('end_time') else None,
            status=SessionStatus(data.get('status', 'active')),
            project_path=data.get('project_path'),
            model_name=data.get('model_name'),
            claude_version=data.get('claude_version'),
            duration_seconds=data.get('duration_seconds', 0.0),
            privacy_level=data.get('privacy_level', 'local_only'),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))
        )
        
        # Load context events
        for event_data in data.get('context_events', []):
            event = ContextEventModel.from_dict(event_data)
            session.context_events.append(event)
        
        # Load metrics
        if data.get('metrics'):
            session.metrics = MetricsModel.from_dict(data['metrics'])
        
        return session
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SessionModel':
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)