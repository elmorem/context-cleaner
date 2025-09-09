"""
Test Fixtures for Enhanced Token Counting System Tests

Provides comprehensive mock data that simulates the 90% undercount scenario
and various conversation patterns found in Claude Code JSONL files.
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Iterator, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
import pytest
import asyncio


@dataclass
class MockJSONLData:
    """Mock JSONL data for testing."""
    
    # Simulates the current limitation: only 10% of tokens are counted
    reported_tokens: int
    actual_tokens: int  # What the enhanced system should detect
    
    # File content
    entries: List[Dict[str, Any]] = field(default_factory=list)
    session_count: int = 1
    total_lines: int = 100
    
    @property
    def undercount_percentage(self) -> float:
        """Calculate undercount percentage."""
        if self.actual_tokens == 0:
            return 0.0
        return ((self.actual_tokens - self.reported_tokens) / self.actual_tokens) * 100


class JSONLTestFixtures:
    """Comprehensive test fixtures for JSONL data patterns."""
    
    @staticmethod
    def create_realistic_conversation_entry(
        message_type: str = "user",
        content: str = "Test message",
        usage: Dict[str, int] = None,
        session_id: str = "test_session_001",
        timestamp: str = None
    ) -> Dict[str, Any]:
        """Create a realistic JSONL conversation entry."""
        
        if timestamp is None:
            timestamp = datetime.now().isoformat()
            
        entry = {
            "type": message_type,
            "timestamp": timestamp,
            "session_id": session_id,
            "message": {
                "role": message_type,
                "content": content
            }
        }
        
        # Add usage stats for assistant messages (current limitation)
        if message_type == "assistant" and usage:
            entry["message"]["usage"] = usage
            
        return entry
    
    @staticmethod
    def create_claude_md_content() -> str:
        """Create Claude MD style content that should be categorized correctly."""
        return """# Claude Code Instructions

You are Claude Code, Anthropic's official CLI tool. You have enhanced capabilities for:

## Development Guidelines

- Always prefer editing existing files to creating new ones
- Use absolute paths for all file operations
- Follow the project's coding standards

## MCP Tool Integration

When using mcp__ tools, ensure proper error handling and validation.

## Test Coverage

Ensure comprehensive test coverage for all new functionality."""

    @staticmethod
    def create_system_prompt_content() -> str:
        """Create system prompt content."""
        return """<system-reminder>
You are a specialized agent designed to help with context cleaning operations.
Your role is to analyze conversation files and provide insights about token usage patterns.

Key responsibilities:
1. Process JSONL files comprehensively
2. Detect token usage undercounts
3. Provide accurate analytics
</system-reminder>"""

    @staticmethod
    def create_tool_usage_content() -> str:
        """Create content with tool usage patterns."""
        return """I'll use the Read tool to examine the file contents and then create comprehensive tests.

<function_calls>
<invoke name="Read">
<parameter name="file_path">/path/to/file.py