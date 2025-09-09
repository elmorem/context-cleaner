"""
Tests for JSONL Discovery Service

Unit tests for filesystem scanning, file inventory, integrity checking,
and manifest generation functionality.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.context_cleaner.migration.jsonl_discovery import JSONLDiscoveryService, JSONLFileInfo, FileDiscoveryResult


@pytest.fixture
def temp_directory():
    """Create temporary directory with sample JSONL files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create sample JSONL files
        samples = {
            "session1.jsonl": [
                {"session_id": "sess_1", "type": "user", "message": {"content": "Hello"}},
                {
                    "session_id": "sess_1",
                    "type": "assistant",
                    "message": {"content": "Hi there", "usage": {"input_tokens": 10, "output_tokens": 15}},
                },
            ],
            "session2.jsonl": [
                {"session_id": "sess_2", "type": "user", "message": {"content": "How are you?"}},
                {
                    "session_id": "sess_2",
                    "type": "assistant",
                    "message": {"content": "I'm doing well", "usage": {"input_tokens": 12, "output_tokens": 18}},
                },
            ],
            "large_session.jsonl": [
                {"session_id": f"sess_large_{i}", "type": "user", "message": {"content": f"Message {i}"}}
                for i in range(1000)
            ],
            "corrupted.jsonl": ["invalid json", '{"valid": "json"}', "another invalid line"],
            "empty.jsonl": [],
        }

        for filename, content in samples.items():
            file_path = tmpdir_path / filename
            with open(file_path, "w") as f:
                for item in content:
                    if isinstance(item, dict):
                        f.write(json.dumps(item) + "\n")
                    else:
                        f.write(item + "\n")

        # Create subdirectory with more files
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()

        with open(subdir / "nested.jsonl", "w") as f:
            f.write('{"session_id": "nested_session", "type": "user", "message": {"content": "Nested file"}}\n')

        yield tmpdir_path


@pytest.fixture
def discovery_service():
    """Create JSONLDiscoveryService instance."""
    return JSONLDiscoveryService(enable_integrity_check=True, enable_content_analysis=True)


class TestJSONLFileInfo:
    """Test JSONLFileInfo data class."""

    def test_file_info_creation(self):
        """Test JSONLFileInfo creation and properties."""
        now = datetime.now()
        file_info = JSONLFileInfo(
            path="/test/file.jsonl",
            filename="file.jsonl",
            size_bytes=1024 * 1024,  # 1MB
            created_at=now,
            modified_at=now,
            estimated_tokens=1000,
        )

        assert file_info.size_mb == 1.0
        assert file_info.age_days == 0
        assert file_info.estimated_tokens == 1000

    def test_file_info_serialization(self):
        """Test file info to_dict conversion."""
        now = datetime.now()
        file_info = JSONLFileInfo(
            path="/test/file.jsonl", filename="file.jsonl", size_bytes=1024, created_at=now, modified_at=now
        )

        data = file_info.to_dict()

        assert data["path"] == "/test/file.jsonl"
        assert data["filename"] == "file.jsonl"
        assert data["size_bytes"] == 1024
        assert "created_at" in data
        assert "modified_at" in data


class TestFileDiscoveryResult:
    """Test FileDiscoveryResult data class."""

    def test_discovery_result_creation(self):
        """Test discovery result creation and properties."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=10)

        result = FileDiscoveryResult(
            discovery_id="test_discovery",
            start_time=start_time,
            end_time=end_time,
            search_paths=["/test/path"],
            total_files_found=5,
            total_size_bytes=5000,
        )

        assert result.total_size_mb == pytest.approx(0.0048, rel=1e-2)
        assert result.discovery_duration_seconds == 10.0

    def test_add_error_and_warning(self):
        """Test error and warning addition."""
        result = FileDiscoveryResult(
            discovery_id="test", start_time=datetime.now(), end_time=datetime.now(), search_paths=[]
        )

        result.add_error("Test error")
        result.add_warning("Test warning")

        assert "Test error" in result.errors
        assert "Test warning" in result.warnings


class TestJSONLDiscoveryService:
    """Test JSONLDiscoveryService functionality."""

    @pytest.mark.asyncio
    async def test_basic_discovery(self, discovery_service, temp_directory):
        """Test basic file discovery functionality."""
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

        assert result.total_files_found >= 5  # At least our sample files
        assert result.total_size_bytes > 0
        assert len(result.processing_manifest) == result.total_files_found

    @pytest.mark.asyncio
    async def test_discovery_with_filters(self, discovery_service, temp_directory):
        """Test discovery with filtering criteria."""
        filter_criteria = {"min_size_mb": 0.001, "max_size_mb": 0.1}  # 1KB minimum  # 100KB maximum

        result = await discovery_service.discover_files(
            search_paths=[str(temp_directory)], filter_criteria=filter_criteria
        )

        # Should exclude empty files and very large files
        for file_info in result.processing_manifest:
            assert file_info.size_mb >= 0.001
            assert file_info.size_mb <= 0.1

    @pytest.mark.asyncio
    async def test_discovery_with_max_files(self, discovery_service, temp_directory):
        """Test discovery with file limit."""
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)], max_files=2)

        assert result.total_files_found <= 2
        assert len(result.processing_manifest) <= 2

    @pytest.mark.asyncio
    async def test_recursive_discovery(self, discovery_service, temp_directory):
        """Test recursive directory scanning."""
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

        # Should find files in subdirectories
        nested_files = [f for f in result.processing_manifest if "nested" in f.filename]
        assert len(nested_files) > 0

    @pytest.mark.asyncio
    async def test_content_analysis(self, discovery_service, temp_directory):
        """Test file content analysis and estimation."""
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

        # Check that content analysis was performed
        for file_info in result.processing_manifest:
            if file_info.size_bytes > 0:  # Skip empty files
                assert file_info.estimated_lines >= 0
                assert file_info.estimated_sessions >= 0
                assert file_info.estimated_tokens >= 0

    @pytest.mark.asyncio
    async def test_integrity_checking(self, discovery_service, temp_directory):
        """Test file integrity checking."""
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

        # Check for corrupt files
        corrupt_files = [f for f in result.processing_manifest if f.is_corrupt]
        assert len(corrupt_files) > 0  # Should detect corrupted.jsonl

        # Check file hashes are calculated
        healthy_files = [f for f in result.processing_manifest if not f.is_corrupt and f.size_bytes > 0]
        assert all(f.file_hash is not None for f in healthy_files)

    @pytest.mark.asyncio
    async def test_file_categorization(self, discovery_service, temp_directory):
        """Test file categorization and prioritization."""
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

        # Check that files are categorized
        assert len(result.files_by_priority) > 0
        assert len(result.files_by_group) > 0

        # Check processing order
        assert len(result.processing_manifest) > 0
        for file_info in result.processing_manifest:
            assert file_info.processing_priority >= 0
            assert file_info.processing_group is not None

    @pytest.mark.asyncio
    async def test_sorting_options(self, discovery_service, temp_directory):
        """Test different sorting options."""
        # Test size-based sorting
        result_size = await discovery_service.discover_files(search_paths=[str(temp_directory)], sort_by="size_desc")

        # Check that files are sorted by size (descending)
        sizes = [f.size_bytes for f in result_size.processing_manifest]
        assert sizes == sorted(sizes, reverse=True)

        # Test priority-based sorting
        result_priority = await discovery_service.discover_files(
            search_paths=[str(temp_directory)], sort_by="priority_asc"
        )

        # Check that files are sorted by priority (ascending)
        priorities = [f.processing_priority for f in result_priority.processing_manifest]
        assert all(priorities[i] <= priorities[i + 1] for i in range(len(priorities) - 1))

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, discovery_service):
        """Test discovery with nonexistent directory."""
        result = await discovery_service.discover_files(search_paths=["/nonexistent/path"])

        assert result.total_files_found == 0
        assert len(result.warnings) > 0
        assert any("does not exist" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_manifest_save_and_load(self, discovery_service, temp_directory):
        """Test manifest saving and loading."""
        # Perform discovery
        result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

        # Save manifest
        manifest_path = temp_directory / "manifest.json"
        success = await discovery_service.save_manifest(result, str(manifest_path))
        assert success
        assert manifest_path.exists()

        # Load manifest
        loaded_result = await discovery_service.load_manifest(str(manifest_path))
        assert loaded_result is not None
        assert loaded_result.discovery_id == result.discovery_id
        assert loaded_result.total_files_found == result.total_files_found

    @pytest.mark.asyncio
    async def test_error_handling(self, discovery_service, temp_directory):
        """Test error handling during discovery."""
        # Create a file that simulates permission error
        restricted_file = temp_directory / "restricted.jsonl"
        restricted_file.write_text('{"test": "data"}')

        # Mock file operations to raise permission error
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = await discovery_service.discover_files(search_paths=[str(temp_directory)])

            # Should handle errors gracefully
            assert len(result.errors) > 0 or len(result.warnings) > 0


class TestPerformance:
    """Test discovery performance with larger datasets."""

    @pytest.mark.asyncio
    async def test_large_directory_performance(self, discovery_service):
        """Test performance with many files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create many small files
            num_files = 100
            for i in range(num_files):
                file_path = tmpdir_path / f"file_{i:03d}.jsonl"
                with open(file_path, "w") as f:
                    f.write(f'{{"session_id": "session_{i}", "type": "user", "message": {{"content": "Test {i}"}}}}\n')

            # Time the discovery
            start_time = datetime.now()
            result = await discovery_service.discover_files(search_paths=[str(tmpdir_path)])
            end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            assert result.total_files_found == num_files
            assert duration < 30  # Should complete within 30 seconds

            # Check performance metrics
            files_per_second = num_files / duration if duration > 0 else float("inf")
            assert files_per_second > 1  # At least 1 file per second

    @pytest.mark.asyncio
    async def test_memory_usage_with_large_files(self, discovery_service):
        """Test memory usage with large files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a large file
            large_file = tmpdir_path / "large.jsonl"
            with open(large_file, "w") as f:
                # Write 10,000 lines
                for i in range(10000):
                    entry = {
                        "session_id": f"session_{i % 100}",
                        "type": "user" if i % 2 == 0 else "assistant",
                        "message": {
                            "content": f"This is a longer message content for line {i} " * 10,
                            "usage": {"input_tokens": i, "output_tokens": i + 10} if i % 2 == 1 else None,
                        },
                    }
                    f.write(json.dumps(entry) + "\n")

            # Monitor memory during discovery
            import psutil

            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            result = await discovery_service.discover_files(search_paths=[str(tmpdir_path)])

            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = memory_after - memory_before

            assert result.total_files_found == 1
            assert memory_increase < 100  # Should not use more than 100MB additional memory


if __name__ == "__main__":
    pytest.main([__file__])
