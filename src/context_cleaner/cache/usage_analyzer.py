"""
Usage Pattern Analyzer

Analyzes file access patterns, workflow recognition, and user behavior patterns
from Claude Code cache data to provide intelligent context optimization insights.
"""

import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re

from .models import SessionAnalysis, ToolUsage, FileAccessPattern, CacheConfig
from .session_parser import SessionCacheParser
from .discovery import CacheDiscoveryService, CacheLocation

logger = logging.getLogger(__name__)


@dataclass
class WorkflowPattern:
    """Represents a recognized workflow pattern."""
    
    pattern_id: str
    name: str
    description: str
    file_sequence: List[str]
    tool_sequence: List[str]
    frequency: int
    confidence_score: float
    average_duration: float  # in minutes
    common_transitions: List[Tuple[str, str, float]]  # (from_file, to_file, probability)
    session_ids: List[str] = field(default_factory=list)
    
    @property
    def is_frequent(self) -> bool:
        """Check if this is a frequently used pattern."""
        return self.frequency >= 3 and self.confidence_score >= 0.7
    
    @property
    def complexity_level(self) -> str:
        """Get complexity level of the workflow."""
        if len(self.file_sequence) <= 2:
            return "Simple"
        elif len(self.file_sequence) <= 5:
            return "Moderate"
        else:
            return "Complex"


@dataclass
class FileUsageMetrics:
    """Metrics about how files are used across sessions."""
    
    file_path: str
    total_accesses: int
    unique_sessions: int
    tool_types: Set[str]
    first_access: datetime
    last_access: datetime
    average_session_frequency: float
    peak_usage_hours: List[int]  # Hours of day when most accessed
    common_contexts: List[str]  # Common words/topics when file is accessed
    
    @property
    def usage_intensity(self) -> str:
        """Categorize usage intensity."""
        if self.average_session_frequency >= 5:
            return "Heavy"
        elif self.average_session_frequency >= 2:
            return "Moderate"
        elif self.average_session_frequency >= 0.5:
            return "Light"
        else:
            return "Rare"
    
    @property
    def staleness_days(self) -> int:
        """Days since last access."""
        return (datetime.now() - self.last_access).days


@dataclass
class UsagePatternSummary:
    """Summary of usage patterns across all analyzed sessions."""
    
    total_sessions_analyzed: int
    total_files_accessed: int
    workflow_patterns: List[WorkflowPattern]
    file_usage_metrics: Dict[str, FileUsageMetrics]
    common_tool_sequences: List[Tuple[List[str], int]]  # (sequence, frequency)
    session_duration_patterns: Dict[str, float]  # duration category -> average
    context_switch_frequency: float
    most_productive_hours: List[int]
    analysis_date: datetime = field(default_factory=datetime.now)
    
    @property
    def top_workflow_patterns(self) -> List[WorkflowPattern]:
        """Get most frequent workflow patterns."""
        return sorted(self.workflow_patterns, 
                     key=lambda x: (x.frequency, x.confidence_score), 
                     reverse=True)[:10]
    
    @property
    def heavily_used_files(self) -> List[FileUsageMetrics]:
        """Get heavily used files."""
        return [m for m in self.file_usage_metrics.values() 
                if m.usage_intensity in ["Heavy", "Moderate"]]


class UsagePatternAnalyzer:
    """Analyzes usage patterns from Claude Code cache data."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize the usage pattern analyzer."""
        self.config = config or CacheConfig()
        self.parser = SessionCacheParser(config)
        self.discovery = CacheDiscoveryService(config)
        
        # Pattern recognition parameters
        self.min_pattern_frequency = 2
        self.min_confidence_score = 0.6
        self.max_pattern_complexity = 10
        
        # Workflow detection patterns
        self.workflow_indicators = {
            'development': ['read', 'edit', 'bash', 'test'],
            'debugging': ['read', 'grep', 'bash', 'edit'],
            'exploration': ['read', 'glob', 'read', 'read'],
            'documentation': ['read', 'write', 'edit'],
            'testing': ['bash', 'read', 'edit', 'bash'],
        }
        
    def analyze_usage_patterns(self, 
                             cache_locations: Optional[List[CacheLocation]] = None,
                             max_sessions: Optional[int] = None) -> UsagePatternSummary:
        """
        Analyze usage patterns across cache locations.
        
        Args:
            cache_locations: Specific cache locations to analyze
            max_sessions: Maximum number of sessions to analyze per location
            
        Returns:
            Comprehensive usage pattern summary
        """
        logger.info("Starting usage pattern analysis...")
        
        if cache_locations is None:
            cache_locations = self.discovery.discover_cache_locations()
        
        all_sessions = []
        
        # Parse sessions from all locations
        for location in cache_locations:
            logger.info(f"Analyzing cache location: {location.project_name}")
            
            session_files = location.session_files
            if max_sessions:
                # Sort by modification time, take most recent
                session_files = sorted(session_files, 
                                     key=lambda x: x.stat().st_mtime, 
                                     reverse=True)[:max_sessions]
            
            for session_file in session_files:
                try:
                    analysis = self.parser.parse_session_file(session_file)
                    if analysis and self._is_valid_session(analysis):
                        all_sessions.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to parse session {session_file}: {e}")
                    continue
        
        logger.info(f"Successfully parsed {len(all_sessions)} sessions")
        
        if not all_sessions:
            return UsagePatternSummary(
                total_sessions_analyzed=0,
                total_files_accessed=0,
                workflow_patterns=[],
                file_usage_metrics={},
                common_tool_sequences=[],
                session_duration_patterns={},
                context_switch_frequency=0.0,
                most_productive_hours=[]
            )
        
        # Analyze patterns
        workflow_patterns = self._detect_workflow_patterns(all_sessions)
        file_metrics = self._analyze_file_usage(all_sessions)
        tool_sequences = self._analyze_tool_sequences(all_sessions)
        duration_patterns = self._analyze_duration_patterns(all_sessions)
        context_switches = self._analyze_context_switches(all_sessions)
        productive_hours = self._analyze_productive_hours(all_sessions)
        
        summary = UsagePatternSummary(
            total_sessions_analyzed=len(all_sessions),
            total_files_accessed=len(file_metrics),
            workflow_patterns=workflow_patterns,
            file_usage_metrics=file_metrics,
            common_tool_sequences=tool_sequences,
            session_duration_patterns=duration_patterns,
            context_switch_frequency=context_switches,
            most_productive_hours=productive_hours
        )
        
        logger.info(f"Analysis complete: {len(workflow_patterns)} patterns, "
                   f"{len(file_metrics)} files analyzed")
        
        return summary
    
    def _is_valid_session(self, session: SessionAnalysis) -> bool:
        """Check if session is valid for pattern analysis."""
        return (
            session.total_messages >= 3 and
            session.total_tokens >= 100 and
            len(session.file_operations) >= 1 and
            session.duration_hours <= 24  # Filter out corrupted sessions
        )
    
    def _detect_workflow_patterns(self, sessions: List[SessionAnalysis]) -> List[WorkflowPattern]:
        """Detect common workflow patterns from sessions."""
        pattern_counter = defaultdict(list)
        
        for session in sessions:
            if len(session.file_operations) < 2:
                continue
                
            # Extract file sequence
            file_sequence = [op.file_path for op in session.file_operations 
                           if op.file_path]
            
            # Extract tool sequence
            tool_sequence = [op.tool_name.lower() for op in session.file_operations]
            
            if len(file_sequence) >= 2:
                # Create pattern signature
                pattern_sig = self._create_pattern_signature(file_sequence, tool_sequence)
                pattern_counter[pattern_sig].append({
                    'session_id': session.session_id,
                    'file_sequence': file_sequence,
                    'tool_sequence': tool_sequence,
                    'duration': session.duration_hours * 60  # convert to minutes
                })
        
        # Convert to workflow patterns
        patterns = []
        for pattern_sig, occurrences in pattern_counter.items():
            if len(occurrences) >= self.min_pattern_frequency:
                pattern = self._create_workflow_pattern(pattern_sig, occurrences)
                if pattern.confidence_score >= self.min_confidence_score:
                    patterns.append(pattern)
        
        return sorted(patterns, key=lambda x: x.frequency, reverse=True)
    
    def _create_pattern_signature(self, file_sequence: List[str], tool_sequence: List[str]) -> str:
        """Create a signature for a workflow pattern."""
        # Normalize file paths to just filenames
        normalized_files = [Path(f).name for f in file_sequence if f]
        
        # Create signature based on file extensions and tool sequence
        file_extensions = [Path(f).suffix for f in normalized_files]
        
        # Combine tool sequence with file type patterns
        signature_parts = []
        
        # Add tool pattern
        tool_pattern = "->".join(tool_sequence[:5])  # Limit to first 5 tools
        signature_parts.append(f"tools:{tool_pattern}")
        
        # Add file type pattern
        if file_extensions:
            ext_pattern = "->".join(file_extensions[:5])
            signature_parts.append(f"types:{ext_pattern}")
        
        return "|".join(signature_parts)
    
    def _create_workflow_pattern(self, signature: str, occurrences: List[Dict]) -> WorkflowPattern:
        """Create a workflow pattern from signature and occurrences."""
        # Calculate statistics
        frequency = len(occurrences)
        avg_duration = sum(occ['duration'] for occ in occurrences) / frequency
        
        # Get representative sequences
        file_sequences = [occ['file_sequence'] for occ in occurrences]
        tool_sequences = [occ['tool_sequence'] for occ in occurrences]
        
        # Find most common sequences
        most_common_files = self._find_most_common_sequence(file_sequences)
        most_common_tools = self._find_most_common_sequence(tool_sequences)
        
        # Calculate confidence based on consistency
        confidence = self._calculate_pattern_confidence(file_sequences, tool_sequences)
        
        # Generate pattern name and description
        pattern_name, description = self._generate_pattern_description(
            most_common_tools, most_common_files
        )
        
        # Calculate common transitions
        transitions = self._calculate_file_transitions(file_sequences)
        
        return WorkflowPattern(
            pattern_id=f"pattern_{hash(signature) % 10000}",
            name=pattern_name,
            description=description,
            file_sequence=most_common_files,
            tool_sequence=most_common_tools,
            frequency=frequency,
            confidence_score=confidence,
            average_duration=avg_duration,
            common_transitions=transitions,
            session_ids=[occ['session_id'] for occ in occurrences]
        )
    
    def _find_most_common_sequence(self, sequences: List[List[str]]) -> List[str]:
        """Find the most representative sequence from a list of sequences."""
        if not sequences:
            return []
            
        # Find the most common length
        lengths = [len(seq) for seq in sequences]
        most_common_length = Counter(lengths).most_common(1)[0][0]
        
        # Filter sequences by most common length
        filtered_sequences = [seq for seq in sequences if len(seq) == most_common_length]
        
        if not filtered_sequences:
            return sequences[0] if sequences else []
        
        # Find most common element at each position
        result = []
        for i in range(most_common_length):
            elements_at_position = [seq[i] for seq in filtered_sequences if i < len(seq)]
            if elements_at_position:
                most_common = Counter(elements_at_position).most_common(1)[0][0]
                result.append(most_common)
        
        return result
    
    def _calculate_pattern_confidence(self, file_sequences: List[List[str]], 
                                    tool_sequences: List[List[str]]) -> float:
        """Calculate confidence score for a pattern based on consistency."""
        total_sequences = len(file_sequences)
        if total_sequences == 0:
            return 0.0
        
        # Calculate tool sequence consistency
        tool_consistency = 0.0
        if tool_sequences:
            most_common_tools = self._find_most_common_sequence(tool_sequences)
            matches = sum(1 for seq in tool_sequences 
                         if self._sequence_similarity(seq, most_common_tools) >= 0.7)
            tool_consistency = matches / len(tool_sequences)
        
        # Calculate file type consistency
        file_type_consistency = 0.0
        if file_sequences:
            file_extensions = [[Path(f).suffix for f in seq] for seq in file_sequences]
            most_common_exts = self._find_most_common_sequence(file_extensions)
            matches = sum(1 for seq in file_extensions 
                         if self._sequence_similarity(seq, most_common_exts) >= 0.7)
            file_type_consistency = matches / len(file_extensions)
        
        # Combine confidences
        return (tool_consistency + file_type_consistency) / 2
    
    def _sequence_similarity(self, seq1: List[str], seq2: List[str]) -> float:
        """Calculate similarity between two sequences."""
        if not seq1 or not seq2:
            return 0.0
        
        # Use Jaccard similarity for simplicity
        set1, set2 = set(seq1), set(seq2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _generate_pattern_description(self, tools: List[str], files: List[str]) -> Tuple[str, str]:
        """Generate human-readable name and description for a pattern."""
        # Check against known workflow indicators
        tool_set = set(t.lower() for t in tools)
        
        for workflow_name, indicators in self.workflow_indicators.items():
            indicator_set = set(indicators)
            if len(tool_set.intersection(indicator_set)) >= len(indicator_set) * 0.6:
                name = workflow_name.title()
                description = f"{name} workflow involving {', '.join(tools[:3])}"
                if len(tools) > 3:
                    description += f" and {len(tools)-3} more operations"
                return name, description
        
        # Generic description
        primary_tool = tools[0] if tools else "unknown"
        name = f"{primary_tool.title()} Workflow"
        description = f"Workflow starting with {primary_tool}"
        if len(tools) > 1:
            description += f" followed by {', '.join(tools[1:3])}"
        
        return name, description
    
    def _calculate_file_transitions(self, file_sequences: List[List[str]]) -> List[Tuple[str, str, float]]:
        """Calculate common file-to-file transitions."""
        transition_counter = Counter()
        total_transitions = 0
        
        for sequence in file_sequences:
            for i in range(len(sequence) - 1):
                from_file = Path(sequence[i]).name if sequence[i] else "unknown"
                to_file = Path(sequence[i + 1]).name if sequence[i + 1] else "unknown"
                transition_counter[(from_file, to_file)] += 1
                total_transitions += 1
        
        # Convert to probabilities
        transitions = []
        for (from_file, to_file), count in transition_counter.most_common(10):
            probability = count / total_transitions if total_transitions > 0 else 0
            transitions.append((from_file, to_file, probability))
        
        return transitions
    
    def _analyze_file_usage(self, sessions: List[SessionAnalysis]) -> Dict[str, FileUsageMetrics]:
        """Analyze how files are used across sessions."""
        file_data = defaultdict(lambda: {
            'accesses': 0,
            'sessions': set(),
            'tools': set(),
            'access_times': [],
            'contexts': []
        })
        
        for session in sessions:
            session_time = session.start_time
            
            for operation in session.file_operations:
                if not operation.file_path:
                    continue
                
                file_path = operation.file_path
                file_data[file_path]['accesses'] += 1
                file_data[file_path]['sessions'].add(session.session_id)
                file_data[file_path]['tools'].add(operation.tool_name)
                file_data[file_path]['access_times'].append(session_time)
                
                # Extract context (simplified - could be enhanced)
                context_words = self._extract_context_words(session, operation)
                file_data[file_path]['contexts'].extend(context_words)
        
        # Convert to FileUsageMetrics
        metrics = {}
        for file_path, data in file_data.items():
            if data['accesses'] > 0:
                access_times = sorted(data['access_times'])
                avg_frequency = data['accesses'] / len(data['sessions'])
                
                # Analyze peak usage hours
                hours = [t.hour for t in access_times]
                peak_hours = [h for h, count in Counter(hours).most_common(3)]
                
                # Common context words
                common_contexts = [word for word, count in 
                                 Counter(data['contexts']).most_common(5)]
                
                metrics[file_path] = FileUsageMetrics(
                    file_path=file_path,
                    total_accesses=data['accesses'],
                    unique_sessions=len(data['sessions']),
                    tool_types=data['tools'],
                    first_access=access_times[0],
                    last_access=access_times[-1],
                    average_session_frequency=avg_frequency,
                    peak_usage_hours=peak_hours,
                    common_contexts=common_contexts
                )
        
        return metrics
    
    def _extract_context_words(self, session: SessionAnalysis, operation: ToolUsage) -> List[str]:
        """Extract context words around a file operation (simplified implementation)."""
        # This is a simplified version - could be enhanced with actual message content
        words = []
        
        # Extract words from file path
        path_parts = Path(operation.file_path).parts
        for part in path_parts:
            words.extend(re.findall(r'\w+', part.lower()))
        
        # Add tool name as context
        words.append(operation.tool_name.lower())
        
        return [w for w in words if len(w) > 2]  # Filter short words
    
    def _analyze_tool_sequences(self, sessions: List[SessionAnalysis]) -> List[Tuple[List[str], int]]:
        """Analyze common tool usage sequences."""
        sequence_counter = Counter()
        
        for session in sessions:
            tools = [op.tool_name for op in session.file_operations]
            
            # Generate subsequences of length 2-4
            for length in range(2, min(5, len(tools) + 1)):
                for i in range(len(tools) - length + 1):
                    subsequence = tuple(tools[i:i + length])
                    sequence_counter[subsequence] += 1
        
        # Convert to list format
        common_sequences = []
        for sequence, count in sequence_counter.most_common(20):
            if count >= 2:  # Only include sequences that appear multiple times
                common_sequences.append((list(sequence), count))
        
        return common_sequences
    
    def _analyze_duration_patterns(self, sessions: List[SessionAnalysis]) -> Dict[str, float]:
        """Analyze session duration patterns."""
        durations = [session.duration_hours * 60 for session in sessions]  # Convert to minutes
        
        patterns = {}
        if durations:
            patterns['average_duration'] = sum(durations) / len(durations)
            patterns['short_session_threshold'] = 15  # minutes
            patterns['long_session_threshold'] = 120   # minutes
            
            short_sessions = [d for d in durations if d <= patterns['short_session_threshold']]
            medium_sessions = [d for d in durations if patterns['short_session_threshold'] < d <= patterns['long_session_threshold']]
            long_sessions = [d for d in durations if d > patterns['long_session_threshold']]
            
            total = len(durations)
            patterns['short_session_ratio'] = len(short_sessions) / total
            patterns['medium_session_ratio'] = len(medium_sessions) / total
            patterns['long_session_ratio'] = len(long_sessions) / total
            
            if short_sessions:
                patterns['avg_short_duration'] = sum(short_sessions) / len(short_sessions)
            if medium_sessions:
                patterns['avg_medium_duration'] = sum(medium_sessions) / len(medium_sessions)
            if long_sessions:
                patterns['avg_long_duration'] = sum(long_sessions) / len(long_sessions)
        
        return patterns
    
    def _analyze_context_switches(self, sessions: List[SessionAnalysis]) -> float:
        """Analyze frequency of context switches."""
        total_switches = sum(session.context_switches for session in sessions)
        total_sessions = len(sessions)
        
        return total_switches / total_sessions if total_sessions > 0 else 0.0
    
    def _analyze_productive_hours(self, sessions: List[SessionAnalysis]) -> List[int]:
        """Analyze most productive hours based on session activity."""
        hour_activity = defaultdict(float)
        
        for session in sessions:
            # Weight by tokens and operations
            activity_score = session.total_tokens + (len(session.file_operations) * 100)
            hour_activity[session.start_time.hour] += activity_score
        
        # Get top 5 productive hours
        sorted_hours = sorted(hour_activity.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, _ in sorted_hours[:5]]
    
    def get_pattern_recommendations(self, summary: UsagePatternSummary) -> List[str]:
        """Generate recommendations based on usage patterns."""
        recommendations = []
        
        # Check for heavily used files
        heavy_files = summary.heavily_used_files
        if len(heavy_files) > 10:
            recommendations.append(
                f"Consider organizing your {len(heavy_files)} heavily-used files into "
                "a dedicated workspace or project structure for better context management."
            )
        
        # Check for workflow optimization opportunities
        frequent_patterns = summary.top_workflow_patterns[:3]
        if frequent_patterns:
            complex_patterns = [p for p in frequent_patterns if p.complexity_level == "Complex"]
            if complex_patterns:
                recommendations.append(
                    f"You have {len(complex_patterns)} complex workflow patterns. "
                    "Consider creating templates or shortcuts for these common workflows."
                )
        
        # Check context switching frequency
        if summary.context_switch_frequency > 5:
            recommendations.append(
                f"High context switching detected ({summary.context_switch_frequency:.1f} per session). "
                "Consider batching similar tasks to improve focus and reduce cognitive load."
            )
        
        # Check for stale files
        stale_files = [m for m in summary.file_usage_metrics.values() if m.staleness_days > 30]
        if len(stale_files) > 20:
            recommendations.append(
                f"Found {len(stale_files)} files not accessed in 30+ days. "
                "Consider archiving old files to improve context cleanliness."
            )
        
        return recommendations