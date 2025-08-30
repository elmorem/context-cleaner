"""
Cache Analysis Module

This module provides intelligent analysis of Claude Code's cache data to enhance
context optimization with real usage patterns and insights.

Components:
- SessionParser: Parse .jsonl conversation history
- CacheModels: Data models for structured cache analysis  
- DiscoveryService: Cross-platform cache location detection
- TokenAnalyzer: Token usage and efficiency analysis
"""

from .models import (
    SessionMessage,
    ToolUsage,
    TokenMetrics,
    CacheAnalysisResult
)

from .session_parser import SessionCacheParser
from .discovery import CacheDiscoveryService

__all__ = [
    'SessionMessage',
    'ToolUsage', 
    'TokenMetrics',
    'CacheAnalysisResult',
    'SessionCacheParser',
    'CacheDiscoveryService'
]