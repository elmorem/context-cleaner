"""Shared test fixtures for context cleaner analysis tests."""

from typing import Dict, List, Any
from datetime import datetime, timedelta
import json


class AnalysisTestData:
    """Helper class for generating test data for analysis tests."""

    @staticmethod
    def create_sample_conversation_data() -> List[Dict[str, Any]]:
        """Create sample conversation data for testing."""
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "role": "user",
                "content": "Help me optimize this code",
                "token_count": 25
            },
            {
                "timestamp": (datetime.now() + timedelta(minutes=1)).isoformat(),
                "role": "assistant",
                "content": "I'll analyze your code and suggest optimizations",
                "token_count": 45
            },
            {
                "timestamp": (datetime.now() + timedelta(minutes=2)).isoformat(),
                "role": "user",
                "content": "Thanks, what about performance?",
                "token_count": 28
            }
        ]

    @staticmethod
    def create_sample_file_analysis() -> Dict[str, Any]:
        """Create sample file analysis data."""
        return {
            "total_files": 15,
            "active_files": 8,
            "stale_files": 7,
            "total_size_mb": 2.5,
            "analysis_timestamp": datetime.now().isoformat(),
            "file_categories": {
                "code": 10,
                "documentation": 3,
                "configuration": 2
            }
        }

    @staticmethod
    def create_sample_token_usage() -> Dict[str, Any]:
        """Create sample token usage data."""
        return {
            "total_tokens": 15000,
            "input_tokens": 8000,
            "output_tokens": 7000,
            "cost_estimate": 0.045,
            "session_duration_minutes": 45,
            "efficiency_score": 0.82
        }

    @staticmethod
    def create_sample_health_metrics() -> Dict[str, Any]:
        """Create sample health metrics."""
        return {
            "focus_score": 0.75,
            "redundancy_score": 0.68,
            "recency_score": 0.85,
            "size_optimization_score": 0.72,
            "overall_health": 0.75,
            "recommendations": [
                "Remove duplicate content",
                "Archive old conversations",
                "Focus on current tasks"
            ]
        }

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
<parameter name="file_path">/path/to/file.py</parameter>
</invoke>
</function_calls>

Let me analyze the code structure and create appropriate tests."""