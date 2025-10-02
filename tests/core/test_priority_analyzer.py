#!/usr/bin/env python3
"""
Tests for the Priority Analysis Engine

Comprehensive tests for priority analysis including:
- Priority score calculation
- Urgency and impact level assessment
- Deadline extraction and parsing
- Dependency detection
- Content categorization by priority
- Reorder recommendations
- Focus improvement suggestions
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.context_cleaner.core.priority_analyzer import (
    PriorityAnalyzer,
    PriorityReport,
    PriorityItem,
)


class TestPriorityAnalyzer:
    """Test suite for PriorityAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = PriorityAnalyzer()

        self.sample_context = {
            "urgent_tasks": [
                "CRITICAL: Production server down - fix immediately!",  # Critical
                "High priority: Deploy hotfix by end of day",  # High + Deadline
                "Urgent: Customer reported login issues blocking sales",  # Critical + Impact
            ],
            "current_work": [
                "Currently implementing OAuth2 integration",  # Current work
                "Working on user authentication module today",  # Current + Today
                "In progress: Writing unit tests for auth system",  # Current + Action
                "Must complete API documentation by Friday",  # Current + Deadline
            ],
            "planned_work": [
                "TODO: Refactor legacy code when time permits",  # Low priority
                "Nice to have: Add dark mode theme",  # Low priority
                "Future: Consider migrating to microservices",  # Future/Low
                "Enhancement: Improve error messaging",  # Enhancement
            ],
            "completed_old": [
                "Completed: Database migration last week",  # Noise (completed)
                "Resolved: Fixed pagination bug yesterday",  # Noise (resolved)
                "Archived: Old authentication system docs",  # Noise (archived)
                "Deprecated: Legacy API endpoints",  # Noise (deprecated)
            ],
            "dependencies": [
                "Waiting for design team to provide new mockups",  # Dependency
                "Blocked by: Need approval from security team",  # Blocking
                "Depends on: Database schema changes",  # Dependency
                "Requires testing environment setup first",  # Dependency
            ],
        }

    @pytest.mark.asyncio
    async def test_analyze_priorities_basic(self):
        """Test basic priority analysis functionality."""
        report = await self.analyzer.analyze_priorities(self.sample_context)

        assert isinstance(report, PriorityReport)
        assert (
            report.priority_alignment_score >= 0
            and report.priority_alignment_score <= 100
        )
        assert report.current_work_focus_percentage >= 0
        assert report.urgent_items_ratio >= 0
        assert report.blocking_items_count >= 0
        assert report.total_items_analyzed > 0
        assert report.priority_analysis_duration > 0

    @pytest.mark.asyncio
    async def test_detect_critical_items(self):
        """Test detection of critical priority items."""
        report = await self.analyzer.analyze_priorities(self.sample_context)

        # Should detect critical items
        assert len(report.critical_items) >= 2  # We have at least 2 critical items

        # Check critical items have high priority scores
        for item in report.critical_items:
            assert item.urgency_level == "critical"
            assert item.priority_score >= 80

    @pytest.mark.asyncio
    async def test_detect_current_work(self):
        """Test detection of current work items."""
        report = await self.analyzer.analyze_priorities(self.sample_context)

        # Should have reasonable current work focus
        assert report.current_work_focus_percentage > 0

        # Should detect current work category items
        current_work_items = [
            item
            for item in report.critical_items + report.high_priority_items
            if item.category == "current_work"
        ]
        assert len(current_work_items) > 0

    @pytest.mark.asyncio
    async def test_detect_noise_items(self):
        """Test detection of noise/obsolete items."""
        report = await self.analyzer.analyze_priorities(self.sample_context)

        # Should detect noise items
        assert len(report.noise_items) >= 4  # We have 4 completed/obsolete items

        # Check noise items have low scores
        for item in report.noise_items:
            assert item.category == "noise"
            assert item.priority_score < 50

    def test_extract_deadlines_basic(self):
        """Test basic deadline extraction."""
        content = "Deploy hotfix by end of day and complete documentation by Friday"
        deadlines = self.analyzer._extract_deadlines(content)

        assert len(deadlines) >= 1
        # Should extract some deadline information
        assert any(
            "day" in deadline.lower() or "friday" in deadline.lower()
            for deadline in deadlines
        )

    def test_extract_deadlines_iso_format(self):
        """Test deadline extraction with ISO format dates."""
        content = "Project deadline: 2024-12-25 and review by 2024-12-20"
        deadlines = self.analyzer._extract_deadlines(content)

        assert len(deadlines) >= 2
        assert "2024-12-25" in deadlines or "2024-12-20" in deadlines

    def test_extract_deadlines_relative(self):
        """Test deadline extraction with relative dates."""
        content = "Due today, review tomorrow, and deploy this week"
        deadlines = self.analyzer._extract_deadlines(content)

        assert len(deadlines) >= 3
        assert "today" in [d.lower() for d in deadlines]

    def test_extract_dependencies_basic(self):
        """Test basic dependency extraction."""
        content = (
            "This task depends on database migration and is blocked by security review"
        )
        dependencies = self.analyzer._extract_dependencies(content)

        assert len(dependencies) >= 2
        # Should extract dependency information
        assert any("database migration" in dep.lower() for dep in dependencies)
        assert any("security review" in dep.lower() for dep in dependencies)

    def test_extract_dependencies_various_patterns(self):
        """Test dependency extraction with various patterns."""
        test_cases = [
            ("Waiting for design team approval", ["design team approval"]),
            (
                "Requires testing environment setup first",
                ["testing environment setup first"],
            ),
            ("Needs API key before proceeding", ["API key"]),
            ("After database schema changes", ["database schema changes"]),
        ]

        for content, expected_deps in test_cases:
            dependencies = self.analyzer._extract_dependencies(content)
            assert len(dependencies) >= len(expected_deps)

    def test_calculate_priority_score_critical(self):
        """Test priority score calculation for critical items."""
        content = "CRITICAL: Production server down - fix immediately!"
        score, urgency, impact = self.analyzer._calculate_priority_score(content, 0, 10)

        assert score >= 85  # Should be high priority
        assert urgency == "critical"
        assert impact == "high"

    def test_calculate_priority_score_current_work(self):
        """Test priority score calculation for current work."""
        content = "Currently implementing user authentication module"
        score, urgency, impact = self.analyzer._calculate_priority_score(content, 0, 10)

        assert score >= 70  # Should be high for current work
        assert urgency in ["high", "critical"]
        assert impact == "high"

    def test_calculate_priority_score_low_priority(self):
        """Test priority score calculation for low priority items."""
        content = "Nice to have feature - maybe consider someday"
        score, urgency, impact = self.analyzer._calculate_priority_score(
            content, 8, 10
        )  # Near end

        assert score <= 60  # Should be lower priority
        assert urgency in ["low", "medium"]
        assert impact == "low"

    def test_calculate_priority_score_position_bonus(self):
        """Test position bonus in priority score calculation."""
        content = "High priority task"

        # Same content, different positions
        score_top, _, _ = self.analyzer._calculate_priority_score(content, 0, 10)  # Top
        score_middle, _, _ = self.analyzer._calculate_priority_score(
            content, 5, 10
        )  # Middle
        score_bottom, _, _ = self.analyzer._calculate_priority_score(
            content, 9, 10
        )  # Bottom

        # Earlier items should get position bonus
        assert score_top >= score_middle >= score_bottom

    def test_categorize_by_priority_current_work(self):
        """Test content categorization for current work."""
        category = self.analyzer._categorize_by_priority(
            75, "high", "Currently working on auth system"
        )
        assert category == "current_work"

    def test_categorize_by_priority_blocking(self):
        """Test content categorization for blocking items."""
        category = self.analyzer._categorize_by_priority(
            70, "high", "Blocked by security review"
        )
        assert category == "blocking"

    def test_categorize_by_priority_noise(self):
        """Test content categorization for noise items."""
        category = self.analyzer._categorize_by_priority(
            30, "low", "Completed old legacy system migration"
        )
        assert category == "noise"

    def test_analyze_priority_conflicts_detection(self):
        """Test priority conflict detection."""
        # Mock items with conflicting signals
        priority_items = [
            PriorityItem(
                path="test1",
                content="High priority: Maybe consider this someday",  # Conflict: high + low
                priority_score=60,
                urgency_level="medium",
                impact_level="medium",
                category="routine",
                deadline=None,
                dependencies=[],
            ),
            PriorityItem(
                path="test2",
                content="Currently working on deprecated feature",  # Conflict: current + obsolete
                priority_score=45,
                urgency_level="medium",
                impact_level="low",
                category="current_work",
                deadline=None,
                dependencies=[],
            ),
        ]

        conflicts = self.analyzer._analyze_priority_conflicts(priority_items)

        # Should detect conflicts
        assert len(conflicts) >= 1

        for conflict in conflicts:
            assert "path" in conflict
            assert "conflicts" in conflict
            assert len(conflict["conflicts"]) > 0

    def test_generate_reorder_recommendations(self):
        """Test reorder recommendation generation."""
        # Mock items with poor ordering - high priority at end, noise in first half
        priority_items = [
            PriorityItem(
                path="item[0]",
                content="Low priority item",
                priority_score=30,
                urgency_level="low",
                impact_level="low",
                category="routine",
                deadline=None,
                dependencies=[],
            ),
            PriorityItem(
                path="item[1]",
                content="Obsolete noise item",
                priority_score=10,
                urgency_level="low",
                impact_level="low",
                category="noise",
                deadline=None,
                dependencies=[],
            ),
            PriorityItem(
                path="item[2]",
                content="Another low priority",
                priority_score=25,
                urgency_level="low",
                impact_level="low",
                category="routine",
                deadline=None,
                dependencies=[],
            ),
            PriorityItem(
                path="item[3]",
                content="CRITICAL: High priority item",
                priority_score=95,
                urgency_level="critical",
                impact_level="high",
                category="critical",
                deadline=None,
                dependencies=[],
            ),
        ]

        recommendations = self.analyzer._generate_reorder_recommendations(
            priority_items
        )

        # Should recommend moving high priority item up
        move_up_recs = [r for r in recommendations if r["type"] == "move_up"]
        assert len(move_up_recs) >= 1

        # Should recommend moving noise item down
        move_down_recs = [r for r in recommendations if r["type"] == "move_down"]
        assert len(move_down_recs) >= 1

    def test_generate_focus_improvements(self):
        """Test focus improvement generation."""
        # Mock items with focus issues
        priority_items = [
            PriorityItem("path1", "Noise item", 20, "low", "low", "noise", None, []),
            PriorityItem("path2", "Another noise", 15, "low", "low", "noise", None, []),
            PriorityItem("path3", "More noise", 10, "low", "low", "noise", None, []),
            PriorityItem(
                "path4", "Some work", 60, "medium", "medium", "routine", None, []
            ),
            PriorityItem(
                "path5", "Blocking item", 70, "high", "high", "blocking", None, []
            ),
        ]

        improvements = self.analyzer._generate_focus_improvements(priority_items, 45)

        assert len(improvements) > 0

        # Should suggest removing noise items
        noise_suggestion = any("noise" in imp.lower() for imp in improvements)
        assert noise_suggestion

        # Should mention blocking items
        blocking_suggestion = any("blocking" in imp.lower() for imp in improvements)
        assert blocking_suggestion

    def test_extract_content_items_with_positions(self):
        """Test content extraction with position information."""
        items = self.analyzer._extract_content_items_with_positions(self.sample_context)

        assert len(items) > 0

        # Check structure
        for position, path, content in items:
            assert isinstance(position, int)
            assert isinstance(path, str)
            assert isinstance(content, str)
            assert position >= 0

    @pytest.mark.asyncio
    async def test_analyze_priorities_with_deadlines(self):
        """Test priority analysis with deadline detection."""
        deadline_context = {
            "tasks": [
                "Deploy hotfix by end of day - URGENT",
                "Complete documentation by Friday",
                "Review code by 2024-12-20",
                "Submit report due tomorrow",
            ]
        }

        report = await self.analyzer.analyze_priorities(deadline_context)

        # Should detect items with deadlines
        assert len(report.items_with_deadlines) >= 3

        # Check deadline extraction
        for item in report.items_with_deadlines:
            assert item.deadline is not None
            assert len(item.deadline) > 0

    @pytest.mark.asyncio
    async def test_analyze_priorities_with_dependencies(self):
        """Test priority analysis with dependency detection."""
        dependency_context = {
            "tasks": [
                "Waiting for design team approval before proceeding",
                "Blocked by security review - cannot continue",
                "Depends on database migration completion",
                "Requires API key setup first",
            ]
        }

        report = await self.analyzer.analyze_priorities(dependency_context)

        # Should detect blocking dependencies
        assert len(report.blocking_dependencies) >= 1

        # Check dependency structure
        for path, deps in report.blocking_dependencies:
            assert isinstance(path, str)
            assert isinstance(deps, list)
            assert len(deps) > 0

    @pytest.mark.asyncio
    async def test_analyze_priorities_empty_context(self):
        """Test priority analysis with empty context."""
        empty_context = {}

        report = await self.analyzer.analyze_priorities(empty_context)

        # Should handle empty context gracefully
        assert isinstance(report, PriorityReport)
        assert report.total_items_analyzed == 0
        assert report.priority_alignment_score == 50  # Default
        assert report.current_work_focus_percentage == 0.0

    @pytest.mark.asyncio
    async def test_analyze_priorities_performance(self):
        """Test priority analysis performance with large dataset."""
        # Create large context
        large_context = {}
        for i in range(100):
            large_context[f"category_{i//10}"] = [
                f'Task {j}: {"urgent" if j % 5 == 0 else "normal"} priority item {i}-{j}'
                for j in range(10)
            ]

        start_time = datetime.now()
        report = await self.analyzer.analyze_priorities(large_context)
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        assert duration < 3.0  # Should complete reasonably quickly
        # Analyzer flattens nested lists, so 10 keys * 10 items each = 100 items
        assert report.total_items_analyzed == 100

    @pytest.mark.asyncio
    async def test_analyze_priorities_error_handling(self):
        """Test priority analysis error handling."""
        # Mock internal method to raise exception
        with patch.object(
            self.analyzer, "_extract_content_items_with_positions"
        ) as mock:
            mock.side_effect = Exception("Test error")

            report = await self.analyzer.analyze_priorities(self.sample_context)

            # Should return empty report on error
            assert isinstance(report, PriorityReport)
            assert report.total_items_analyzed == 0

    def test_priority_keyword_regex_patterns(self):
        """Test that priority keyword regex patterns work correctly."""
        # Test critical urgency keywords
        critical_text = "CRITICAL: Production server is down"
        assert self.analyzer.critical_regex.search(critical_text) is not None

        # Test high priority keywords
        priority_text = "High priority task needs attention"
        assert self.analyzer.high_priority_regex.search(priority_text) is not None

        # Test current work keywords
        current_text = "Currently implementing new feature"
        assert self.analyzer.current_work_regex.search(current_text) is not None

        # Test low priority keywords
        low_text = "Nice to have feature for someday"
        assert self.analyzer.low_priority_regex.search(low_text) is not None

        # Test noise keywords
        noise_text = "Completed old deprecated functionality"
        assert self.analyzer.noise_regex.search(noise_text) is not None


class TestPriorityItem:
    """Test suite for PriorityItem NamedTuple."""

    def test_priority_item_creation(self):
        """Test creating PriorityItem with all fields."""
        item = PriorityItem(
            path="test.path",
            content="Test content with urgent priority",
            priority_score=85,
            urgency_level="high",
            impact_level="medium",
            category="current_work",
            deadline="end of day",
            dependencies=["task1", "task2"],
        )

        assert item.path == "test.path"
        assert item.priority_score == 85
        assert item.urgency_level == "high"
        assert item.category == "current_work"
        assert len(item.dependencies) == 2

    def test_priority_item_optional_fields(self):
        """Test PriorityItem with optional fields as None."""
        item = PriorityItem(
            path="test.path",
            content="Test content",
            priority_score=60,
            urgency_level="medium",
            impact_level="low",
            category="routine",
            deadline=None,
            dependencies=[],
        )

        assert item.deadline is None
        assert len(item.dependencies) == 0


class TestPriorityReport:
    """Test suite for PriorityReport dataclass."""

    def test_priority_report_creation(self):
        """Test creating PriorityReport with all fields."""
        report = PriorityReport(
            priority_alignment_score=75,
            current_work_focus_percentage=60.5,
            urgent_items_ratio=0.3,
            blocking_items_count=2,
            critical_items=[],
            high_priority_items=[],
            medium_priority_items=[],
            low_priority_items=[],
            noise_items=[],
            items_with_deadlines=[],
            blocking_dependencies=[],
            priority_conflicts=[],
            reorder_recommendations=[],
            focus_improvement_actions=["Action 1", "Action 2"],
            priority_cleanup_opportunities=["Cleanup 1"],
            total_items_analyzed=50,
            items_with_priority_signals=30,
            priority_analysis_duration=1.8,
        )

        assert report.priority_alignment_score == 75
        assert report.current_work_focus_percentage == 60.5
        assert len(report.focus_improvement_actions) == 2
        assert report.priority_analysis_duration == 1.8

    def test_get_priority_summary(self):
        """Test priority summary generation."""
        report = PriorityReport(
            priority_alignment_score=82,
            current_work_focus_percentage=67.5,
            urgent_items_ratio=0.25,
            blocking_items_count=3,
            critical_items=[Mock(), Mock()],  # 2 critical items
            high_priority_items=[],
            medium_priority_items=[],
            low_priority_items=[],
            noise_items=[],
            items_with_deadlines=[],
            blocking_dependencies=[],
            priority_conflicts=[],
            reorder_recommendations=[],
            focus_improvement_actions=[],
            priority_cleanup_opportunities=[],
            total_items_analyzed=0,
            items_with_priority_signals=0,
            priority_analysis_duration=0,
        )

        summary = report.get_priority_summary()

        assert "82%" in summary  # Priority alignment
        assert "68%" in summary  # Current work focus (rounded)
        assert "2" in summary  # Critical items count
        assert "3" in summary  # Blocking items count


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
