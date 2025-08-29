"""
Pytest configuration and fixtures for Context Cleaner tests.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from context_cleaner.config.settings import ContextCleanerConfig
from context_cleaner.analytics.productivity_analyzer import ProductivityAnalyzer


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def test_config(temp_data_dir):
    """Create test configuration."""
    config = ContextCleanerConfig.default()
    config.data_directory = temp_data_dir
    config.tracking.enabled = True
    config.tracking.session_timeout_minutes = 5
    config.analysis.max_context_size = 10000
    return config


@pytest.fixture
def productivity_analyzer(test_config):
    """Create ProductivityAnalyzer instance for testing."""
    return ProductivityAnalyzer(test_config)


@pytest.fixture
def mock_session_data():
    """Generate mock session data for testing."""
    base_time = datetime.now() - timedelta(days=7)
    
    sessions = []
    for i in range(10):
        session_time = base_time + timedelta(hours=i * 8)
        sessions.append({
            "timestamp": session_time.isoformat(),
            "session_duration": 120 + (i * 15),  # 2-4 hours
            "context_health_score": 70 + (i * 3),  # Improving over time
            "productivity_score": 65 + (i * 4),   # Improving productivity
            "optimization_events": i % 3,          # Variable optimizations
            "session_type": ["coding", "debugging", "testing"][i % 3]
        })
    
    return sessions


@pytest.fixture
def mock_context_data():
    """Generate mock context data for testing."""
    return {
        "total_tokens": 15000,
        "file_count": 25,
        "conversation_depth": 45,
        "last_optimization": "2024-12-20T10:30:00",
        "tools_used": ["Read", "Write", "Bash", "Edit"],
        "session_start": "2024-12-20T09:00:00"
    }