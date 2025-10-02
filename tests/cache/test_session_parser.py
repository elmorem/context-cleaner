#!/usr/bin/env python3
"""
Tests for Session Cache Parser

Comprehensive tests for parsing Claude Code .jsonl session files
including message extraction, token metrics, and error handling.
"""

import pytest
import json
import tempfile
from datetime import datetime
from pathlib import Path

from src.context_cleaner.analysis.session_parser import SessionCacheParser
from src.context_cleaner.analysis.models import (
    SessionMessage,
    MessageRole,
    MessageType,
    CacheConfig,
)


class TestSessionCacheParser:
    """Test suite for SessionCacheParser class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SessionCacheParser()
        self.config = CacheConfig()

        # Sample message data
        self.sample_message_data = {
            "uuid": "test-uuid-123",
            "parentUuid": "parent-uuid-456",
            "sessionId": "session-123",
            "timestamp": "2025-08-30T10:30:00.000Z",
            "type": "user",
            "message": {"role": "user", "content": "Help me debug this function"},
        }

        self.sample_assistant_message = {
            "uuid": "assistant-uuid-123",
            "parentUuid": "test-uuid-123",
            "sessionId": "session-123",
            "timestamp": "2025-08-30T10:31:00.000Z",
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll help you debug that function."},
                    {
                        "type": "tool_use",
                        "id": "tool-123",
                        "name": "Read",
                        "input": {"file_path": "/test/file.py"},
                    },
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 150,
                    "cache_creation": {
                        "ephemeral_5m_input_tokens": 200,
                        "ephemeral_1h_input_tokens": 0,
                    },
                },
            },
        }

    def test_parse_message_data_user_message(self):
        """Test parsing a basic user message."""
        message = self.parser._parse_message_data(self.sample_message_data)

        assert message is not None
        assert message.uuid == "test-uuid-123"
        assert message.parent_uuid == "parent-uuid-456"
        assert message.session_id == "session-123"
        assert message.role == MessageRole.USER
        assert message.message_type == MessageType.USER
        assert message.content == "Help me debug this function"
        assert message.token_metrics is None  # No usage data in user message

    def test_parse_message_data_assistant_message(self):
        """Test parsing an assistant message with tool usage and token metrics."""
        message = self.parser._parse_message_data(self.sample_assistant_message)

        assert message is not None
        assert message.uuid == "assistant-uuid-123"
        assert message.role == MessageRole.ASSISTANT
        assert message.message_type == MessageType.ASSISTANT

        # Check token metrics
        assert message.token_metrics is not None
        assert message.token_metrics.input_tokens == 100
        assert message.token_metrics.output_tokens == 50
        assert message.token_metrics.cache_creation_input_tokens == 200
        assert message.token_metrics.cache_read_input_tokens == 150

        # Check tool usage
        assert len(message.tool_usage) == 1
        tool = message.tool_usage[0]
        assert tool.tool_name == "Read"
        assert tool.tool_id == "tool-123"
        assert tool.parameters["file_path"] == "/test/file.py"
        assert tool.is_file_operation is True

    def test_parse_timestamp_iso_format(self):
        """Test parsing ISO format timestamps."""
        # Test UTC timestamp
        timestamp = self.parser._parse_timestamp("2025-08-30T10:30:00.000Z")
        assert timestamp is not None
        assert timestamp.year == 2025
        assert timestamp.month == 8
        assert timestamp.day == 30
        assert timestamp.hour == 10
        assert timestamp.minute == 30

        # Test timestamp without Z
        timestamp2 = self.parser._parse_timestamp("2025-08-30T10:30:00.000")
        assert timestamp2 is not None

    def test_parse_timestamp_invalid_format(self):
        """Test handling of invalid timestamp formats."""
        invalid_timestamps = [
            "",
            "invalid",
            "2025-13-45T25:70:00.000Z",  # Invalid date
            None,
        ]

        for invalid_ts in invalid_timestamps:
            result = self.parser._parse_timestamp(invalid_ts)
            assert result is None

    def test_parse_token_metrics(self):
        """Test parsing token usage metrics."""
        usage_data = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 150,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 200,
                "ephemeral_1h_input_tokens": 100,
            },
        }

        metrics = self.parser._parse_token_metrics(usage_data)

        assert metrics.input_tokens == 100
        assert metrics.output_tokens == 50
        assert metrics.cache_creation_input_tokens == 200
        assert metrics.cache_read_input_tokens == 150
        assert metrics.ephemeral_5m_input_tokens == 200
        assert metrics.ephemeral_1h_input_tokens == 100
        assert (
            metrics.total_tokens == 500
        )  # input + output + cache_creation + cache_read
        assert abs(metrics.cache_hit_ratio - 0.4286) < 0.001  # 150/(200+150)

    def test_parse_session_file_valid(self):
        """Test parsing a valid .jsonl session file."""
        # Create temporary file with sample data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            json.dump(self.sample_message_data, f)
            f.write("\n")
            json.dump(self.sample_assistant_message, f)
            temp_path = Path(f.name)

        try:
            analysis = self.parser.parse_session_file(temp_path)

            assert analysis is not None
            assert analysis.session_id == "session-123"
            assert analysis.total_messages == 2
            assert analysis.total_tokens > 0
            assert len(analysis.file_operations) == 1
            assert analysis.file_operations[0].tool_name == "Read"

        finally:
            temp_path.unlink()  # Clean up

    def test_parse_session_file_empty(self):
        """Test parsing an empty session file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = Path(f.name)

        try:
            analysis = self.parser.parse_session_file(temp_path)
            assert analysis is None

        finally:
            temp_path.unlink()

    def test_parse_session_file_invalid_json(self):
        """Test parsing a file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"valid": "json"}\n')
            f.write("invalid json line\n")
            f.write('{"another": "valid", "line": true}\n')
            temp_path = Path(f.name)

        try:
            # Parser should handle invalid lines gracefully
            messages = list(self.parser._parse_messages(temp_path))
            assert len(messages) == 0  # No valid messages in our test data

        finally:
            temp_path.unlink()

    def test_parse_session_file_too_large(self):
        """Test handling of files that exceed size limit."""
        config = CacheConfig(max_file_size_mb=0.001)  # Very small limit
        parser = SessionCacheParser(config)

        # Create file that exceeds limit
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            # Write enough data to exceed 0.001 MB limit
            large_data = {"data": "x" * 2000}  # > 0.001 MB
            json.dump(large_data, f)
            temp_path = Path(f.name)

        try:
            analysis = parser.parse_session_file(temp_path)
            assert analysis is None

        finally:
            temp_path.unlink()

    def test_parse_session_file_nonexistent(self):
        """Test parsing a non-existent file."""
        nonexistent_path = Path("/nonexistent/file.jsonl")
        analysis = self.parser.parse_session_file(nonexistent_path)
        assert analysis is None

    def test_analyze_file_access_patterns(self):
        """Test file access pattern analysis."""
        # Create mock session with file operations
        from src.context_cleaner.analysis.models import SessionAnalysis, ToolUsage

        now = datetime.now()
        tool1 = ToolUsage("Read", "t1", {"file_path": "/test/file.py"}, now)
        tool2 = ToolUsage(
            "Edit", "t2", {"file_path": "/test/file.py"}, now
        )  # Same file
        tool3 = ToolUsage("Read", "t3", {"file_path": "/test/other.py"}, now)

        session = SessionAnalysis(
            session_id="test",
            start_time=now,
            end_time=now,
            total_messages=1,
            total_tokens=100,
            file_operations=[tool1, tool2, tool3],
            context_switches=0,
            average_response_time=1.0,
            cache_efficiency=0.8,
        )

        patterns = self.parser.analyze_file_access_patterns([session])

        assert len(patterns) == 2

        # file.py should have 2 accesses (most frequent, so first)
        assert patterns[0].file_path == "/test/file.py"
        assert patterns[0].access_count == 2
        assert "Read" in patterns[0].operation_types
        assert "Edit" in patterns[0].operation_types

        # other.py should have 1 access
        assert patterns[1].file_path == "/test/other.py"
        assert patterns[1].access_count == 1
        assert "Read" in patterns[1].operation_types

    def test_message_content_text_extraction(self):
        """Test text extraction from various message content formats."""
        # Test string content
        msg1 = SessionMessage(
            uuid="1",
            parent_uuid=None,
            message_type=MessageType.USER,
            role=MessageRole.USER,
            content="Simple text",
            timestamp=datetime.now(),
        )
        assert msg1.content_text == "Simple text"

        # Test list content with tool usage
        content_list = [
            {"type": "text", "text": "Let me help you"},
            {"type": "tool_use", "name": "Read", "id": "tool1"},
            {"type": "tool_result", "content": "File contents here"},
        ]

        msg2 = SessionMessage(
            uuid="2",
            parent_uuid=None,
            message_type=MessageType.ASSISTANT,
            role=MessageRole.ASSISTANT,
            content=content_list,
            timestamp=datetime.now(),
        )

        content_text = msg2.content_text
        assert "Let me help you" in content_text
        assert "Tool: Read" in content_text
        assert "Result: File contents here" in content_text

    def test_context_switch_detection(self):
        """Test context switch detection in messages."""
        switch_messages = [
            "Let me switch to a different approach",
            "Now let's work on something else",
            "Moving on to the next task",
            "Okay, now I need help with authentication",
        ]

        for content in switch_messages:
            msg = SessionMessage(
                uuid="test",
                parent_uuid=None,
                message_type=MessageType.USER,
                role=MessageRole.USER,
                content=content,
                timestamp=datetime.now(),
            )
            assert msg.is_context_switch is True

        # Non-switch message
        normal_msg = SessionMessage(
            uuid="test",
            parent_uuid=None,
            message_type=MessageType.USER,
            role=MessageRole.USER,
            content="Help me debug this function",
            timestamp=datetime.now(),
        )
        assert normal_msg.is_context_switch is False

    def test_parser_stats_tracking(self):
        """Test parser statistics tracking."""
        initial_stats = self.parser.get_parsing_stats()

        assert initial_stats["files_parsed"] == 0
        assert initial_stats["messages_parsed"] == 0
        assert initial_stats["errors_encountered"] == 0

        # Create and parse a valid file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            json.dump(self.sample_message_data, f)
            temp_path = Path(f.name)

        try:
            self.parser.parse_session_file(temp_path)
            stats = self.parser.get_parsing_stats()

            assert stats["files_parsed"] == 1
            assert stats["messages_parsed"] == 1
            assert stats["parse_time_seconds"] > 0

        finally:
            temp_path.unlink()

        # Test stats reset
        self.parser.reset_stats()
        reset_stats = self.parser.get_parsing_stats()
        assert reset_stats["files_parsed"] == 0
        assert reset_stats["messages_parsed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
