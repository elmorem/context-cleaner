"""
Test Fixtures for Enhanced Token Counting System

Comprehensive mock data and utilities for testing the 90% undercount fix.
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Iterator
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from dataclasses import dataclass, field
import pytest
import asyncio


@dataclass
class UndercountScenario:
    """Test scenario for various undercount patterns."""
    name: str
    description: str
    reported_tokens: int
    actual_tokens: int
    expected_undercount_percentage: float
    
    @property
    def undercount_percentage(self) -> float:
        if self.actual_tokens == 0:
            return 0.0
        return ((self.actual_tokens - self.reported_tokens) / self.actual_tokens) * 100


class MockAPIResponses:
    """Mock responses for Anthropic count-tokens API."""
    
    @staticmethod
    def create_count_tokens_response(token_count: int) -> Dict[str, Any]:
        """Create mock API response."""
        return {
            "input_tokens": token_count,
            "output_tokens": 0
        }
    
    @staticmethod
    def create_error_response(status: int = 429, message: str = "Rate limit exceeded") -> Dict[str, Any]:
        """Create mock error response."""
        return {
            "type": "error",
            "error": {
                "type": "rate_limit_error",
                "message": message
            }
        }


class JSONLFixtures:
    """Factory for creating test JSONL data."""
    
    @classmethod
    def create_undercount_conversation(cls, session_id: str = "session_001") -> List[Dict[str, Any]]:
        """
        Create conversation data that demonstrates the 90% undercount issue.
        
        This simulates the current limitation where only assistant messages with usage 
        stats are counted, missing user messages, system prompts, and tool usage.
        """
        base_time = datetime.now() - timedelta(hours=1)
        
        entries = []
        
        # User message - MISSED by current system (no usage stats)
        entries.append({
            "type": "user",
            "timestamp": (base_time + timedelta(minutes=0)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "user",
                "content": "I need help creating comprehensive tests for the Enhanced Token Counting System that addresses a 90% token undercount issue in the current implementation. The system consists of EnhancedTokenCounterService, DashboardTokenAnalyzer, and CLI commands. Please create tests that validate file discovery (all JSONL files vs 10), complete file processing (entire files vs 1000 lines), all message types processing, session tracking, API integration, dashboard integration, fallback handling, undercount detection, accuracy improvement, and performance for large files."
            }
        })
        
        # System prompt - MISSED by current system
        entries.append({
            "type": "system",
            "timestamp": (base_time + timedelta(minutes=1)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "system",
                "content": """<system-reminder>
You are Claude Code, Anthropic's official CLI for Claude. You are an expert test engineer specializing in Django/React applications with deep expertise in both frontend and backend testing methodologies. You create robust, performant, and maintainable test suites that minimize flakiness and maximize reliability for modern web applications.
</system-reminder>"""
            }
        })
        
        # Assistant message - COUNTED by current system (has usage stats) 
        entries.append({
            "type": "assistant", 
            "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "assistant",
                "content": "I'll create comprehensive tests for the Enhanced Token Counting System that validates the 90% undercount fix. Let me start by examining the existing code structure and then create thorough tests.",
                "usage": {
                    "input_tokens": 150,  # Only these tokens are counted currently
                    "output_tokens": 45,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0
                }
            }
        })
        
        # Tool usage - MISSED by current system
        entries.append({
            "type": "tool_use",
            "timestamp": (base_time + timedelta(minutes=3)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "assistant",
                "content": "I'll examine the enhanced token counter code.",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "Read",
                            "arguments": {
                                "file_path": "/Users/markelmore/_code/context-cleaner/src/context_cleaner/analysis/enhanced_token_counter.py"
                            }
                        }
                    }
                ]
            }
        })
        
        # Tool result - MISSED by current system
        entries.append({
            "type": "tool_result",
            "timestamp": (base_time + timedelta(minutes=4)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "tool",
                "content": "Enhanced Token Counter using Anthropic's Count-Tokens API... [large file content that contains hundreds of lines of code and would significantly contribute to token count]"
            }
        })
        
        # Another user message - MISSED
        entries.append({
            "type": "user",
            "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "user", 
                "content": "Please focus on ensuring the tests validate that this system truly addresses the 90% undercount issue and provides accurate token analytics."
            }
        })
        
        # Another assistant message - COUNTED
        entries.append({
            "type": "assistant",
            "timestamp": (base_time + timedelta(minutes=6)).isoformat(),
            "session_id": session_id,
            "message": {
                "role": "assistant",
                "content": "I'll create tests specifically focused on validating the 90% undercount detection and accuracy improvements.",
                "usage": {
                    "input_tokens": 75,  # Only these are counted currently
                    "output_tokens": 25,
                    "cache_creation_input_tokens": 0, 
                    "cache_read_input_tokens": 0
                }
            }
        })
        
        return entries
    
    @classmethod
    def create_large_conversation(cls, session_id: str = "large_session", num_entries: int = 2000) -> List[Dict[str, Any]]:
        """Create a large conversation to test performance and line limits."""
        entries = []
        base_time = datetime.now() - timedelta(hours=2)
        
        for i in range(num_entries):
            message_type = "user" if i % 2 == 0 else "assistant"
            content = f"Message {i + 1}: " + "This is test content " * 10  # Varied length
            
            entry = {
                "type": message_type,
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "session_id": session_id,
                "message": {
                    "role": message_type,
                    "content": content
                }
            }
            
            # Add usage stats only to assistant messages (current limitation)
            if message_type == "assistant" and i % 10 == 1:  # Only some assistant messages have usage
                entry["message"]["usage"] = {
                    "input_tokens": 50,
                    "output_tokens": 20,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0
                }
            
            entries.append(entry)
        
        return entries
    
    @classmethod
    def create_multiple_sessions_data(cls) -> Dict[str, List[Dict[str, Any]]]:
        """Create data spanning multiple sessions."""
        sessions = {}
        
        # Session with high undercount
        sessions["high_undercount"] = cls.create_undercount_conversation("session_high_undercount")
        
        # Session with moderate undercount 
        sessions["moderate_undercount"] = [
            {
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": "session_moderate",
                "message": {"role": "user", "content": "Short message"}
            },
            {
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "session_moderate",
                "message": {
                    "role": "assistant",
                    "content": "Short response",
                    "usage": {"input_tokens": 100, "output_tokens": 30, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                }
            }
        ]
        
        # Session with accurate counting (rare case)
        sessions["accurate_counting"] = [
            {
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "session_accurate",
                "message": {
                    "role": "assistant",
                    "content": "Only assistant message",
                    "usage": {"input_tokens": 200, "output_tokens": 50, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                }
            }
        ]
        
        return sessions


class UndercountTestCases:
    """Predefined test cases for undercount scenarios."""
    
    SEVERE_UNDERCOUNT = UndercountScenario(
        name="severe_undercount",
        description="90% of tokens missed due to system limitations",
        reported_tokens=100,
        actual_tokens=1000,
        expected_undercount_percentage=90.0
    )
    
    MODERATE_UNDERCOUNT = UndercountScenario(
        name="moderate_undercount", 
        description="50% of tokens missed",
        reported_tokens=500,
        actual_tokens=1000,
        expected_undercount_percentage=50.0
    )
    
    MINIMAL_UNDERCOUNT = UndercountScenario(
        name="minimal_undercount",
        description="10% of tokens missed",
        reported_tokens=900,
        actual_tokens=1000,
        expected_undercount_percentage=10.0
    )
    
    NO_UNDERCOUNT = UndercountScenario(
        name="no_undercount",
        description="Accurate token counting",
        reported_tokens=1000,
        actual_tokens=1000,
        expected_undercount_percentage=0.0
    )
    
    @classmethod
    def all_scenarios(cls) -> List[UndercountScenario]:
        return [cls.SEVERE_UNDERCOUNT, cls.MODERATE_UNDERCOUNT, cls.MINIMAL_UNDERCOUNT, cls.NO_UNDERCOUNT]


class MockFileSystem:
    """Mock file system for testing file discovery and processing."""
    
    def __init__(self):
        self.files = {}
        self.directories = set()
    
    def add_jsonl_file(self, path: str, content: List[Dict[str, Any]]):
        """Add a JSONL file with given content."""
        self.files[path] = content
        self.directories.add(str(Path(path).parent))
    
    def create_test_file_structure(self, base_path: str = "/test/claude/projects"):
        """Create realistic file structure for testing."""
        # Current limitation: only processes 10 most recent files
        # Enhanced system: processes ALL files
        
        base = Path(base_path)
        
        # Create 15 files to test file discovery limitations
        for i in range(15):
            file_path = str(base / f"session_{i:03d}.jsonl")
            
            if i < 5:
                # Recent files with severe undercount
                content = JSONLFixtures.create_undercount_conversation(f"session_{i:03d}")
            elif i < 10:
                # Older files that current system would miss
                content = JSONLFixtures.create_large_conversation(f"session_{i:03d}", 500)
            else:
                # Even older files - completely missed by current system
                content = JSONLFixtures.create_large_conversation(f"session_{i:03d}", 1500)
            
            self.add_jsonl_file(file_path, content)
    
    def get_file_content_as_text(self, path: str) -> str:
        """Get file content as JSONL text."""
        if path not in self.files:
            raise FileNotFoundError(f"Mock file {path} not found")
        
        lines = []
        for entry in self.files[path]:
            lines.append(json.dumps(entry))
        
        return "\n".join(lines)


class MockAnthropicAPI:
    """Mock Anthropic count-tokens API client."""
    
    def __init__(self, simulate_errors: bool = False, rate_limit: bool = False):
        self.simulate_errors = simulate_errors
        self.rate_limit = rate_limit
        self.call_count = 0
        self.requests_made = []
    
    async def count_tokens_for_messages(self, messages: List[Dict[str, Any]], system: str = None) -> int:
        """Mock token counting that returns realistic values."""
        self.call_count += 1
        self.requests_made.append({"messages": messages, "system": system})
        
        if self.rate_limit and self.call_count > 5:
            raise Exception("Rate limit exceeded")
        
        if self.simulate_errors and self.call_count % 3 == 0:
            raise Exception("API error")
        
        # Calculate realistic token count based on content length
        total_chars = 0
        for message in messages:
            content = message.get("content", "")
            total_chars += len(str(content))
        
        if system:
            total_chars += len(system)
        
        # Rough approximation: 4 chars per token
        return max(1, total_chars // 4)


# Pytest fixtures

@pytest.fixture
def undercount_scenarios():
    """Provide all undercount test scenarios."""
    return UndercountTestCases.all_scenarios()


@pytest.fixture  
def mock_file_system():
    """Provide mock file system with test data."""
    fs = MockFileSystem()
    fs.create_test_file_structure()
    return fs


@pytest.fixture
def mock_anthropic_api():
    """Provide mock Anthropic API client."""
    return MockAnthropicAPI()


@pytest.fixture
def mock_anthropic_api_with_errors():
    """Provide mock Anthropic API client that simulates errors."""
    return MockAnthropicAPI(simulate_errors=True)


@pytest.fixture
def mock_anthropic_api_rate_limited():
    """Provide mock Anthropic API client that hits rate limits."""
    return MockAnthropicAPI(rate_limit=True)


@pytest.fixture
def jsonl_test_data():
    """Provide comprehensive JSONL test data."""
    return {
        "undercount_conversation": JSONLFixtures.create_undercount_conversation(),
        "large_conversation": JSONLFixtures.create_large_conversation(),
        "multiple_sessions": JSONLFixtures.create_multiple_sessions_data()
    }


@pytest.fixture
async def temp_jsonl_files(tmp_path):
    """Create temporary JSONL files for testing."""
    files = {}
    
    # Create undercount scenario file
    undercount_file = tmp_path / "undercount_session.jsonl"
    undercount_data = JSONLFixtures.create_undercount_conversation()
    
    with open(undercount_file, 'w') as f:
        for entry in undercount_data:
            f.write(json.dumps(entry) + "\n")
    
    files["undercount"] = undercount_file
    
    # Create large file
    large_file = tmp_path / "large_session.jsonl" 
    large_data = JSONLFixtures.create_large_conversation(num_entries=1200)
    
    with open(large_file, 'w') as f:
        for entry in large_data:
            f.write(json.dumps(entry) + "\n")
    
    files["large"] = large_file
    
    return files