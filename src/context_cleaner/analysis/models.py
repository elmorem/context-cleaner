"""
Cache Data Models

Data structures for analyzing Claude Code cache information including
session messages, tool usage patterns, token metrics, and analysis results.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum


class MessageRole(Enum):
    """Message role types in Claude Code conversations."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(Enum):
    """Message types in Claude Code sessions."""
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"


@dataclass
class TokenMetrics:
    """Token usage metrics for cache efficiency analysis."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    ephemeral_5m_input_tokens: int = 0
    ephemeral_1h_input_tokens: int = 0
    total_tokens: int = 0
    
    def __post_init__(self):
        """Calculate total tokens if not provided."""
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
    
    @property
    def cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total_cache = self.cache_creation_input_tokens + self.cache_read_input_tokens
        if total_cache == 0:
            return 0.0
        return self.cache_read_input_tokens / total_cache
    
    @property
    def cache_efficiency(self) -> float:
        """Calculate cache efficiency (read vs creation)."""
        if self.cache_creation_input_tokens == 0:
            return 1.0 if self.cache_read_input_tokens > 0 else 0.0
        return self.cache_read_input_tokens / self.cache_creation_input_tokens


@dataclass 
class ToolUsage:
    """Tool usage information from Claude Code sessions."""
    tool_name: str
    tool_id: str
    parameters: Dict[str, Any]
    timestamp: datetime
    success: bool = True
    duration_ms: Optional[int] = None
    result_size: Optional[int] = None
    
    @property
    def is_file_operation(self) -> bool:
        """Check if this is a file-related operation."""
        file_tools = ['Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep']
        return self.tool_name in file_tools
    
    @property
    def is_bash_operation(self) -> bool:
        """Check if this is a bash/command operation."""
        return self.tool_name == 'Bash'
    
    @property
    def file_path(self) -> Optional[str]:
        """Extract file path from tool parameters if available."""
        if not self.is_file_operation:
            return None
        
        # Common file path parameter names
        path_keys = ['file_path', 'path', 'pattern']
        for key in path_keys:
            if key in self.parameters:
                return self.parameters[key]
        return None


@dataclass
class SessionMessage:
    """A message from a Claude Code session."""
    uuid: str
    parent_uuid: Optional[str]
    message_type: MessageType
    role: MessageRole
    content: Union[str, List[Dict[str, Any]]]
    timestamp: datetime
    token_metrics: Optional[TokenMetrics] = None
    tool_usage: List[ToolUsage] = field(default_factory=list)
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    git_branch: Optional[str] = None
    working_directory: Optional[str] = None
    
    @property
    def content_text(self) -> str:
        """Extract text content from message."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, list):
            text_parts = []
            for item in self.content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    elif item.get('type') == 'tool_use':
                        text_parts.append(f"Tool: {item.get('name', 'unknown')}")
                    elif item.get('type') == 'tool_result':
                        text_parts.append(f"Result: {str(item.get('content', ''))[:100]}")
            return ' '.join(text_parts)
        return str(self.content)
    
    @property
    def estimated_tokens(self) -> int:
        """Estimate token count from content."""
        if self.token_metrics:
            return self.token_metrics.total_tokens
        
        # Rough estimation: ~4 characters per token
        return max(1, len(self.content_text) // 4)
    
    @property
    def is_context_switch(self) -> bool:
        """Detect if this message represents a context switch."""
        content_lower = self.content_text.lower()
        switch_indicators = [
            'switch', 'change topic', 'different', 'now let', 'moving on',
            'next task', 'switch to', 'let me', 'okay, now'
        ]
        return any(indicator in content_lower for indicator in switch_indicators)


@dataclass
class SessionAnalysis:
    """Analysis results for a single session."""
    session_id: str
    start_time: datetime
    end_time: datetime
    total_messages: int
    total_tokens: int
    file_operations: List[ToolUsage]
    context_switches: int
    average_response_time: float
    cache_efficiency: float
    primary_topics: List[str] = field(default_factory=list)
    working_directories: List[str] = field(default_factory=list)
    git_branches: List[str] = field(default_factory=list)
    
    @property
    def duration_hours(self) -> float:
        """Calculate session duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600
    
    @property
    def messages_per_hour(self) -> float:
        """Calculate message frequency."""
        if self.duration_hours == 0:
            return 0
        return self.total_messages / self.duration_hours
    
    @property
    def tokens_per_message(self) -> float:
        """Calculate average tokens per message."""
        if self.total_messages == 0:
            return 0
        return self.total_tokens / self.total_messages


@dataclass
class FileAccessPattern:
    """Pattern analysis for file access behavior."""
    file_path: str
    access_count: int
    first_access: datetime
    last_access: datetime
    operation_types: List[str]
    total_read_size: int = 0
    
    @property
    def access_frequency(self) -> float:
        """Calculate access frequency (accesses per hour)."""
        duration = (self.last_access - self.first_access).total_seconds() / 3600
        if duration == 0:
            return float(self.access_count)
        return self.access_count / duration
    
    @property
    def is_frequently_accessed(self) -> bool:
        """Determine if file is frequently accessed."""
        return self.access_count >= 3
    
    @property
    def is_recently_accessed(self) -> bool:
        """Check if file was accessed recently."""
        return (datetime.now() - self.last_access).total_seconds() < 3600  # 1 hour


@dataclass
class CacheAnalysisResult:
    """Comprehensive cache analysis results."""
    
    # Session-level metrics
    sessions_analyzed: int
    total_messages: int
    total_tokens: int
    analysis_start_time: datetime
    analysis_end_time: datetime
    
    # Token efficiency metrics  
    overall_cache_hit_ratio: float
    cache_efficiency_score: float
    token_waste_estimate: int
    
    # Usage patterns
    file_access_patterns: List[FileAccessPattern]
    most_accessed_files: List[str]
    context_switch_frequency: float
    
    # Temporal analysis
    session_analyses: List[SessionAnalysis]
    peak_usage_hours: List[int]
    average_session_duration: float
    
    # Recommendations
    optimization_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    files_safe_to_remove: List[str] = field(default_factory=list)
    context_pruning_suggestions: List[str] = field(default_factory=list)
    
    @property
    def analysis_duration(self) -> float:
        """Calculate analysis duration in seconds."""
        return (self.analysis_end_time - self.analysis_start_time).total_seconds()
    
    @property
    def average_tokens_per_session(self) -> float:
        """Calculate average tokens per session."""
        if self.sessions_analyzed == 0:
            return 0
        return self.total_tokens / self.sessions_analyzed
    
    @property
    def cache_effectiveness_grade(self) -> str:
        """Grade cache effectiveness."""
        if self.cache_efficiency_score >= 0.8:
            return "Excellent"
        elif self.cache_efficiency_score >= 0.6:
            return "Good" 
        elif self.cache_efficiency_score >= 0.4:
            return "Fair"
        else:
            return "Needs Improvement"
    
    def get_summary(self) -> str:
        """Generate human-readable summary."""
        return f"""
Cache Analysis Summary:
- {self.sessions_analyzed} sessions analyzed
- {self.total_messages:,} messages processed
- {self.total_tokens:,} tokens analyzed
- Cache hit ratio: {self.overall_cache_hit_ratio:.1%}
- Efficiency grade: {self.cache_effectiveness_grade}
- {len(self.optimization_opportunities)} optimization opportunities found
- Analysis completed in {self.analysis_duration:.2f}s
        """.strip()


@dataclass
class CacheConfig:
    """Configuration for cache analysis."""
    
    # Analysis limits
    max_sessions_to_analyze: int = 50
    max_file_size_mb: int = 100
    analysis_timeout_seconds: int = 30
    
    # Pattern detection thresholds
    frequent_access_threshold: int = 3
    recent_access_hours: int = 1
    context_switch_detection: bool = True
    
    # Privacy settings
    anonymize_file_paths: bool = False
    include_content_analysis: bool = True
    store_analysis_results: bool = True
    
    # Cache discovery settings
    search_all_projects: bool = True
    include_archived_sessions: bool = False
    max_cache_age_days: int = 30