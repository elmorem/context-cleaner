#!/usr/bin/env python3
"""
Focus Scoring Engine

Calculates focus-related metrics for context analysis:
- Focus Score: Percentage of context directly related to current work
- Priority Alignment: Whether important items appear early in context
- Current Work Ratio: Ratio of active tasks to total context
- Attention Clarity: How clear the next steps are vs contextual noise

Uses semantic analysis, keyword detection, and content positioning to assess focus quality.
"""

import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class FocusMetrics:
    """Comprehensive focus analysis metrics."""

    # Core focus metrics (0-100 scores)
    focus_score: int  # Overall focus score
    priority_alignment_score: int  # Important items in top 25%
    current_work_ratio: float  # Active tasks vs total content
    attention_clarity_score: int  # Clear next steps vs noise

    # Detailed analysis
    total_content_items: int  # Total items analyzed
    work_related_items: int  # Items related to current work
    high_priority_items: int  # Items marked as high priority
    active_task_items: int  # Active/in-progress items
    noise_items: int  # Items adding noise/distraction

    # Content quality metrics
    context_coherence_score: int  # How well content fits together
    task_clarity_score: int  # How clear current tasks are
    goal_alignment_score: int  # Alignment with stated goals

    # Position analysis
    important_items_in_top_quarter: int  # High priority items in first 25%
    current_work_in_top_half: int  # Current work items in first 50%
    noise_in_bottom_half: int  # Noise items in last 50%

    # Analysis metadata
    focus_keywords_found: List[str]  # Keywords indicating focus
    distraction_keywords_found: List[str]  # Keywords indicating distraction
    analysis_method_breakdown: Dict[str, int]  # How items were categorized
    focus_analysis_duration: float  # Time taken for analysis

    def get_focus_summary(self) -> str:
        """Get human-readable focus summary."""
        return (
            f"Focus: {self.focus_score}% | Priority Alignment: {self.priority_alignment_score}% | "
            f"Current Work: {self.current_work_ratio:.1%} | Clarity: {self.attention_clarity_score}%"
        )


class FocusScorer:
    """
    Advanced Focus Scoring Engine

    Analyzes context content to determine how well-focused it is on current work
    and how clearly it presents actionable next steps.
    """

    # Focus-related keyword patterns
    CURRENT_WORK_KEYWORDS = [
        # Active work indicators
        "current",
        "currently",
        "working on",
        "in progress",
        "now",
        "today",
        "implementing",
        "debugging",
        "fixing",
        "building",
        "developing",
        "active",
        "ongoing",
        "next",
        "immediate",
        "priority",
        "urgent",
        # Task action words
        "todo",
        "task",
        "action",
        "need to",
        "should",
        "must",
        "required",
        "objective",
        "goal",
        "target",
        "milestone",
        "deadline",
        # Problem-solving indicators
        "issue",
        "problem",
        "bug",
        "error",
        "fix",
        "resolve",
        "solve",
        "investigate",
        "analyze",
        "review",
        "check",
        "test",
        "verify",
    ]

    DISTRACTION_KEYWORDS = [
        # Old/completed work
        "completed",
        "done",
        "finished",
        "archived",
        "old",
        "previous",
        "legacy",
        "deprecated",
        "obsolete",
        "historical",
        "past",
        # Low priority items
        "nice to have",
        "maybe",
        "consider",
        "someday",
        "eventually",
        "low priority",
        "not urgent",
        "future",
        "later",
        # Noise indicators
        "random",
        "tangent",
        "aside",
        "off topic",
        "unrelated",
        "distraction",
        "interruption",
        "sidebar",
    ]

    HIGH_PRIORITY_INDICATORS = [
        "urgent",
        "critical",
        "important",
        "priority",
        "asap",
        "immediate",
        "blocker",
        "blocking",
        "high priority",
        "must have",
        "required",
        "deadline",
        "due",
        "needed",
        "essential",
        "crucial",
    ]

    TASK_ACTION_PATTERNS = [
        # Clear action verbs
        r"\b(implement|build|create|develop|write|code|design)\b",
        r"\b(fix|debug|resolve|solve|address|handle)\b",
        r"\b(test|verify|validate|check|review|analyze)\b",
        r"\b(deploy|release|launch|publish|ship)\b",
        r"\b(update|modify|change|refactor|improve)\b",
        # Task structures
        r"\b(need to|should|must|have to|going to)\s+\w+",
        r"\b(todo|task|action):\s*\w+",
        r"\[\s*\]\s*\w+",  # Checkbox items
    ]

    def __init__(self):
        """Initialize focus scoring engine."""
        self.current_work_regex = re.compile(
            "|".join(self.CURRENT_WORK_KEYWORDS), re.IGNORECASE
        )
        self.distraction_regex = re.compile(
            "|".join(self.DISTRACTION_KEYWORDS), re.IGNORECASE
        )
        self.high_priority_regex = re.compile(
            "|".join(self.HIGH_PRIORITY_INDICATORS), re.IGNORECASE
        )
        self.task_action_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.TASK_ACTION_PATTERNS
        ]
        logger.debug("FocusScorer initialized")

    def _extract_content_with_positions(
        self, context_data: Dict[str, Any]
    ) -> List[Tuple[int, str, Any]]:
        """Extract content items with their position indices for priority analysis."""
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
                        items.append((position, current_path, value))
                        position += 1
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    current_path = f"{path}[{i}]"
                    if isinstance(item, (dict, list)):
                        extract_recursive(item, current_path)
                    else:
                        items.append((position, current_path, item))
                        position += 1

        extract_recursive(context_data)
        return items

    def _analyze_content_focus(self, content: str) -> Dict[str, Any]:
        """Analyze a single content item for focus-related characteristics."""
        content_lower = content.lower()

        analysis = {
            "is_current_work": False,
            "is_high_priority": False,
            "is_distraction": False,
            "is_actionable": False,
            "focus_keywords": [],
            "distraction_keywords": [],
            "priority_keywords": [],
            "action_patterns": [],
            "focus_score": 0,
        }

        # Check for current work indicators
        current_work_matches = self.current_work_regex.findall(content_lower)
        if current_work_matches:
            analysis["is_current_work"] = True
            analysis["focus_keywords"].extend(current_work_matches)

        # Check for high priority indicators
        priority_matches = self.high_priority_regex.findall(content_lower)
        if priority_matches:
            analysis["is_high_priority"] = True
            analysis["priority_keywords"].extend(priority_matches)

        # Check for distraction indicators
        distraction_matches = self.distraction_regex.findall(content_lower)
        if distraction_matches:
            analysis["is_distraction"] = True
            analysis["distraction_keywords"].extend(distraction_matches)

        # Check for actionable patterns
        for pattern in self.task_action_patterns:
            matches = pattern.findall(content_lower)
            if matches:
                analysis["is_actionable"] = True
                analysis["action_patterns"].extend(matches)

        # Calculate item-level focus score
        focus_points = 0
        if analysis["is_current_work"]:
            focus_points += 30
        if analysis["is_high_priority"]:
            focus_points += 25
        if analysis["is_actionable"]:
            focus_points += 20
        if analysis["is_distraction"]:
            focus_points -= 25

        # Bonus for multiple focus indicators
        if (
            sum(
                [
                    analysis["is_current_work"],
                    analysis["is_high_priority"],
                    analysis["is_actionable"],
                ]
            )
            >= 2
        ):
            focus_points += 15

        analysis["focus_score"] = min(100, max(0, focus_points))

        return analysis

    def _calculate_priority_alignment(
        self, items_with_analysis: List[Tuple[int, str, Any, Dict]]
    ) -> int:
        """Calculate how well high-priority items are positioned in the context."""
        if not items_with_analysis:
            return 50  # Neutral score

        total_items = len(items_with_analysis)
        top_quarter_threshold = total_items // 4

        # Count high priority items in top quarter
        high_priority_items = [
            item for item in items_with_analysis if item[3]["is_high_priority"]
        ]
        high_priority_in_top = sum(
            1 for item in high_priority_items if item[0] <= top_quarter_threshold
        )

        if not high_priority_items:
            return 70  # No high priority items found, assume decent organization

        alignment_ratio = high_priority_in_top / len(high_priority_items)
        return int(alignment_ratio * 100)

    def _calculate_attention_clarity(
        self, items_with_analysis: List[Tuple[int, str, Any, Dict]]
    ) -> int:
        """Calculate how clear the next steps are vs contextual noise."""
        if not items_with_analysis:
            return 50

        actionable_items = sum(
            1 for item in items_with_analysis if item[3]["is_actionable"]
        )
        current_work_items = sum(
            1 for item in items_with_analysis if item[3]["is_current_work"]
        )
        distraction_items = sum(
            1 for item in items_with_analysis if item[3]["is_distraction"]
        )

        total_items = len(items_with_analysis)

        # Calculate clarity components
        actionable_ratio = actionable_items / total_items if total_items > 0 else 0
        current_work_ratio = current_work_items / total_items if total_items > 0 else 0
        distraction_ratio = distraction_items / total_items if total_items > 0 else 0

        # Clarity score: high when many actionable/current items, low when many distractions
        clarity_score = ((actionable_ratio + current_work_ratio) * 50) - (
            distraction_ratio * 30
        )

        return int(min(100, max(0, clarity_score)))

    def _calculate_context_coherence(
        self, items_with_analysis: List[Tuple[int, str, Any, Dict]]
    ) -> int:
        """Calculate how well the context content fits together."""
        if len(items_with_analysis) < 2:
            return 80  # Small contexts assumed coherent

        # Analyze keyword overlap between items
        all_keywords = []
        for item in items_with_analysis:
            analysis = item[3]
            all_keywords.extend(analysis["focus_keywords"])
            all_keywords.extend(analysis["priority_keywords"])

        # Calculate keyword diversity vs repetition
        keyword_counter = Counter(all_keywords)
        total_keywords = len(all_keywords)
        unique_keywords = len(keyword_counter)

        if total_keywords == 0:
            return 60  # No keywords found, moderate coherence

        # Good coherence: some repetition (shared themes) but not too much
        repetition_ratio = (total_keywords - unique_keywords) / total_keywords
        optimal_repetition = 0.3  # 30% repetition is good for coherence

        coherence_score = 100 - abs(repetition_ratio - optimal_repetition) * 200
        return int(min(100, max(30, coherence_score)))

    def _calculate_overall_focus_score(self, metrics: Dict[str, Any]) -> int:
        """Calculate the overall focus score from component metrics."""
        # Weighted combination of focus components
        focus_components = [
            (metrics["work_related_ratio"] * 100, 0.3),  # 30% weight for work relevance
            (
                metrics["priority_alignment_score"],
                0.25,
            ),  # 25% weight for priority alignment
            (
                metrics["attention_clarity_score"],
                0.25,
            ),  # 25% weight for attention clarity
            (metrics["context_coherence_score"], 0.2),  # 20% weight for coherence
        ]

        weighted_score = sum(score * weight for score, weight in focus_components)
        return int(min(100, max(0, weighted_score)))

    async def calculate_focus_metrics(
        self, context_data: Dict[str, Any]
    ) -> FocusMetrics:
        """
        Calculate comprehensive focus metrics for context data.

        Args:
            context_data: Context data to analyze for focus quality

        Returns:
            FocusMetrics with detailed focus analysis and scores
        """
        analysis_start = datetime.now()

        try:
            # Extract content items with positions
            items_with_positions = self._extract_content_with_positions(context_data)

            if not items_with_positions:
                logger.warning("No content items found for focus analysis")
                return self._get_empty_focus_metrics(analysis_start)

            # Analyze each content item for focus characteristics
            items_with_analysis = []
            focus_keywords_found = []
            distraction_keywords_found = []

            for position, path, content in items_with_positions:
                content_str = str(content)
                analysis = self._analyze_content_focus(content_str)
                items_with_analysis.append((position, path, content, analysis))

                focus_keywords_found.extend(analysis["focus_keywords"])
                distraction_keywords_found.extend(analysis["distraction_keywords"])

            # Calculate core metrics
            total_items = len(items_with_analysis)
            work_related_items = sum(
                1 for item in items_with_analysis if item[3]["is_current_work"]
            )
            high_priority_items = sum(
                1 for item in items_with_analysis if item[3]["is_high_priority"]
            )
            active_task_items = sum(
                1 for item in items_with_analysis if item[3]["is_actionable"]
            )
            noise_items = sum(
                1 for item in items_with_analysis if item[3]["is_distraction"]
            )

            # Calculate ratios and scores
            work_related_ratio = (
                work_related_items / total_items if total_items > 0 else 0
            )
            priority_alignment_score = self._calculate_priority_alignment(
                items_with_analysis
            )
            attention_clarity_score = self._calculate_attention_clarity(
                items_with_analysis
            )
            context_coherence_score = self._calculate_context_coherence(
                items_with_analysis
            )

            # Position analysis
            top_quarter_threshold = total_items // 4
            top_half_threshold = total_items // 2
            bottom_half_threshold = total_items // 2

            important_items_in_top_quarter = sum(
                1
                for item in items_with_analysis
                if item[0] <= top_quarter_threshold and item[3]["is_high_priority"]
            )
            current_work_in_top_half = sum(
                1
                for item in items_with_analysis
                if item[0] <= top_half_threshold and item[3]["is_current_work"]
            )
            noise_in_bottom_half = sum(
                1
                for item in items_with_analysis
                if item[0] >= bottom_half_threshold and item[3]["is_distraction"]
            )

            # Task and goal clarity
            task_clarity_score = min(
                100, (active_task_items / max(1, total_items)) * 200
            )
            goal_alignment_score = min(
                100,
                ((work_related_items + high_priority_items) / max(1, total_items))
                * 100,
            )

            # Calculate overall focus score
            metrics_dict = {
                "work_related_ratio": work_related_ratio,
                "priority_alignment_score": priority_alignment_score,
                "attention_clarity_score": attention_clarity_score,
                "context_coherence_score": context_coherence_score,
            }
            overall_focus_score = self._calculate_overall_focus_score(metrics_dict)

            # Analysis method breakdown
            analysis_method_breakdown = {
                "keyword_based": sum(
                    1 for item in items_with_analysis if item[3]["focus_keywords"]
                ),
                "priority_based": high_priority_items,
                "action_based": active_task_items,
                "distraction_based": noise_items,
            }

            analysis_duration = (datetime.now() - analysis_start).total_seconds()

            metrics = FocusMetrics(
                focus_score=overall_focus_score,
                priority_alignment_score=priority_alignment_score,
                current_work_ratio=work_related_ratio,
                attention_clarity_score=attention_clarity_score,
                total_content_items=total_items,
                work_related_items=work_related_items,
                high_priority_items=high_priority_items,
                active_task_items=active_task_items,
                noise_items=noise_items,
                context_coherence_score=context_coherence_score,
                task_clarity_score=int(task_clarity_score),
                goal_alignment_score=int(goal_alignment_score),
                important_items_in_top_quarter=important_items_in_top_quarter,
                current_work_in_top_half=current_work_in_top_half,
                noise_in_bottom_half=noise_in_bottom_half,
                focus_keywords_found=list(set(focus_keywords_found))[
                    :10
                ],  # Limit to top 10
                distraction_keywords_found=list(set(distraction_keywords_found))[:10],
                analysis_method_breakdown=analysis_method_breakdown,
                focus_analysis_duration=analysis_duration,
            )

            logger.info(
                f"Focus analysis completed: {overall_focus_score}% focus score, "
                f"{work_related_ratio:.1%} work-related content"
            )

            return metrics

        except Exception as e:
            logger.error(f"Focus analysis failed: {e}")
            return self._get_empty_focus_metrics(analysis_start)

    def _get_empty_focus_metrics(self, analysis_start: datetime) -> FocusMetrics:
        """Return empty focus metrics in case of failure."""
        analysis_duration = (datetime.now() - analysis_start).total_seconds()

        return FocusMetrics(
            focus_score=50,  # Neutral score
            priority_alignment_score=50,
            current_work_ratio=0.0,
            attention_clarity_score=50,
            total_content_items=0,
            work_related_items=0,
            high_priority_items=0,
            active_task_items=0,
            noise_items=0,
            context_coherence_score=50,
            task_clarity_score=50,
            goal_alignment_score=50,
            important_items_in_top_quarter=0,
            current_work_in_top_half=0,
            noise_in_bottom_half=0,
            focus_keywords_found=[],
            distraction_keywords_found=[],
            analysis_method_breakdown={},
            focus_analysis_duration=analysis_duration,
        )


if __name__ == "__main__":
    # Test focus scoring
    test_data = {
        "current_objectives": [
            "Currently implementing OAuth2 authentication system",  # High focus
            "Fix urgent login bug that's blocking users",  # High focus + priority
            "Need to write unit tests for auth module",  # Actionable current work
        ],
        "completed_tasks": [
            "Completed database migration last week",  # Distraction (completed)
            "Old legacy system documentation",  # Distraction (old)
            "Archived project from 2023",  # Distraction (archived)
        ],
        "mixed_content": [
            "Review pull request - high priority",  # Priority work
            "Maybe consider refactoring later",  # Low priority
            "Random note about coffee preferences",  # Noise
            "Debug session for current auth implementation",  # Current work
            "Historical context from previous sprint",  # Potential distraction
        ],
        "action_items": [
            "TODO: Implement password validation",  # Clear action
            "[ ] Test OAuth flow with Google provider",  # Clear action
            "Should probably update documentation",  # Vague action
            "Must deploy hotfix by end of day",  # Urgent action
        ],
    }

    import asyncio

    async def test_focus_scorer():
        scorer = FocusScorer()
        metrics = await scorer.calculate_focus_metrics(test_data)

        print("=== Focus Analysis Results ===")
        print(f"Overall Focus Score: {metrics.focus_score}/100")
        print(f"Priority Alignment: {metrics.priority_alignment_score}/100")
        print(f"Current Work Ratio: {metrics.current_work_ratio:.1%}")
        print(f"Attention Clarity: {metrics.attention_clarity_score}/100")
        print(f"Context Coherence: {metrics.context_coherence_score}/100")
        print(f"Task Clarity: {metrics.task_clarity_score}/100")

        print(f"\nContent Breakdown:")
        print(f"  Total Items: {metrics.total_content_items}")
        print(f"  Work-Related: {metrics.work_related_items}")
        print(f"  High Priority: {metrics.high_priority_items}")
        print(f"  Actionable: {metrics.active_task_items}")
        print(f"  Noise/Distractions: {metrics.noise_items}")

        print(f"\nPosition Analysis:")
        print(f"  Priority Items in Top 25%: {metrics.important_items_in_top_quarter}")
        print(f"  Current Work in Top 50%: {metrics.current_work_in_top_half}")
        print(f"  Noise in Bottom 50%: {metrics.noise_in_bottom_half}")

        print(f"\nKeywords Found:")
        print(f"  Focus Keywords: {metrics.focus_keywords_found[:5]}")
        print(f"  Distraction Keywords: {metrics.distraction_keywords_found[:3]}")

        print(f"\nAnalysis Duration: {metrics.focus_analysis_duration:.3f}s")

    asyncio.run(test_focus_scorer())
