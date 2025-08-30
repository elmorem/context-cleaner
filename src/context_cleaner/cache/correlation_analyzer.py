"""
Cross-Session Correlation Analyzer

Analyzes correlations and patterns across multiple Claude Code sessions to identify
long-term trends, recurring themes, and cross-session dependencies.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path

from .models import SessionAnalysis, CacheConfig
from .session_parser import SessionCacheParser
from .discovery import CacheDiscoveryService, CacheLocation

logger = logging.getLogger(__name__)


@dataclass
class SessionCluster:
    """Represents a cluster of related sessions."""
    
    cluster_id: str
    session_ids: List[str]
    common_theme: str
    similarity_score: float
    time_span: Tuple[datetime, datetime]
    dominant_files: List[str]
    dominant_tools: List[str]
    cluster_size: int
    
    average_session_length: float
    total_tokens: int
    productivity_score: float
    
    @property
    def is_major_cluster(self) -> bool:
        """Check if this is a major cluster worth attention."""
        return self.cluster_size >= 3 and self.similarity_score >= 0.6
    
    @property  
    def cluster_strength(self) -> str:
        """Get cluster strength category."""
        if self.similarity_score >= 0.8:
            return "Strong"
        elif self.similarity_score >= 0.6:
            return "Moderate"
        else:
            return "Weak"


@dataclass
class CrossSessionPattern:
    """Represents a pattern that spans across multiple sessions."""
    
    pattern_id: str
    pattern_type: str  # 'recurring_workflow', 'progressive_project', 'cyclical_maintenance', etc.
    description: str
    
    session_sequence: List[str]  # Session IDs in order
    time_intervals: List[float]  # Hours between sessions
    
    consistency_score: float
    evolution_trend: str  # 'increasing', 'decreasing', 'stable', 'cyclical'
    
    key_indicators: List[str]
    correlation_strength: float
    
    first_occurrence: datetime
    last_occurrence: datetime
    frequency_days: float  # Average days between occurrences
    
    @property
    def is_recurring_pattern(self) -> bool:
        """Check if this pattern recurs regularly."""
        return (
            len(self.session_sequence) >= 3 and
            self.consistency_score >= 0.7 and
            self.frequency_days < 30
        )
    
    @property
    def pattern_maturity(self) -> str:
        """Get pattern maturity level."""
        days_active = (self.last_occurrence - self.first_occurrence).days
        if days_active > 60:
            return "Mature"
        elif days_active > 21:
            return "Developing"
        else:
            return "Emerging"


@dataclass  
class LongTermTrend:
    """Represents a long-term trend across sessions."""
    
    trend_id: str
    trend_type: str  # 'skill_development', 'project_evolution', 'tool_adoption', etc.
    description: str
    
    metric_name: str  # What's being measured
    trend_direction: str  # 'increasing', 'decreasing', 'stable'
    trend_strength: float  # How strong the trend is (0-1)
    
    data_points: List[Tuple[datetime, float]]  # (time, value) pairs
    statistical_significance: float
    
    start_date: datetime
    end_date: datetime
    rate_of_change: float  # Units per day
    
    confidence_interval: Tuple[float, float]
    r_squared: float  # Goodness of fit
    
    @property
    def is_significant_trend(self) -> bool:
        """Check if this is a statistically significant trend."""
        return (
            self.statistical_significance >= 0.05 and
            self.r_squared >= 0.6 and
            len(self.data_points) >= 5
        )
    
    @property
    def trend_velocity(self) -> str:
        """Get trend velocity category."""
        abs_rate = abs(self.rate_of_change)
        if abs_rate < 0.01:
            return "Slow"
        elif abs_rate < 0.1:
            return "Moderate"
        else:
            return "Rapid"


@dataclass
class CorrelationInsights:
    """Comprehensive cross-session correlation insights."""
    
    session_clusters: List[SessionCluster]
    cross_session_patterns: List[CrossSessionPattern]
    long_term_trends: List[LongTermTrend]
    
    total_sessions_analyzed: int
    analysis_time_span_days: int
    
    # Correlation metrics
    file_usage_correlations: Dict[str, float]  # file -> consistency score
    tool_usage_correlations: Dict[str, float]  # tool -> consistency score  
    temporal_correlations: Dict[str, float]    # time pattern -> strength
    
    # Cross-session dependencies
    session_dependencies: List[Tuple[str, str, float]]  # (session1, session2, dependency_strength)
    workflow_continuations: List[Tuple[str, str, str]]  # (session1, session2, continuation_type)
    
    # Evolution metrics
    complexity_evolution: List[Tuple[datetime, float]]
    efficiency_evolution: List[Tuple[datetime, float]]
    focus_evolution: List[Tuple[datetime, float]]
    
    # Predictive insights
    predicted_next_patterns: List[Tuple[str, float]]  # (pattern_description, probability)
    recommended_session_timing: List[str]
    optimal_workflow_sequences: List[List[str]]
    
    analysis_confidence: float
    data_completeness: float
    
    @property
    def dominant_themes(self) -> List[str]:
        """Get dominant themes across all sessions."""
        major_clusters = [c for c in self.session_clusters if c.is_major_cluster]
        return [c.common_theme for c in major_clusters[:5]]
    
    @property
    def most_significant_trends(self) -> List[LongTermTrend]:
        """Get most significant long-term trends."""
        return [t for t in self.long_term_trends if t.is_significant_trend][:3]


class CrossSessionCorrelationAnalyzer:
    """Analyzes correlations and patterns across multiple Claude Code sessions."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize the cross-session correlation analyzer."""
        self.config = config or CacheConfig()
        self.parser = SessionCacheParser(config)
        self.discovery = CacheDiscoveryService(config)
        
        # Analysis parameters
        self.min_cluster_size = 2
        self.similarity_threshold = 0.5
        self.correlation_threshold = 0.3
        self.min_trend_points = 4
        self.max_analysis_days = 90  # Limit analysis to recent 3 months
        
        # Pattern recognition parameters
        self.time_window_hours = 24  # Hours to consider sessions as related
        self.recurring_pattern_min_occurrences = 3
        
    def analyze_cross_session_correlations(self, 
                                         cache_locations: Optional[List[CacheLocation]] = None,
                                         max_sessions: Optional[int] = None) -> CorrelationInsights:
        """
        Analyze correlations and patterns across sessions.
        
        Args:
            cache_locations: Specific cache locations to analyze
            max_sessions: Maximum number of sessions to analyze
            
        Returns:
            Comprehensive cross-session correlation insights
        """
        logger.info("Starting cross-session correlation analysis...")
        
        if cache_locations is None:
            cache_locations = self.discovery.discover_cache_locations()
        
        # Parse and filter sessions
        all_sessions = self._parse_and_filter_sessions(cache_locations, max_sessions)
        
        if len(all_sessions) < 3:
            logger.warning("Insufficient sessions for correlation analysis")
            return self._create_empty_insights()
        
        logger.info(f"Analyzing correlations across {len(all_sessions)} sessions")
        
        # Perform correlation analysis
        session_clusters = self._cluster_similar_sessions(all_sessions)
        cross_patterns = self._identify_cross_session_patterns(all_sessions)
        long_term_trends = self._analyze_long_term_trends(all_sessions)
        
        # Calculate correlation metrics
        correlations = self._calculate_correlation_metrics(all_sessions)
        
        # Identify dependencies and continuations
        dependencies = self._identify_session_dependencies(all_sessions)
        continuations = self._identify_workflow_continuations(all_sessions)
        
        # Analyze evolution
        evolution_metrics = self._analyze_evolution_metrics(all_sessions)
        
        # Generate predictive insights
        predictions = self._generate_predictive_insights(
            all_sessions, cross_patterns, long_term_trends
        )
        
        # Calculate analysis quality metrics
        confidence, completeness = self._calculate_analysis_quality(all_sessions)
        
        insights = CorrelationInsights(
            session_clusters=session_clusters,
            cross_session_patterns=cross_patterns,
            long_term_trends=long_term_trends,
            total_sessions_analyzed=len(all_sessions),
            analysis_time_span_days=self._calculate_time_span(all_sessions),
            file_usage_correlations=correlations['files'],
            tool_usage_correlations=correlations['tools'],
            temporal_correlations=correlations['temporal'],
            session_dependencies=dependencies,
            workflow_continuations=continuations,
            complexity_evolution=evolution_metrics['complexity'],
            efficiency_evolution=evolution_metrics['efficiency'],
            focus_evolution=evolution_metrics['focus'],
            predicted_next_patterns=predictions['patterns'],
            recommended_session_timing=predictions['timing'],
            optimal_workflow_sequences=predictions['workflows'],
            analysis_confidence=confidence,
            data_completeness=completeness
        )
        
        logger.info(f"Correlation analysis complete. Found {len(session_clusters)} clusters, "
                   f"{len(cross_patterns)} patterns, {len(long_term_trends)} trends")
        
        return insights
    
    def _parse_and_filter_sessions(self, 
                                 cache_locations: List[CacheLocation],
                                 max_sessions: Optional[int]) -> List[SessionAnalysis]:
        """Parse sessions and filter for correlation analysis."""
        all_sessions = []
        cutoff_date = datetime.now() - timedelta(days=self.max_analysis_days)
        
        for location in cache_locations:
            logger.debug(f"Parsing sessions from: {location.project_name}")
            
            session_files = location.session_files
            if max_sessions:
                # Sort by modification time, take most recent
                session_files = sorted(session_files, 
                                     key=lambda x: x.stat().st_mtime, 
                                     reverse=True)[:max_sessions]
            
            for session_file in session_files:
                try:
                    analysis = self.parser.parse_session_file(session_file)
                    if (analysis and analysis.start_time and 
                        analysis.start_time >= cutoff_date and
                        self._is_valid_for_correlation(analysis)):
                        all_sessions.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to parse session {session_file}: {e}")
                    continue
        
        # Sort by start time
        all_sessions.sort(key=lambda x: x.start_time)
        return all_sessions
    
    def _is_valid_for_correlation(self, session: SessionAnalysis) -> bool:
        """Check if session is valid for correlation analysis."""
        return (
            session.total_messages >= 3 and
            session.duration_hours > 0.1 and
            len(session.file_operations) >= 1
        )
    
    def _create_empty_insights(self) -> CorrelationInsights:
        """Create empty insights when insufficient data."""
        return CorrelationInsights(
            session_clusters=[],
            cross_session_patterns=[],
            long_term_trends=[],
            total_sessions_analyzed=0,
            analysis_time_span_days=0,
            file_usage_correlations={},
            tool_usage_correlations={},
            temporal_correlations={},
            session_dependencies=[],
            workflow_continuations=[],
            complexity_evolution=[],
            efficiency_evolution=[],
            focus_evolution=[],
            predicted_next_patterns=[],
            recommended_session_timing=[],
            optimal_workflow_sequences=[],
            analysis_confidence=0.0,
            data_completeness=0.0
        )
    
    def _cluster_similar_sessions(self, sessions: List[SessionAnalysis]) -> List[SessionCluster]:
        """Cluster sessions based on similarity."""
        clusters = []
        processed_sessions = set()
        
        for i, session in enumerate(sessions):
            if session.session_id in processed_sessions:
                continue
            
            # Find similar sessions
            similar_sessions = [session]
            for j, other_session in enumerate(sessions[i+1:], i+1):
                if other_session.session_id in processed_sessions:
                    continue
                
                similarity = self._calculate_session_similarity(session, other_session)
                if similarity >= self.similarity_threshold:
                    similar_sessions.append(other_session)
            
            if len(similar_sessions) >= self.min_cluster_size:
                cluster = self._create_session_cluster(similar_sessions)
                clusters.append(cluster)
                
                # Mark sessions as processed
                for s in similar_sessions:
                    processed_sessions.add(s.session_id)
        
        # Sort clusters by size and similarity
        clusters.sort(key=lambda x: (x.cluster_size, x.similarity_score), reverse=True)
        return clusters[:10]  # Return top 10 clusters
    
    def _calculate_session_similarity(self, session1: SessionAnalysis, session2: SessionAnalysis) -> float:
        """Calculate similarity score between two sessions."""
        similarities = []
        
        # File similarity
        files1 = set(op.file_path for op in session1.file_operations if op.file_path)
        files2 = set(op.file_path for op in session2.file_operations if op.file_path)
        
        if files1 or files2:
            union_size = len(files1.union(files2))
            file_similarity = len(files1.intersection(files2)) / union_size if union_size > 0 else 0.0
            similarities.append(file_similarity)
        
        # Tool similarity
        tools1 = Counter(op.tool_name for op in session1.file_operations)
        tools2 = Counter(op.tool_name for op in session2.file_operations)
        
        all_tools = set(tools1.keys()) | set(tools2.keys())
        if all_tools:
            total_max = sum(max(tools1[t], tools2[t]) for t in all_tools)
            tool_similarity = sum(min(tools1[t], tools2[t]) for t in all_tools) / total_max if total_max > 0 else 0.0
            similarities.append(tool_similarity)
        
        # Duration similarity (normalized)
        max_duration = max(session1.duration_hours, session2.duration_hours)
        duration_ratio = min(session1.duration_hours, session2.duration_hours) / max_duration if max_duration > 0 else 0.0
        similarities.append(duration_ratio)
        
        # Token count similarity (normalized)
        if session1.total_tokens > 0 and session2.total_tokens > 0:
            max_tokens = max(session1.total_tokens, session2.total_tokens)
            token_ratio = min(session1.total_tokens, session2.total_tokens) / max_tokens if max_tokens > 0 else 0.0
            similarities.append(token_ratio)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _create_session_cluster(self, sessions: List[SessionAnalysis]) -> SessionCluster:
        """Create a session cluster from a list of similar sessions."""
        session_ids = [s.session_id for s in sessions]
        
        # Calculate average similarity within cluster
        similarities = []
        for i in range(len(sessions)):
            for j in range(i+1, len(sessions)):
                sim = self._calculate_session_similarity(sessions[i], sessions[j])
                similarities.append(sim)
        
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        
        # Determine common theme
        common_theme = self._determine_common_theme(sessions)
        
        # Find dominant files and tools
        all_files = []
        all_tools = []
        for session in sessions:
            all_files.extend(op.file_path for op in session.file_operations if op.file_path)
            all_tools.extend(op.tool_name for op in session.file_operations)
        
        dominant_files = [f for f, count in Counter(all_files).most_common(5)]
        dominant_tools = [t for t, count in Counter(all_tools).most_common(3)]
        
        # Calculate metrics
        avg_length = sum(s.duration_hours for s in sessions) / len(sessions)
        total_tokens = sum(s.total_tokens for s in sessions)
        productivity_score = total_tokens / sum(s.duration_hours for s in sessions)
        
        # Time span
        start_times = [s.start_time for s in sessions if s.start_time]
        end_times = [s.end_time for s in sessions if s.end_time]
        time_span = (min(start_times), max(end_times)) if start_times and end_times else (datetime.now(), datetime.now())
        
        return SessionCluster(
            cluster_id=f"cluster_{hash(''.join(session_ids)) % 10000}",
            session_ids=session_ids,
            common_theme=common_theme,
            similarity_score=avg_similarity,
            time_span=time_span,
            dominant_files=dominant_files,
            dominant_tools=dominant_tools,
            cluster_size=len(sessions),
            average_session_length=avg_length,
            total_tokens=total_tokens,
            productivity_score=productivity_score
        )
    
    def _determine_common_theme(self, sessions: List[SessionAnalysis]) -> str:
        """Determine the common theme of clustered sessions."""
        # Analyze file types
        file_extensions = []
        for session in sessions:
            for op in session.file_operations:
                if op.file_path and '.' in op.file_path:
                    ext = Path(op.file_path).suffix.lower()
                    file_extensions.append(ext)
        
        ext_counter = Counter(file_extensions)
        
        # Analyze tools
        tools = []
        for session in sessions:
            for op in session.file_operations:
                tools.append(op.tool_name.lower())
        
        tool_counter = Counter(tools)
        
        # Determine theme based on patterns
        if ext_counter.get('.py', 0) > len(sessions):
            return "Python Development"
        elif ext_counter.get('.js', 0) > len(sessions):
            return "JavaScript Development"
        elif ext_counter.get('.md', 0) > len(sessions):
            return "Documentation"
        elif tool_counter.get('bash', 0) > len(sessions) * 2:
            return "System Administration"
        elif tool_counter.get('read', 0) > len(sessions) * 3:
            return "Code Exploration"
        elif tool_counter.get('edit', 0) > len(sessions) * 2:
            return "Code Development"
        else:
            return "General Development"
    
    def _identify_cross_session_patterns(self, sessions: List[SessionAnalysis]) -> List[CrossSessionPattern]:
        """Identify patterns that span across multiple sessions."""
        patterns = []
        
        # Look for recurring sequences
        patterns.extend(self._find_recurring_workflows(sessions))
        patterns.extend(self._find_progressive_patterns(sessions))
        patterns.extend(self._find_cyclical_patterns(sessions))
        
        return sorted(patterns, key=lambda x: x.correlation_strength, reverse=True)[:20]
    
    def _find_recurring_workflows(self, sessions: List[SessionAnalysis]) -> List[CrossSessionPattern]:
        """Find workflows that recur across sessions."""
        patterns = []
        
        # Group sessions by time windows
        time_groups = self._group_sessions_by_time(sessions, days=7)  # Weekly groups
        
        for group in time_groups:
            if len(group) < 2:
                continue
            
            # Look for similar tool sequences
            tool_sequences = []
            for session in group:
                sequence = [op.tool_name for op in session.file_operations[:10]]  # First 10 operations
                tool_sequences.append(sequence)
            
            # Find common subsequences
            common_patterns = self._find_common_subsequences(tool_sequences)
            
            for pattern_seq, frequency in common_patterns:
                if frequency >= self.recurring_pattern_min_occurrences:
                    pattern = CrossSessionPattern(
                        pattern_id=f"recurring_{hash(''.join(pattern_seq)) % 10000}",
                        pattern_type="recurring_workflow",
                        description=f"Recurring workflow: {' -> '.join(pattern_seq)}",
                        session_sequence=[s.session_id for s in group if any(pattern_seq[0] in [op.tool_name for op in s.file_operations] for op in s.file_operations)],
                        time_intervals=self._calculate_time_intervals(group),
                        consistency_score=frequency / len(group),
                        evolution_trend="stable",
                        key_indicators=pattern_seq,
                        correlation_strength=frequency / len(group),
                        first_occurrence=min(s.start_time for s in group if s.start_time),
                        last_occurrence=max(s.start_time for s in group if s.start_time),
                        frequency_days=7.0  # Weekly pattern
                    )
                    patterns.append(pattern)
        
        return patterns
    
    def _find_progressive_patterns(self, sessions: List[SessionAnalysis]) -> List[CrossSessionPattern]:
        """Find patterns that show progression over time."""
        patterns = []
        
        # Look for increasing complexity patterns
        complexity_scores = []
        for session in sessions:
            complexity = self._calculate_session_complexity(session)
            complexity_scores.append((session, complexity))
        
        # Find trends in complexity
        if len(complexity_scores) >= 4:
            trend_strength = self._calculate_trend_strength([c for _, c in complexity_scores])
            
            if abs(trend_strength) > 0.3:  # Significant trend
                direction = "increasing" if trend_strength > 0 else "decreasing"
                
                pattern = CrossSessionPattern(
                    pattern_id=f"progressive_complexity_{direction}",
                    pattern_type="progressive_project",
                    description=f"Project complexity is {direction} over time",
                    session_sequence=[s.session_id for s, _ in complexity_scores],
                    time_intervals=self._calculate_time_intervals([s for s, _ in complexity_scores]),
                    consistency_score=abs(trend_strength),
                    evolution_trend=direction,
                    key_indicators=["complexity", direction],
                    correlation_strength=abs(trend_strength),
                    first_occurrence=complexity_scores[0][0].start_time,
                    last_occurrence=complexity_scores[-1][0].start_time,
                    frequency_days=(complexity_scores[-1][0].start_time - complexity_scores[0][0].start_time).days / len(complexity_scores)
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_cyclical_patterns(self, sessions: List[SessionAnalysis]) -> List[CrossSessionPattern]:
        """Find cyclical patterns in session data."""
        patterns = []
        
        # Look for weekly cycles (e.g., Monday planning sessions)
        weekday_patterns = defaultdict(list)
        for session in sessions:
            if session.start_time:
                weekday = session.start_time.weekday()
                weekday_patterns[weekday].append(session)
        
        for weekday, day_sessions in weekday_patterns.items():
            if len(day_sessions) >= 3:  # At least 3 occurrences
                # Check for similarity in these sessions
                similarities = []
                for i in range(len(day_sessions)):
                    for j in range(i+1, len(day_sessions)):
                        sim = self._calculate_session_similarity(day_sessions[i], day_sessions[j])
                        similarities.append(sim)
                
                if similarities and sum(similarities) / len(similarities) > 0.5:
                    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    
                    pattern = CrossSessionPattern(
                        pattern_id=f"weekly_{weekday}",
                        pattern_type="cyclical_maintenance", 
                        description=f"Regular {weekday_names[weekday]} sessions",
                        session_sequence=[s.session_id for s in day_sessions],
                        time_intervals=[7.0 * 24] * (len(day_sessions) - 1),  # Weekly intervals
                        consistency_score=sum(similarities) / len(similarities),
                        evolution_trend="cyclical",
                        key_indicators=[weekday_names[weekday], "weekly"],
                        correlation_strength=sum(similarities) / len(similarities),
                        first_occurrence=min(s.start_time for s in day_sessions),
                        last_occurrence=max(s.start_time for s in day_sessions),
                        frequency_days=7.0
                    )
                    patterns.append(pattern)
        
        return patterns
    
    def _group_sessions_by_time(self, sessions: List[SessionAnalysis], days: int) -> List[List[SessionAnalysis]]:
        """Group sessions into time windows."""
        if not sessions:
            return []
        
        groups = []
        current_group = []
        group_start = sessions[0].start_time
        
        for session in sessions:
            if session.start_time and (session.start_time - group_start).days < days:
                current_group.append(session)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [session]
                group_start = session.start_time
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _find_common_subsequences(self, sequences: List[List[str]]) -> List[Tuple[List[str], int]]:
        """Find common subsequences in a list of sequences."""
        subsequence_counter = Counter()
        
        for sequence in sequences:
            # Generate all subsequences of length 2-4
            for length in range(2, min(5, len(sequence) + 1)):
                for i in range(len(sequence) - length + 1):
                    subseq = tuple(sequence[i:i + length])
                    subsequence_counter[subseq] += 1
        
        # Return subsequences that appear multiple times
        common = [(list(subseq), count) for subseq, count in subsequence_counter.items() if count > 1]
        return sorted(common, key=lambda x: x[1], reverse=True)
    
    def _calculate_time_intervals(self, sessions: List[SessionAnalysis]) -> List[float]:
        """Calculate time intervals between sessions in hours."""
        if len(sessions) < 2:
            return []
        
        intervals = []
        for i in range(1, len(sessions)):
            if sessions[i-1].end_time and sessions[i].start_time:
                interval = (sessions[i].start_time - sessions[i-1].end_time).total_seconds() / 3600
                intervals.append(interval)
        
        return intervals
    
    def _calculate_session_complexity(self, session: SessionAnalysis) -> float:
        """Calculate complexity score for a session."""
        # Factors: unique files, unique tools, context switches, duration
        unique_files = len(set(op.file_path for op in session.file_operations if op.file_path))
        unique_tools = len(set(op.tool_name for op in session.file_operations))
        
        complexity = (
            min(unique_files / 10, 1.0) * 0.3 +
            min(unique_tools / 8, 1.0) * 0.3 +
            min(session.context_switches / 15, 1.0) * 0.2 +
            min(session.duration_hours / 4, 1.0) * 0.2
        )
        
        return complexity
    
    def _calculate_trend_strength(self, values: List[float]) -> float:
        """Calculate trend strength using simple linear regression."""
        if len(values) < 3:
            return 0.0
        
        n = len(values)
        x_values = list(range(n))
        
        # Calculate correlation coefficient
        x_mean = sum(x_values) / n
        y_mean = sum(values) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        x_var = sum((x - x_mean) ** 2 for x in x_values)
        y_var = sum((y - y_mean) ** 2 for y in values)
        
        if x_var == 0 or y_var == 0:
            return 0.0
        
        correlation = numerator / (x_var * y_var) ** 0.5
        return correlation
    
    def _analyze_long_term_trends(self, sessions: List[SessionAnalysis]) -> List[LongTermTrend]:
        """Analyze long-term trends across sessions."""
        trends = []
        
        if len(sessions) < self.min_trend_points:
            return trends
        
        # Analyze various metrics over time
        metrics = {
            'session_length': [(s.start_time, s.duration_hours) for s in sessions if s.start_time],
            'token_efficiency': [(s.start_time, s.total_tokens / s.duration_hours if s.duration_hours > 0 else 0) for s in sessions if s.start_time],
            'file_operations': [(s.start_time, len(s.file_operations)) for s in sessions if s.start_time],
            'complexity': [(s.start_time, self._calculate_session_complexity(s)) for s in sessions if s.start_time]
        }
        
        for metric_name, data_points in metrics.items():
            if len(data_points) >= self.min_trend_points:
                trend = self._create_trend_analysis(metric_name, data_points)
                if trend and trend.statistical_significance >= 0.05:
                    trends.append(trend)
        
        return trends
    
    def _create_trend_analysis(self, metric_name: str, data_points: List[Tuple[datetime, float]]) -> Optional[LongTermTrend]:
        """Create trend analysis for a specific metric."""
        if len(data_points) < 3:
            return None
        
        # Convert to numerical data for regression
        start_date = min(dp[0] for dp in data_points)
        x_values = [(dp[0] - start_date).days for dp in data_points]
        y_values = [dp[1] for dp in data_points]
        
        # Simple linear regression
        n = len(x_values)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n
        
        # Calculate slope and correlation
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        x_var = sum((x - x_mean) ** 2 for x in x_values)
        y_var = sum((y - y_mean) ** 2 for y in y_values)
        
        if x_var == 0:
            return None
        
        slope = numerator / x_var
        
        if y_var == 0:
            correlation = 0.0
        else:
            correlation = numerator / (x_var * y_var) ** 0.5
        
        r_squared = correlation ** 2
        
        # Determine trend direction
        if slope > 0.01:
            direction = "increasing"
        elif slope < -0.01:
            direction = "decreasing"
        else:
            direction = "stable"
        
        # Calculate confidence interval (simplified)
        std_error = (sum((y - (y_mean + slope * (x - x_mean))) ** 2 for x, y in zip(x_values, y_values)) / (n - 2)) ** 0.5 if n > 2 else 0
        confidence_interval = (y_mean - 1.96 * std_error, y_mean + 1.96 * std_error)
        
        # Generate description
        descriptions = {
            'session_length': f"Session duration is {direction}",
            'token_efficiency': f"Token efficiency is {direction}", 
            'file_operations': f"File operation complexity is {direction}",
            'complexity': f"Overall session complexity is {direction}"
        }
        
        return LongTermTrend(
            trend_id=f"trend_{metric_name}",
            trend_type="metric_evolution",
            description=descriptions.get(metric_name, f"{metric_name} is {direction}"),
            metric_name=metric_name,
            trend_direction=direction,
            trend_strength=abs(correlation),
            data_points=data_points,
            statistical_significance=abs(correlation),  # Simplified
            start_date=start_date,
            end_date=max(dp[0] for dp in data_points),
            rate_of_change=slope,
            confidence_interval=confidence_interval,
            r_squared=r_squared
        )
    
    def _calculate_correlation_metrics(self, sessions: List[SessionAnalysis]) -> Dict[str, Dict[str, float]]:
        """Calculate various correlation metrics."""
        correlations = {
            'files': {},
            'tools': {},
            'temporal': {}
        }
        
        # File usage correlations
        file_sessions = defaultdict(list)
        for session in sessions:
            for op in session.file_operations:
                if op.file_path:
                    file_sessions[op.file_path].append(session)
        
        for file_path, file_session_list in file_sessions.items():
            if len(file_session_list) >= 2:
                # Calculate consistency across sessions
                consistency = len(file_session_list) / len(sessions)
                correlations['files'][file_path] = consistency
        
        # Tool usage correlations  
        tool_sessions = defaultdict(list)
        for session in sessions:
            session_tools = set(op.tool_name for op in session.file_operations)
            for tool in session_tools:
                tool_sessions[tool].append(session)
        
        for tool_name, tool_session_list in tool_sessions.items():
            if len(tool_session_list) >= 2:
                consistency = len(tool_session_list) / len(sessions)
                correlations['tools'][tool_name] = consistency
        
        # Temporal correlations (simplified)
        hour_sessions = defaultdict(int)
        for session in sessions:
            if session.start_time:
                hour = session.start_time.hour
                hour_sessions[hour] += 1
        
        total_sessions = len(sessions)
        for hour, count in hour_sessions.items():
            if count >= 2:
                correlations['temporal'][f"hour_{hour}"] = count / total_sessions
        
        return correlations
    
    def _identify_session_dependencies(self, sessions: List[SessionAnalysis]) -> List[Tuple[str, str, float]]:
        """Identify dependencies between sessions."""
        dependencies = []
        
        for i, session1 in enumerate(sessions[:-1]):
            session2 = sessions[i + 1]
            
            # Check for file continuations
            files1 = set(op.file_path for op in session1.file_operations if op.file_path)
            files2 = set(op.file_path for op in session2.file_operations if op.file_path)
            
            if files1 and files2:
                file_overlap = len(files1.intersection(files2)) / len(files1.union(files2))
                
                # Check temporal proximity
                if session1.end_time and session2.start_time:
                    time_gap = (session2.start_time - session1.end_time).total_seconds() / 3600
                    
                    # Strong dependency if high file overlap and short time gap
                    if file_overlap > 0.5 and time_gap < 24:
                        dependency_strength = file_overlap * (1 - min(time_gap / 24, 1))
                        dependencies.append((session1.session_id, session2.session_id, dependency_strength))
        
        return sorted(dependencies, key=lambda x: x[2], reverse=True)[:20]
    
    def _identify_workflow_continuations(self, sessions: List[SessionAnalysis]) -> List[Tuple[str, str, str]]:
        """Identify workflow continuations between sessions."""
        continuations = []
        
        for i, session1 in enumerate(sessions[:-1]):
            session2 = sessions[i + 1]
            
            # Look for continuation patterns
            last_ops1 = session1.file_operations[-3:] if len(session1.file_operations) >= 3 else session1.file_operations
            first_ops2 = session2.file_operations[:3] if len(session2.file_operations) >= 3 else session2.file_operations
            
            # Check for read -> edit continuation
            if (last_ops1 and first_ops2 and 
                any(op.tool_name == "Read" for op in last_ops1) and
                any(op.tool_name == "Edit" for op in first_ops2)):
                
                # Check if same file
                read_files = set(op.file_path for op in last_ops1 if op.tool_name == "Read" and op.file_path)
                edit_files = set(op.file_path for op in first_ops2 if op.tool_name == "Edit" and op.file_path)
                
                if read_files.intersection(edit_files):
                    continuations.append((session1.session_id, session2.session_id, "read_to_edit"))
            
            # Check for debugging continuation
            if (any("error" in str(op.parameters).lower() for op in last_ops1) and
                any(op.tool_name == "Bash" for op in first_ops2)):
                continuations.append((session1.session_id, session2.session_id, "debug_to_test"))
        
        return continuations
    
    def _analyze_evolution_metrics(self, sessions: List[SessionAnalysis]) -> Dict[str, List[Tuple[datetime, float]]]:
        """Analyze how various metrics evolve over time."""
        evolution = {
            'complexity': [],
            'efficiency': [],
            'focus': []
        }
        
        for session in sessions:
            if not session.start_time:
                continue
            
            # Complexity evolution
            complexity = self._calculate_session_complexity(session)
            evolution['complexity'].append((session.start_time, complexity))
            
            # Efficiency evolution (tokens per hour)
            if session.duration_hours > 0:
                efficiency = session.total_tokens / session.duration_hours
                evolution['efficiency'].append((session.start_time, efficiency))
            
            # Focus evolution (inverse of context switches per message)
            if session.total_messages > 0:
                focus = 1.0 - min(session.context_switches / session.total_messages, 1.0)
                evolution['focus'].append((session.start_time, focus))
        
        return evolution
    
    def _generate_predictive_insights(self, 
                                    sessions: List[SessionAnalysis],
                                    patterns: List[CrossSessionPattern],
                                    trends: List[LongTermTrend]) -> Dict[str, Any]:
        """Generate predictive insights based on analysis."""
        predictions = {
            'patterns': [],
            'timing': [],
            'workflows': []
        }
        
        # Predict next patterns based on recurring patterns
        recurring_patterns = [p for p in patterns if p.is_recurring_pattern]
        for pattern in recurring_patterns[:3]:
            # Simple prediction based on frequency
            probability = min(pattern.consistency_score, 0.9)
            predictions['patterns'].append((pattern.description, probability))
        
        # Recommend session timing based on productive hours
        hour_productivity = defaultdict(list)
        for session in sessions:
            if session.start_time and session.duration_hours > 0:
                hour = session.start_time.hour
                productivity = session.total_tokens / session.duration_hours
                hour_productivity[hour].append(productivity)
        
        # Find most productive hours
        avg_productivity = {}
        for hour, productivities in hour_productivity.items():
            avg_productivity[hour] = sum(productivities) / len(productivities)
        
        if avg_productivity:
            top_hours = sorted(avg_productivity.items(), key=lambda x: x[1], reverse=True)[:3]
            for hour, _ in top_hours:
                predictions['timing'].append(f"Consider scheduling focused work around {hour}:00")
        
        # Suggest optimal workflow sequences based on successful patterns
        successful_patterns = [p for p in patterns if p.correlation_strength > 0.7]
        for pattern in successful_patterns[:3]:
            if len(pattern.key_indicators) >= 2:
                workflow = pattern.key_indicators
                predictions['workflows'].append(workflow)
        
        return predictions
    
    def _calculate_time_span(self, sessions: List[SessionAnalysis]) -> int:
        """Calculate time span of analysis in days."""
        if not sessions:
            return 0
        
        start_times = [s.start_time for s in sessions if s.start_time]
        if not start_times:
            return 0
        
        return (max(start_times) - min(start_times)).days
    
    def _calculate_analysis_quality(self, sessions: List[SessionAnalysis]) -> Tuple[float, float]:
        """Calculate analysis confidence and data completeness."""
        if not sessions:
            return 0.0, 0.0
        
        # Confidence based on session count and time span
        session_factor = min(len(sessions) / 20, 1.0)  # Up to 20 sessions = full confidence
        time_span = self._calculate_time_span(sessions)
        time_factor = min(time_span / 30, 1.0)  # Up to 30 days = full confidence
        
        confidence = (session_factor + time_factor) / 2
        
        # Completeness based on data availability
        sessions_with_full_data = sum(1 for s in sessions if 
                                    s.start_time and s.end_time and 
                                    s.total_messages > 0 and len(s.file_operations) > 0)
        
        completeness = sessions_with_full_data / len(sessions)
        
        return confidence, completeness