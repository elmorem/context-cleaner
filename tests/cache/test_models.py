#!/usr/bin/env python3
"""
Tests for Cache Data Models

Comprehensive tests for cache analysis data structures including
token metrics, session messages, and analysis results.
"""

import pytest
from datetime import datetime, timedelta

from src.context_cleaner.analysis.models import (
    TokenMetrics, ToolUsage, SessionMessage, SessionAnalysis,
    FileAccessPattern, CacheAnalysisResult, CacheConfig,
    MessageRole, MessageType
)


class TestTokenMetrics:
    """Test suite for TokenMetrics dataclass."""
    
    def test_token_metrics_creation(self):
        """Test creating TokenMetrics with various configurations."""
        metrics = TokenMetrics(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=150
        )
        
        assert metrics.input_tokens == 100
        assert metrics.output_tokens == 50
        assert metrics.total_tokens == 150  # Auto-calculated
        assert metrics.cache_creation_input_tokens == 200
        assert metrics.cache_read_input_tokens == 150
    
    def test_cache_hit_ratio_calculation(self):
        """Test cache hit ratio calculation."""
        # Normal case
        metrics = TokenMetrics(
            cache_creation_input_tokens=200,
            cache_read_input_tokens=300
        )
        assert metrics.cache_hit_ratio == 0.6  # 300/(200+300)
        
        # No cache usage
        metrics_no_cache = TokenMetrics()
        assert metrics_no_cache.cache_hit_ratio == 0.0
        
        # Only cache reads
        metrics_reads_only = TokenMetrics(cache_read_input_tokens=100)
        assert metrics_reads_only.cache_hit_ratio == 1.0
    
    def test_cache_efficiency_calculation(self):
        """Test cache efficiency calculation."""
        # Normal case
        metrics = TokenMetrics(
            cache_creation_input_tokens=100,
            cache_read_input_tokens=200
        )
        assert metrics.cache_efficiency == 2.0  # 200/100
        
        # No cache creation (perfect efficiency)
        metrics_no_creation = TokenMetrics(cache_read_input_tokens=100)
        assert metrics_no_creation.cache_efficiency == 1.0
        
        # No cache usage at all
        metrics_no_cache = TokenMetrics()
        assert metrics_no_cache.cache_efficiency == 0.0


class TestToolUsage:
    """Test suite for ToolUsage dataclass."""
    
    def test_tool_usage_creation(self):
        """Test creating ToolUsage instances."""
        now = datetime.now()
        tool = ToolUsage(
            tool_name="Read",
            tool_id="tool-123",
            parameters={"file_path": "/test/file.py"},
            timestamp=now
        )
        
        assert tool.tool_name == "Read"
        assert tool.tool_id == "tool-123"
        assert tool.parameters["file_path"] == "/test/file.py"
        assert tool.timestamp == now
        assert tool.success is True  # Default
    
    def test_is_file_operation_detection(self):
        """Test file operation detection."""
        file_tools = ['Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep']
        
        for tool_name in file_tools:
            tool = ToolUsage(tool_name, "id", {}, datetime.now())
            assert tool.is_file_operation is True
        
        # Non-file tools
        non_file_tool = ToolUsage("Bash", "id", {}, datetime.now())
        assert non_file_tool.is_file_operation is False
    
    def test_is_bash_operation_detection(self):
        """Test bash operation detection."""
        bash_tool = ToolUsage("Bash", "id", {}, datetime.now())
        assert bash_tool.is_bash_operation is True
        
        read_tool = ToolUsage("Read", "id", {}, datetime.now())
        assert read_tool.is_bash_operation is False
    
    def test_file_path_extraction(self):
        """Test file path extraction from parameters."""
        test_cases = [
            ({"file_path": "/test/file.py"}, "/test/file.py"),
            ({"path": "/another/file.js"}, "/another/file.js"),
            ({"pattern": "*.py"}, "*.py"),
            ({"command": "ls"}, None),  # No file path
            ({}, None)  # Empty parameters
        ]
        
        for params, expected_path in test_cases:
            tool = ToolUsage("Read", "id", params, datetime.now())
            assert tool.file_path == expected_path


class TestSessionMessage:
    """Test suite for SessionMessage dataclass."""
    
    def test_session_message_creation(self):
        """Test creating SessionMessage instances."""
        now = datetime.now()
        message = SessionMessage(
            uuid="msg-123",
            parent_uuid="parent-456",
            message_type=MessageType.USER,
            role=MessageRole.USER,
            content="Help me debug this function",
            timestamp=now
        )
        
        assert message.uuid == "msg-123"
        assert message.parent_uuid == "parent-456"
        assert message.role == MessageRole.USER
        assert message.content == "Help me debug this function"
        assert message.timestamp == now
    
    def test_content_text_extraction_string(self):
        """Test text extraction from string content."""
        message = SessionMessage(
            uuid="1", parent_uuid=None, message_type=MessageType.USER,
            role=MessageRole.USER, content="Simple text content",
            timestamp=datetime.now()
        )
        assert message.content_text == "Simple text content"
    
    def test_content_text_extraction_list(self):
        """Test text extraction from list content."""
        content_list = [
            {"type": "text", "text": "I'll help you debug that."},
            {"type": "tool_use", "name": "Read", "id": "tool1"},
            {"type": "tool_result", "content": "File content here"},
            {"type": "unknown", "data": "ignored"}
        ]
        
        message = SessionMessage(
            uuid="1", parent_uuid=None, message_type=MessageType.ASSISTANT,
            role=MessageRole.ASSISTANT, content=content_list,
            timestamp=datetime.now()
        )
        
        content_text = message.content_text
        assert "I'll help you debug that." in content_text
        assert "Tool: Read" in content_text
        assert "Result: File content here" in content_text
    
    def test_estimated_tokens_with_metrics(self):
        """Test token estimation when metrics are available."""
        metrics = TokenMetrics(input_tokens=100, output_tokens=50)
        message = SessionMessage(
            uuid="1", parent_uuid=None, message_type=MessageType.ASSISTANT,
            role=MessageRole.ASSISTANT, content="Test", timestamp=datetime.now(),
            token_metrics=metrics
        )
        
        assert message.estimated_tokens == 150  # From metrics
    
    def test_estimated_tokens_without_metrics(self):
        """Test token estimation without metrics (character-based)."""
        long_content = "x" * 400  # 400 characters
        message = SessionMessage(
            uuid="1", parent_uuid=None, message_type=MessageType.USER,
            role=MessageRole.USER, content=long_content,
            timestamp=datetime.now()
        )
        
        # Should estimate ~100 tokens (400 chars / 4)
        assert message.estimated_tokens == 100
    
    def test_context_switch_detection(self):
        """Test context switch detection."""
        switch_phrases = [
            "Let me switch to a different topic",
            "Now let's move on to the next issue",
            "Okay, now I need help with authentication",
            "Let me change direction here"
        ]
        
        for content in switch_phrases:
            message = SessionMessage(
                uuid="1", parent_uuid=None, message_type=MessageType.USER,
                role=MessageRole.USER, content=content, timestamp=datetime.now()
            )
            assert message.is_context_switch is True
        
        # Regular message should not be detected as context switch
        normal_message = SessionMessage(
            uuid="1", parent_uuid=None, message_type=MessageType.USER,
            role=MessageRole.USER, content="Can you help me with this bug?",
            timestamp=datetime.now()
        )
        assert normal_message.is_context_switch is False


class TestSessionAnalysis:
    """Test suite for SessionAnalysis dataclass."""
    
    def test_session_analysis_creation(self):
        """Test creating SessionAnalysis instances."""
        now = datetime.now()
        start_time = now - timedelta(hours=2)
        
        analysis = SessionAnalysis(
            session_id="session-123",
            start_time=start_time,
            end_time=now,
            total_messages=50,
            total_tokens=5000,
            file_operations=[],
            context_switches=3,
            average_response_time=1.5,
            cache_efficiency=0.75
        )
        
        assert analysis.session_id == "session-123"
        assert analysis.total_messages == 50
        assert analysis.total_tokens == 5000
        assert analysis.context_switches == 3
    
    def test_duration_calculation(self):
        """Test session duration calculation."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 12, 30, 0)  # 2.5 hours later
        
        analysis = SessionAnalysis(
            session_id="test",
            start_time=start,
            end_time=end,
            total_messages=10,
            total_tokens=1000,
            file_operations=[],
            context_switches=0,
            average_response_time=1.0,
            cache_efficiency=0.5
        )
        
        assert analysis.duration_hours == 2.5
    
    def test_messages_per_hour_calculation(self):
        """Test messages per hour calculation."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 12, 0, 0)  # 2 hours
        
        analysis = SessionAnalysis(
            session_id="test",
            start_time=start,
            end_time=end,
            total_messages=20,  # 10 messages per hour
            total_tokens=1000,
            file_operations=[],
            context_switches=0,
            average_response_time=1.0,
            cache_efficiency=0.5
        )
        
        assert analysis.messages_per_hour == 10.0
        
        # Test zero duration
        same_time_analysis = SessionAnalysis(
            session_id="test",
            start_time=start,
            end_time=start,  # Same time
            total_messages=5,
            total_tokens=500,
            file_operations=[],
            context_switches=0,
            average_response_time=1.0,
            cache_efficiency=0.5
        )
        
        assert same_time_analysis.messages_per_hour == 0
    
    def test_tokens_per_message_calculation(self):
        """Test tokens per message calculation."""
        analysis = SessionAnalysis(
            session_id="test",
            start_time=datetime.now(),
            end_time=datetime.now(),
            total_messages=10,
            total_tokens=500,  # 50 tokens per message
            file_operations=[],
            context_switches=0,
            average_response_time=1.0,
            cache_efficiency=0.5
        )
        
        assert analysis.tokens_per_message == 50.0
        
        # Test zero messages
        zero_messages_analysis = SessionAnalysis(
            session_id="test",
            start_time=datetime.now(),
            end_time=datetime.now(),
            total_messages=0,
            total_tokens=100,
            file_operations=[],
            context_switches=0,
            average_response_time=0.0,
            cache_efficiency=0.0
        )
        
        assert zero_messages_analysis.tokens_per_message == 0


class TestFileAccessPattern:
    """Test suite for FileAccessPattern dataclass."""
    
    def test_file_access_pattern_creation(self):
        """Test creating FileAccessPattern instances."""
        now = datetime.now()
        first_access = now - timedelta(hours=2)
        
        pattern = FileAccessPattern(
            file_path="/test/file.py",
            access_count=5,
            first_access=first_access,
            last_access=now,
            operation_types=["Read", "Edit"]
        )
        
        assert pattern.file_path == "/test/file.py"
        assert pattern.access_count == 5
        assert pattern.operation_types == ["Read", "Edit"]
    
    def test_access_frequency_calculation(self):
        """Test access frequency calculation."""
        now = datetime.now()
        first_access = now - timedelta(hours=2)  # 2 hours ago
        
        pattern = FileAccessPattern(
            file_path="/test/file.py",
            access_count=4,  # 4 accesses in 2 hours = 2 per hour
            first_access=first_access,
            last_access=now,
            operation_types=["Read"]
        )
        
        assert pattern.access_frequency == 2.0
        
        # Test same time access
        same_time_pattern = FileAccessPattern(
            file_path="/test/file.py",
            access_count=3,
            first_access=now,
            last_access=now,  # Same time
            operation_types=["Read"]
        )
        
        assert same_time_pattern.access_frequency == 3.0  # All accesses at once
    
    def test_frequently_accessed_threshold(self):
        """Test frequently accessed detection."""
        now = datetime.now()
        
        # Frequently accessed (>= 3 accesses)
        frequent_pattern = FileAccessPattern(
            file_path="/test/frequent.py",
            access_count=5,
            first_access=now,
            last_access=now,
            operation_types=["Read"]
        )
        assert frequent_pattern.is_frequently_accessed is True
        
        # Not frequently accessed (< 3 accesses)
        rare_pattern = FileAccessPattern(
            file_path="/test/rare.py",
            access_count=2,
            first_access=now,
            last_access=now,
            operation_types=["Read"]
        )
        assert rare_pattern.is_frequently_accessed is False
    
    def test_recently_accessed_detection(self):
        """Test recently accessed detection."""
        now = datetime.now()
        
        # Recently accessed (within 1 hour)
        recent_pattern = FileAccessPattern(
            file_path="/test/recent.py",
            access_count=1,
            first_access=now - timedelta(minutes=30),
            last_access=now - timedelta(minutes=30),
            operation_types=["Read"]
        )
        assert recent_pattern.is_recently_accessed is True
        
        # Not recently accessed (> 1 hour ago)
        old_pattern = FileAccessPattern(
            file_path="/test/old.py",
            access_count=1,
            first_access=now - timedelta(hours=2),
            last_access=now - timedelta(hours=2),
            operation_types=["Read"]
        )
        assert old_pattern.is_recently_accessed is False


class TestCacheAnalysisResult:
    """Test suite for CacheAnalysisResult dataclass."""
    
    def test_cache_analysis_result_creation(self):
        """Test creating CacheAnalysisResult instances."""
        now = datetime.now()
        start_time = now - timedelta(seconds=5)
        
        result = CacheAnalysisResult(
            sessions_analyzed=10,
            total_messages=500,
            total_tokens=25000,
            analysis_start_time=start_time,
            analysis_end_time=now,
            overall_cache_hit_ratio=0.75,
            cache_efficiency_score=0.85,
            token_waste_estimate=1000,
            file_access_patterns=[],
            most_accessed_files=["/test/file1.py", "/test/file2.py"],
            context_switch_frequency=0.1,
            session_analyses=[],
            peak_usage_hours=[9, 10, 14, 15],
            average_session_duration=2.5
        )
        
        assert result.sessions_analyzed == 10
        assert result.total_messages == 500
        assert result.total_tokens == 25000
        assert result.overall_cache_hit_ratio == 0.75
    
    def test_analysis_duration_calculation(self):
        """Test analysis duration calculation."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 5)  # 5 seconds later
        
        result = CacheAnalysisResult(
            sessions_analyzed=1,
            total_messages=10,
            total_tokens=500,
            analysis_start_time=start,
            analysis_end_time=end,
            overall_cache_hit_ratio=0.5,
            cache_efficiency_score=0.6,
            token_waste_estimate=100,
            file_access_patterns=[],
            most_accessed_files=[],
            context_switch_frequency=0.0,
            session_analyses=[],
            peak_usage_hours=[],
            average_session_duration=1.0
        )
        
        assert result.analysis_duration == 5.0
    
    def test_average_tokens_per_session(self):
        """Test average tokens per session calculation."""
        result = CacheAnalysisResult(
            sessions_analyzed=5,
            total_messages=100,
            total_tokens=10000,  # 2000 tokens per session
            analysis_start_time=datetime.now(),
            analysis_end_time=datetime.now(),
            overall_cache_hit_ratio=0.5,
            cache_efficiency_score=0.6,
            token_waste_estimate=100,
            file_access_patterns=[],
            most_accessed_files=[],
            context_switch_frequency=0.0,
            session_analyses=[],
            peak_usage_hours=[],
            average_session_duration=1.0
        )
        
        assert result.average_tokens_per_session == 2000.0
        
        # Test zero sessions
        zero_sessions_result = CacheAnalysisResult(
            sessions_analyzed=0,
            total_messages=0,
            total_tokens=1000,
            analysis_start_time=datetime.now(),
            analysis_end_time=datetime.now(),
            overall_cache_hit_ratio=0.0,
            cache_efficiency_score=0.0,
            token_waste_estimate=0,
            file_access_patterns=[],
            most_accessed_files=[],
            context_switch_frequency=0.0,
            session_analyses=[],
            peak_usage_hours=[],
            average_session_duration=0.0
        )
        
        assert zero_sessions_result.average_tokens_per_session == 0
    
    def test_cache_effectiveness_grading(self):
        """Test cache effectiveness grading."""
        test_cases = [
            (0.9, "Excellent"),
            (0.8, "Excellent"),
            (0.7, "Good"),
            (0.6, "Good"),
            (0.5, "Fair"),
            (0.4, "Fair"),
            (0.3, "Needs Improvement"),
            (0.1, "Needs Improvement")
        ]
        
        for efficiency_score, expected_grade in test_cases:
            result = CacheAnalysisResult(
                sessions_analyzed=1,
                total_messages=10,
                total_tokens=500,
                analysis_start_time=datetime.now(),
                analysis_end_time=datetime.now(),
                overall_cache_hit_ratio=0.5,
                cache_efficiency_score=efficiency_score,
                token_waste_estimate=100,
                file_access_patterns=[],
                most_accessed_files=[],
                context_switch_frequency=0.0,
                session_analyses=[],
                peak_usage_hours=[],
                average_session_duration=1.0
            )
            
            assert result.cache_effectiveness_grade == expected_grade
    
    def test_summary_generation(self):
        """Test summary generation."""
        result = CacheAnalysisResult(
            sessions_analyzed=5,
            total_messages=100,
            total_tokens=5000,
            analysis_start_time=datetime.now(),
            analysis_end_time=datetime.now() + timedelta(seconds=2),
            overall_cache_hit_ratio=0.75,
            cache_efficiency_score=0.85,
            token_waste_estimate=500,
            file_access_patterns=[],
            most_accessed_files=[],
            context_switch_frequency=0.1,
            session_analyses=[],
            peak_usage_hours=[],
            average_session_duration=2.0,
            optimization_opportunities=[{"type": "test"}]
        )
        
        summary = result.get_summary()
        
        assert "5 sessions analyzed" in summary
        assert "100 messages processed" in summary
        assert "5,000 tokens analyzed" in summary
        assert "75.0%" in summary  # Cache hit ratio
        assert "Excellent" in summary  # Efficiency grade
        assert "1 optimization opportunities" in summary


class TestCacheConfig:
    """Test suite for CacheConfig dataclass."""
    
    def test_cache_config_defaults(self):
        """Test default configuration values."""
        config = CacheConfig()
        
        assert config.max_sessions_to_analyze == 50
        assert config.max_file_size_mb == 100
        assert config.analysis_timeout_seconds == 30
        assert config.frequent_access_threshold == 3
        assert config.recent_access_hours == 1
        assert config.context_switch_detection is True
        assert config.anonymize_file_paths is False
        assert config.include_content_analysis is True
        assert config.store_analysis_results is True
        assert config.search_all_projects is True
        assert config.include_archived_sessions is False
        assert config.max_cache_age_days == 30
    
    def test_cache_config_customization(self):
        """Test custom configuration values."""
        config = CacheConfig(
            max_sessions_to_analyze=20,
            max_file_size_mb=50,
            analysis_timeout_seconds=15,
            anonymize_file_paths=True,
            include_archived_sessions=True
        )
        
        assert config.max_sessions_to_analyze == 20
        assert config.max_file_size_mb == 50
        assert config.analysis_timeout_seconds == 15
        assert config.anonymize_file_paths is True
        assert config.include_archived_sessions is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])