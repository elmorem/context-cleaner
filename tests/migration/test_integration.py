"""
Integration Tests for Migration System

End-to-end integration tests covering complete migration workflows,
CLI command integration, database integration, and performance testing
with realistic data scenarios.
"""

import pytest
import asyncio
import tempfile
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.context_cleaner.migration import (
    JSONLDiscoveryService,
    DataExtractionEngine,
    MigrationEngine,
    ProgressTracker,
    MigrationValidator,
)
from src.context_cleaner.services.token_analysis_bridge import TokenAnalysisBridge
from src.context_cleaner.models.token_bridge_models import BridgeResult


@pytest.fixture
def realistic_dataset():
    """Create realistic dataset for integration testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create realistic JSONL files simulating actual Claude Code sessions
        datasets = {
            "coding_session_001.jsonl": [
                {
                    "session_id": "coding_001",
                    "type": "user",
                    "timestamp": "2024-01-15T09:00:00Z",
                    "message": {"content": "I need help creating a Python script to analyze CSV files"},
                },
                {
                    "session_id": "coding_001",
                    "type": "assistant",
                    "timestamp": "2024-01-15T09:00:05Z",
                    "message": {
                        "content": "I'd be happy to help you create a Python script for CSV analysis! Here's a comprehensive script using pandas...",
                        "usage": {
                            "input_tokens": 45,
                            "output_tokens": 280,
                            "cache_creation_input_tokens": 15,
                            "cache_read_input_tokens": 8,
                        },
                    },
                },
                {
                    "session_id": "coding_001",
                    "type": "user",
                    "timestamp": "2024-01-15T09:05:00Z",
                    "message": {"content": "Can you add error handling and make it more robust?"},
                },
                {
                    "session_id": "coding_001",
                    "type": "assistant",
                    "timestamp": "2024-01-15T09:05:10Z",
                    "message": {
                        "content": "Absolutely! Here's the enhanced version with comprehensive error handling...",
                        "usage": {
                            "input_tokens": 325,  # Includes previous context
                            "output_tokens": 420,
                            "cache_read_input_tokens": 200,
                        },
                    },
                },
            ],
            "mcp_tools_session.jsonl": [
                {
                    "session_id": "mcp_tools_001",
                    "type": "user",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "message": {
                        "content": "Can you help me analyze this repository structure using the filesystem tools?"
                    },
                },
                {
                    "session_id": "mcp_tools_001",
                    "type": "assistant",
                    "timestamp": "2024-01-15T10:00:02Z",
                    "message": {
                        "content": "I'll help you analyze the repository structure using the MCP filesystem tools.",
                        "usage": {"input_tokens": 35, "output_tokens": 85},
                    },
                    "tool_calls": [
                        {"name": "mcp__filesystem__list_directory", "arguments": {"path": "/project"}},
                        {"name": "mcp__filesystem__read_file", "arguments": {"path": "/project/README.md"}},
                    ],
                },
                {
                    "session_id": "mcp_tools_001",
                    "type": "tool_result",
                    "timestamp": "2024-01-15T10:00:03Z",
                    "message": {
                        "content": "Directory listing and README content...",
                        "tool_result": {
                            "files": ["README.md", "src/", "tests/", "package.json"],
                            "readme_content": "# Project Repository...",
                        },
                    },
                },
                {
                    "session_id": "mcp_tools_001",
                    "type": "assistant",
                    "timestamp": "2024-01-15T10:00:05Z",
                    "message": {
                        "content": "Based on the repository structure analysis, here's what I found...",
                        "usage": {"input_tokens": 150, "output_tokens": 300, "cache_creation_input_tokens": 50},
                    },
                },
            ],
            "large_conversation.jsonl": [],  # Will be populated with large dataset
        }

        # Create large conversation for performance testing
        large_conversation = []
        for i in range(200):  # 200 exchanges = 400 total entries
            # User message
            user_msg = {
                "session_id": "large_conv_001",
                "type": "user",
                "timestamp": f"2024-01-15T{10 + (i//60):02d}:{i%60:02d}:00Z",
                "message": {
                    "content": f"This is user message {i} in a long conversation about technical topics. "
                    + "It discusses various aspects of software development, debugging techniques, and best practices. "
                    * 3
                },
            }
            large_conversation.append(user_msg)

            # Assistant message
            assistant_msg = {
                "session_id": "large_conv_001",
                "type": "assistant",
                "timestamp": f"2024-01-15T{10 + (i//60):02d}:{i%60:02d}:05Z",
                "message": {
                    "content": f"Assistant response {i} providing detailed technical explanation. "
                    + "This response covers multiple concepts, includes code examples, and provides comprehensive guidance. "
                    * 5,
                    "usage": {
                        "input_tokens": 100 + (i * 2),  # Growing context
                        "output_tokens": 200 + (i * 3),
                        "cache_creation_input_tokens": 10 if i % 10 == 0 else 0,
                        "cache_read_input_tokens": min(50, i * 2),
                    },
                },
            }
            large_conversation.append(assistant_msg)

        datasets["large_conversation.jsonl"] = large_conversation

        # Write all datasets to files
        for filename, content in datasets.items():
            file_path = tmpdir_path / filename
            with open(file_path, "w", encoding="utf-8") as f:
                for entry in content:
                    f.write(json.dumps(entry) + "\n")

        # Create subdirectory with additional files
        subdir = tmpdir_path / "archived_sessions"
        subdir.mkdir()

        archived_session = [
            {
                "session_id": "archived_001",
                "type": "user",
                "timestamp": "2023-12-01T15:00:00Z",
                "message": {"content": "Old conversation from last year"},
            },
            {
                "session_id": "archived_001",
                "type": "assistant",
                "timestamp": "2023-12-01T15:00:05Z",
                "message": {
                    "content": "This is an archived conversation.",
                    "usage": {"input_tokens": 25, "output_tokens": 40},
                },
            },
        ]

        with open(subdir / "archived_001.jsonl", "w") as f:
            for entry in archived_session:
                f.write(json.dumps(entry) + "\n")

        yield tmpdir_path


@pytest.fixture
def mock_bridge_with_stats():
    """Create comprehensive mock bridge service with statistics."""
    bridge = Mock(spec=TokenAnalysisBridge)

    # Track storage calls for validation
    stored_sessions = []

    async def mock_bulk_store(sessions, batch_size=None):
        stored_sessions.extend(sessions)
        return [
            BridgeResult(
                success=True,
                operation_type="bulk_store_sessions",
                records_stored=len(sessions),
                total_tokens=sum(s.calculated_total_tokens for s in sessions),
                processing_time_seconds=0.1,
            )
        ]

    bridge.bulk_store_sessions = AsyncMock(side_effect=mock_bulk_store)
    bridge.stored_sessions = stored_sessions

    # Mock health check
    health_status = Mock()
    health_status.is_healthy.return_value = True
    health_status.database_connected = True
    health_status.recent_success_rate = 100.0

    bridge.health_check = AsyncMock(return_value=health_status)

    # Mock statistics
    async def mock_get_stats():
        return {
            "total_sessions": len(stored_sessions),
            "total_tokens": sum(s.calculated_total_tokens for s in stored_sessions),
        }

    bridge._get_storage_statistics = AsyncMock(side_effect=mock_get_stats)

    return bridge


class TestEndToEndMigration:
    """End-to-end migration workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_migration_workflow(self, realistic_dataset, mock_bridge_with_stats):
        """Test complete migration workflow from discovery to validation."""

        # Initialize services
        discovery_service = JSONLDiscoveryService(enable_integrity_check=True, enable_content_analysis=True)

        extraction_engine = DataExtractionEngine(max_memory_mb=200, enable_validation=True)

        progress_tracker = ProgressTracker()

        migration_engine = MigrationEngine(
            bridge_service=mock_bridge_with_stats,
            discovery_service=discovery_service,
            extraction_engine=extraction_engine,
            progress_tracker=progress_tracker,
            batch_size=50,
            max_concurrent_files=2,
        )

        validator = MigrationValidator(bridge_service=mock_bridge_with_stats)

        # Track progress updates
        progress_phases = []

        def track_progress(progress):
            if progress.current_phase not in progress_phases:
                progress_phases.append(progress.current_phase)

        # Step 1: Discovery
        discovery_result = await discovery_service.discover_files(search_paths=[str(realistic_dataset)])

        assert discovery_result.total_files_found >= 4  # Our test files
        assert discovery_result.estimated_total_tokens > 0

        # Step 2: Migration
        migration_result = await migration_engine.migrate_all_historical_data(
            source_directories=[str(realistic_dataset)], progress_callback=track_progress
        )

        # Verify migration results
        assert migration_result.success
        assert migration_result.total_files_processed >= 4
        assert migration_result.total_sessions_created >= 4  # At least 4 different sessions
        assert migration_result.total_tokens_migrated > 0

        # Verify progress tracking
        expected_phases = ["discovery", "processing", "validation", "finalization"]
        for phase in expected_phases:
            assert phase in progress_phases

        # Step 3: Validation
        validation_result = await validator.validate_migration_integrity(sample_size=10, verify_counts=True)

        assert validation_result.validation_passed
        assert validation_result.sessions_validated > 0

        # Verify bridge service was called appropriately
        assert len(mock_bridge_with_stats.stored_sessions) > 0
        mock_bridge_with_stats.bulk_store_sessions.assert_called()

    @pytest.mark.asyncio
    async def test_large_dataset_migration(self, realistic_dataset, mock_bridge_with_stats):
        """Test migration with large dataset (performance test)."""

        migration_engine = MigrationEngine(
            bridge_service=mock_bridge_with_stats, batch_size=100, max_concurrent_files=3, max_memory_mb=300
        )

        start_time = datetime.now()

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(realistic_dataset)])

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Performance assertions
        assert result.success
        assert duration < 120  # Should complete within 2 minutes
        assert result.average_processing_rate_tokens_per_second > 100  # At least 100 tokens/second
        assert result.peak_memory_usage_mb < 400  # Should stay under memory limit

        # Check that large conversation was processed
        large_session = next(
            (s for s in mock_bridge_with_stats.stored_sessions if s.session_id == "large_conv_001"), None
        )
        assert large_session is not None
        assert large_session.calculated_total_tokens > 10000  # Large conversation should have many tokens

    @pytest.mark.asyncio
    async def test_incremental_migration_workflow(self, realistic_dataset, mock_bridge_with_stats):
        """Test incremental migration after initial full migration."""

        migration_engine = MigrationEngine(bridge_service=mock_bridge_with_stats, batch_size=50)

        # First migration (historical)
        result1 = await migration_engine.migrate_all_historical_data(source_directories=[str(realistic_dataset)])

        assert result1.success
        initial_sessions = len(mock_bridge_with_stats.stored_sessions)

        # Add new file for incremental migration
        new_file = realistic_dataset / "new_session.jsonl"
        new_data = [
            {
                "session_id": "new_session_001",
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "message": {"content": "New conversation after initial migration"},
            },
            {
                "session_id": "new_session_001",
                "type": "assistant",
                "timestamp": (datetime.now() + timedelta(seconds=5)).isoformat(),
                "message": {
                    "content": "Response to new conversation",
                    "usage": {"input_tokens": 30, "output_tokens": 50},
                },
            },
        ]

        with open(new_file, "w") as f:
            for entry in new_data:
                f.write(json.dumps(entry) + "\n")

        # Incremental migration
        result2 = await migration_engine.migrate_incremental_changes(
            since=datetime.now() - timedelta(minutes=5), source_directories=[str(realistic_dataset)]
        )

        # Should have processed the new file
        assert result2.migration_type == "incremental"
        final_sessions = len(mock_bridge_with_stats.stored_sessions)
        assert final_sessions > initial_sessions  # Should have new session

    @pytest.mark.asyncio
    async def test_error_recovery_and_resume(self, realistic_dataset, mock_bridge_with_stats):
        """Test error recovery and migration resume functionality."""

        progress_tracker = ProgressTracker()

        migration_engine = MigrationEngine(
            bridge_service=mock_bridge_with_stats,
            progress_tracker=progress_tracker,
            checkpoint_interval_files=2,
            enable_resume=True,
        )

        # Start migration
        result = await migration_engine.migrate_all_historical_data(source_directories=[str(realistic_dataset)])

        # Should have created checkpoints
        assert result.checkpoints_created > 0

        # List available checkpoints
        checkpoints = await migration_engine.list_available_checkpoints()
        assert len(checkpoints) > 0

        # Test resume functionality (simulate resume from last checkpoint)
        if result.final_checkpoint_id:
            # Clear stored sessions to simulate fresh start
            mock_bridge_with_stats.stored_sessions.clear()

            # Resume migration
            resume_result = await migration_engine.migrate_all_historical_data(
                source_directories=[str(realistic_dataset)], resume_from_checkpoint=result.final_checkpoint_id
            )

            assert resume_result.migration_type == "historical"


class TestCLIIntegration:
    """Test CLI command integration."""

    @pytest.mark.asyncio
    async def test_discovery_cli_integration(self, realistic_dataset):
        """Test discovery CLI command integration."""

        # Create manifest file path
        manifest_path = realistic_dataset / "test_manifest.json"

        # Test discovery command (mock CLI call)
        from src.context_cleaner.cli.commands.migration import discover_jsonl
        from click.testing import CliRunner

        runner = CliRunner()

        # Run discovery command
        result = runner.invoke(
            discover_jsonl,
            [
                "--path",
                str(realistic_dataset),
                "--output",
                str(manifest_path),
                "--check-integrity",
                "--analyze-content",
            ],
        )

        # Should succeed
        assert result.exit_code == 0
        assert manifest_path.exists()

        # Verify manifest content
        with open(manifest_path) as f:
            manifest_data = json.load(f)

        assert manifest_data["total_files_found"] >= 4
        assert manifest_data["estimated_total_tokens"] > 0
        assert len(manifest_data["processing_manifest"]) >= 4

    @pytest.mark.asyncio
    @patch("src.context_cleaner.cli.commands.migration.TokenAnalysisBridge")
    async def test_migration_cli_integration(self, mock_bridge_class, realistic_dataset):
        """Test migration CLI command integration."""

        # Mock the bridge service
        mock_bridge_instance = Mock()
        mock_bridge_instance.bulk_store_sessions = AsyncMock(
            return_value=[BridgeResult(success=True, operation_type="bulk_store", records_stored=5, total_tokens=1000)]
        )
        mock_bridge_instance.health_check = AsyncMock(return_value=Mock(is_healthy=lambda: True))

        mock_bridge_class.return_value = mock_bridge_instance

        from src.context_cleaner.cli.commands.migration import migrate_historical
        from click.testing import CliRunner

        runner = CliRunner()

        # Run migration command with dry run
        result = runner.invoke(
            migrate_historical, ["--path", str(realistic_dataset), "--batch-size", "50", "--dry-run"]
        )

        # Should succeed (dry run)
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Migration completed" in result.output


class TestDataIntegrity:
    """Test data integrity across the migration pipeline."""

    @pytest.mark.asyncio
    async def test_token_count_accuracy(self, realistic_dataset, mock_bridge_with_stats):
        """Test token count accuracy through migration pipeline."""

        # Manually calculate expected tokens
        expected_tokens = 0
        expected_sessions = set()

        for jsonl_file in realistic_dataset.glob("**/*.jsonl"):
            with open(jsonl_file) as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("type") == "assistant":
                            usage = entry.get("message", {}).get("usage", {})
                            expected_tokens += usage.get("input_tokens", 0)
                            expected_tokens += usage.get("output_tokens", 0)
                            expected_tokens += usage.get("cache_creation_input_tokens", 0)
                            expected_tokens += usage.get("cache_read_input_tokens", 0)

                        if "session_id" in entry:
                            expected_sessions.add(entry["session_id"])

        # Run migration
        migration_engine = MigrationEngine(bridge_service=mock_bridge_with_stats, batch_size=100)

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(realistic_dataset)])

        # Verify token counts
        migrated_tokens = sum(
            s.reported_input_tokens
            + s.reported_output_tokens
            + s.reported_cache_creation_tokens
            + s.reported_cache_read_tokens
            for s in mock_bridge_with_stats.stored_sessions
        )

        # Allow small variance due to processing differences
        variance = abs(migrated_tokens - expected_tokens) / expected_tokens if expected_tokens > 0 else 0
        assert variance < 0.05  # Less than 5% variance

        # Verify session counts
        migrated_session_ids = set(s.session_id for s in mock_bridge_with_stats.stored_sessions)
        assert len(migrated_session_ids) == len(expected_sessions)

    @pytest.mark.asyncio
    async def test_content_categorization_accuracy(self, realistic_dataset, mock_bridge_with_stats):
        """Test content categorization accuracy."""

        migration_engine = MigrationEngine(bridge_service=mock_bridge_with_stats)

        result = await migration_engine.migrate_all_historical_data(source_directories=[str(realistic_dataset)])

        # Check for MCP tools categorization
        mcp_session = next((s for s in mock_bridge_with_stats.stored_sessions if s.session_id == "mcp_tools_001"), None)

        if mcp_session:
            # Should have detected MCP tool content
            assert mcp_session.content_categories.get("mcp_tools", 0) > 0


class TestPerformanceAndScalability:
    """Test performance and scalability characteristics."""

    @pytest.mark.asyncio
    async def test_memory_scalability(self, mock_bridge_with_stats):
        """Test memory usage scalability with large datasets."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create large dataset (simulate 1000 sessions)
            num_sessions = 1000
            entries_per_session = 10

            large_file = tmpdir_path / "massive_dataset.jsonl"
            with open(large_file, "w") as f:
                for session_idx in range(num_sessions):
                    session_id = f"session_{session_idx:04d}"

                    for entry_idx in range(entries_per_session):
                        entry = {
                            "session_id": session_id,
                            "type": "user" if entry_idx % 2 == 0 else "assistant",
                            "timestamp": f"2024-01-01T{entry_idx:02d}:00:00Z",
                            "message": {
                                "content": f"Message {entry_idx} in session {session_idx} " * 20,
                                "usage": (
                                    {"input_tokens": 50 + entry_idx, "output_tokens": 100 + entry_idx}
                                    if entry_idx % 2 == 1
                                    else None
                                ),
                            },
                        }
                        f.write(json.dumps(entry) + "\n")

            # Monitor memory during migration
            import psutil

            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            # Run migration with memory constraints
            migration_engine = MigrationEngine(
                bridge_service=mock_bridge_with_stats, max_memory_mb=500, batch_size=100  # Limit memory usage
            )

            result = await migration_engine.migrate_all_historical_data(source_directories=[str(tmpdir_path)])

            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = memory_after - memory_before

            # Performance assertions
            assert result.success
            assert result.total_sessions_created == num_sessions
            assert memory_increase < 600  # Should stay within reasonable limits
            assert result.average_processing_rate_tokens_per_second > 1000  # Should be efficient

    @pytest.mark.asyncio
    async def test_concurrent_processing_efficiency(self, realistic_dataset, mock_bridge_with_stats):
        """Test concurrent processing efficiency."""

        # Test with different concurrency levels
        concurrency_results = {}

        for max_concurrent in [1, 2, 4]:
            migration_engine = MigrationEngine(
                bridge_service=mock_bridge_with_stats, max_concurrent_files=max_concurrent, batch_size=50
            )

            # Clear previous results
            mock_bridge_with_stats.stored_sessions.clear()

            start_time = datetime.now()

            result = await migration_engine.migrate_all_historical_data(source_directories=[str(realistic_dataset)])

            duration = (datetime.now() - start_time).total_seconds()

            concurrency_results[max_concurrent] = {
                "duration": duration,
                "files_per_second": result.total_files_processed / duration if duration > 0 else 0,
                "success": result.success,
            }

        # Higher concurrency should generally be faster (with some exceptions for overhead)
        assert all(r["success"] for r in concurrency_results.values())

        # At minimum, concurrent processing should not be significantly slower
        single_thread_duration = concurrency_results[1]["duration"]
        multi_thread_duration = concurrency_results[4]["duration"]

        # Allow some variance, but concurrent should not be more than 50% slower
        assert multi_thread_duration < single_thread_duration * 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
