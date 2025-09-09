"""
Migration Test Configuration

Shared fixtures and configuration for migration tests.
Provides common test utilities, mock services, and data generators.
"""

import pytest
import tempfile
import json
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from src.context_cleaner.services.token_analysis_bridge import TokenAnalysisBridge
from src.context_cleaner.models.token_bridge_models import BridgeResult, SessionTokenMetrics
from src.context_cleaner.migration.jsonl_discovery import JSONLFileInfo


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_clickhouse_client():
    """Create mock ClickHouse client."""
    client = Mock()

    # Mock successful operations
    client.execute_query = AsyncMock(return_value=[])
    client.bulk_insert = AsyncMock(return_value=True)
    client.health_check = AsyncMock(return_value=True)

    return client


@pytest.fixture
def mock_enhanced_counter():
    """Create mock enhanced token counter."""
    counter = Mock()

    # Mock analysis result
    analysis_result = Mock()
    analysis_result.total_calculated_tokens = 2768000000  # 2.768B tokens
    analysis_result.total_sessions_analyzed = 1000
    analysis_result.sessions = {}

    counter.analyze_comprehensive_token_usage = AsyncMock(return_value=analysis_result)

    return counter


@pytest.fixture
def sample_session_metrics():
    """Create sample SessionTokenMetrics for testing."""
    return SessionTokenMetrics(
        session_id="test_session_001",
        start_time=datetime(2024, 1, 1, 10, 0, 0),
        end_time=datetime(2024, 1, 1, 10, 30, 0),
        reported_input_tokens=150,
        reported_output_tokens=200,
        reported_cache_creation_tokens=25,
        reported_cache_read_tokens=30,
        calculated_total_tokens=450,
        content_categories={"user_messages": 100, "system_tools": 50, "mcp_tools": 25},
    )


def create_test_jsonl_data(num_sessions=5, entries_per_session=4):
    """Generate test JSONL data."""
    data = []

    for session_idx in range(num_sessions):
        session_id = f"test_session_{session_idx:03d}"

        for entry_idx in range(entries_per_session):
            if entry_idx % 2 == 0:  # User message
                entry = {
                    "session_id": session_id,
                    "type": "user",
                    "timestamp": f"2024-01-01T{10 + entry_idx}:00:00Z",
                    "message": {"content": f"User message {entry_idx} in session {session_idx}"},
                }
            else:  # Assistant message
                entry = {
                    "session_id": session_id,
                    "type": "assistant",
                    "timestamp": f"2024-01-01T{10 + entry_idx}:00:30Z",
                    "message": {
                        "content": f"Assistant response {entry_idx} in session {session_idx}",
                        "usage": {
                            "input_tokens": 20 + entry_idx,
                            "output_tokens": 40 + entry_idx,
                            "cache_creation_input_tokens": 5 if entry_idx % 4 == 1 else 0,
                            "cache_read_input_tokens": 10 if entry_idx > 1 else 0,
                        },
                    },
                }

            data.append(entry)

    return data


@pytest.fixture
def test_jsonl_files():
    """Create temporary JSONL files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create multiple test files
        test_files = {}

        # Small file
        small_data = create_test_jsonl_data(num_sessions=2, entries_per_session=2)
        small_file = tmpdir_path / "small_session.jsonl"
        with open(small_file, "w") as f:
            for entry in small_data:
                f.write(json.dumps(entry) + "\n")
        test_files["small"] = str(small_file)

        # Medium file
        medium_data = create_test_jsonl_data(num_sessions=10, entries_per_session=6)
        medium_file = tmpdir_path / "medium_session.jsonl"
        with open(medium_file, "w") as f:
            for entry in medium_data:
                f.write(json.dumps(entry) + "\n")
        test_files["medium"] = str(medium_file)

        # Large file
        large_data = create_test_jsonl_data(num_sessions=50, entries_per_session=10)
        large_file = tmpdir_path / "large_session.jsonl"
        with open(large_file, "w") as f:
            for entry in large_data:
                f.write(json.dumps(entry) + "\n")
        test_files["large"] = str(large_file)

        # Corrupted file
        corrupted_file = tmpdir_path / "corrupted.jsonl"
        with open(corrupted_file, "w") as f:
            f.write('{"valid": "json"}\n')
            f.write("invalid json line\n")
            f.write('{"another": "valid", "entry": true}\n')
        test_files["corrupted"] = str(corrupted_file)

        test_files["directory"] = str(tmpdir_path)

        yield test_files


@pytest.fixture
def file_info_factory():
    """Factory for creating JSONLFileInfo objects."""

    def create_file_info(path, size_bytes=1024, is_corrupt=False, estimated_tokens=100):
        file_path = Path(path)
        return JSONLFileInfo(
            path=str(file_path),
            filename=file_path.name,
            size_bytes=size_bytes,
            created_at=datetime(2024, 1, 1, 9, 0, 0),
            modified_at=datetime(2024, 1, 1, 10, 0, 0),
            estimated_tokens=estimated_tokens,
            is_corrupt=is_corrupt,
            corruption_reason="Test corruption" if is_corrupt else None,
        )

    return create_file_info


@pytest.fixture
def performance_timer():
    """Timer utility for performance testing."""
    import time

    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()
            return self

        def stop(self):
            self.end_time = time.time()
            return self

        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0.0

    return PerformanceTimer


@pytest.fixture
def memory_monitor():
    """Memory monitoring utility."""
    import psutil

    class MemoryMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.initial_memory = None
            self.peak_memory = None

        def start(self):
            self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = self.initial_memory
            return self

        def update(self):
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            if current_memory > self.peak_memory:
                self.peak_memory = current_memory
            return current_memory

        @property
        def memory_increase(self):
            if self.initial_memory:
                return self.peak_memory - self.initial_memory
            return 0.0

    return MemoryMonitor


# Test configuration constants
TEST_BATCH_SIZE = 10
TEST_MAX_MEMORY_MB = 100
TEST_CHUNK_SIZE = 5


# Custom pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (may take minutes)")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "cli: marks tests as CLI integration tests")
