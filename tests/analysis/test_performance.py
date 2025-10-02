"""
Performance Tests for Enhanced Token Counting System

Tests handling of large files, many files, and performance characteristics
to ensure the system scales properly beyond current limitations.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
import tempfile

from src.context_cleaner.analysis.enhanced_token_counter import (
    EnhancedTokenCounterService,
    AnthropicTokenCounter,
    SessionTokenTracker,
)
from .fixtures import JSONLFixtures, MockAnthropicAPI


class TestLargeFileProcessing:
    """Test processing of large JSONL files."""

    @pytest.fixture
    def service(self):
        """Create service instance for performance testing."""
        return EnhancedTokenCounterService(anthropic_api_key="test_key")

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)  # Should complete within 30 seconds
    async def test_large_single_file_processing(self, service, tmp_path):
        """Test processing a single file with 10,000+ lines."""
        large_file = tmp_path / "massive_conversation.jsonl"

        # Create file with 10,000 entries
        num_entries = 10000
        entries_per_batch = 1000

        with open(large_file, "w") as f:
            for batch in range(0, num_entries, entries_per_batch):
                batch_entries = []
                for i in range(batch, min(batch + entries_per_batch, num_entries)):
                    message_type = "user" if i % 2 == 0 else "assistant"
                    content = f"Message {i}: " + "Test content " * (
                        i % 10 + 1
                    )  # Varied lengths

                    entry = {
                        "type": message_type,
                        "timestamp": (
                            datetime.now() + timedelta(minutes=i)
                        ).isoformat(),
                        "session_id": f"large_session_{i // 100}",  # Multiple sessions
                        "message": {"role": message_type, "content": content},
                    }

                    # Add usage stats to some assistant messages
                    if message_type == "assistant" and i % 10 == 0:
                        entry["message"]["usage"] = {
                            "input_tokens": 50 + (i % 100),
                            "output_tokens": 25 + (i % 50),
                            "cache_creation_input_tokens": i % 20,
                            "cache_read_input_tokens": i % 15,
                        }

                    batch_entries.append(entry)

                # Write batch to file
                for entry in batch_entries:
                    f.write(json.dumps(entry) + "\n")

        # Measure processing time
        start_time = time.time()

        with patch.object(service, "cache_dir", tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False  # Avoid API delays
            )

        processing_time = time.time() - start_time

        # Verify results
        assert analysis.total_files_processed == 1
        assert analysis.total_lines_processed == num_entries
        assert len(analysis.sessions) > 90  # Should detect multiple sessions

        # Verify performance
        assert processing_time < 20.0  # Should process 10k lines in under 20 seconds
        lines_per_second = num_entries / processing_time
        assert lines_per_second > 500  # Should process at least 500 lines/second

        # Verify accuracy despite large volume
        assert analysis.global_undercount_percentage > 0  # Should detect undercount
        assert analysis.total_calculated_tokens > analysis.total_reported_tokens

    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_multiple_large_files_processing(self, service, tmp_path):
        """Test processing multiple large files (25 files, 2000 lines each)."""
        num_files = 25
        lines_per_file = 2000

        # Create multiple large files
        files_created = []
        for file_num in range(num_files):
            file_path = tmp_path / f"large_file_{file_num:03d}.jsonl"
            files_created.append(file_path)

            entries = JSONLFixtures.create_large_conversation(
                session_id=f"session_{file_num:03d}", num_entries=lines_per_file
            )

            with open(file_path, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")

        start_time = time.time()

        with patch.object(service, "cache_dir", tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )

        processing_time = time.time() - start_time

        # Verify results
        assert analysis.total_files_processed == num_files
        assert analysis.total_lines_processed == num_files * lines_per_file
        assert len(analysis.sessions) == num_files

        # Verify performance
        total_lines = num_files * lines_per_file
        assert processing_time < 45.0  # Should handle 50k lines in under 45 seconds
        lines_per_second = total_lines / processing_time
        assert lines_per_second > 1000  # Good throughput

        # Verify system handles volume without degradation
        assert analysis.global_accuracy_ratio > 1.0
        assert len(analysis.errors_encountered) == 0  # No errors at scale

    @pytest.mark.asyncio
    async def test_memory_usage_with_large_files(self, service, tmp_path):
        """Test memory usage remains reasonable with large files."""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create very large file
        huge_file = tmp_path / "huge_conversation.jsonl"
        num_entries = 15000

        with open(huge_file, "w") as f:
            for i in range(num_entries):
                entry = {
                    "type": "user" if i % 2 == 0 else "assistant",
                    "timestamp": datetime.now().isoformat(),
                    "session_id": f"huge_session_{i // 1000}",
                    "message": {
                        "role": "user" if i % 2 == 0 else "assistant",
                        "content": f"Large content block {i}: "
                        + "X" * 1000,  # 1KB per message
                    },
                }

                if i % 2 == 1 and i % 20 == 0:  # Some assistant messages have usage
                    entry["message"]["usage"] = {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": 10,
                        "cache_read_input_tokens": 5,
                    }

                f.write(json.dumps(entry) + "\n")

        # Process the large file
        with patch.object(service, "cache_dir", tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )

        # Check memory usage after processing
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory usage should be reasonable (less than 200MB increase)
        assert (
            memory_increase < 200
        ), f"Memory usage increased by {memory_increase:.1f}MB"

        # Verify processing succeeded
        assert analysis.total_lines_processed == num_entries
        assert len(analysis.sessions) > 10  # Multiple sessions detected

    @pytest.mark.asyncio
    async def test_file_discovery_performance(self, service, tmp_path):
        """Test performance of file discovery with many files."""
        # Create many small files
        num_files = 100
        files_created = []

        # Create nested directory structure
        for i in range(num_files):
            if i % 10 == 0:
                # Create subdirectory every 10 files
                subdir = tmp_path / f"subdir_{i // 10}"
                subdir.mkdir(exist_ok=True)
                file_path = subdir / f"session_{i:03d}.jsonl"
            else:
                file_path = tmp_path / f"session_{i:03d}.jsonl"

            files_created.append(file_path)

            # Create small file with 10 entries
            entries = [
                JSONLFixtures.create_realistic_conversation_entry(
                    session_id=f"session_{i:03d}", content=f"Content {j}"
                )
                for j in range(10)
            ]

            with open(file_path, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")

        start_time = time.time()

        with patch.object(service, "cache_dir", tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )

        discovery_time = time.time() - start_time

        # Verify all files were discovered
        assert analysis.total_files_processed == num_files

        # File discovery should be fast
        assert discovery_time < 10.0  # Should discover 100 files in under 10 seconds
        files_per_second = num_files / discovery_time
        assert files_per_second > 20  # Should discover at least 20 files/second


class TestAPIPerformance:
    """Test performance with Anthropic count-tokens API."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API for performance testing."""
        return MockAnthropicAPI()

    @pytest.mark.asyncio
    async def test_api_rate_limiting_handling(self, tmp_path):
        """Test handling of API rate limiting."""
        service = EnhancedTokenCounterService(anthropic_api_key="test_key")

        # Create file that would trigger many API calls
        test_file = tmp_path / "api_heavy.jsonl"

        entries = []
        for i in range(20):  # Enough to trigger API validation
            entries.extend(
                [
                    JSONLFixtures.create_realistic_conversation_entry(
                        message_type="user",
                        content=f"User message {i}",
                        session_id="api_session",
                    ),
                    JSONLFixtures.create_realistic_conversation_entry(
                        message_type="assistant",
                        content=f"Assistant response {i}",
                        usage={
                            "input_tokens": 50,
                            "output_tokens": 25,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 0,
                        },
                        session_id="api_session",
                    ),
                ]
            )

        with open(test_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        # Mock API that hits rate limit after 5 calls
        call_count = 0

        async def mock_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                raise Exception("Rate limit exceeded")
            return 200  # Return token count

        with patch.object(service, "cache_dir", tmp_path):
            with patch(
                "src.context_cleaner.analysis.enhanced_token_counter.AnthropicTokenCounter"
            ) as mock_counter_class:
                mock_counter = AsyncMock()
                mock_counter.count_tokens_for_messages = mock_api_call
                mock_counter_class.return_value = mock_counter

                # Should handle rate limiting gracefully
                analysis = await service.analyze_comprehensive_token_usage(
                    use_count_tokens_api=True
                )

                # Should still produce results despite rate limiting
                assert analysis.total_sessions_analyzed > 0
                assert analysis.api_calls_made <= 5  # Should stop after rate limit
                assert len(analysis.errors_encountered) == 0  # Should handle gracefully

    @pytest.mark.asyncio
    async def test_api_timeout_handling(self, tmp_path):
        """Test handling of API timeouts."""
        service = EnhancedTokenCounterService(anthropic_api_key="test_key")

        test_file = tmp_path / "timeout_test.jsonl"
        entries = [
            JSONLFixtures.create_realistic_conversation_entry(
                message_type="user",
                content="Test message",
                session_id="timeout_session",
            )
        ] * 10  # Multiple entries

        with open(test_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        # Mock API that times out
        async def mock_timeout(*args, **kwargs):
            await asyncio.sleep(0.1)  # Small delay
            raise asyncio.TimeoutError("API timeout")

        start_time = time.time()

        with patch.object(service, "cache_dir", tmp_path):
            with patch(
                "src.context_cleaner.analysis.enhanced_token_counter.AnthropicTokenCounter"
            ) as mock_counter_class:
                mock_counter = AsyncMock()
                mock_counter.count_tokens_for_messages = mock_timeout
                mock_counter_class.return_value = mock_counter

                analysis = await service.analyze_comprehensive_token_usage(
                    use_count_tokens_api=True
                )

        processing_time = time.time() - start_time

        # Should handle timeouts quickly and gracefully
        assert processing_time < 5.0  # Should not hang
        assert analysis.total_sessions_analyzed > 0  # Should fallback to heuristics
        assert analysis.api_calls_made == 0  # No successful API calls


class TestSessionTrackerPerformance:
    """Test performance of real-time session tracking."""

    @pytest.fixture
    def tracker(self):
        """Create session tracker for performance testing."""
        return SessionTokenTracker()

    @pytest.mark.asyncio
    async def test_concurrent_session_updates(self, tracker):
        """Test performance with many concurrent session updates."""
        num_sessions = 100
        updates_per_session = 50

        async def update_session_worker(session_id: str):
            """Worker function to update a single session multiple times."""
            for i in range(updates_per_session):
                await tracker.update_session_tokens(
                    session_id=session_id, input_tokens=10 + i, output_tokens=5 + i
                )

        start_time = time.time()

        # Run concurrent updates
        tasks = [update_session_worker(f"session_{i:03d}") for i in range(num_sessions)]

        await asyncio.gather(*tasks)

        update_time = time.time() - start_time

        # Verify all updates completed
        all_metrics = await tracker.get_all_session_metrics()
        assert len(all_metrics) == num_sessions

        # Verify data integrity
        for i in range(num_sessions):
            session_id = f"session_{i:03d}"
            metrics = all_metrics[session_id]
            expected_input = sum(10 + j for j in range(updates_per_session))
            expected_output = sum(5 + j for j in range(updates_per_session))
            assert metrics.reported_input_tokens == expected_input
            assert metrics.reported_output_tokens == expected_output

        # Performance verification
        total_updates = num_sessions * updates_per_session
        updates_per_second = total_updates / update_time
        assert updates_per_second > 1000  # Should handle 1000+ updates/second
        assert update_time < 10.0  # Should complete in reasonable time

    @pytest.mark.asyncio
    async def test_session_cleanup_performance(self, tracker):
        """Test performance of session cleanup operations."""
        # Create many sessions with different ages
        num_sessions = 1000
        old_sessions = 0

        for i in range(num_sessions):
            session_id = f"perf_session_{i:04d}"
            await tracker.update_session_tokens(
                session_id=session_id, input_tokens=100, output_tokens=50
            )

            # Make some sessions old
            if i < 300:
                metrics = await tracker.get_session_metrics(session_id)
                old_time = datetime.now() - timedelta(
                    hours=25
                )  # Older than cleanup threshold
                metrics.start_time = old_time
                metrics.end_time = old_time
                old_sessions += 1

        start_time = time.time()

        # Run cleanup
        await tracker.cleanup_old_sessions(hours=24)

        cleanup_time = time.time() - start_time

        # Verify cleanup worked
        remaining_sessions = await tracker.get_all_session_metrics()
        expected_remaining = num_sessions - old_sessions
        assert len(remaining_sessions) == expected_remaining

        # Performance verification
        assert cleanup_time < 2.0  # Cleanup should be fast
        sessions_per_second = num_sessions / cleanup_time
        assert sessions_per_second > 500  # Should process many sessions quickly


class TestScalabilityLimits:
    """Test system behavior at scale limits."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_maximum_file_count(self, tmp_path):
        """Test processing at maximum reasonable file count."""
        service = EnhancedTokenCounterService()

        # Create many files (simulate real-world maximum)
        num_files = 200  # Reasonable maximum for testing

        for i in range(num_files):
            file_path = tmp_path / f"scale_file_{i:04d}.jsonl"

            # Small files to keep test reasonable
            entries = [
                JSONLFixtures.create_realistic_conversation_entry(
                    session_id=f"scale_session_{i:04d}",
                    content=f"Scale test content {i}",
                )
                for _ in range(20)  # 20 lines per file
            ]

            with open(file_path, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")

        start_time = time.time()

        with patch.object(service, "cache_dir", tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )

        processing_time = time.time() - start_time

        # Should handle maximum file count
        assert analysis.total_files_processed == num_files
        assert processing_time < 60.0  # Should complete within 1 minute
        assert len(analysis.errors_encountered) == 0

        # Verify quality doesn't degrade at scale
        assert analysis.total_sessions_analyzed == num_files
        # Note: accuracy ratio may be 0 if no reported tokens (no usage stats in test data)
        # The key is that files were processed successfully
        assert analysis.total_calculated_tokens > 0  # Content was analyzed

    @pytest.mark.asyncio
    async def test_error_recovery_at_scale(self, tmp_path):
        """Test error recovery when processing many files with some errors."""
        service = EnhancedTokenCounterService()

        num_files = 50
        corrupt_files = 5

        for i in range(num_files):
            file_path = tmp_path / f"error_test_{i:03d}.jsonl"

            if i < corrupt_files:
                # Create corrupted files
                with open(file_path, "w") as f:
                    f.write("invalid json\n")
                    f.write('{"type": "incomplete"\n')
                    f.write("more invalid content\n")
            else:
                # Create valid files
                entries = [
                    JSONLFixtures.create_realistic_conversation_entry(
                        session_id=f"error_session_{i:03d}",
                        content=f"Valid content {i}",
                    )
                    for _ in range(10)
                ]

                with open(file_path, "w") as f:
                    for entry in entries:
                        f.write(json.dumps(entry) + "\n")

        with patch.object(service, "cache_dir", tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )

        # Should process all files, handling errors gracefully
        assert analysis.total_files_processed == num_files
        assert analysis.total_sessions_analyzed == (
            num_files - corrupt_files
        )  # Only valid files create sessions

        # Should continue processing despite errors
        assert len(analysis.sessions) > 0
        assert analysis.total_lines_processed > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
