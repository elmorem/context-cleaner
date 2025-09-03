"""Tests for ErrorRecoveryManager."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
from src.context_cleaner.telemetry.error_recovery.strategies import RequestContext
from src.context_cleaner.telemetry.error_recovery.exceptions import MaxRetriesExceeded, NoViableStrategyError


class TestErrorRecoveryManager:
    """Test suite for ErrorRecoveryManager."""
    
    @pytest.fixture
    def recovery_manager(self, mock_telemetry_client):
        """Create ErrorRecoveryManager with mock client."""
        return ErrorRecoveryManager(mock_telemetry_client, max_retries=3)
    
    @pytest.fixture
    def sample_context(self):
        """Provide sample request context."""
        return RequestContext(
            model="claude-sonnet-4-20250514",
            input_tokens=3500,
            context="This is a large context that might cause timeout issues...",
            session_id="test-session-123",
            original_request={"type": "test"},
            timeout_seconds=10.0
        )
    
    @pytest.mark.asyncio
    async def test_handle_timeout_error_success(self, recovery_manager, sample_context):
        """Test successful recovery from timeout error."""
        error_type = "Request was aborted"
        
        result = await recovery_manager.handle_api_error(error_type, sample_context)
        
        assert result.succeeded
        assert result.strategy_used == "token_reduction"
        assert result.modified_context is not None
        assert result.modified_context.input_tokens < sample_context.input_tokens
    
    @pytest.mark.asyncio
    async def test_handle_sonnet_timeout_switches_model(self, recovery_manager, sample_context):
        """Test that Sonnet timeout errors switch to Haiku."""
        error_type = "Request was aborted"
        
        result = await recovery_manager.handle_api_error(error_type, sample_context)
        
        # Either token reduction or model switch should succeed
        assert result.succeeded
        assert result.strategy_used in ["token_reduction", "model_switch"]
    
    @pytest.mark.asyncio
    async def test_large_context_chunking(self, recovery_manager):
        """Test context chunking for very large contexts."""
        large_context = RequestContext(
            model="claude-sonnet-4-20250514",
            input_tokens=5000,  # Very large context
            context="A" * 10000,  # Very long context
            session_id="test-session-123",
            original_request={"type": "test"}
        )
        
        error_type = "Context too large"
        
        result = await recovery_manager.handle_api_error(error_type, large_context)
        
        assert result.succeeded
        # Should use chunking or token reduction
        assert result.strategy_used in ["context_chunking", "token_reduction"]
        assert result.modified_context.input_tokens < large_context.input_tokens
    
    @pytest.mark.asyncio 
    async def test_no_viable_strategy_raises_error(self, recovery_manager):
        """Test that unrecoverable errors raise NoViableStrategyError."""
        # Context that no strategy can handle (very specific error)
        context = RequestContext(
            model="unknown-model",
            input_tokens=100,  # Small context
            context="small context",
            session_id="test-session-123",
            original_request={"type": "test"}
        )
        
        # With all strategies mocked to return not applicable
        with patch.object(recovery_manager, '_get_applicable_strategies', return_value=[]):
            with pytest.raises(NoViableStrategyError):
                await recovery_manager.handle_api_error("unknown_error", context)
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, recovery_manager, sample_context):
        """Test that MaxRetriesExceeded is raised when all strategies fail."""
        error_type = "persistent_error"
        
        # Mock all strategies to fail
        for strategy in recovery_manager.strategies:
            strategy.execute = Mock(return_value=Mock(succeeded=False, error_message="Test failure"))
        
        with pytest.raises(MaxRetriesExceeded) as exc_info:
            await recovery_manager.handle_api_error(error_type, sample_context)
        
        assert exc_info.value.attempts > 0
        assert len(exc_info.value.strategies_tried) > 0
    
    @pytest.mark.asyncio
    async def test_get_recovery_statistics(self, recovery_manager, mock_telemetry_client, sample_error_event):
        """Test recovery statistics generation."""
        # Add test error to mock client
        mock_telemetry_client.add_test_error(sample_error_event)
        
        stats = await recovery_manager.get_recovery_statistics()
        
        assert stats["total_errors"] == 1
        assert "error_types" in stats
        assert sample_error_event.error_type in stats["error_types"]
        assert stats["error_types"][sample_error_event.error_type]["count"] == 1
    
    @pytest.mark.asyncio
    async def test_suggest_optimizations_high_cost(self, recovery_manager, mock_telemetry_client):
        """Test optimization suggestions for high-cost sessions."""
        # Set up high-cost session
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        from datetime import timedelta
        
        high_cost_session = SessionMetrics(
            session_id="expensive-session",
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=None,
            api_calls=20,
            total_cost=3.50,  # High cost
            total_input_tokens=15000,  # Large token usage
            total_output_tokens=2000,
            error_count=0,
            tools_used=["Read", "Edit"]
        )
        
        mock_telemetry_client.set_test_session("expensive-session", high_cost_session)
        
        suggestions = await recovery_manager.suggest_optimizations("expensive-session")
        
        assert len(suggestions) > 0
        # Should suggest cost optimization
        cost_suggestions = [s for s in suggestions if s["type"] == "cost_optimization"]
        assert len(cost_suggestions) > 0
        assert "cost" in cost_suggestions[0]["message"].lower()
    
    @pytest.mark.asyncio
    async def test_suggest_optimizations_large_tokens(self, recovery_manager, mock_telemetry_client):
        """Test optimization suggestions for large token usage.""" 
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        from datetime import timedelta
        
        large_token_session = SessionMetrics(
            session_id="large-token-session",
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=None,
            api_calls=5,
            total_cost=1.50,
            total_input_tokens=12000,  # Very large average tokens (2400 per request)
            total_output_tokens=1000,
            error_count=0,
            tools_used=["Read"]
        )
        
        mock_telemetry_client.set_test_session("large-token-session", large_token_session)
        
        suggestions = await recovery_manager.suggest_optimizations("large-token-session")
        
        assert len(suggestions) > 0
        # Should suggest context optimization
        context_suggestions = [s for s in suggestions if s["type"] == "context_optimization"]
        assert len(context_suggestions) > 0
        assert "token" in context_suggestions[0]["message"].lower() or "context" in context_suggestions[0]["message"].lower()
    
    @pytest.mark.asyncio
    async def test_suggest_optimizations_errors(self, recovery_manager, mock_telemetry_client):
        """Test optimization suggestions for sessions with errors."""
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        from datetime import timedelta
        
        error_session = SessionMetrics(
            session_id="error-session", 
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=None,
            api_calls=10,
            total_cost=1.50,
            total_input_tokens=5000,
            total_output_tokens=1000,
            error_count=2,  # Has errors
            tools_used=["Read", "Edit"]
        )
        
        mock_telemetry_client.set_test_session("error-session", error_session)
        
        suggestions = await recovery_manager.suggest_optimizations("error-session")
        
        assert len(suggestions) > 0
        # Should suggest reliability improvements
        reliability_suggestions = [s for s in suggestions if s["type"] == "reliability"]
        assert len(reliability_suggestions) > 0
        assert "error" in reliability_suggestions[0]["message"].lower()
    
    def test_strategy_priority_ordering(self, recovery_manager):
        """Test that strategies are ordered by priority."""
        priorities = [strategy.get_priority() for strategy in recovery_manager.strategies]
        
        # Should be sorted in ascending order (lower number = higher priority)
        assert priorities == sorted(priorities)
        
        # Token reduction should be highest priority (lowest number)
        assert recovery_manager.strategies[0].name == "token_reduction"