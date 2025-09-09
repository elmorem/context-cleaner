"""
Tests for Data Extraction Engine

Unit tests for JSONL parsing, SessionTokenMetrics conversion,
schema handling, and data transformation functionality.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from src.context_cleaner.migration.data_extraction import DataExtractionEngine, ExtractionResult
from src.context_cleaner.migration.jsonl_discovery import JSONLFileInfo
from src.context_cleaner.models.token_bridge_models import SessionTokenMetrics


@pytest.fixture
def sample_jsonl_file():
    """Create a sample JSONL file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        sample_data = [
            {
                "session_id": "session_1",
                "type": "user",
                "timestamp": "2024-01-01T10:00:00Z",
                "message": {"content": "Hello, how are you?"},
            },
            {
                "session_id": "session_1",
                "type": "assistant",
                "timestamp": "2024-01-01T10:00:01Z",
                "message": {
                    "content": "I'm doing well, thank you for asking!",
                    "usage": {
                        "input_tokens": 15,
                        "output_tokens": 25,
                        "cache_creation_input_tokens": 5,
                        "cache_read_input_tokens": 3,
                    },
                },
            },
            {
                "session_id": "session_2",
                "type": "user",
                "timestamp": "2024-01-01T11:00:00Z",
                "message": {"content": "What's the weather like?"},
            },
            {
                "session_id": "session_2",
                "type": "assistant",
                "timestamp": "2024-01-01T11:00:01Z",
                "message": {
                    "content": "I don't have access to real-time weather data.",
                    "usage": {"input_tokens": 20, "output_tokens": 30},
                },
            },
        ]

        for entry in sample_data:
            f.write(json.dumps(entry) + "\n")

        return f.name


@pytest.fixture
def complex_jsonl_file():
    """Create a JSONL file with complex data structures."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        sample_data = [
            {
                "sessionId": "complex_session",  # Different field name
                "type": "user",
                "content": "Complex user message with tools",
                "messages": [{"role": "user", "content": "First part"}, {"role": "user", "content": "Second part"}],
            },
            {
                "session_id": "complex_session",
                "type": "assistant",
                "data": "Assistant response with MCP tools",
                "metadata": {"usage": {"input_tokens": 100, "output_tokens": 150}},
                "tool_calls": [
                    {"name": "bash", "arguments": {"command": "ls"}},
                    {"name": "read", "arguments": {"file_path": "/test"}},
                ],
            },
            {
                "id": "another_session",  # Another session ID field variant
                "type": "system",
                "text": "System prompt: You are a helpful assistant",
            },
        ]

        for entry in sample_data:
            f.write(json.dumps(entry) + "\n")

        return f.name


@pytest.fixture
def corrupted_jsonl_file():
    """Create a JSONL file with some corrupted entries."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        lines = [
            '{"session_id": "valid_session", "type": "user", "message": {"content": "Valid entry"}}',
            "invalid json line",
            '{"session_id": "valid_session", "type": "assistant", "message": {"content": "Another valid entry"}}',
            '{"incomplete": "json"',  # Missing closing brace
            "",  # Empty line
            '{"session_id": "valid_session", "type": "user", "message": {"content": "Final valid entry"}}',
        ]

        f.write("\n".join(lines))
        return f.name


@pytest.fixture
def extraction_engine():
    """Create DataExtractionEngine instance."""
    return DataExtractionEngine(max_memory_mb=100, enable_validation=True, chunk_size=10)


@pytest.fixture
def file_info(sample_jsonl_file):
    """Create JSONLFileInfo for sample file."""
    path = Path(sample_jsonl_file)
    stat = path.stat()

    return JSONLFileInfo(
        path=str(path),
        filename=path.name,
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_ctime),
        modified_at=datetime.fromtimestamp(stat.st_mtime),
        is_corrupt=False,
    )


class TestExtractionResult:
    """Test ExtractionResult data class."""

    def test_extraction_result_creation(self):
        """Test extraction result creation and properties."""
        start_time = datetime.now()

        result = ExtractionResult(
            extraction_id="test_extraction",
            start_time=start_time,
            end_time=start_time,
            file_path="/test/file.jsonl",
            total_lines_processed=100,
            total_lines_skipped=5,
        )

        assert result.success_rate == pytest.approx(95.238, rel=1e-2)  # 100/105 * 100
        assert result.extraction_duration_seconds == 0.0

    def test_add_error_and_warning(self):
        """Test error and warning addition."""
        result = ExtractionResult(
            extraction_id="test", start_time=datetime.now(), end_time=datetime.now(), file_path="/test/file.jsonl"
        )

        result.add_error("Test error")
        result.add_warning("Test warning")

        assert "Test error" in result.errors
        assert "Test warning" in result.warnings


class TestDataExtractionEngine:
    """Test DataExtractionEngine functionality."""

    @pytest.mark.asyncio
    async def test_basic_extraction(self, extraction_engine, file_info):
        """Test basic data extraction from JSONL file."""
        result = await extraction_engine.extract_from_file(file_info)

        assert result.total_sessions_found == 2  # session_1 and session_2
        assert result.total_lines_processed > 0
        assert len(result.sessions_extracted) == 2

        # Check session data
        session_1 = result.sessions_extracted.get("session_1")
        assert session_1 is not None
        assert session_1.reported_input_tokens == 15
        assert session_1.reported_output_tokens == 25
        assert session_1.reported_cache_creation_tokens == 5
        assert session_1.reported_cache_read_tokens == 3

        session_2 = result.sessions_extracted.get("session_2")
        assert session_2 is not None
        assert session_2.reported_input_tokens == 20
        assert session_2.reported_output_tokens == 30

    @pytest.mark.asyncio
    async def test_complex_schema_extraction(self, extraction_engine, complex_jsonl_file):
        """Test extraction from complex JSONL schema."""
        # Create file info for complex file
        path = Path(complex_jsonl_file)
        stat = path.stat()

        file_info = JSONLFileInfo(
            path=str(path),
            filename=path.name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_corrupt=False,
        )

        result = await extraction_engine.extract_from_file(file_info)

        assert result.total_sessions_found >= 2  # complex_session and another_session

        # Check that different session ID fields are recognized
        session_ids = list(result.sessions_extracted.keys())
        assert "complex_session" in session_ids
        assert "another_session" in session_ids

        # Check content categorization
        complex_session = result.sessions_extracted.get("complex_session")
        if complex_session:
            assert "system_tools" in complex_session.content_categories

    @pytest.mark.asyncio
    async def test_corrupted_file_handling(self, extraction_engine, corrupted_jsonl_file):
        """Test handling of corrupted JSONL entries."""
        path = Path(corrupted_jsonl_file)
        stat = path.stat()

        file_info = JSONLFileInfo(
            path=str(path),
            filename=path.name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_corrupt=False,
        )

        result = await extraction_engine.extract_from_file(file_info)

        # Should extract valid sessions despite corrupted entries
        assert result.total_sessions_found >= 1
        assert result.parsing_errors > 0  # Should detect parsing errors
        assert result.total_lines_skipped > 0  # Should skip invalid lines

        # Should still extract the valid session
        assert "valid_session" in result.sessions_extracted

    @pytest.mark.asyncio
    async def test_max_lines_limit(self, extraction_engine, file_info):
        """Test extraction with line limit."""
        result = await extraction_engine.extract_from_file(file_info, max_lines=2)

        assert result.total_lines_processed <= 2
        # May have fewer sessions if lines are limited
        assert result.total_sessions_found <= 2

    @pytest.mark.asyncio
    async def test_skip_corrupted_file(self, extraction_engine):
        """Test handling of files marked as corrupted."""
        file_info = JSONLFileInfo(
            path="/test/corrupted.jsonl",
            filename="corrupted.jsonl",
            size_bytes=100,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            is_corrupt=True,
            corruption_reason="Test corruption",
        )

        result = await extraction_engine.extract_from_file(file_info, skip_corrupted=False)

        assert len(result.errors) > 0
        assert any("corrupt" in error for error in result.errors)

    @pytest.mark.asyncio
    async def test_multiple_files_extraction(self, extraction_engine, file_info, complex_jsonl_file):
        """Test extraction from multiple files concurrently."""
        # Create second file info
        path2 = Path(complex_jsonl_file)
        stat2 = path2.stat()

        file_info_2 = JSONLFileInfo(
            path=str(path2),
            filename=path2.name,
            size_bytes=stat2.st_size,
            created_at=datetime.fromtimestamp(stat2.st_ctime),
            modified_at=datetime.fromtimestamp(stat2.st_mtime),
            is_corrupt=False,
        )

        files = [file_info, file_info_2]
        results = await extraction_engine.extract_from_multiple_files(files, max_concurrent=2)

        assert len(results) == 2

        # Check that both files were processed
        total_sessions = sum(r.total_sessions_found for r in results)
        assert total_sessions >= 3  # At least 3 different sessions across files

    @pytest.mark.asyncio
    async def test_schema_version_detection(self, extraction_engine, file_info):
        """Test schema version detection."""
        result = await extraction_engine.extract_from_file(file_info)

        # Should detect a schema version
        assert result.schema_version_detected is not None
        assert result.schema_version_detected in ["v1", "v2", "enhanced", "unknown"]

    @pytest.mark.asyncio
    async def test_content_categorization(self, extraction_engine, file_info):
        """Test content categorization functionality."""
        result = await extraction_engine.extract_from_file(file_info)

        # Check that content categories are populated
        for session_metrics in result.sessions_extracted.values():
            assert isinstance(session_metrics.content_categories, dict)
            assert "user_messages" in session_metrics.content_categories

    @pytest.mark.asyncio
    async def test_timestamp_extraction(self, extraction_engine, file_info):
        """Test timestamp extraction from entries."""
        result = await extraction_engine.extract_from_file(file_info)

        # Check that timestamps are extracted
        for session_metrics in result.sessions_extracted.values():
            # At least one of start_time or end_time should be set
            assert session_metrics.start_time is not None or session_metrics.end_time is not None

    @pytest.mark.asyncio
    async def test_bridge_format_conversion(self, extraction_engine, file_info):
        """Test conversion to bridge-compatible format."""
        result = await extraction_engine.extract_from_file(file_info)

        bridge_sessions = await extraction_engine.convert_to_bridge_format(result)

        assert len(bridge_sessions) == result.total_sessions_found

        for session in bridge_sessions:
            assert isinstance(session, SessionTokenMetrics)
            assert session.data_source == "historical_migration"
            assert session.files_processed == 1

    @pytest.mark.asyncio
    async def test_memory_management(self, extraction_engine):
        """Test memory management with large chunks."""
        # Create engine with very small memory limit
        small_memory_engine = DataExtractionEngine(max_memory_mb=1, chunk_size=5)  # Very small limit

        # Create a file that would exceed memory limit
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(100):
                entry = {
                    "session_id": f"session_{i}",
                    "type": "user",
                    "message": {"content": f"Long message content {i} " * 50},
                }
                f.write(json.dumps(entry) + "\n")

            file_path = f.name

        # Create file info
        path = Path(file_path)
        stat = path.stat()

        file_info = JSONLFileInfo(
            path=str(path),
            filename=path.name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_corrupt=False,
        )

        # Should handle memory limits gracefully
        result = await small_memory_engine.extract_from_file(file_info)

        # Should process some data even with memory constraints
        assert result.total_lines_processed > 0

        # Clean up
        Path(file_path).unlink()

    @pytest.mark.asyncio
    async def test_validation_enabled(self, extraction_engine, file_info):
        """Test validation when enabled."""
        # Create engine with validation enabled
        validating_engine = DataExtractionEngine(enable_validation=True)

        result = await validating_engine.extract_from_file(file_info)

        # Should complete without validation errors for valid data
        assert result.validation_errors == 0

    @pytest.mark.asyncio
    async def test_performance_metrics(self, extraction_engine, file_info):
        """Test performance metrics calculation."""
        result = await extraction_engine.extract_from_file(file_info)

        # Should have performance metrics
        assert result.processing_rate_lines_per_second >= 0
        assert result.extraction_duration_seconds >= 0

        if result.extraction_duration_seconds > 0:
            expected_rate = result.total_lines_processed / result.extraction_duration_seconds
            assert abs(result.processing_rate_lines_per_second - expected_rate) < 1


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, extraction_engine):
        """Test handling of nonexistent files."""
        file_info = JSONLFileInfo(
            path="/nonexistent/file.jsonl",
            filename="file.jsonl",
            size_bytes=0,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            is_corrupt=False,
        )

        result = await extraction_engine.extract_from_file(file_info)

        assert len(result.errors) > 0
        assert result.total_sessions_found == 0

    @pytest.mark.asyncio
    async def test_permission_denied(self, extraction_engine, sample_jsonl_file):
        """Test handling of permission denied errors."""
        from unittest.mock import patch

        path = Path(sample_jsonl_file)
        stat = path.stat()

        file_info = JSONLFileInfo(
            path=str(path),
            filename=path.name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            is_corrupt=False,
        )

        # Mock file open to raise permission error
        with patch("aiofiles.open", side_effect=PermissionError("Permission denied")):
            result = await extraction_engine.extract_from_file(file_info)

            assert len(result.errors) > 0
            assert any("Permission denied" in error or "failed" in error.lower() for error in result.errors)


if __name__ == "__main__":
    pytest.main([__file__])
