"""
Tests for Migration Engine

Integration tests for complete migration workflow including orchestration,
batch processing, progress tracking, error handling, and resume functionality.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.context_cleaner.migration.migration_engine import MigrationEngine, MigrationResult
from src.context_cleaner.migration.jsonl_discovery import JSONLDiscoveryService
from src.context_cleaner.migration.data_extraction import DataExtractionEngine
from src.context_cleaner.migration.progress_tracker import ProgressTracker
from src.context_cleaner.services.token_analysis_bridge import TokenAnalysisBridge
from src.context_cleaner.models.token_bridge_models import BridgeResult


@pytest.fixture
def sample_migration_data():
    """Create sample data directory for migration testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create multiple JSONL files with realistic data
        files_data = {
            "session_001.jsonl": [
                {
                    "session_id": "sess_001",
                    "type": "user",
                    "timestamp": "2024-01-01T10:00:00Z",
                    "message": {"content": "Hello, I need help with Python"},
                },
                {
                    "session_id": "sess_001",
                    "type": "assistant",
                    "timestamp": "2024-01-01T10:00:01Z",
                    "message": {
                        "content": "I'd be happy to help you with Python!",
                        "usage": {"input_tokens": 25, "output_tokens": 35},
                    },
                },
                {
                    "session_id": "sess_001",
                    "type": "user",
                    "timestamp": "2024-01-01T10:01:00Z",
                    "message": {"content": "How do I create a list?"},
                },
                {
                    "session_id": "sess_001",
                    "type": "assistant",
                    "timestamp": "2024-01-01T10:01:01Z",
                    "message": {
                        "content": "You can create a list using square brackets: my_list = [1, 2, 3]",
                        "usage": {"input_tokens": 15, "output_tokens": 45},
                    },
                },
            ],
            "session_002.jsonl": [
                {
                    "session_id": "sess_002",
                    "type": "user",
                    "timestamp": "2024-01-01T11:00:00Z",
                    "message": {"content": "What's machine learning?"},
                },
                {
                    "session_id": "sess_002",
                    "type": "assistant",
                    "timestamp": "2024-01-01T11:00:01Z",
                    "message": {
                        "content": "Machine learning is a subset of AI...",
                        "usage": {"input_tokens": 20, "output_tokens": 100},
                    },
                },
            ],
            "session_003.jsonl": [
                {
                    "session_id": "sess_003",
                    "type": "user",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "message": {"content": "Explain neural networks"},
                },
                {
                    "session_id": "sess_003",
                    "type": "assistant",
                    "timestamp": "2024-01-01T12:00:01Z",
                    "message": {
                        "content": "Neural networks are computing systems inspired by biological neural networks...",
                        "usage": {"input_tokens": 30, "output_tokens": 200},
                    },
                },
            ],
        }

        for filename, content in files_data.items():
            file_path = tmpdir_path / filename
            with open(file_path, "w") as f:
                for entry in content:
                    f.write(json.dumps(entry) + "\n")

        yield tmpdir_path


@pytest.fixture
def mock_bridge_service():
    """Create mock bridge service."""
    bridge = Mock(spec=TokenAnalysisBridge)

    # Mock successful bulk store
    async def mock_bulk_store(sessions, batch_size=None):
        return [
            BridgeResult(
                success=True,
                operation_type="bulk_store_sessions",
                records_stored=len(sessions),
                total_tokens=sum(s.calculated_total_tokens for s in sessions),
            )
        ]

    bridge.bulk_store_sessions = AsyncMock(side_effect=mock_bulk_store)

    # Mock health check
    bridge.health_check = AsyncMock(return_value=Mock(is_healthy=lambda: True))

    return bridge


@pytest.fixture
def migration_engine(mock_bridge_service):
    """Create migration engine with mocked dependencies."""
    discovery_service = JSONLDiscoveryService()
    extraction_engine = DataExtractionEngine()
    progress_tracker = ProgressTracker()

    return MigrationEngine(
        bridge_service=mock_bridge_service,
        discovery_service=discovery_service,
        extraction_engine=extraction_engine,
        progress_tracker=progress_tracker,
        batch_size=10,
        max_concurrent_files=2,
        checkpoint_interval_files=2,
    )


class TestMigrationResult:
    """Test MigrationResult data class."""

    def test_migration_result_creation(self):
        """Test migration result creation and properties."""
        start_time = datetime.now()

        result = MigrationResult(
            migration_id="test_migration",
            migration_type="historical",
            start_time=start_time,
            end_time=start_time,
            total_files_discovered=10,
            total_files_processed=8,
            files_succeeded=7,
            files_failed=1,
        )

        assert result.completion_percentage == 80.0  # 8/10 * 100
        assert not result.success  # Has failed files

    def test_migration_result_success_conditions(self):
        """Test success condition evaluation."""
        start_time = datetime.now()

        # Successful migration
        successful_result = MigrationResult(
            migration_id="test_migration",
            migration_type="historical",
            start_time=start_time,
            end_time=start_time,
            files_failed=0,
            failed_bridges=0,
            validation_passed=True,
        )

        assert successful_result.success

        # Failed migration (has errors)
        failed_result = MigrationResult(
            migration_id="test_migration",
            migration_type="historical",
            start_time=start_time,
            end_time=start_time,
            files_failed=1,
            failed_bridges=0,
            validation_passed=True,
        )

        assert not failed_result.success


class TestMigrationEngine:
    """Test MigrationEngine functionality."""

    @pytest.mark.asyncio
    async def test_basic_historical_migration(self, migration_engine, sample_migration_data):
        """Test basic historical data migration."""
        # Track progress updates
        progress_updates = []

        def progress_callback(progress):
            progress_updates.append(progress.current_phase)

        result = await migration_engine.migrate_all_historical_data(
            source_directories=[str(sample_migration_data)], progress_callback=progress_callback
        )

        # Check migration completed
        assert result.migration_type == "historical"
        assert result.total_files_discovered >= 3  # Our sample files
        assert result.total_files_processed > 0
        assert result.total_sessions_created >= 3  # At least 3 sessions
        assert result.total_tokens_migrated > 0

        # Check progress phases were executed
        assert "discovery" in progress_updates
        assert "processing" in progress_updates

        # Check performance metrics
        assert result.processing_duration_seconds >= 0
        assert result.average_processing_rate_files_per_minute >= 0

    @pytest.mark.asyncio
    async def test_dry_run_migration(self, migration_engine, sample_migration_data):
        """Test dry run migration (no actual data storage)."""
        result = await migration_engine.migrate_all_historical_data(
            source_directories=[str(sample_migration_data)], dry_run=True
        )

        # Should process files but not store data
        assert result.total_files_processed > 0
        assert result.total_sessions_created >= 0

        # Bridge service should not have been called for storage
        migration_engine.bridge_service.bulk_store_sessions.assert_not_called()

    @pytest.mark.asyncio
    async def test_incremental_migration(self, migration_engine, sample_migration_data):
        """Test incremental migration functionality."""
        # Set since date to recent time
        since_date = datetime.now()

        result = await migration_engine.migrate_incremental_changes(
            since=since_date, source_directories=[str(sample_migration_data)]
        )

        assert result.migration_type == "incremental"
        # May have fewer files if filtering by date
        assert result.total_files_discovered >= 0

    @pytest.mark.asyncio
    async def test_migration_with_filters(self, migration_engine, sample_migration_data):
        """Test migration with filtering criteria."""
        filter_criteria = {"min_size_mb": 0.001, "max_size_mb": 1.0}  # 1KB minimum  # 1MB maximum

        result = await migration_engine.migrate_all_historical_data(
            source_directories=[str(sample_migration_data)], filter_criteria=filter_criteria
        )

        assert result.total_files_discovered >= 0
        # All discovered files should meet filter criteria

    @pytest.mark.asyncio
    async def test_batch_processing(self, migration_engine, sample_migration_data):
        """Test batch processing functionality."""
        # Use small batch size to ensure batching
        migration_engine.batch_size = 2
        migration_engine.max_concurrent_files = 1

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should still process all files successfully
        assert result.files_succeeded > 0
        assert result.files_failed == 0

    @pytest.mark.asyncio
    async def test_checkpoint_creation(self, migration_engine, sample_migration_data):
        """Test checkpoint creation during migration."""
        # Set short checkpoint interval
        migration_engine.checkpoint_interval_files = 1

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should have created checkpoints
        assert result.checkpoints_created > 0
        assert result.final_checkpoint_id is not None

    @pytest.mark.asyncio
    async def test_error_handling_invalid_directory(self, migration_engine):
        """Test error handling with invalid source directory."""
        result = await migration_engine.migrate_all_historical_data(source_directories=["/nonexistent/directory"])

        # Should handle error gracefully
        assert result.total_files_discovered == 0
        # May have warnings about nonexistent directory

    @pytest.mark.asyncio
    async def test_bridge_service_failure(self, migration_engine, sample_migration_data):
        """Test handling of bridge service failures."""

        # Mock bridge service to fail
        async def failing_bulk_store(sessions, batch_size=None):
            raise Exception("Bridge storage failed")

        migration_engine.bridge_service.bulk_store_sessions = AsyncMock(side_effect=failing_bulk_store)

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should record errors but continue processing
        assert len(result.errors) > 0
        assert not result.success

    @pytest.mark.asyncio
    async def test_memory_management(self, migration_engine, sample_migration_data):
        """Test memory management during migration."""
        # Set low memory limit
        migration_engine.max_memory_mb = 50

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should complete despite memory constraints
        assert result.total_files_processed > 0
        assert result.peak_memory_usage_mb > 0

    @pytest.mark.asyncio
    async def test_concurrent_file_processing(self, migration_engine, sample_migration_data):
        """Test concurrent file processing."""
        # Enable multiple concurrent files
        migration_engine.max_concurrent_files = 3

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should process files efficiently
        assert result.files_succeeded > 0
        assert result.average_processing_rate_files_per_minute > 0

    @pytest.mark.asyncio
    async def test_validation_phase(self, migration_engine, sample_migration_data):
        """Test validation phase execution."""
        # Enable validation
        migration_engine.enable_validation = True

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should have validation results
        assert isinstance(result.validation_passed, bool)
        assert result.data_integrity_score >= 0

    @pytest.mark.asyncio
    async def test_migration_status_tracking(self, migration_engine, sample_migration_data):
        """Test migration status tracking."""
        # Start migration in background
        migration_task = asyncio.create_task(
            migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])
        )

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Check status
        if migration_engine.current_migration:
            status = await migration_engine.get_migration_status(migration_engine.current_migration.migration_id)
            assert status is not None
            assert "migration_result" in status

        # Wait for completion
        result = await migration_task
        assert result.total_files_processed > 0


class TestResumeCapability:
    """Test migration resume capability."""

    @pytest.mark.asyncio
    async def test_checkpoint_loading(self, migration_engine):
        """Test checkpoint loading functionality."""
        # Test loading non-existent checkpoint
        checkpoints = await migration_engine.list_available_checkpoints()
        assert isinstance(checkpoints, list)

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self, migration_engine, sample_migration_data):
        """Test resuming migration from checkpoint."""
        # First, run partial migration to create checkpoint
        migration_engine.checkpoint_interval_files = 1

        # Start migration
        result1 = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        if result1.final_checkpoint_id:
            # Try to resume from checkpoint
            result2 = await migration_engine.migrate_all_historical_data(
                source_directories=[str(sample_migration_data)], resume_from_checkpoint=result1.final_checkpoint_id
            )

            assert result2.migration_type == "historical"


class TestPerformance:
    """Test migration performance characteristics."""

    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, migration_engine):
        """Test performance with larger dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create larger dataset
            num_files = 10
            sessions_per_file = 50

            for file_idx in range(num_files):
                file_path = tmpdir_path / f"large_session_{file_idx:03d}.jsonl"
                with open(file_path, "w") as f:
                    for session_idx in range(sessions_per_file):
                        session_id = f"session_{file_idx}_{session_idx}"

                        # User message
                        user_entry = {
                            "session_id": session_id,
                            "type": "user",
                            "timestamp": "2024-01-01T10:00:00Z",
                            "message": {"content": f"User message {session_idx} with some content"},
                        }
                        f.write(json.dumps(user_entry) + "\n")

                        # Assistant message
                        assistant_entry = {
                            "session_id": session_id,
                            "type": "assistant",
                            "timestamp": "2024-01-01T10:00:01Z",
                            "message": {
                                "content": f"Assistant response {session_idx} with detailed explanation",
                                "usage": {"input_tokens": 20 + session_idx, "output_tokens": 50 + session_idx},
                            },
                        }
                        f.write(json.dumps(assistant_entry) + "\n")

            # Run migration and measure performance
            start_time = datetime.now()

            result = await migration_engine.migrate_all_historical_data(source_directories=[str(tmpdir_path)])

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Performance assertions
            assert result.total_files_processed == num_files
            assert result.total_sessions_created == num_files * sessions_per_file
            assert duration < 60  # Should complete within 1 minute
            assert result.average_processing_rate_files_per_minute > 0

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, migration_engine):
        """Test memory efficiency with large files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create single large file
            large_file = tmpdir_path / "large_file.jsonl"
            with open(large_file, "w") as f:
                for i in range(5000):  # 5000 entries
                    entry = {
                        "session_id": f"session_{i % 100}",  # 100 different sessions
                        "type": "user" if i % 2 == 0 else "assistant",
                        "timestamp": "2024-01-01T10:00:00Z",
                        "message": {
                            "content": f"Message content {i} " * 20,  # Longer content
                            "usage": {"input_tokens": i, "output_tokens": i + 10} if i % 2 == 1 else None,
                        },
                    }
                    f.write(json.dumps(entry) + "\n")

            # Monitor memory usage
            import psutil

            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            result = await migration_engine.migrate_all_historical_data(source_directories=[str(tmpdir_path)])

            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = memory_after - memory_before

            # Should process successfully with reasonable memory usage
            assert result.total_files_processed == 1
            assert result.total_sessions_created == 100  # 100 unique sessions
            assert memory_increase < 200  # Should not use more than 200MB additional


class TestErrorRecovery:
    """Test error recovery and resilience."""

    @pytest.mark.asyncio
    async def test_partial_file_failure(self, migration_engine, sample_migration_data):
        """Test handling when some files fail to process."""
        # Create a corrupted file
        corrupted_file = sample_migration_data / "corrupted.jsonl"
        with open(corrupted_file, "w") as f:
            f.write("invalid json line\n")
            f.write('{"valid": "entry"}\n')
            f.write("another invalid line\n")

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(sample_migration_data)])

        # Should process valid files and handle corrupted ones
        assert result.total_files_processed > 0
        # May have some successful and some failed files
        assert result.files_succeeded + result.files_failed == result.total_files_processed

    @pytest.mark.asyncio
    async def test_cleanup_after_error(self, migration_engine):
        """Test cleanup after migration errors."""
        # Test with invalid directory
        result = await migration_engine.migrate_all_historical_data(source_directories=["/invalid/path"])

        # Should complete gracefully even with errors
        assert result.end_time is not None
        assert result.processing_duration_seconds >= 0


if __name__ == "__main__":
    pytest.main([__file__])
