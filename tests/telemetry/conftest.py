"""Test configuration and fixtures for telemetry tests."""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any

from src.context_cleaner.telemetry.clients.base import TelemetryClient, SessionMetrics, ErrorEvent


class MockTelemetryClient(TelemetryClient):
    """Mock telemetry client for testing."""
    
    def __init__(self):
        self.sessions = {}
        self.errors = []
        self.cost_trends = {}
        self.model_stats = {}
    
    async def get_session_metrics(self, session_id: str) -> SessionMetrics:
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Return default test session
        return SessionMetrics(
            session_id=session_id,
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=None,
            api_calls=10,
            total_cost=1.50,
            total_input_tokens=5000,
            total_output_tokens=1000,
            error_count=1,
            tools_used=["Read", "Edit", "TodoWrite"]
        )
    
    async def get_recent_errors(self, hours: int = 24) -> List[ErrorEvent]:
        return self.errors
    
    async def get_cost_trends(self, days: int = 7) -> Dict[str, float]:
        return self.cost_trends
    
    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        return []
    
    async def get_current_session_cost(self, session_id: str) -> float:
        if session_id in self.sessions:
            return self.sessions[session_id].total_cost
        return 1.50
    
    async def get_model_usage_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        return self.model_stats

    async def get_total_aggregated_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Provide aggregate telemetry stats required by modern manager."""
        return {
            "hours": hours,
            "total_sessions": len(self.sessions),
            "total_errors": len(self.errors),
            "total_cost": sum(
                metrics.total_cost for metrics in self.sessions.values()
            ) if self.sessions else 0.0,
        }
    
    def add_test_error(self, error: ErrorEvent):
        """Add test error for testing."""
        self.errors.append(error)
    
    def set_test_session(self, session_id: str, metrics: SessionMetrics):
        """Set test session data."""
        self.sessions[session_id] = metrics
    
    def set_cost_trends(self, trends: Dict[str, float]):
        """Set test cost trends."""
        self.cost_trends = trends
    
    def set_model_stats(self, stats: Dict[str, Dict[str, Any]]):
        """Set test model stats."""
        self.model_stats = stats


@pytest.fixture
def mock_telemetry_client():
    """Provide mock telemetry client for tests."""
    return MockTelemetryClient()


@pytest.fixture
def sample_error_event():
    """Provide sample error event for testing."""
    return ErrorEvent(
        timestamp=datetime.now(),
        session_id="test-session-123",
        error_type="Request was aborted",
        duration_ms=7200,
        model="claude-sonnet-4-20250514",
        input_tokens=3500,
        terminal_type="vscode"
    )


@pytest.fixture
def sample_session_metrics():
    """Provide sample session metrics for testing."""
    return SessionMetrics(
        session_id="test-session-123",
        start_time=datetime.now() - timedelta(minutes=45),
        end_time=datetime.now() - timedelta(minutes=5),
        api_calls=15,
        total_cost=2.25,
        total_input_tokens=8000,
        total_output_tokens=1500,
        error_count=2,
        tools_used=["Read", "Bash", "Edit", "TodoWrite", "Grep"]
    )
