"""
Unit Tests for EnhancedTokenCounterService

Tests validating the 90% undercount fix and comprehensive token analysis functionality.
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime, timedelta

from src.context_cleaner.analysis.enhanced_token_counter import (
    EnhancedTokenCounterService,
    AnthropicTokenCounter,
    SessionTokenMetrics,
    EnhancedTokenAnalysis,
    SessionTokenTracker
)
from .fixtures import (
    UndercountTestCases, 
    JSONLFixtures, 
    MockFileSystem,
    MockAnthropicAPI
)


class TestSessionTokenMetrics:
    """Test SessionTokenMetrics data class functionality."""
    
    def test_session_metrics_initialization(self):
        """Test basic session metrics initialization."""
        metrics = SessionTokenMetrics(session_id="test_session")
        
        assert metrics.session_id == "test_session"
        assert metrics.total_reported_tokens == 0
        assert metrics.accuracy_ratio == 0.0
        assert metrics.undercount_percentage == 0.0
    
    def test_total_reported_tokens_calculation(self):
        """Test total reported tokens calculation."""
        metrics = SessionTokenMetrics(
            session_id="test",
            reported_input_tokens=100,
            reported_output_tokens=50,
            reported_cache_creation_tokens=25,
            reported_cache_read_tokens=15
        )
        
        assert metrics.total_reported_tokens == 190
    
    def test_accuracy_ratio_calculation(self):
        """Test accuracy ratio calculation for undercount detection."""
        metrics = SessionTokenMetrics(
            session_id="test",
            reported_input_tokens=100,
            reported_output_tokens=50,
            calculated_total_tokens=1500  # 10x undercount
        )
        
        assert metrics.accuracy_ratio == 10.0  # 1500 / 150
    
    def test_undercount_percentage_calculation(self):
        """Test undercount percentage calculation."""
        # 90% undercount scenario
        metrics = SessionTokenMetrics(
            session_id="test",
            reported_input_tokens=50,
            reported_output_tokens=50,
            calculated_total_tokens=1000
        )
        
        # Expected: (1000 - 100) / 1000 * 100 = 90%
        assert metrics.undercount_percentage == 90.0
    
    def test_zero_division_handling(self):
        """Test handling of zero values in calculations."""
        metrics = SessionTokenMetrics(session_id="test")
        
        assert metrics.accuracy_ratio == 0.0
        assert metrics.undercount_percentage == 0.0


class TestAnthropicTokenCounter:
    """Test AnthropicTokenCounter API client."""
    
    @pytest.fixture
    def token_counter(self):
        """Create AnthropicTokenCounter instance."""
        return AnthropicTokenCounter(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_successful_token_counting(self, token_counter):
        """Test successful token counting via API."""
        messages = [
            {"role": "user", "content": "Test message"},
            {"role": "assistant", "content": "Test response"}
        ]
        
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"input_tokens": 150})
        
        # Mock aiohttp session
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_client_session.return_value = mock_session
            token_counter.session = mock_session
            
            result = await token_counter.count_tokens_for_messages(messages)
            
            assert result == 150
            mock_session.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, token_counter):
        """Test API error handling returns zero tokens."""
        messages = [{"role": "user", "content": "Test"}]
        
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.text = AsyncMock(return_value="Rate limit exceeded")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_client_session.return_value = mock_session
            token_counter.session = mock_session
            
            result = await token_counter.count_tokens_for_messages(messages)
            
            assert result == 0  # Should return 0 on error
    
    @pytest.mark.asyncio
    async def test_request_format(self, token_counter):
        """Test that API requests are formatted correctly."""
        messages = [{"role": "user", "content": "Test message"}]
        system_prompt = "You are a helpful assistant"
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"input_tokens": 100})
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_client_session.return_value = mock_session
            token_counter.session = mock_session
            
            await token_counter.count_tokens_for_messages(messages, system_prompt)
            
            # Verify the request payload
            call_args = mock_session.post.call_args
            payload = call_args[1]['json']
            
            assert payload['model'] == "claude-3-sonnet-20240229"
            assert payload['messages'] == messages
            assert payload['system'] == system_prompt


class TestEnhancedTokenCounterService:
    """Test core EnhancedTokenCounterService functionality."""
    
    @pytest.fixture
    def service(self):
        """Create service instance."""
        return EnhancedTokenCounterService(anthropic_api_key="test_key")
    
    @pytest.fixture
    def mock_cache_dir(self, tmp_path):
        """Create mock cache directory with JSONL files."""
        cache_dir = tmp_path / ".claude" / "projects"
        cache_dir.mkdir(parents=True)
        return cache_dir
    
    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.anthropic_api_key == "test_key"
        assert service.cache_dir == Path.home() / ".claude" / "projects"
        assert "claude_md" in service.categorization_patterns
    
    def test_content_categorization(self, service):
        """Test content categorization logic."""
        # Test Claude MD content
        claude_md_content = "You are Claude Code, Anthropic's CLI tool"
        assert service._categorize_content(claude_md_content) == "claude_md"
        
        # Test system prompt content
        system_content = "<system-reminder>You are a helpful assistant</system-reminder>"
        assert service._categorize_content(system_content) == "system_prompts"
        
        # Test MCP tool content
        mcp_content = "Using mcp__ browser tools to analyze"
        assert service._categorize_content(mcp_content) == "mcp_tools"
        
        # Test regular user message
        user_content = "Please help me with this task"
        assert service._categorize_content(user_content) == "user_messages"
    
    def test_session_id_extraction(self, service):
        """Test session ID extraction from JSONL entries."""
        # Test direct session_id field
        entry1 = {"session_id": "session_123"}
        assert service._extract_session_id(entry1) == "session_123"
        
        # Test sessionId field (camelCase)
        entry2 = {"sessionId": "session_456"}
        assert service._extract_session_id(entry2) == "session_456"
        
        # Test fallback
        entry3 = {"other_field": "value"}
        assert service._extract_session_id(entry3) == "unknown_session"
    
    @pytest.mark.asyncio
    async def test_file_discovery_vs_current_limitation(self, service, mock_cache_dir):
        """Test that enhanced system finds ALL files vs current 10 file limit."""
        # Create 15 JSONL files (current system only processes 10 most recent)
        files = []
        for i in range(15):
            file_path = mock_cache_dir / f"session_{i:03d}.jsonl"
            
            # Create minimal JSONL content
            with open(file_path, 'w') as f:
                entry = JSONLFixtures.create_realistic_conversation_entry(
                    session_id=f"session_{i:03d}",
                    content=f"Test content for session {i}"
                )
                f.write(json.dumps(entry) + "\n")
            
            files.append(file_path)
        
        # Mock the cache directory
        with patch.object(service, 'cache_dir', mock_cache_dir):
            # Test without file limit (enhanced system)
            analysis = await service.analyze_comprehensive_token_usage(
                max_files=None,
                use_count_tokens_api=False
            )
            
            assert analysis.total_files_processed == 15  # All files processed
            
            # Test with current system limitation
            analysis_limited = await service.analyze_comprehensive_token_usage(
                max_files=10,
                use_count_tokens_api=False
            )
            
            assert analysis_limited.total_files_processed == 10  # Only 10 files
    
    @pytest.mark.asyncio
    async def test_complete_file_processing_vs_line_limit(self, service, mock_cache_dir):
        """Test processing complete files vs current 1000 line limit."""
        # Create file with 2000 lines
        large_file = mock_cache_dir / "large_session.jsonl"
        
        with open(large_file, 'w') as f:
            for i in range(2000):
                entry = JSONLFixtures.create_realistic_conversation_entry(
                    session_id="large_session",
                    content=f"Line {i + 1} content"
                )
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', mock_cache_dir):
            # Test without line limit (enhanced system)
            analysis = await service.analyze_comprehensive_token_usage(
                max_lines_per_file=None,
                use_count_tokens_api=False
            )
            
            assert analysis.total_lines_processed == 2000  # All lines processed
            
            # Test with current system limitation
            analysis_limited = await service.analyze_comprehensive_token_usage(
                max_lines_per_file=1000,
                use_count_tokens_api=False
            )
            
            assert analysis_limited.total_lines_processed == 1000  # Only 1000 lines
    
    @pytest.mark.asyncio
    async def test_all_message_types_processing(self, service, mock_cache_dir):
        """Test processing all message types vs current assistant-only limitation."""
        # Create file with various message types
        test_file = mock_cache_dir / "mixed_types.jsonl"
        
        entries = [
            # User message - MISSED by current system
            JSONLFixtures.create_realistic_conversation_entry(
                message_type="user",
                content="User request with lots of content that should be counted",
                session_id="mixed_session"
            ),
            # System message - MISSED by current system  
            JSONLFixtures.create_realistic_conversation_entry(
                message_type="system",
                content="System prompt with extensive instructions",
                session_id="mixed_session"
            ),
            # Assistant message - COUNTED by current system
            JSONLFixtures.create_realistic_conversation_entry(
                message_type="assistant",
                content="Assistant response",
                usage={"input_tokens": 50, "output_tokens": 25, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
                session_id="mixed_session"
            )
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', mock_cache_dir):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            session = analysis.sessions["mixed_session"]
            
            # Verify all message types are captured
            assert len(session.user_messages) == 1
            assert len(session.assistant_messages) == 1
            assert session.reported_input_tokens == 50  # From assistant usage stats
            assert session.calculated_total_tokens > session.total_reported_tokens  # Enhanced counting
    
    @pytest.mark.asyncio 
    async def test_undercount_detection(self, service, mock_cache_dir):
        """Test that the system detects significant undercounts."""
        # Create conversation that demonstrates 90% undercount
        test_file = mock_cache_dir / "undercount_demo.jsonl"
        undercount_data = JSONLFixtures.create_undercount_conversation("undercount_session")
        
        with open(test_file, 'w') as f:
            for entry in undercount_data:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', mock_cache_dir):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            # Should detect significant undercount
            assert analysis.global_undercount_percentage > 50.0  # Significant undercount detected
            assert analysis.global_accuracy_ratio > 2.0  # Much more content than reported
    
    @pytest.mark.asyncio
    async def test_api_integration(self, service, mock_cache_dir):
        """Test integration with count-tokens API."""
        test_file = mock_cache_dir / "api_test.jsonl"
        
        # Create conversation with multiple exchanges
        entries = []
        for i in range(10):  # Enough to trigger API validation
            entries.extend([
                JSONLFixtures.create_realistic_conversation_entry(
                    message_type="user",
                    content=f"User message {i}",
                    session_id="api_session"
                ),
                JSONLFixtures.create_realistic_conversation_entry(
                    message_type="assistant", 
                    content=f"Assistant response {i}",
                    usage={"input_tokens": 20, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
                    session_id="api_session"
                )
            ])
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        # Mock the API to return higher token counts
        with patch.object(service, 'cache_dir', mock_cache_dir):
            with patch('src.context_cleaner.analysis.enhanced_token_counter.AnthropicTokenCounter') as mock_counter:
                mock_instance = AsyncMock()
                mock_instance.count_tokens_for_messages = AsyncMock(return_value=500)
                mock_counter.return_value = mock_instance
                
                analysis = await service.analyze_comprehensive_token_usage(
                    use_count_tokens_api=True
                )
                
                assert analysis.api_calls_made > 0  # API was called
                session = analysis.sessions["api_session"]
                assert session.calculated_total_tokens >= 500  # API validation used
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service, mock_cache_dir):
        """Test handling of various error conditions."""
        # Test non-existent cache directory
        service.cache_dir = Path("/non/existent/directory")
        
        analysis = await service.analyze_comprehensive_token_usage()
        
        assert analysis.total_files_processed == 0
        assert analysis.total_sessions_analyzed == 0
        assert len(analysis.errors_encountered) > 0
    
    @pytest.mark.asyncio
    async def test_fallback_processing(self, service, mock_cache_dir):
        """Test fallback processing when API is not available."""
        test_file = mock_cache_dir / "fallback_test.jsonl"
        
        entries = [
            JSONLFixtures.create_realistic_conversation_entry(
                message_type="user",
                content="Test content for fallback processing",
                session_id="fallback_session"
            )
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', mock_cache_dir):
            # Test without API key (should use fallback)
            service.anthropic_api_key = None
            
            analysis = await service.analyze_comprehensive_token_usage()
            
            assert analysis.api_calls_made == 0  # No API calls made
            assert analysis.total_sessions_analyzed > 0  # But still processed data
            assert analysis.sessions["fallback_session"].calculated_total_tokens > 0  # Estimated tokens


class TestSessionTokenTracker:
    """Test SessionTokenTracker for real-time analytics."""
    
    @pytest.fixture
    def tracker(self):
        """Create SessionTokenTracker instance."""
        return SessionTokenTracker()
    
    @pytest.mark.asyncio
    async def test_session_token_updates(self, tracker):
        """Test updating session token counts."""
        await tracker.update_session_tokens(
            session_id="test_session",
            input_tokens=100,
            output_tokens=50
        )
        
        metrics = await tracker.get_session_metrics("test_session")
        
        assert metrics.session_id == "test_session"
        assert metrics.reported_input_tokens == 100
        assert metrics.reported_output_tokens == 50
        assert metrics.start_time is not None
        assert metrics.end_time is not None
    
    @pytest.mark.asyncio
    async def test_multiple_session_tracking(self, tracker):
        """Test tracking multiple sessions simultaneously."""
        sessions = ["session_1", "session_2", "session_3"]
        
        for i, session_id in enumerate(sessions):
            await tracker.update_session_tokens(
                session_id=session_id,
                input_tokens=(i + 1) * 100,
                output_tokens=(i + 1) * 50
            )
        
        all_metrics = await tracker.get_all_session_metrics()
        
        assert len(all_metrics) == 3
        for i, session_id in enumerate(sessions):
            assert all_metrics[session_id].reported_input_tokens == (i + 1) * 100
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, tracker):
        """Test cleanup of old session data."""
        # Create old session
        old_session = "old_session"
        await tracker.update_session_tokens(session_id=old_session, input_tokens=100)
        
        # Manually set old timestamp
        metrics = await tracker.get_session_metrics(old_session)
        old_time = datetime.now() - timedelta(hours=25)  # Older than cleanup threshold
        metrics.start_time = old_time
        metrics.end_time = old_time
        
        # Create recent session
        recent_session = "recent_session"
        await tracker.update_session_tokens(session_id=recent_session, input_tokens=200)
        
        # Run cleanup
        await tracker.cleanup_old_sessions(hours=24)
        
        all_metrics = await tracker.get_all_session_metrics()
        
        # Old session should be removed, recent should remain
        assert old_session not in all_metrics
        assert recent_session in all_metrics
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, tracker):
        """Test thread-safe concurrent access to session data."""
        session_id = "concurrent_session"
        
        # Simulate concurrent updates
        async def update_session(tokens):
            await tracker.update_session_tokens(
                session_id=session_id,
                input_tokens=tokens
            )
        
        # Run concurrent updates
        tasks = [update_session(i * 10) for i in range(10)]
        await asyncio.gather(*tasks)
        
        metrics = await tracker.get_session_metrics(session_id)
        
        # Should have accumulated all tokens
        assert metrics.reported_input_tokens == sum(i * 10 for i in range(10))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])