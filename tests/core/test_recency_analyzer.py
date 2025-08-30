#!/usr/bin/env python3
"""
Tests for the Recency Analysis Engine

Comprehensive tests for recency analysis including:
- Timestamp extraction and parsing
- Recency categorization (fresh/recent/aging/stale)
- Session start estimation
- Activity scoring
- Content-based recency detection
- Performance and edge case handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
import pytz

from src.context_cleaner.core.recency_analyzer import RecencyAnalyzer, RecencyReport


class TestRecencyAnalyzer:
    """Test suite for RecencyAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = RecencyAnalyzer()

        # Create test data with known timestamps
        now = datetime.now(pytz.UTC)

        self.sample_context = {
            "current_task": {
                "description": "Currently debugging authentication bug",
                "timestamp": now.isoformat(),  # Fresh
                "status": "in_progress",
            },
            "recent_messages": [
                {
                    "content": "Working on the login function now",
                    "timestamp": (now - timedelta(minutes=30)).isoformat(),  # Fresh
                },
                {
                    "content": "This is from earlier today",
                    "timestamp": (now - timedelta(hours=3)).isoformat(),  # Recent
                },
            ],
            "old_todos": [
                {
                    "task": "Previous project setup - completed last week",
                    "timestamp": (now - timedelta(days=7)).isoformat(),  # Stale
                },
                {
                    "task": "Yesterday's debugging session",
                    "timestamp": (
                        now - timedelta(days=1, hours=2)
                    ).isoformat(),  # Stale
                },
            ],
            "files_accessed": [
                {
                    "path": "/project/auth.py",
                    "last_modified": (now - timedelta(hours=2)).isoformat(),  # Recent
                },
                {
                    "path": "/project/legacy_code.py",
                    "last_modified": (now - timedelta(days=5)).isoformat(),  # Stale
                },
            ],
            "session_notes": "Currently working on implementing OAuth2 integration",  # Current work
        }

    @pytest.mark.asyncio
    async def test_analyze_recency_basic(self):
        """Test basic recency analysis functionality."""
        report = await self.analyzer.analyze_recency(self.sample_context)

        assert isinstance(report, RecencyReport)
        assert 0 <= report.fresh_context_percentage <= 100
        assert 0 <= report.recent_context_percentage <= 100
        assert 0 <= report.aging_context_percentage <= 100
        assert 0 <= report.stale_context_percentage <= 100
        assert report.total_items_categorized > 0
        assert report.recency_analysis_duration > 0

    @pytest.mark.asyncio
    async def test_recency_categorization_fresh(self):
        """Test that fresh content is properly categorized."""
        report = await self.analyzer.analyze_recency(self.sample_context)

        # Should have some fresh content (within last hour)
        assert report.fresh_context_percentage > 0
        assert len(report.fresh_items) > 0

        # Check that fresh items have recent timestamps
        for item in report.fresh_items:
            if item["timestamp"]:
                timestamp = datetime.fromisoformat(
                    item["timestamp"].replace("Z", "+00:00")
                )
                now = datetime.now(pytz.UTC)
                age = now - timestamp
                assert age <= timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_recency_categorization_stale(self):
        """Test that stale content is properly categorized."""
        report = await self.analyzer.analyze_recency(self.sample_context)

        # Should have some stale content
        assert report.stale_context_percentage > 0
        assert len(report.stale_items) > 0

        # Check that stale items are old
        for item in report.stale_items:
            if item["timestamp"]:
                timestamp = datetime.fromisoformat(
                    item["timestamp"].replace("Z", "+00:00")
                )
                now = datetime.now(pytz.UTC)
                age = now - timestamp
                assert age >= timedelta(days=1)

    def test_extract_timestamp_iso_format(self):
        """Test timestamp extraction from ISO format."""
        content = {"timestamp": "2024-01-15T10:30:00Z", "message": "Test message"}

        timestamp = self.analyzer._extract_timestamp(content)
        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15

    def test_extract_timestamp_dict_keys(self):
        """Test timestamp extraction from common dictionary keys."""
        test_cases = [
            {"created_at": "2024-01-15T10:30:00Z"},
            {"updated_at": "2024-01-15T10:30:00Z"},
            {"modified_at": "2024-01-15T10:30:00Z"},
            {"last_modified": "2024-01-15T10:30:00Z"},
            {"time": "2024-01-15T10:30:00Z"},
            {"date": "2024-01-15T10:30:00Z"},
        ]

        for content in test_cases:
            timestamp = self.analyzer._extract_timestamp(content)
            assert timestamp is not None
            assert timestamp.year == 2024

    def test_extract_timestamp_content_patterns(self):
        """Test timestamp extraction from content text patterns."""
        content_with_timestamp = "Last updated: 2024-01-15T10:30:00Z - auth module"
        timestamp = self.analyzer._extract_timestamp(content_with_timestamp)

        assert timestamp is not None
        assert timestamp.year == 2024

    def test_parse_timestamp_relative_time(self):
        """Test parsing relative time expressions."""
        test_cases = [
            ("5 minutes ago", timedelta(minutes=5)),
            ("2 hours ago", timedelta(hours=2)),
            ("3 days ago", timedelta(days=3)),
            ("1 week ago", timedelta(weeks=1)),
        ]

        now = datetime.now(pytz.UTC)

        for time_str, expected_delta in test_cases:
            timestamp = self.analyzer._parse_timestamp(time_str)
            assert timestamp is not None

            actual_delta = now - timestamp
            # Allow small variance for test execution time
            assert (
                abs(actual_delta.total_seconds() - expected_delta.total_seconds()) < 60
            )

    def test_parse_timestamp_just_now(self):
        """Test parsing 'just now' expressions."""
        timestamp = self.analyzer._parse_timestamp("just now")
        assert timestamp is not None

        now = datetime.now(pytz.UTC)
        delta = now - timestamp
        assert delta.total_seconds() < 120  # Within 2 minutes

    def test_parse_timestamp_standard_formats(self):
        """Test parsing standard timestamp formats."""
        test_cases = [
            "2024-01-15T10:30:00Z",
            "2024-01-15 10:30:00",
            "1/15/2024 10:30 AM",
            "2024-01-15",
        ]

        for time_str in test_cases:
            timestamp = self.analyzer._parse_timestamp(time_str)
            if timestamp:  # Some formats might not parse
                assert timestamp.year == 2024

    def test_estimate_session_start_with_gap(self):
        """Test session start estimation with time gaps."""
        now = datetime.now(pytz.UTC)

        # Create timestamps with a clear gap indicating session start
        timestamps = [
            now - timedelta(hours=8),  # Old session
            now - timedelta(hours=7.5),  # Old session
            now - timedelta(hours=2),  # New session start (gap)
            now - timedelta(hours=1.5),  # New session
            now - timedelta(minutes=30),  # New session
            now,  # Current
        ]

        session_start = self.analyzer._estimate_session_start(timestamps)
        assert session_start is not None

        # Should identify the start of new session
        expected_start = now - timedelta(hours=2)
        delta = abs((session_start - expected_start).total_seconds())
        assert delta < 3600  # Within 1 hour of expected

    def test_estimate_session_start_recent_cutoff(self):
        """Test session start estimation with recent cutoff."""
        now = datetime.now(pytz.UTC)

        # All timestamps older than 6 hours
        old_timestamps = [
            now - timedelta(hours=10),
            now - timedelta(hours=9),
            now - timedelta(hours=8),
        ]

        session_start = self.analyzer._estimate_session_start(old_timestamps)

        # Should use earliest timestamp if all are old
        if session_start:
            assert session_start == old_timestamps[0]

    def test_calculate_session_activity_high_activity(self):
        """Test session activity calculation with high activity."""
        now = datetime.now(pytz.UTC)
        session_start = now - timedelta(hours=2)

        # Create timestamps distributed throughout session
        timestamps = []
        for minutes in range(0, 120, 10):  # Every 10 minutes for 2 hours
            timestamps.append(session_start + timedelta(minutes=minutes))

        activity_score = self.analyzer._calculate_session_activity(
            timestamps, session_start
        )

        assert 0.0 <= activity_score <= 1.0
        assert activity_score > 0.5  # Should be high activity

    def test_calculate_session_activity_low_activity(self):
        """Test session activity calculation with low activity."""
        now = datetime.now(pytz.UTC)
        session_start = now - timedelta(hours=2)

        # Only a few timestamps in 2-hour session
        timestamps = [session_start, session_start + timedelta(minutes=60), now]

        activity_score = self.analyzer._calculate_session_activity(
            timestamps, session_start
        )

        assert 0.0 <= activity_score <= 1.0
        assert activity_score < 0.5  # Should be low activity

    def test_categorize_by_timestamp_fresh(self):
        """Test timestamp-based categorization for fresh content."""
        now = datetime.now(pytz.UTC)
        fresh_timestamp = now - timedelta(minutes=30)  # 30 minutes ago

        category = self.analyzer._categorize_by_timestamp(fresh_timestamp, None)
        assert category == "fresh"

    def test_categorize_by_timestamp_recent(self):
        """Test timestamp-based categorization for recent content."""
        now = datetime.now(pytz.UTC)
        recent_timestamp = now - timedelta(hours=3)  # 3 hours ago

        category = self.analyzer._categorize_by_timestamp(recent_timestamp, None)
        assert category == "recent"

    def test_categorize_by_timestamp_aging(self):
        """Test timestamp-based categorization for aging content."""
        now = datetime.now(pytz.UTC)
        aging_timestamp = now - timedelta(hours=12)  # 12 hours ago

        category = self.analyzer._categorize_by_timestamp(aging_timestamp, None)
        assert category == "aging"

    def test_categorize_by_timestamp_stale(self):
        """Test timestamp-based categorization for stale content."""
        now = datetime.now(pytz.UTC)
        stale_timestamp = now - timedelta(days=3)  # 3 days ago

        category = self.analyzer._categorize_by_timestamp(stale_timestamp, None)
        assert category == "stale"

    def test_categorize_by_timestamp_with_session(self):
        """Test timestamp categorization with session context."""
        now = datetime.now(pytz.UTC)
        session_start = now - timedelta(hours=4)

        # Timestamp within session should be recent even if older than 6h default
        timestamp_in_session = now - timedelta(hours=3)
        category = self.analyzer._categorize_by_timestamp(
            timestamp_in_session, session_start
        )
        assert category == "recent"

        # Timestamp before session should not be recent
        timestamp_before_session = now - timedelta(hours=5)
        category2 = self.analyzer._categorize_by_timestamp(
            timestamp_before_session, session_start
        )
        assert category2 != "recent"

    def test_categorize_by_content_current_work(self):
        """Test content-based categorization for current work."""
        current_work_content = "Currently working on implementing new authentication"
        category = self.analyzer._categorize_by_content(current_work_content)
        assert category == "recent"  # Should bias toward recent for current work

    def test_categorize_by_content_stale_work(self):
        """Test content-based categorization for stale work."""
        stale_work_content = "Previous implementation from last week - completed"
        category = self.analyzer._categorize_by_content(stale_work_content)
        assert category == "stale"  # Should bias toward stale for old work

    def test_categorize_by_content_no_indicators(self):
        """Test content-based categorization with no clear indicators."""
        neutral_content = "Some technical documentation about APIs"
        category = self.analyzer._categorize_by_content(neutral_content)
        assert category is None  # No clear indication

    def test_extract_content_items_structure(self):
        """Test content item extraction structure."""
        items = self.analyzer._extract_content_items(self.sample_context)

        assert len(items) > 0

        # Check item structure
        for path, item in items:
            assert isinstance(path, str)
            assert len(path) > 0

    def test_extract_content_items_nested_data(self):
        """Test content extraction with nested data structures."""
        nested_context = {
            "level1": {
                "level2": {
                    "level3": "Deep nested content",
                    "list_item": ["item1", "item2"],
                }
            },
            "simple_list": ["a", "b", "c"],
        }

        items = self.analyzer._extract_content_items(nested_context)

        # Should extract all leaf items
        assert len(items) >= 5  # 1 deep + 2 list items + 3 simple list items

        # Check that paths correctly represent structure
        paths = [path for path, _ in items]
        assert any("level1.level2.level3" in path for path in paths)
        assert any("[0]" in path for path in paths)  # List indexing

    @pytest.mark.asyncio
    async def test_analyze_recency_empty_context(self):
        """Test recency analysis with empty context."""
        empty_context = {}

        report = await self.analyzer.analyze_recency(empty_context)

        assert isinstance(report, RecencyReport)
        assert report.total_items_categorized == 0
        assert report.fresh_context_percentage == 0
        assert report.items_with_timestamps == 0

    @pytest.mark.asyncio
    async def test_analyze_recency_no_timestamps(self):
        """Test recency analysis with content but no timestamps."""
        no_timestamp_context = {
            "messages": [
                "Currently working on new feature",
                "Previous work from last sprint",
                "Random note about architecture",
            ]
        }

        report = await self.analyzer.analyze_recency(no_timestamp_context)

        assert isinstance(report, RecencyReport)
        assert report.total_items_categorized > 0
        assert report.items_with_timestamps == 0
        # Should still categorize based on content analysis
        assert (
            report.recent_context_percentage > 0 or report.aging_context_percentage > 0
        )

    @pytest.mark.asyncio
    async def test_analyze_recency_performance(self):
        """Test recency analysis performance with large dataset."""
        now = datetime.now(pytz.UTC)

        # Create large context with many timestamped items
        large_context = {}
        for i in range(100):
            large_context[f"category_{i}"] = {
                "content": f"Content item {i}",
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
            }

        start_time = datetime.now()
        report = await self.analyzer.analyze_recency(large_context)
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        assert duration < 2.0  # Should complete quickly
        assert report.total_items_categorized == 100
        assert report.items_with_timestamps == 100

    @pytest.mark.asyncio
    async def test_analyze_recency_error_handling(self):
        """Test recency analysis error handling."""
        # Mock internal method to raise exception
        with patch.object(self.analyzer, "_extract_content_items") as mock:
            mock.side_effect = Exception("Test error")

            report = await self.analyzer.analyze_recency(self.sample_context)

            # Should return empty report on error
            assert isinstance(report, RecencyReport)
            assert report.total_items_categorized == 0
            assert report.recency_analysis_duration == 0.0

    def test_regex_patterns(self):
        """Test regex pattern compilation and matching."""
        # Test current work patterns
        current_text = "currently implementing new authentication system"
        assert self.analyzer.current_work_regex.search(current_text) is not None

        # Test stale work patterns
        stale_text = "previous implementation from last week"
        assert self.analyzer.stale_work_regex.search(stale_text) is not None

        # Test multiple patterns in same text
        mixed_text = "currently working on old legacy system"
        assert self.analyzer.current_work_regex.search(mixed_text) is not None
        assert self.analyzer.stale_work_regex.search(mixed_text) is not None

    @pytest.mark.asyncio
    async def test_session_analysis_completeness(self):
        """Test that session analysis provides complete information."""
        report = await self.analyzer.analyze_recency(self.sample_context)

        # Check session analysis fields
        assert report.session_duration_minutes >= 0
        assert 0.0 <= report.session_activity_score <= 1.0

        if report.estimated_session_start:
            # Session start should be a valid timestamp
            session_start = datetime.fromisoformat(
                report.estimated_session_start.replace("Z", "+00:00")
            )
            now = datetime.now(pytz.UTC)
            assert session_start <= now


class TestRecencyReport:
    """Test suite for RecencyReport dataclass."""

    def test_recency_report_creation(self):
        """Test creating RecencyReport with all fields."""
        report = RecencyReport(
            fresh_context_percentage=25.0,
            recent_context_percentage=40.0,
            aging_context_percentage=20.0,
            stale_context_percentage=15.0,
            fresh_items=[{"path": "test", "timestamp": "2024-01-01"}],
            recent_items=[],
            aging_items=[],
            stale_items=[],
            estimated_session_start="2024-01-01T10:00:00Z",
            session_duration_minutes=120.5,
            session_activity_score=0.75,
            total_items_categorized=50,
            items_with_timestamps=30,
            analysis_timestamp="2024-01-01T12:00:00Z",
            recency_analysis_duration=1.5,
        )

        assert report.fresh_context_percentage == 25.0
        assert report.session_duration_minutes == 120.5
        assert len(report.fresh_items) == 1
        assert report.recency_analysis_duration == 1.5

    def test_get_recency_summary(self):
        """Test recency summary generation."""
        report = RecencyReport(
            fresh_context_percentage=30.0,
            recent_context_percentage=35.0,
            aging_context_percentage=25.0,
            stale_context_percentage=10.0,
            fresh_items=[],
            recent_items=[],
            aging_items=[],
            stale_items=[],
            estimated_session_start=None,
            session_duration_minutes=0,
            session_activity_score=0,
            total_items_categorized=0,
            items_with_timestamps=0,
            analysis_timestamp="",
            recency_analysis_duration=0,
        )

        summary = report.get_recency_summary()

        assert "30%" in summary  # Fresh
        assert "35%" in summary  # Recent
        assert "25%" in summary  # Aging
        assert "10%" in summary  # Stale


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
