"""Base telemetry client interface and common functionality."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import asyncio


@dataclass
class TelemetryEvent:
    """Represents a telemetry event from Claude Code."""
    timestamp: datetime
    event_type: str  # api_request, tool_decision, api_error, etc.
    session_id: str
    attributes: Dict[str, Any]
    

@dataclass
class SessionMetrics:
    """Session-level telemetry metrics."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    api_calls: int
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    error_count: int
    tools_used: List[str]


@dataclass 
class ErrorEvent:
    """Represents an API error event."""
    timestamp: datetime
    session_id: str
    error_type: str
    duration_ms: float
    model: str
    input_tokens: Optional[int]
    terminal_type: str
    
    
class TelemetryClient(ABC):
    """Abstract base class for telemetry data clients."""
    
    @abstractmethod
    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get comprehensive metrics for a specific session."""
        pass
    
    @abstractmethod
    async def get_recent_errors(self, hours: int = 24) -> List[ErrorEvent]:
        """Get recent error events within specified time window."""
        pass
    
    @abstractmethod
    async def get_cost_trends(self, days: int = 7) -> Dict[str, float]:
        """Get cost trends over specified number of days."""
        pass
    
    @abstractmethod
    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a raw query against the telemetry database."""
        pass
    
    @abstractmethod
    async def get_current_session_cost(self, session_id: str) -> float:
        """Get the current cost for an active session."""
        pass
    
    @abstractmethod
    async def get_model_usage_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get model usage statistics over specified period."""
        pass
    
    @abstractmethod
    async def get_total_aggregated_stats(self) -> Dict[str, Any]:
        """Get total aggregated statistics across all sessions."""
        pass