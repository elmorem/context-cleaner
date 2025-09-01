"""
Temporal Context Analyzer

Analyzes temporal patterns in Claude Code sessions including session boundaries,
topic drift detection, context transitions, and time-based usage patterns.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from .models import SessionAnalysis, CacheConfig
from .session_parser import SessionCacheParser
from .discovery import CacheDiscoveryService, CacheLocation

logger = logging.getLogger(__name__)


@dataclass
class TopicTransition:
    """Represents a transition between topics within or across sessions."""

    from_topic: str
    to_topic: str
    transition_time: datetime
    session_id: str
    confidence_score: float
    transition_type: str  # 'gradual', 'abrupt', 'return', 'continuation'
    context_similarity: float
    time_gap_minutes: float

    @property
    def is_abrupt_change(self) -> bool:
        """Check if this represents an abrupt topic change."""
        return self.transition_type == "abrupt" and self.confidence_score > 0.7

    @property
    def transition_speed(self) -> str:
        """Categorize transition speed."""
        if self.time_gap_minutes < 5:
            return "Immediate"
        elif self.time_gap_minutes < 30:
            return "Quick"
        elif self.time_gap_minutes < 120:
            return "Gradual"
        else:
            return "Delayed"


@dataclass
class SessionBoundary:
    """Represents a detected session boundary or natural break point."""

    boundary_time: datetime
    boundary_type: str  # 'natural_break', 'topic_shift', 'workflow_change', 'time_gap'
    confidence_score: float
    preceding_context: str
    following_context: str
    time_gap_minutes: float
    activity_change_score: float

    session_before: Optional[str] = None
    session_after: Optional[str] = None

    @property
    def is_strong_boundary(self) -> bool:
        """Check if this is a strong session boundary."""
        return (
            self.confidence_score > 0.8
            or self.time_gap_minutes > 60
            or self.activity_change_score > 0.7
        )

    @property
    def boundary_strength(self) -> str:
        """Get boundary strength category."""
        if self.confidence_score > 0.8:
            return "Strong"
        elif self.confidence_score > 0.6:
            return "Moderate"
        else:
            return "Weak"


@dataclass
class ContextEvolutionPattern:
    """Represents how context evolves over time."""

    pattern_id: str
    time_window: Tuple[datetime, datetime]
    evolution_type: str  # 'linear_progression', 'cyclical', 'branching', 'convergent'
    topics_sequence: List[str]
    complexity_progression: List[float]  # How complexity changes over time
    focus_drift_score: float
    return_frequency: float  # How often topics return

    dominant_topics: List[Tuple[str, float]]  # (topic, time_percentage)
    transition_patterns: List[str]
    productivity_correlation: float

    @property
    def evolution_stability(self) -> str:
        """Get stability of context evolution."""
        if self.focus_drift_score < 0.3:
            return "Stable"
        elif self.focus_drift_score < 0.6:
            return "Moderate"
        else:
            return "Unstable"


@dataclass
class TemporalInsights:
    """Comprehensive temporal analysis insights."""

    session_boundaries: List[SessionBoundary]
    topic_transitions: List[TopicTransition]
    evolution_patterns: List[ContextEvolutionPattern]

    average_session_length: float
    typical_break_duration: float
    peak_activity_periods: List[Tuple[datetime, datetime]]
    context_stability_score: float

    topic_drift_frequency: float  # transitions per hour
    return_to_topic_rate: float  # how often users return to previous topics
    multitasking_intensity: float  # concurrent context handling

    optimal_session_length: float  # suggested based on patterns
    recommended_break_frequency: float  # minutes between breaks

    productivity_time_patterns: Dict[str, float]  # hour -> productivity score
    context_switching_cost: float  # estimated productivity impact

    analysis_period: Tuple[datetime, datetime]
    confidence_score: float

    @property
    def overall_temporal_health(self) -> str:
        """Get overall temporal health assessment."""
        health_score = (
            (1 - self.topic_drift_frequency / 10) * 0.3  # Lower drift is better
            + self.context_stability_score * 0.3
            + (1 - self.context_switching_cost) * 0.2
            + (min(self.return_to_topic_rate, 1.0)) * 0.2
        )

        if health_score > 0.8:
            return "Excellent"
        elif health_score > 0.6:
            return "Good"
        elif health_score > 0.4:
            return "Fair"
        else:
            return "Needs Improvement"


class TemporalContextAnalyzer:
    """Analyzes temporal patterns and context evolution in Claude Code sessions."""

    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize the temporal context analyzer."""
        self.config = config or CacheConfig()
        self.parser = SessionCacheParser(config)
        self.discovery = CacheDiscoveryService(config)

        # Analysis parameters
        self.topic_similarity_threshold = 0.7
        self.session_boundary_time_threshold = 30  # minutes
        self.topic_transition_confidence_threshold = 0.6
        self.context_window_size = 5  # messages to consider for context

        # Topic detection keywords (simplified approach)
        self.topic_keywords = {
            "coding": [
                "function",
                "class",
                "variable",
                "import",
                "def",
                "return",
                "if",
            ],
            "debugging": [
                "error",
                "bug",
                "fix",
                "issue",
                "problem",
                "exception",
                "traceback",
            ],
            "testing": ["test", "assert", "mock", "unittest", "pytest", "coverage"],
            "documentation": [
                "readme",
                "docs",
                "document",
                "comment",
                "explain",
                "describe",
            ],
            "refactoring": ["refactor", "cleanup", "reorganize", "improve", "optimize"],
            "learning": [
                "how",
                "what",
                "why",
                "learn",
                "understand",
                "explain",
                "tutorial",
            ],
            "planning": [
                "plan",
                "design",
                "architecture",
                "structure",
                "approach",
                "strategy",
            ],
            "configuration": ["config", "setup", "install", "configure", "environment"],
        }

    def analyze_temporal_patterns(
        self,
        cache_locations: Optional[List[CacheLocation]] = None,
        time_window_days: Optional[int] = 30,
    ) -> TemporalInsights:
        """
        Analyze temporal patterns across cache locations.

        Args:
            cache_locations: Specific cache locations to analyze
            time_window_days: Number of days to include in analysis

        Returns:
            Comprehensive temporal analysis insights
        """
        logger.info("Starting temporal pattern analysis...")

        if cache_locations is None:
            cache_locations = self.discovery.discover_cache_locations()

        # Parse sessions and sort by time
        all_sessions = []
        cutoff_date = (
            datetime.now() - timedelta(days=time_window_days)
            if time_window_days
            else None
        )

        for location in cache_locations:
            logger.info(f"Analyzing temporal patterns in: {location.project_name}")

            for session_file in location.session_files:
                try:
                    analysis = self.parser.parse_session_file(session_file)
                    if (
                        analysis
                        and analysis.start_time
                        and (cutoff_date is None or analysis.start_time >= cutoff_date)
                    ):
                        all_sessions.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to parse session {session_file}: {e}")
                    continue

        # Sort sessions by start time
        all_sessions.sort(key=lambda x: x.start_time)

        logger.info(f"Analyzing {len(all_sessions)} sessions for temporal patterns")

        if not all_sessions:
            return self._create_empty_insights()

        # Perform temporal analysis
        session_boundaries = self._detect_session_boundaries(all_sessions)
        topic_transitions = self._analyze_topic_transitions(all_sessions)
        evolution_patterns = self._analyze_context_evolution(all_sessions)

        # Calculate metrics
        session_metrics = self._calculate_session_metrics(all_sessions)
        temporal_metrics = self._calculate_temporal_metrics(
            all_sessions, topic_transitions
        )
        productivity_patterns = self._analyze_productivity_patterns(all_sessions)

        # Determine analysis period
        start_time = min(s.start_time for s in all_sessions)
        end_time = max(s.end_time for s in all_sessions if s.end_time)

        insights = TemporalInsights(
            session_boundaries=session_boundaries,
            topic_transitions=topic_transitions,
            evolution_patterns=evolution_patterns,
            average_session_length=session_metrics["avg_length"],
            typical_break_duration=session_metrics["avg_break"],
            peak_activity_periods=productivity_patterns["peak_periods"],
            context_stability_score=temporal_metrics["stability"],
            topic_drift_frequency=temporal_metrics["drift_frequency"],
            return_to_topic_rate=temporal_metrics["return_rate"],
            multitasking_intensity=temporal_metrics["multitasking"],
            optimal_session_length=session_metrics["optimal_length"],
            recommended_break_frequency=session_metrics["recommended_breaks"],
            productivity_time_patterns=productivity_patterns["hourly_patterns"],
            context_switching_cost=temporal_metrics["switching_cost"],
            analysis_period=(start_time, end_time),
            confidence_score=self._calculate_analysis_confidence(all_sessions),
        )

        logger.info(
            f"Temporal analysis complete. Overall health: {insights.overall_temporal_health}"
        )

        return insights

    def _create_empty_insights(self) -> TemporalInsights:
        """Create empty insights when no data is available."""
        now = datetime.now()
        return TemporalInsights(
            session_boundaries=[],
            topic_transitions=[],
            evolution_patterns=[],
            average_session_length=0.0,
            typical_break_duration=0.0,
            peak_activity_periods=[],
            context_stability_score=0.0,
            topic_drift_frequency=0.0,
            return_to_topic_rate=0.0,
            multitasking_intensity=0.0,
            optimal_session_length=0.0,
            recommended_break_frequency=0.0,
            productivity_time_patterns={},
            context_switching_cost=0.0,
            analysis_period=(now, now),
            confidence_score=0.0,
        )

    def _detect_session_boundaries(
        self, sessions: List[SessionAnalysis]
    ) -> List[SessionBoundary]:
        """Detect natural session boundaries and break points."""
        boundaries = []

        for i in range(len(sessions) - 1):
            current_session = sessions[i]
            next_session = sessions[i + 1]

            if not current_session.end_time or not next_session.start_time:
                continue

            # Calculate time gap
            time_gap = next_session.start_time - current_session.end_time
            gap_minutes = time_gap.total_seconds() / 60

            # Analyze context change
            current_context = self._extract_session_context(current_session)
            next_context = self._extract_session_context(next_session)

            activity_change = self._calculate_activity_change(
                current_session, next_session
            )

            # Determine boundary type and confidence
            boundary_type, confidence = self._classify_boundary(
                gap_minutes, current_context, next_context, activity_change
            )

            if confidence > 0.3:  # Only include meaningful boundaries
                boundary = SessionBoundary(
                    boundary_time=current_session.end_time,
                    boundary_type=boundary_type,
                    confidence_score=confidence,
                    preceding_context=current_context,
                    following_context=next_context,
                    time_gap_minutes=gap_minutes,
                    activity_change_score=activity_change,
                    session_before=current_session.session_id,
                    session_after=next_session.session_id,
                )
                boundaries.append(boundary)

        return sorted(boundaries, key=lambda x: x.confidence_score, reverse=True)

    def _extract_session_context(self, session: SessionAnalysis) -> str:
        """Extract context summary from a session."""
        context_elements = []

        # Add file types worked on
        file_extensions = set()
        for op in session.file_operations:
            if op.file_path:
                ext = op.file_path.split(".")[-1] if "." in op.file_path else "unknown"
                file_extensions.add(ext)

        if file_extensions:
            context_elements.append(f"files:{','.join(sorted(file_extensions))}")

        # Add dominant tools
        tool_counts = {}
        for op in session.file_operations:
            tool_counts[op.tool_name] = tool_counts.get(op.tool_name, 0) + 1

        if tool_counts:
            top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]
            context_elements.append(f"tools:{','.join(tool for tool, _ in top_tools)}")

        # Add estimated topic (simplified)
        topic = self._estimate_session_topic(session)
        if topic:
            context_elements.append(f"topic:{topic}")

        return "|".join(context_elements)

    def _estimate_session_topic(self, session: SessionAnalysis) -> str:
        """Estimate the main topic of a session based on operations and content."""
        # Analyze file operations for topic clues
        topic_scores = defaultdict(int)

        for op in session.file_operations:
            # Score based on tool usage
            tool_name = op.tool_name.lower()
            if tool_name in ["bash", "run"]:
                topic_scores["testing"] += 2
            elif tool_name in ["edit", "write"]:
                topic_scores["coding"] += 2
            elif tool_name == "read":
                topic_scores["learning"] += 1

            # Score based on file types
            if op.file_path:
                if op.file_path.endswith((".py", ".js", ".java", ".cpp")):
                    topic_scores["coding"] += 2
                elif op.file_path.endswith((".md", ".txt", ".rst")):
                    topic_scores["documentation"] += 2
                elif "test" in op.file_path.lower():
                    topic_scores["testing"] += 3
                elif "config" in op.file_path.lower():
                    topic_scores["configuration"] += 2

        # Return most likely topic
        if topic_scores:
            return max(topic_scores.items(), key=lambda x: x[1])[0]

        return "general"

    def _calculate_activity_change(
        self, session1: SessionAnalysis, session2: SessionAnalysis
    ) -> float:
        """Calculate the degree of activity change between sessions."""
        # Compare token usage patterns
        token_ratio = abs(session2.total_tokens - session1.total_tokens) / max(
            session1.total_tokens, 1
        )
        token_change = min(token_ratio, 1.0)

        # Compare operation counts
        ops_ratio = abs(
            len(session2.file_operations) - len(session1.file_operations)
        ) / max(len(session1.file_operations), 1)
        ops_change = min(ops_ratio, 1.0)

        # Compare message counts
        msg_ratio = abs(session2.total_messages - session1.total_messages) / max(
            session1.total_messages, 1
        )
        msg_change = min(msg_ratio, 1.0)

        # Combined activity change score
        return (token_change + ops_change + msg_change) / 3

    def _classify_boundary(
        self, gap_minutes: float, context1: str, context2: str, activity_change: float
    ) -> Tuple[str, float]:
        """Classify boundary type and calculate confidence score."""
        confidence = 0.0
        boundary_type = "natural_break"

        # Time gap contribution
        if gap_minutes > 240:  # 4 hours
            confidence += 0.4
            boundary_type = "time_gap"
        elif gap_minutes > 60:  # 1 hour
            confidence += 0.3
        elif gap_minutes > 30:
            confidence += 0.2

        # Context change contribution
        context_similarity = self._calculate_context_similarity(context1, context2)
        if context_similarity < 0.3:
            confidence += 0.4
            boundary_type = "topic_shift"
        elif context_similarity < 0.6:
            confidence += 0.2

        # Activity change contribution
        if activity_change > 0.7:
            confidence += 0.3
            if boundary_type == "natural_break":
                boundary_type = "workflow_change"
        elif activity_change > 0.4:
            confidence += 0.1

        return boundary_type, min(confidence, 1.0)

    def _calculate_context_similarity(self, context1: str, context2: str) -> float:
        """Calculate similarity between two context strings."""
        if not context1 or not context2:
            return 0.0

        # Simple similarity based on common elements
        elements1 = set(context1.split("|"))
        elements2 = set(context2.split("|"))

        intersection = len(elements1.intersection(elements2))
        union = len(elements1.union(elements2))

        return intersection / union if union > 0 else 0.0

    def _analyze_topic_transitions(
        self, sessions: List[SessionAnalysis]
    ) -> List[TopicTransition]:
        """Analyze transitions between topics within and across sessions."""
        transitions = []

        # Track topics across sessions
        session_topics = []
        for session in sessions:
            topic = self._estimate_session_topic(session)
            session_topics.append((session, topic))

        # Detect transitions
        for i in range(len(session_topics) - 1):
            current_session, current_topic = session_topics[i]
            next_session, next_topic = session_topics[i + 1]

            if (
                current_topic != next_topic
                and current_session.end_time
                and next_session.start_time
            ):
                time_gap = (
                    next_session.start_time - current_session.end_time
                ).total_seconds() / 60

                # Calculate transition characteristics
                transition_type = self._classify_transition_type(
                    current_session, next_session, time_gap
                )

                confidence = self._calculate_transition_confidence(
                    current_session, next_session, current_topic, next_topic
                )

                context_similarity = self._calculate_session_similarity(
                    current_session, next_session
                )

                transition = TopicTransition(
                    from_topic=current_topic,
                    to_topic=next_topic,
                    transition_time=next_session.start_time,
                    session_id=next_session.session_id,
                    confidence_score=confidence,
                    transition_type=transition_type,
                    context_similarity=context_similarity,
                    time_gap_minutes=time_gap,
                )

                transitions.append(transition)

        return transitions

    def _classify_transition_type(
        self, session1: SessionAnalysis, session2: SessionAnalysis, time_gap: float
    ) -> str:
        """Classify the type of topic transition."""
        if time_gap < 5:
            return "immediate"
        elif time_gap < 30:
            return "quick"
        elif time_gap < 120:
            return "gradual"
        else:
            return "delayed"

    def _calculate_transition_confidence(
        self,
        session1: SessionAnalysis,
        session2: SessionAnalysis,
        topic1: str,
        topic2: str,
    ) -> float:
        """Calculate confidence in topic transition detection."""
        confidence = 0.5  # Base confidence

        # Increase confidence if sessions have clear topic indicators
        topic1_strength = self._calculate_topic_strength(session1, topic1)
        topic2_strength = self._calculate_topic_strength(session2, topic2)

        confidence += (topic1_strength + topic2_strength) * 0.25

        # Adjust based on session characteristics
        if len(session1.file_operations) > 5 and len(session2.file_operations) > 5:
            confidence += 0.1  # More operations = more confident classification

        return min(confidence, 1.0)

    def _calculate_topic_strength(self, session: SessionAnalysis, topic: str) -> float:
        """Calculate how strongly a session matches a topic."""
        if topic not in self.topic_keywords:
            return 0.0

        keywords = self.topic_keywords[topic]
        matches = 0
        total_checks = 0

        # Check file operations for topic keywords
        for op in session.file_operations:
            if op.file_path:
                file_content = op.file_path.lower()
                for keyword in keywords:
                    total_checks += 1
                    if keyword in file_content:
                        matches += 1

            tool_name = op.tool_name.lower()
            for keyword in keywords:
                total_checks += 1
                if keyword in tool_name:
                    matches += 1

        return matches / max(total_checks, 1)

    def _calculate_session_similarity(
        self, session1: SessionAnalysis, session2: SessionAnalysis
    ) -> float:
        """Calculate similarity between two sessions."""
        # File type similarity
        files1 = set(
            op.file_path.split(".")[-1]
            for op in session1.file_operations
            if op.file_path and "." in op.file_path
        )
        files2 = set(
            op.file_path.split(".")[-1]
            for op in session2.file_operations
            if op.file_path and "." in op.file_path
        )

        file_similarity = len(files1.intersection(files2)) / max(
            len(files1.union(files2)), 1
        )

        # Tool usage similarity
        tools1 = set(op.tool_name for op in session1.file_operations)
        tools2 = set(op.tool_name for op in session2.file_operations)

        tool_similarity = len(tools1.intersection(tools2)) / max(
            len(tools1.union(tools2)), 1
        )

        return (file_similarity + tool_similarity) / 2

    def _analyze_context_evolution(
        self, sessions: List[SessionAnalysis]
    ) -> List[ContextEvolutionPattern]:
        """Analyze how context evolves over time."""
        if len(sessions) < 3:
            return []

        patterns = []

        # Analyze evolution in sliding windows
        window_size = min(10, len(sessions) // 2)  # Adaptive window size

        for i in range(0, len(sessions) - window_size + 1, window_size // 2):
            window_sessions = sessions[i : i + window_size]

            if len(window_sessions) < 3:
                continue

            pattern = self._create_evolution_pattern(window_sessions)
            if pattern:
                patterns.append(pattern)

        return patterns

    def _create_evolution_pattern(
        self, sessions: List[SessionAnalysis]
    ) -> Optional[ContextEvolutionPattern]:
        """Create an evolution pattern from a window of sessions."""
        if not sessions:
            return None

        # Extract topics sequence
        topics_sequence = [
            self._estimate_session_topic(session) for session in sessions
        ]

        # Calculate complexity progression
        complexity_progression = []
        for session in sessions:
            complexity = self._calculate_session_complexity(session)
            complexity_progression.append(complexity)

        # Analyze evolution type
        evolution_type = self._classify_evolution_type(
            topics_sequence, complexity_progression
        )

        # Calculate focus drift
        focus_drift = self._calculate_focus_drift(topics_sequence)

        # Calculate return frequency
        return_frequency = self._calculate_return_frequency(topics_sequence)

        # Find dominant topics
        topic_counts = {}
        for topic in topics_sequence:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        total_sessions = len(sessions)
        dominant_topics = [
            (topic, count / total_sessions)
            for topic, count in sorted(
                topic_counts.items(), key=lambda x: x[1], reverse=True
            )[:3]
        ]

        # Analyze transition patterns
        transition_patterns = self._analyze_transition_patterns(topics_sequence)

        # Calculate productivity correlation
        productivity_correlation = self._calculate_productivity_correlation(
            sessions, complexity_progression
        )

        start_time = min(s.start_time for s in sessions if s.start_time)
        end_time = max(s.end_time for s in sessions if s.end_time)

        return ContextEvolutionPattern(
            pattern_id=f"evolution_{hash(''.join(topics_sequence)) % 10000}",
            time_window=(start_time, end_time),
            evolution_type=evolution_type,
            topics_sequence=topics_sequence,
            complexity_progression=complexity_progression,
            focus_drift_score=focus_drift,
            return_frequency=return_frequency,
            dominant_topics=dominant_topics,
            transition_patterns=transition_patterns,
            productivity_correlation=productivity_correlation,
        )

    def _calculate_session_complexity(self, session: SessionAnalysis) -> float:
        """Calculate complexity score for a session."""
        # Factors: number of operations, unique tools, unique files, context switches
        ops_score = min(len(session.file_operations) / 20, 1.0)  # Normalize to 0-1

        unique_tools = len(set(op.tool_name for op in session.file_operations))
        tools_score = min(unique_tools / 10, 1.0)

        unique_files = len(
            set(op.file_path for op in session.file_operations if op.file_path)
        )
        files_score = min(unique_files / 15, 1.0)

        context_switches_score = min(session.context_switches / 10, 1.0)

        return (ops_score + tools_score + files_score + context_switches_score) / 4

    def _classify_evolution_type(
        self, topics: List[str], complexity: List[float]
    ) -> str:
        """Classify the type of context evolution."""
        if len(topics) < 3:
            return "insufficient_data"

        # Check for linear progression
        unique_topics = len(set(topics))
        if unique_topics == len(topics):
            return "linear_progression"

        # Check for cyclical pattern
        if self._is_cyclical_pattern(topics):
            return "cyclical"

        # Check for branching (increasing complexity/diversity)
        if self._is_branching_pattern(topics, complexity):
            return "branching"

        # Check for convergent (decreasing complexity/diversity)
        if self._is_convergent_pattern(topics, complexity):
            return "convergent"

        return "mixed"

    def _is_cyclical_pattern(self, topics: List[str]) -> bool:
        """Check if topics show a cyclical pattern."""
        if len(topics) < 4:
            return False

        # Simple cyclical detection: check if topics repeat in a pattern
        for cycle_length in range(2, len(topics) // 2 + 1):
            is_cyclical = True
            for i in range(cycle_length, len(topics)):
                if topics[i] != topics[i % cycle_length]:
                    is_cyclical = False
                    break
            if is_cyclical:
                return True

        return False

    def _is_branching_pattern(self, topics: List[str], complexity: List[float]) -> bool:
        """Check if pattern shows branching (increasing diversity)."""
        if len(topics) < 3:
            return False

        # Check if unique topics increase over time
        unique_counts = []
        for i in range(1, len(topics) + 1):
            unique_counts.append(len(set(topics[:i])))

        # Check if generally increasing
        increases = sum(
            1
            for i in range(1, len(unique_counts))
            if unique_counts[i] > unique_counts[i - 1]
        )

        return increases > len(unique_counts) * 0.6

    def _is_convergent_pattern(
        self, topics: List[str], complexity: List[float]
    ) -> bool:
        """Check if pattern shows convergence (decreasing diversity)."""
        if len(complexity) < 3:
            return False

        # Check if complexity generally decreases
        decreases = sum(
            1 for i in range(1, len(complexity)) if complexity[i] < complexity[i - 1]
        )

        return decreases > len(complexity) * 0.6

    def _calculate_focus_drift(self, topics: List[str]) -> float:
        """Calculate how much focus drifts across topics."""
        if len(topics) < 2:
            return 0.0

        topic_changes = sum(
            1 for i in range(1, len(topics)) if topics[i] != topics[i - 1]
        )
        max_possible_changes = len(topics) - 1

        return topic_changes / max_possible_changes if max_possible_changes > 0 else 0.0

    def _calculate_return_frequency(self, topics: List[str]) -> float:
        """Calculate how often topics return after being abandoned."""
        if len(topics) < 3:
            return 0.0

        topic_positions = defaultdict(list)
        for i, topic in enumerate(topics):
            topic_positions[topic].append(i)

        returns = 0
        total_opportunities = 0

        for topic, positions in topic_positions.items():
            if len(positions) > 1:
                for i in range(1, len(positions)):
                    gap = positions[i] - positions[i - 1]
                    if gap > 1:  # Topic returned after being away
                        returns += 1
                    total_opportunities += 1

        return returns / max(total_opportunities, 1)

    def _analyze_transition_patterns(self, topics: List[str]) -> List[str]:
        """Analyze common transition patterns in topics."""
        patterns = []

        if len(topics) < 3:
            return patterns

        # Find common 2-topic transitions
        transitions = {}
        for i in range(len(topics) - 1):
            transition = f"{topics[i]} -> {topics[i+1]}"
            transitions[transition] = transitions.get(transition, 0) + 1

        # Add frequent transitions to patterns
        for transition, count in transitions.items():
            if count > 1:
                patterns.append(f"{transition} ({count}x)")

        return patterns[:5]  # Top 5 patterns

    def _calculate_productivity_correlation(
        self, sessions: List[SessionAnalysis], complexity: List[float]
    ) -> float:
        """Calculate correlation between complexity and productivity metrics."""
        if len(sessions) != len(complexity) or len(sessions) < 3:
            return 0.0

        # Use tokens per hour as productivity proxy
        productivity = []
        for session in sessions:
            if session.duration_hours > 0:
                productivity.append(session.total_tokens / session.duration_hours)
            else:
                productivity.append(0)

        # Simple correlation calculation
        try:
            n = len(complexity)
            sum_x = sum(complexity)
            sum_y = sum(productivity)
            sum_xy = sum(x * y for x, y in zip(complexity, productivity))
            sum_x2 = sum(x * x for x in complexity)
            sum_y2 = sum(y * y for y in productivity)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = (
                (n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)
            ) ** 0.5

            if denominator == 0:
                return 0.0

            return numerator / denominator
        except Exception:
            return 0.0

    def _calculate_session_metrics(
        self, sessions: List[SessionAnalysis]
    ) -> Dict[str, float]:
        """Calculate session-related metrics."""
        durations = [s.duration_hours for s in sessions if s.duration_hours > 0]

        if not durations:
            return {
                "avg_length": 0.0,
                "avg_break": 0.0,
                "optimal_length": 0.0,
                "recommended_breaks": 0.0,
            }

        avg_length = statistics.mean(durations)

        # Calculate breaks between sessions
        breaks = []
        for i in range(len(sessions) - 1):
            if sessions[i].end_time and sessions[i + 1].start_time:
                break_duration = (
                    sessions[i + 1].start_time - sessions[i].end_time
                ).total_seconds() / 3600
                if 0 < break_duration < 24:  # Filter reasonable breaks
                    breaks.append(break_duration)

        avg_break = statistics.mean(breaks) if breaks else 1.0

        # Estimate optimal session length (sessions with highest productivity)
        productivity_scores = []
        for session in sessions:
            if session.duration_hours > 0 and session.total_messages > 0:
                score = session.total_messages / session.duration_hours
                productivity_scores.append((session.duration_hours, score))

        if productivity_scores:
            # Find duration with highest average productivity
            duration_groups = defaultdict(list)
            for duration, score in productivity_scores:
                bucket = round(duration * 2) / 2  # Group into 30-minute buckets
                duration_groups[bucket].append(score)

            avg_productivity = {
                d: statistics.mean(scores)
                for d, scores in duration_groups.items()
                if len(scores) >= 2
            }

            if avg_productivity:
                optimal_length = max(avg_productivity.items(), key=lambda x: x[1])[0]
            else:
                optimal_length = avg_length
        else:
            optimal_length = 2.0  # Default 2 hours

        # Recommend breaks based on optimal session length
        recommended_breaks = (
            optimal_length * 60 / 2
        )  # Half the optimal session length in minutes

        return {
            "avg_length": avg_length,
            "avg_break": avg_break,
            "optimal_length": optimal_length,
            "recommended_breaks": recommended_breaks,
        }

    def _calculate_temporal_metrics(
        self, sessions: List[SessionAnalysis], transitions: List[TopicTransition]
    ) -> Dict[str, float]:
        """Calculate temporal-related metrics."""
        if not sessions:
            return {
                "stability": 0.0,
                "drift_frequency": 0.0,
                "return_rate": 0.0,
                "multitasking": 0.0,
                "switching_cost": 0.0,
            }

        # Calculate stability (inverse of context switches)
        total_switches = sum(s.context_switches for s in sessions)
        total_messages = sum(s.total_messages for s in sessions)
        stability = 1.0 - min(total_switches / max(total_messages, 1), 1.0)

        # Calculate drift frequency (transitions per hour)
        total_hours = sum(s.duration_hours for s in sessions)
        drift_frequency = len(transitions) / max(total_hours, 1)

        # Calculate return rate from transitions
        topic_returns = sum(1 for t in transitions if t.transition_type == "return")
        return_rate = topic_returns / max(len(transitions), 1)

        # Estimate multitasking intensity
        avg_concurrent_files = []
        for session in sessions:
            unique_files = len(
                set(op.file_path for op in session.file_operations if op.file_path)
            )
            session_hours = max(session.duration_hours, 0.1)
            concurrent_estimate = unique_files / session_hours
            avg_concurrent_files.append(concurrent_estimate)

        multitasking = (
            statistics.mean(avg_concurrent_files) if avg_concurrent_files else 0.0
        )
        multitasking = min(multitasking / 5, 1.0)  # Normalize

        # Estimate switching cost (productivity loss from context switches)
        switching_cost = min(drift_frequency / 5, 1.0)  # Normalize

        return {
            "stability": stability,
            "drift_frequency": drift_frequency,
            "return_rate": return_rate,
            "multitasking": multitasking,
            "switching_cost": switching_cost,
        }

    def _analyze_productivity_patterns(
        self, sessions: List[SessionAnalysis]
    ) -> Dict[str, Any]:
        """Analyze productivity patterns over time."""
        hourly_productivity = defaultdict(list)
        peak_periods = []

        for session in sessions:
            if (
                session.start_time
                and session.duration_hours > 0
                and session.total_messages > 0
            ):
                hour = session.start_time.hour
                productivity = session.total_messages / session.duration_hours
                hourly_productivity[hour].append(productivity)

        # Calculate average productivity by hour
        hourly_patterns = {}
        for hour, productivities in hourly_productivity.items():
            hourly_patterns[str(hour)] = statistics.mean(productivities)

        # Find peak periods (consecutive high-productivity hours)
        if hourly_patterns:
            avg_productivity = statistics.mean(hourly_patterns.values())
            high_productivity_hours = [
                int(h) for h, p in hourly_patterns.items() if p > avg_productivity * 1.2
            ]

            # Group consecutive hours into periods
            if high_productivity_hours:
                high_productivity_hours.sort()
                periods = []
                start = high_productivity_hours[0]
                end = start

                for hour in high_productivity_hours[1:]:
                    if hour == end + 1:
                        end = hour
                    else:
                        periods.append((start, end))
                        start = hour
                        end = hour

                periods.append((start, end))

                # Convert to datetime periods (using arbitrary date)
                base_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                for start_hour, end_hour in periods:
                    start_time = base_date.replace(hour=start_hour)
                    end_time = base_date.replace(hour=end_hour)
                    peak_periods.append((start_time, end_time))

        return {"hourly_patterns": hourly_patterns, "peak_periods": peak_periods}

    def _calculate_analysis_confidence(self, sessions: List[SessionAnalysis]) -> float:
        """Calculate confidence in the temporal analysis."""
        if not sessions:
            return 0.0

        confidence = 0.0

        # More sessions = higher confidence
        session_factor = min(len(sessions) / 20, 1.0)
        confidence += session_factor * 0.4

        # Longer time span = higher confidence
        if len(sessions) > 1:
            start_time = min(s.start_time for s in sessions if s.start_time)
            end_time = max(s.end_time for s in sessions if s.end_time)
            time_span_days = (end_time - start_time).days
            time_factor = min(time_span_days / 30, 1.0)  # Up to 30 days
            confidence += time_factor * 0.3

        # Data quality factor
        sessions_with_good_data = sum(
            1 for s in sessions if s.total_messages > 5 and s.duration_hours > 0.1
        )
        quality_factor = sessions_with_good_data / len(sessions)
        confidence += quality_factor * 0.3

        return confidence
