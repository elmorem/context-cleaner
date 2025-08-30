#!/usr/bin/env python3
"""
Priority Analysis Engine

Analyzes context content to determine priority levels and work importance:
- Current Work Assessment: How much content relates to immediate tasks
- Urgency Detection: Identifies time-sensitive or blocking items
- Impact Analysis: Assesses relative importance of different content areas
- Priority Ranking: Ranks content by importance for focus optimization

Uses deadline detection, urgency keywords, dependency analysis, and semantic importance scoring.
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


class PriorityItem(NamedTuple):
    """Represents a prioritized content item."""

    path: str
    content: str
    priority_score: int  # 0-100 priority score
    urgency_level: str  # 'critical', 'high', 'medium', 'low'
    impact_level: str  # 'high', 'medium', 'low'
    category: str  # 'current_work', 'blocking', 'important', 'routine', 'noise'
    deadline: Optional[str]  # Extracted deadline if any
    dependencies: List[str]  # Items this depends on or blocks


@dataclass
class PriorityReport:
    """Comprehensive priority analysis report."""

    # Overall priority assessment
    priority_alignment_score: int  # How well priorities are organized (0-100)
    current_work_focus_percentage: float  # Percentage focused on current work
    urgent_items_ratio: float  # Ratio of urgent to total items
    blocking_items_count: int  # Items that are blocking progress

    # Prioritized content lists
    critical_items: List[PriorityItem]  # Critical/urgent items
    high_priority_items: List[PriorityItem]  # Important current work
    medium_priority_items: List[PriorityItem]  # Useful but not urgent
    low_priority_items: List[PriorityItem]  # Nice to have/future
    noise_items: List[PriorityItem]  # Distracting/irrelevant

    # Deadline and dependency analysis
    items_with_deadlines: List[PriorityItem]  # Items with time constraints
    blocking_dependencies: List[Tuple[str, List[str]]]  # Dependency chains
    priority_conflicts: List[Dict[str, Any]]  # Conflicting priority signals

    # Optimization recommendations
    reorder_recommendations: List[Dict[str, Any]]  # Suggestions for reordering
    focus_improvement_actions: List[str]  # Actions to improve focus
    priority_cleanup_opportunities: List[str]  # Items safe to remove/demote

    # Analysis metadata
    total_items_analyzed: int  # Total content items analyzed
    items_with_priority_signals: int  # Items with detectable priority
    priority_analysis_duration: float  # Time taken for analysis

    def get_priority_summary(self) -> str:
        """Get human-readable priority summary."""
        return (
            f"Priority Alignment: {self.priority_alignment_score}% | "
            f"Current Work Focus: {self.current_work_focus_percentage:.0f}% | "
            f"Urgent Items: {len(self.critical_items)} | "
            f"Blocking Items: {self.blocking_items_count}"
        )


class PriorityAnalyzer:
    """
    Advanced Priority Analysis Engine

    Analyzes context content to identify priority levels, urgency, and importance
    for optimal context organization and focus optimization.
    """

    # Priority signal patterns
    CRITICAL_URGENCY_KEYWORDS = [
        "critical",
        "urgent",
        "emergency",
        "blocker",
        "blocking",
        "asap",
        "immediately",
        "now",
        "crisis",
        "broken",
        "down",
        "failing",
        "deadline today",
        "due now",
        "overdue",
    ]

    HIGH_PRIORITY_KEYWORDS = [
        "high priority",
        "important",
        "priority",
        "needed",
        "required",
        "must have",
        "essential",
        "crucial",
        "key",
        "main",
        "primary",
        "deadline",
        "due",
        "target",
        "milestone",
        "goal",
    ]

    CURRENT_WORK_KEYWORDS = [
        "current",
        "currently",
        "working on",
        "in progress",
        "active",
        "implementing",
        "developing",
        "building",
        "debugging",
        "fixing",
        "today",
        "this",
        "now",
        "immediate",
        "next",
    ]

    LOW_PRIORITY_KEYWORDS = [
        "nice to have",
        "optional",
        "maybe",
        "consider",
        "someday",
        "eventually",
        "future",
        "later",
        "low priority",
        "if time",
        "bonus",
        "enhancement",
        "improvement",
    ]

    NOISE_KEYWORDS = [
        "random",
        "tangent",
        "unrelated",
        "off topic",
        "aside",
        "obsolete",
        "deprecated",
        "old",
        "archived",
        "completed",
        "done",
        "finished",
        "resolved",
        "closed",
    ]

    # Deadline detection patterns
    DEADLINE_PATTERNS = [
        r"(?i)deadline\s*:?\s*([^\n,\.]+)",
        r"(?i)due\s*:?\s*([^\n,\.]+)",
        r"(?i)by\s+([\d]{1,2}[/-][\d]{1,2}(?:[/-][\d]{2,4})?)",
        r"(?i)end\s+of\s+(day|week|month|sprint)",
        r"(?i)(today|tomorrow|this\s+week|next\s+week)",
        r"(?i)(\d{4}-\d{2}-\d{2})",
    ]

    # Dependency detection patterns
    DEPENDENCY_PATTERNS = [
        r"(?i)depends\s+on\s+([^\n,\.]+)",
        r"(?i)blocked\s+by\s+([^\n,\.]+)",
        r"(?i)waiting\s+for\s+([^\n,\.]+)",
        r"(?i)requires?\s+([^\n,\.]+)",
        r"(?i)needs?\s+([^\n,\.]+)\s+(?:to|before)",
        r"(?i)after\s+([^\n,\.]+)",
    ]

    def __init__(self):
        """Initialize priority analysis engine."""
        # Compile regex patterns for efficiency
        self.critical_regex = re.compile(
            "|".join(self.CRITICAL_URGENCY_KEYWORDS), re.IGNORECASE
        )
        self.high_priority_regex = re.compile(
            "|".join(self.HIGH_PRIORITY_KEYWORDS), re.IGNORECASE
        )
        self.current_work_regex = re.compile(
            "|".join(self.CURRENT_WORK_KEYWORDS), re.IGNORECASE
        )
        self.low_priority_regex = re.compile(
            "|".join(self.LOW_PRIORITY_KEYWORDS), re.IGNORECASE
        )
        self.noise_regex = re.compile("|".join(self.NOISE_KEYWORDS), re.IGNORECASE)

        self.deadline_patterns = [
            re.compile(pattern) for pattern in self.DEADLINE_PATTERNS
        ]
        self.dependency_patterns = [
            re.compile(pattern) for pattern in self.DEPENDENCY_PATTERNS
        ]

        logger.debug("PriorityAnalyzer initialized")

    def _extract_deadlines(self, content: str) -> List[str]:
        """Extract deadline information from content."""
        deadlines = []

        for pattern in self.deadline_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    match = (
                        match[0] if match[0] else (match[1] if len(match) > 1 else "")
                    )
                if match and len(match.strip()) > 0:
                    deadlines.append(match.strip())

        return deadlines

    def _extract_dependencies(self, content: str) -> List[str]:
        """Extract dependency information from content."""
        dependencies = []

        for pattern in self.dependency_patterns:
            matches = pattern.findall(content)
            for match in matches:
                if match and len(match.strip()) > 0:
                    # Clean up the dependency text
                    cleaned = re.sub(r"[^\w\s-]", "", match.strip())
                    if len(cleaned) > 2:  # Skip very short matches
                        dependencies.append(cleaned)

        return dependencies

    def _calculate_priority_score(
        self, content: str, context_position: int, total_items: int
    ) -> Tuple[int, str, str]:
        """Calculate priority score and categorization for content item."""
        content_lower = content.lower()
        base_score = 50  # Default medium priority

        # Priority signal detection
        urgency_signals = {"critical": 0, "high": 0, "current": 0, "low": 0, "noise": 0}

        # Check for different priority signals
        if self.critical_regex.search(content_lower):
            urgency_signals["critical"] = 40
        if self.high_priority_regex.search(content_lower):
            urgency_signals["high"] = 30
        if self.current_work_regex.search(content_lower):
            urgency_signals["current"] = 25
        if self.low_priority_regex.search(content_lower):
            urgency_signals["low"] = -20
        if self.noise_regex.search(content_lower):
            urgency_signals["noise"] = -30

        # Calculate weighted score
        signal_score = sum(urgency_signals.values())
        priority_score = min(100, max(0, base_score + signal_score))

        # Position bonus (items appearing earlier get slight priority boost)
        position_ratio = context_position / max(1, total_items)
        if position_ratio < 0.25:  # Top 25%
            priority_score += 10
        elif position_ratio < 0.5:  # Top 50%
            priority_score += 5

        # Determine urgency and impact levels
        if urgency_signals["critical"] > 0 or priority_score >= 90:
            urgency_level = "critical"
        elif urgency_signals["high"] > 0 or priority_score >= 75:
            urgency_level = "high"
        elif priority_score >= 55:
            urgency_level = "medium"
        else:
            urgency_level = "low"

        # Impact assessment (simplified - could be more sophisticated)
        if urgency_signals["critical"] > 0 or urgency_signals["current"] > 0:
            impact_level = "high"
        elif urgency_signals["high"] > 0:
            impact_level = "medium"
        else:
            impact_level = "low"

        return int(priority_score), urgency_level, impact_level

    def _categorize_by_priority(
        self, priority_score: int, urgency_level: str, content: str
    ) -> str:
        """Categorize content by priority and characteristics."""
        content_lower = content.lower()

        # Special categories
        if self.noise_regex.search(content_lower):
            return "noise"

        if "block" in content_lower or "stuck" in content_lower:
            return "blocking"

        if self.current_work_regex.search(content_lower):
            return "current_work"

        # Priority-based categories
        if priority_score >= 85:
            return "critical"
        elif priority_score >= 70:
            return "important"
        elif priority_score >= 45:
            return "routine"
        else:
            return "low_priority"

    def _analyze_priority_conflicts(
        self, priority_items: List[PriorityItem]
    ) -> List[Dict[str, Any]]:
        """Identify conflicting priority signals in content."""
        conflicts = []

        for item in priority_items:
            content_lower = item.content.lower()

            # Look for mixed signals
            has_high_priority = self.high_priority_regex.search(content_lower)
            has_low_priority = self.low_priority_regex.search(content_lower)
            has_current = self.current_work_regex.search(content_lower)
            has_noise = self.noise_regex.search(content_lower)

            conflict_signals = []
            if has_high_priority and has_low_priority:
                conflict_signals.append("High and low priority signals")
            if has_current and has_noise:
                conflict_signals.append("Current work and noise signals")
            if has_high_priority and has_noise:
                conflict_signals.append("High priority and obsolete signals")

            if conflict_signals:
                conflicts.append(
                    {
                        "path": item.path,
                        "content_preview": item.content[:100] + "...",
                        "conflicts": conflict_signals,
                        "priority_score": item.priority_score,
                    }
                )

        return conflicts

    def _generate_reorder_recommendations(
        self, priority_items: List[PriorityItem]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations for reordering content by priority."""
        recommendations = []

        # Sort items by current position (assuming path indicates position)
        sorted_items = sorted(priority_items, key=lambda x: x.path)

        # Find high-priority items that appear late
        total_items = len(sorted_items)
        for i, item in enumerate(sorted_items):
            position_percentage = i / total_items

            if item.priority_score >= 80 and position_percentage > 0.5:
                recommendations.append(
                    {
                        "type": "move_up",
                        "item_path": item.path,
                        "current_position_pct": position_percentage * 100,
                        "recommended_position": "top_25_percent",
                        "reason": f"High priority item ({item.priority_score}) appearing in bottom half",
                        "content_preview": item.content[:80] + "...",
                    }
                )

            elif item.category == "noise" and position_percentage < 0.5:
                recommendations.append(
                    {
                        "type": "move_down",
                        "item_path": item.path,
                        "current_position_pct": position_percentage * 100,
                        "recommended_position": "bottom_25_percent",
                        "reason": "Noise/obsolete content appearing in top half",
                        "content_preview": item.content[:80] + "...",
                    }
                )

        return recommendations

    def _generate_focus_improvements(
        self, priority_items: List[PriorityItem], priority_alignment_score: int
    ) -> List[str]:
        """Generate actionable recommendations for improving focus."""
        improvements = []

        # Count items by category
        category_counts = defaultdict(int)
        for item in priority_items:
            category_counts[item.category] += 1

        total_items = len(priority_items)

        # Focus improvement suggestions based on content analysis
        if category_counts["noise"] > total_items * 0.2:
            improvements.append(
                f"Remove {category_counts['noise']} obsolete/noise items to improve focus"
            )

        if category_counts["critical"] == 0:
            improvements.append(
                "Consider marking current urgent items as critical priority"
            )

        if category_counts["current_work"] < total_items * 0.3:
            improvements.append(
                "Increase focus on current work items - only 30% of context relates to active tasks"
            )

        if priority_alignment_score < 60:
            improvements.append(
                "Reorder context to move high-priority items to the top"
            )

        blocking_items = [
            item for item in priority_items if item.category == "blocking"
        ]
        if blocking_items:
            improvements.append(
                f"Address {len(blocking_items)} blocking items to unblock progress"
            )

        return improvements

    def _extract_content_items_with_positions(
        self, context_data: Dict[str, Any]
    ) -> List[Tuple[int, str, str]]:
        """Extract content items with position information."""
        items = []
        position = 0

        def extract_recursive(data: Any, path: str = ""):
            nonlocal position
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, (dict, list)):
                        extract_recursive(value, current_path)
                    else:
                        items.append((position, current_path, str(value)))
                        position += 1
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    current_path = f"{path}[{i}]"
                    if isinstance(item, (dict, list)):
                        extract_recursive(item, current_path)
                    else:
                        items.append((position, current_path, str(item)))
                        position += 1

        extract_recursive(context_data)
        return items

    async def analyze_priorities(self, context_data: Dict[str, Any]) -> PriorityReport:
        """
        Perform comprehensive priority analysis on context data.

        Args:
            context_data: Context data to analyze for priority patterns

        Returns:
            PriorityReport with detailed priority analysis and recommendations
        """
        analysis_start = datetime.now()

        try:
            # Extract content items with positions
            content_items = self._extract_content_items_with_positions(context_data)

            if not content_items:
                logger.warning("No content items found for priority analysis")
                return self._get_empty_priority_report(analysis_start)

            # Analyze each item for priority characteristics
            priority_items = []
            items_with_deadlines = []
            blocking_dependencies = []

            for position, path, content in content_items:
                # Calculate priority score and levels
                priority_score, urgency_level, impact_level = (
                    self._calculate_priority_score(
                        content, position, len(content_items)
                    )
                )

                # Extract deadlines and dependencies
                deadlines = self._extract_deadlines(content)
                dependencies = self._extract_dependencies(content)

                # Categorize the item
                category = self._categorize_by_priority(
                    priority_score, urgency_level, content
                )

                # Create priority item
                priority_item = PriorityItem(
                    path=path,
                    content=content,
                    priority_score=priority_score,
                    urgency_level=urgency_level,
                    impact_level=impact_level,
                    category=category,
                    deadline=deadlines[0] if deadlines else None,
                    dependencies=dependencies,
                )

                priority_items.append(priority_item)

                if deadlines:
                    items_with_deadlines.append(priority_item)

                if dependencies and category == "blocking":
                    blocking_dependencies.append((path, dependencies))

            # Categorize items by priority levels
            critical_items = [
                item for item in priority_items if item.urgency_level == "critical"
            ]
            high_priority_items = [
                item for item in priority_items if item.urgency_level == "high"
            ]
            medium_priority_items = [
                item for item in priority_items if item.urgency_level == "medium"
            ]
            low_priority_items = [
                item for item in priority_items if item.urgency_level == "low"
            ]
            noise_items = [item for item in priority_items if item.category == "noise"]

            # Calculate priority alignment score
            total_items = len(priority_items)
            high_priority_count = len(
                [item for item in priority_items if item.priority_score >= 70]
            )
            top_quarter_count = total_items // 4

            # Count high-priority items in top quarter
            sorted_by_position = sorted(
                priority_items,
                key=lambda x: (
                    int(x.path.split("[")[-1].split("]")[0])
                    if "[" in x.path and "]" in x.path
                    else 0
                ),
            )
            high_priority_in_top = sum(
                1
                for item in sorted_by_position[:top_quarter_count]
                if item.priority_score >= 70
            )

            if high_priority_count > 0:
                priority_alignment_score = int(
                    (high_priority_in_top / high_priority_count) * 100
                )
            else:
                priority_alignment_score = 70  # Default if no high priority items

            # Calculate other metrics
            current_work_items = [
                item for item in priority_items if item.category == "current_work"
            ]
            current_work_focus_percentage = (
                (len(current_work_items) / total_items) * 100 if total_items > 0 else 0
            )

            urgent_items = len(critical_items) + len(high_priority_items)
            urgent_items_ratio = urgent_items / total_items if total_items > 0 else 0

            blocking_items_count = len(
                [item for item in priority_items if item.category == "blocking"]
            )

            # Generate analysis and recommendations
            priority_conflicts = self._analyze_priority_conflicts(priority_items)
            reorder_recommendations = self._generate_reorder_recommendations(
                priority_items
            )
            focus_improvement_actions = self._generate_focus_improvements(
                priority_items, priority_alignment_score
            )

            # Cleanup opportunities
            priority_cleanup_opportunities = []
            if noise_items:
                priority_cleanup_opportunities.append(
                    f"Remove {len(noise_items)} obsolete/noise items"
                )

            low_value_items = [
                item for item in priority_items if item.priority_score < 30
            ]
            if low_value_items:
                priority_cleanup_opportunities.append(
                    f"Consider removing {len(low_value_items)} very low priority items"
                )

            items_with_priority_signals = sum(
                1
                for item in priority_items
                if item.priority_score != 50 or item.deadline or item.dependencies
            )

            analysis_duration = (datetime.now() - analysis_start).total_seconds()

            report = PriorityReport(
                priority_alignment_score=priority_alignment_score,
                current_work_focus_percentage=current_work_focus_percentage,
                urgent_items_ratio=urgent_items_ratio,
                blocking_items_count=blocking_items_count,
                critical_items=critical_items,
                high_priority_items=high_priority_items,
                medium_priority_items=medium_priority_items,
                low_priority_items=low_priority_items,
                noise_items=noise_items,
                items_with_deadlines=items_with_deadlines,
                blocking_dependencies=blocking_dependencies,
                priority_conflicts=priority_conflicts,
                reorder_recommendations=reorder_recommendations,
                focus_improvement_actions=focus_improvement_actions,
                priority_cleanup_opportunities=priority_cleanup_opportunities,
                total_items_analyzed=total_items,
                items_with_priority_signals=items_with_priority_signals,
                priority_analysis_duration=analysis_duration,
            )

            logger.info(
                f"Priority analysis completed: {priority_alignment_score}% alignment, "
                f"{current_work_focus_percentage:.0f}% current work focus"
            )

            return report

        except Exception as e:
            logger.error(f"Priority analysis failed: {e}")
            return self._get_empty_priority_report(analysis_start)

    def _get_empty_priority_report(self, analysis_start: datetime) -> PriorityReport:
        """Return empty priority report in case of failure."""
        analysis_duration = (datetime.now() - analysis_start).total_seconds()

        return PriorityReport(
            priority_alignment_score=50,
            current_work_focus_percentage=0.0,
            urgent_items_ratio=0.0,
            blocking_items_count=0,
            critical_items=[],
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
            priority_analysis_duration=analysis_duration,
        )


if __name__ == "__main__":
    # Test priority analysis
    test_data = {
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

    import asyncio

    async def test_priority_analyzer():
        analyzer = PriorityAnalyzer()
        report = await analyzer.analyze_priorities(test_data)

        print("=== Priority Analysis Results ===")
        print(f"Priority Alignment Score: {report.priority_alignment_score}/100")
        print(f"Current Work Focus: {report.current_work_focus_percentage:.0f}%")
        print(f"Urgent Items Ratio: {report.urgent_items_ratio:.1%}")
        print(f"Blocking Items: {report.blocking_items_count}")

        print(f"\nPriority Breakdown:")
        print(f"  Critical Items: {len(report.critical_items)}")
        print(f"  High Priority Items: {len(report.high_priority_items)}")
        print(f"  Medium Priority Items: {len(report.medium_priority_items)}")
        print(f"  Low Priority Items: {len(report.low_priority_items)}")
        print(f"  Noise Items: {len(report.noise_items)}")

        print(f"\nCritical Items:")
        for item in report.critical_items[:3]:
            print(f"  - [{item.priority_score}] {item.content[:60]}...")

        print(f"\nItems with Deadlines ({len(report.items_with_deadlines)}):")
        for item in report.items_with_deadlines[:3]:
            print(f"  - {item.deadline}: {item.content[:50]}...")

        print(f"\nBlocking Dependencies ({len(report.blocking_dependencies)}):")
        for path, deps in report.blocking_dependencies[:2]:
            print(f"  - {path}: {deps}")

        print(f"\nReorder Recommendations ({len(report.reorder_recommendations)}):")
        for rec in report.reorder_recommendations[:2]:
            print(f"  - {rec['type']}: {rec['reason']}")

        print(f"\nFocus Improvements:")
        for improvement in report.focus_improvement_actions[:3]:
            print(f"  - {improvement}")

        print(f"\nAnalysis Duration: {report.priority_analysis_duration:.3f}s")

    asyncio.run(test_priority_analyzer())
