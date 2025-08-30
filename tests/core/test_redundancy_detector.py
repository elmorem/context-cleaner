#!/usr/bin/env python3
"""
Tests for the Redundancy Detection Engine

Comprehensive tests for redundancy detection including:
- Exact duplicate detection
- Similar content identification
- Obsolete todo detection
- Redundant file detection
- Stale error message identification
- Performance and edge case handling
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from src.context_cleaner.core.redundancy_detector import (
    RedundancyDetector,
    RedundancyReport,
)


class TestRedundancyDetector:
    """Test suite for RedundancyDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = RedundancyDetector()

        self.sample_context = {
            "messages": [
                "Help me debug this function",
                "I can help you debug that function",
                "Help me debug this function",  # Exact duplicate
                "Help me debug this method",  # Similar content
                "The function is working now - fixed it!",  # Resolution
            ],
            "todos": [
                "Fix authentication bug",
                "Write unit tests",
                "Update documentation",
                "Deploy to staging - COMPLETED ✅",  # Obsolete
                "Fix login issue - already done",  # Obsolete
                "Refactor code - RESOLVED",  # Obsolete
            ],
            "files": [
                "/project/src/main.py",
                "/project/src/utils.py",
                "/project/src/main.py",  # Duplicate
                "/project/tests/test_main.py",
                "/project/src/main.py",  # Another duplicate
            ],
            "errors": [
                "TypeError: invalid argument",
                "This error was fixed in the last commit",  # Stale
                "Connection timeout error",
                "Login bug - this has been resolved",  # Stale
            ],
        }

    @pytest.mark.asyncio
    async def test_analyze_redundancy_basic(self):
        """Test basic redundancy analysis functionality."""
        report = await self.detector.analyze_redundancy(self.sample_context)

        assert isinstance(report, RedundancyReport)
        assert report.duplicate_content_percentage >= 0
        assert report.stale_content_percentage >= 0
        assert report.redundant_files_count >= 0
        assert report.obsolete_todos_count >= 0
        assert report.total_items_analyzed > 0
        assert report.redundancy_analysis_duration > 0

    @pytest.mark.asyncio
    async def test_detect_exact_duplicates(self):
        """Test exact duplicate detection."""
        report = await self.detector.analyze_redundancy(self.sample_context)

        # Should find duplicates in messages and files
        duplicate_items = [
            item for item in report.duplicate_items if item["type"] == "exact_duplicate"
        ]
        assert len(duplicate_items) > 0

        # Should identify file duplicates
        assert report.redundant_files_count > 0
        assert len(report.redundant_file_groups) > 0

    @pytest.mark.asyncio
    async def test_detect_obsolete_todos(self):
        """Test obsolete todo detection."""
        report = await self.detector.analyze_redundancy(self.sample_context)

        # Should detect completed/obsolete todos
        assert report.obsolete_todos_count >= 3  # We have at least 3 obsolete todos

        obsolete_items = [
            item for item in report.obsolete_items if item["type"] == "obsolete_todo"
        ]
        assert len(obsolete_items) >= 3

    @pytest.mark.asyncio
    async def test_detect_stale_errors(self):
        """Test stale error message detection."""
        report = await self.detector.analyze_redundancy(self.sample_context)

        # Should detect stale error messages
        assert len(report.stale_error_messages) >= 2  # We have 2 stale errors

    def test_calculate_similarity_exact_match(self):
        """Test similarity calculation for exact matches."""
        text1 = "This is a test message"
        text2 = "This is a test message"

        similarity = self.detector._calculate_similarity(text1, text2)
        assert similarity == 1.0

    def test_calculate_similarity_no_match(self):
        """Test similarity calculation for completely different text."""
        text1 = "This is about authentication"
        text2 = "Database migration completed"

        similarity = self.detector._calculate_similarity(text1, text2)
        assert similarity < 0.5  # Should be low similarity

    def test_calculate_similarity_similar_content(self):
        """Test similarity calculation for similar content."""
        text1 = "Help me debug this function"
        text2 = "Help me debug this method"

        similarity = self.detector._calculate_similarity(text1, text2)
        assert 0.8 <= similarity < 1.0  # Should be high but not exact

    def test_calculate_similarity_short_strings(self):
        """Test similarity calculation with short strings."""
        text1 = "Hi"
        text2 = "Hello"

        similarity = self.detector._calculate_similarity(text1, text2)
        # Short strings below threshold should only match exactly
        assert similarity == 0.0

        # Test exact short string match
        similarity2 = self.detector._calculate_similarity("Hi", "Hi")
        assert similarity2 == 1.0

    def test_extract_text_content_string(self):
        """Test text content extraction from string."""
        text = "This is a test message"
        result = self.detector._extract_text_content(text)
        assert result == text

    def test_extract_text_content_dict(self):
        """Test text content extraction from dictionary."""
        data = {"type": "error", "message": "Test error", "priority": 5}
        result = self.detector._extract_text_content(data)

        assert "type: error" in result
        assert "message: Test error" in result
        assert "priority: 5" in result

    def test_extract_text_content_list(self):
        """Test text content extraction from list."""
        data = ["item1", "item2", "item3"]
        result = self.detector._extract_text_content(data)

        assert "item1" in result
        assert "item2" in result
        assert "item3" in result

    def test_detect_exact_duplicates_simple(self):
        """Test exact duplicate detection with simple data."""
        items = [
            "Test message one",
            "Test message two",
            "Test message one",  # Duplicate of first
            "Test message three",
            "Test message two",  # Duplicate of second
        ]

        duplicates = self.detector._detect_exact_duplicates(items)

        # Should find 2 duplicate pairs
        assert len(duplicates) >= 2

        # Check that correct indices are identified as duplicates
        duplicate_indices = set()
        for i, j in duplicates:
            duplicate_indices.add(i)
            duplicate_indices.add(j)

        assert 0 in duplicate_indices and 2 in duplicate_indices  # First and third
        assert 1 in duplicate_indices and 4 in duplicate_indices  # Second and fifth

    def test_detect_similar_content_basic(self):
        """Test similar content detection."""
        items = [
            "Help me debug this function",
            "Help me debug this method",
            "Database connection error",
            "Help me debug that function",
        ]

        similar_pairs = self.detector._detect_similar_content(items)

        # Should find similar pairs
        assert len(similar_pairs) > 0

        # Check similarity scores are in expected range
        for i, j, similarity in similar_pairs:
            assert self.detector.SIMILARITY_THRESHOLD <= similarity < 1.0

    def test_detect_obsolete_todos_patterns(self):
        """Test obsolete todo detection with various patterns."""
        todos = [
            "Fix authentication bug",  # Active
            "Write unit tests",  # Active
            "Deploy to staging - COMPLETED",  # Obsolete
            "Update docs ✅",  # Obsolete
            "Fix login - already done",  # Obsolete
            "Refactor code - resolved",  # Obsolete
            "Archive old files - no longer needed",  # Obsolete
        ]

        obsolete_indices = self.detector._detect_obsolete_todos(todos)

        # Should detect at least 5 obsolete todos
        assert len(obsolete_indices) >= 5

        # First two should not be obsolete
        assert 0 not in obsolete_indices
        assert 1 not in obsolete_indices

        # Others should be detected as obsolete
        assert 2 in obsolete_indices  # COMPLETED
        assert 3 in obsolete_indices  # ✅

    def test_detect_redundant_files_simple(self):
        """Test redundant file detection."""
        files = [
            "/project/main.py",
            "/project/utils.py",
            "/project/main.py",  # Duplicate
            "/project/test.py",
            "/project/main.py",  # Another duplicate
        ]

        redundant_groups = self.detector._detect_redundant_files(files)

        # Should find one group with main.py duplicates
        assert len(redundant_groups) >= 1

        # Group should contain the duplicated file path
        main_py_group = None
        for group in redundant_groups:
            if "/project/main.py" in group[0]:
                main_py_group = group
                break

        assert main_py_group is not None
        assert len(main_py_group) >= 4  # Path + 3 indices

    def test_detect_redundant_files_dict_format(self):
        """Test redundant file detection with dictionary format."""
        files = [
            {"path": "/project/auth.py", "type": "source"},
            {"path": "/project/utils.py", "type": "source"},
            {"path": "/project/auth.py", "type": "source"},  # Duplicate
            {"filepath": "/project/auth.py", "size": 1024},  # Different key, same file
        ]

        redundant_groups = self.detector._detect_redundant_files(files)

        # Should detect auth.py duplicates
        assert len(redundant_groups) >= 1

    def test_detect_stale_errors_patterns(self):
        """Test stale error detection with various patterns."""
        errors = [
            "TypeError: Cannot read property",  # Active
            "Connection timeout error",  # Active
            "Login bug - this was fixed",  # Stale
            "Database error - resolved in commit abc",  # Stale
            "This error no longer occurs",  # Stale
            "Authentication issue - corrected",  # Stale
        ]

        stale_errors = self.detector._detect_stale_errors(errors)

        # Should detect at least 4 stale errors
        assert len(stale_errors) >= 4

    def test_categorize_content_basic(self):
        """Test content categorization functionality."""
        categories = self.detector._categorize_content(self.sample_context)

        assert isinstance(categories, dict)
        assert "messages" in categories
        assert "files" in categories
        assert "todos" in categories
        assert "errors" in categories

        # Should have content in expected categories
        assert len(categories["messages"]) > 0
        assert len(categories["files"]) > 0
        assert len(categories["todos"]) > 0
        assert len(categories["errors"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_redundancy_empty_context(self):
        """Test redundancy analysis with empty context."""
        empty_context = {}

        report = await self.detector.analyze_redundancy(empty_context)

        assert isinstance(report, RedundancyReport)
        assert report.total_items_analyzed == 0
        assert report.duplicate_content_percentage == 0
        assert report.redundant_files_count == 0

    @pytest.mark.asyncio
    async def test_analyze_redundancy_performance(self):
        """Test redundancy analysis performance with large dataset."""
        # Create large context with many items
        large_context = {
            "messages": [f"Message {i}" for i in range(100)]
            + [f"Message {i}" for i in range(50)],  # Add duplicates
            "files": [f"/project/file{i}.py" for i in range(50)]
            + [f"/project/file{i}.py" for i in range(25)],  # Add duplicates
        }

        start_time = datetime.now()
        report = await self.detector.analyze_redundancy(large_context)
        end_time = datetime.now()

        # Should complete within reasonable time
        duration = (end_time - start_time).total_seconds()
        assert duration < 5.0  # Should be fast

        # Should detect duplicates
        assert report.duplicate_content_percentage > 0
        assert report.total_items_analyzed > 100

    @pytest.mark.asyncio
    async def test_analyze_redundancy_error_handling(self):
        """Test redundancy analysis error handling."""
        # Mock internal method to raise exception
        with patch.object(self.detector, "_categorize_content") as mock_categorize:
            mock_categorize.side_effect = Exception("Test error")

            report = await self.detector.analyze_redundancy(self.sample_context)

            # Should return empty report on error
            assert isinstance(report, RedundancyReport)
            assert report.total_items_analyzed == 0
            assert report.redundancy_analysis_duration == 0.0

    def test_similarity_threshold_boundary(self):
        """Test similarity threshold boundary conditions."""
        # Test content just above threshold
        text1 = "This is a test message about debugging"
        text2 = "This is a test message about testing"  # High similarity

        similarity = self.detector._calculate_similarity(text1, text2)
        assert similarity > self.detector.SIMILARITY_THRESHOLD

        # Test content just below threshold
        text3 = "Completely different content here"
        text4 = "This is a test message about debugging"

        similarity2 = self.detector._calculate_similarity(text3, text4)
        assert similarity2 < self.detector.SIMILARITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_safe_to_remove_recommendations(self):
        """Test safe removal recommendations."""
        report = await self.detector.analyze_redundancy(self.sample_context)

        # Should have items marked as safe to remove
        assert len(report.safe_to_remove) > 0

        # Check that safe removal items have proper structure
        for item in report.safe_to_remove:
            assert "type" in item
            assert "reason" in item
            assert item["reason"]  # Should have a reason

    @pytest.mark.asyncio
    async def test_consolidation_candidates(self):
        """Test consolidation candidate identification."""
        report = await self.detector.analyze_redundancy(self.sample_context)

        # Should have consolidation candidates
        assert len(report.consolidation_candidates) >= 0

        # Check structure if any candidates exist
        if report.consolidation_candidates:
            for candidate in report.consolidation_candidates:
                assert "type" in candidate
                assert "reason" in candidate


class TestRedundancyReport:
    """Test suite for RedundancyReport dataclass."""

    def test_redundancy_report_creation(self):
        """Test creating RedundancyReport with all fields."""
        report = RedundancyReport(
            duplicate_content_percentage=25.0,
            stale_content_percentage=15.0,
            redundant_files_count=3,
            obsolete_todos_count=5,
            duplicate_items=[{"type": "test"}],
            obsolete_items=[{"type": "obsolete"}],
            redundant_file_groups=[["file1", "0", "2"]],
            stale_error_messages=["error1", "error2"],
            total_items_analyzed=100,
            total_estimated_tokens=25000,
            redundancy_analysis_duration=1.5,
            safe_to_remove=[{"type": "duplicate"}],
            consolidation_candidates=[{"type": "similar"}],
        )

        assert report.duplicate_content_percentage == 25.0
        assert report.redundant_files_count == 3
        assert len(report.duplicate_items) == 1
        assert len(report.stale_error_messages) == 2

    def test_get_redundancy_summary(self):
        """Test redundancy summary generation."""
        report = RedundancyReport(
            duplicate_content_percentage=20.5,
            stale_content_percentage=12.3,
            redundant_files_count=4,
            obsolete_todos_count=6,
            duplicate_items=[],
            obsolete_items=[],
            redundant_file_groups=[],
            stale_error_messages=[],
            total_items_analyzed=0,
            total_estimated_tokens=0,
            redundancy_analysis_duration=0,
            safe_to_remove=[],
            consolidation_candidates=[],
        )

        summary = report.get_redundancy_summary()

        assert "20.5%" in summary
        assert "12.3%" in summary
        assert "4" in summary  # Redundant files
        assert "6" in summary  # Obsolete todos


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
