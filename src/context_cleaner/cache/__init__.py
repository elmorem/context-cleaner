"""
Cache Analysis Module

This module provides intelligent analysis of Claude Code's cache data to enhance
context optimization with real usage patterns and insights.

Components:
- SessionParser: Parse .jsonl conversation history
- CacheModels: Data models for structured cache analysis  
- DiscoveryService: Cross-platform cache location detection
- UsageAnalyzer: File access patterns and workflow recognition
- TokenAnalyzer: Token usage and efficiency analysis
- TemporalAnalyzer: Session boundaries and topic drift detection
"""

from .models import (
    SessionMessage,
    ToolUsage,
    TokenMetrics,
    CacheAnalysisResult,
    FileAccessPattern,
    SessionAnalysis
)

from .session_parser import SessionCacheParser
from .discovery import CacheDiscoveryService, CacheLocation
from .usage_analyzer import UsagePatternAnalyzer, WorkflowPattern, FileUsageMetrics, UsagePatternSummary
from .token_analyzer import TokenEfficiencyAnalyzer, TokenWastePattern, CacheEfficiencyMetrics, TokenAnalysisSummary
from .temporal_analyzer import TemporalContextAnalyzer, TopicTransition, SessionBoundary, TemporalInsights
from .enhanced_context_analyzer import EnhancedContextAnalyzer, CacheEnhancedAnalysis, UsageWeightedScore
from .correlation_analyzer import CrossSessionCorrelationAnalyzer, SessionCluster, CrossSessionPattern, LongTermTrend, CorrelationInsights

__all__ = [
    # Core models and data structures
    'SessionMessage',
    'ToolUsage', 
    'TokenMetrics',
    'CacheAnalysisResult',
    'FileAccessPattern',
    'SessionAnalysis',
    
    # Discovery and parsing
    'SessionCacheParser',
    'CacheDiscoveryService',
    'CacheLocation',
    
    # Usage pattern analysis
    'UsagePatternAnalyzer',
    'WorkflowPattern',
    'FileUsageMetrics', 
    'UsagePatternSummary',
    
    # Token efficiency analysis
    'TokenEfficiencyAnalyzer',
    'TokenWastePattern',
    'CacheEfficiencyMetrics',
    'TokenAnalysisSummary',
    
    # Temporal analysis
    'TemporalContextAnalyzer',
    'TopicTransition',
    'SessionBoundary',
    'TemporalInsights',
    
    # Enhanced context analysis
    'EnhancedContextAnalyzer',
    'CacheEnhancedAnalysis',
    'UsageWeightedScore',
    
    # Cross-session correlation
    'CrossSessionCorrelationAnalyzer',
    'SessionCluster',
    'CrossSessionPattern',
    'LongTermTrend',
    'CorrelationInsights'
]