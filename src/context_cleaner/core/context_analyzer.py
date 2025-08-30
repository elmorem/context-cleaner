#!/usr/bin/env python3
"""
Advanced Context Analysis Engine

Provides comprehensive context analysis capabilities including:
- Focus metrics calculation (Focus Score, Priority Alignment, Current Work Ratio)
- Redundancy analysis (duplicates, obsolete content, redundant files)
- Recency analysis (fresh/recent/aging/stale context categorization)
- Priority analysis (attention clarity, work relevance assessment)

Performance targets: <2s analysis for contexts up to 100k tokens
"""

import asyncio
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from .redundancy_detector import RedundancyDetector, RedundancyReport
from .recency_analyzer import RecencyAnalyzer, RecencyReport  
from .focus_scorer import FocusScorer, FocusMetrics
from .priority_analyzer import PriorityAnalyzer, PriorityReport

logger = logging.getLogger(__name__)


@dataclass
class ContextAnalysisResult:
    """Comprehensive result from context analysis."""
    
    # Core metrics
    health_score: int                    # Overall health score (0-100)
    focus_metrics: FocusMetrics          # Focus-related metrics
    redundancy_report: RedundancyReport  # Redundancy analysis results
    recency_report: RecencyReport        # Recency analysis results
    priority_report: PriorityReport      # Priority analysis results
    
    # Size and performance
    total_tokens: int                    # Estimated total tokens
    total_chars: int                     # Total character count
    context_categories: Dict[str, int]   # Breakdown by content type
    
    # Analysis metadata
    analysis_timestamp: str              # When analysis was performed
    analysis_duration: float             # Time taken for analysis
    performance_metrics: Dict[str, Any]  # Performance tracking data
    
    # Optimization potential
    optimization_potential: float        # Percentage reduction possible
    critical_context_ratio: float       # Percentage that must be preserved
    cleanup_impact_estimate: int        # Estimated tokens that could be saved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def get_health_status(self) -> str:
        """Get human-readable health status."""
        if self.health_score >= 85:
            return "Excellent"
        elif self.health_score >= 70:
            return "Good"
        elif self.health_score >= 55:
            return "Fair"
        else:
            return "Needs Attention"
    
    def get_size_category(self) -> str:
        """Get context size category."""
        if self.total_tokens < 10000:
            return "Small"
        elif self.total_tokens < 50000:
            return "Medium"
        elif self.total_tokens < 100000:
            return "Large"
        else:
            return "Very Large"


class ContextAnalyzer:
    """
    Advanced Context Analysis Engine
    
    Coordinates multiple analysis components to provide comprehensive
    context health assessment and optimization guidance.
    """
    
    # Performance constants
    MAX_ANALYSIS_TIME = 5.0      # Maximum time for full analysis
    MAX_CONTEXT_SIZE = 500000    # Maximum context size to analyze (chars)
    CIRCUIT_BREAKER_THRESHOLD = 3  # Failures before circuit breaker trips
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the context analyzer with optional configuration."""
        self.config = config or {}
        
        # Initialize analysis components
        self.redundancy_detector = RedundancyDetector()
        self.recency_analyzer = RecencyAnalyzer()
        self.focus_scorer = FocusScorer()
        self.priority_analyzer = PriorityAnalyzer()
        
        # Performance tracking
        self.circuit_breaker_failures = 0
        self.last_failure_time = None
        self.analysis_cache = {}
        
        logger.info("ContextAnalyzer initialized with performance limits")
    
    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker allows operation to proceed."""
        if self.circuit_breaker_failures < self.CIRCUIT_BREAKER_THRESHOLD:
            return True
        
        # Check if timeout has passed
        if self.last_failure_time:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure > 60:  # 1 minute timeout
                self.circuit_breaker_failures = 0
                self.last_failure_time = None
                return True
        
        return False
    
    def _record_failure(self):
        """Record analysis failure for circuit breaker."""
        self.circuit_breaker_failures += 1
        self.last_failure_time = time.time()
    
    def _record_success(self):
        """Record successful analysis."""
        if self.circuit_breaker_failures > 0:
            self.circuit_breaker_failures = max(0, self.circuit_breaker_failures - 1)
    
    def _generate_cache_key(self, context_data: Dict[str, Any]) -> str:
        """Generate cache key for context data."""
        try:
            # Create hash of context structure and key content
            context_str = json.dumps(context_data, sort_keys=True, default=str)
            return hashlib.md5(context_str.encode()).hexdigest()
        except Exception:
            return str(time.time())  # Fallback to timestamp
    
    def _validate_context_data(self, context_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate context data structure and size."""
        if not isinstance(context_data, dict):
            return False, "Context data must be a dictionary"
        
        if not context_data:
            return False, "Context data cannot be empty"
        
        try:
            # Check size limits
            context_str = json.dumps(context_data, default=str)
            if len(context_str) > self.MAX_CONTEXT_SIZE:
                return False, f"Context size {len(context_str)} exceeds limit {self.MAX_CONTEXT_SIZE}"
            
            return True, "Valid"
            
        except Exception as e:
            return False, f"Context data validation error: {e}"
    
    def _extract_context_categories(self, context_data: Dict[str, Any]) -> Dict[str, int]:
        """Extract and categorize different types of context content."""
        categories = {
            'conversations': 0,
            'files': 0,
            'todos': 0,
            'errors': 0,
            'system_messages': 0,
            'code_snippets': 0,
            'documentation': 0,
            'other': 0
        }
        
        try:
            # Analyze context structure to categorize content
            for key, value in context_data.items():
                if 'conversation' in key.lower() or 'message' in key.lower():
                    categories['conversations'] += len(str(value))
                elif 'file' in key.lower() or 'path' in key.lower():
                    categories['files'] += len(str(value))
                elif 'todo' in key.lower() or 'task' in key.lower():
                    categories['todos'] += len(str(value))
                elif 'error' in key.lower() or 'exception' in key.lower():
                    categories['errors'] += len(str(value))
                elif 'system' in key.lower() or 'reminder' in key.lower():
                    categories['system_messages'] += len(str(value))
                elif 'code' in key.lower() or '.py' in str(value) or '.js' in str(value):
                    categories['code_snippets'] += len(str(value))
                elif 'doc' in key.lower() or 'readme' in key.lower():
                    categories['documentation'] += len(str(value))
                else:
                    categories['other'] += len(str(value))
        
        except Exception as e:
            logger.warning(f"Error categorizing context: {e}")
            categories['other'] = len(json.dumps(context_data, default=str))
        
        return categories
    
    def _calculate_optimization_potential(self, 
                                        redundancy_report: RedundancyReport,
                                        recency_report: RecencyReport,
                                        focus_metrics: FocusMetrics) -> Tuple[float, float, int]:
        """Calculate optimization potential based on analysis results."""
        try:
            # Base optimization potential from redundancy
            redundancy_potential = redundancy_report.duplicate_content_percentage / 100
            
            # Additional potential from stale content
            stale_potential = recency_report.stale_context_percentage / 100
            
            # Reduced potential if focus is already good
            focus_penalty = max(0, (focus_metrics.focus_score - 70) / 100)
            
            # Total optimization potential (capped at 80%)
            optimization_potential = min(0.8, redundancy_potential + (stale_potential * 0.5) - (focus_penalty * 0.2))
            
            # Critical context ratio (must preserve)
            critical_ratio = 1.0 - optimization_potential
            
            # Cleanup impact estimate (tokens that could be saved)
            total_tokens = redundancy_report.total_estimated_tokens
            cleanup_impact = int(total_tokens * optimization_potential)
            
            return optimization_potential, critical_ratio, cleanup_impact
            
        except Exception as e:
            logger.error(f"Error calculating optimization potential: {e}")
            return 0.2, 0.8, 0  # Conservative defaults
    
    def _calculate_overall_health_score(self,
                                      focus_metrics: FocusMetrics,
                                      redundancy_report: RedundancyReport,
                                      recency_report: RecencyReport,
                                      priority_report: PriorityReport) -> int:
        """Calculate overall context health score (0-100)."""
        try:
            # Weighted scoring components
            focus_component = focus_metrics.focus_score * 0.3
            redundancy_component = max(0, 100 - redundancy_report.duplicate_content_percentage) * 0.25
            recency_component = (recency_report.fresh_context_percentage + 
                               recency_report.recent_context_percentage) * 0.5 * 0.25
            priority_component = priority_report.priority_alignment_score * 0.2
            
            # Total score
            health_score = int(focus_component + redundancy_component + 
                              recency_component + priority_component)
            
            return min(100, max(0, health_score))
            
        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 50  # Default neutral score
    
    async def _perform_analysis(self, context_data: Dict[str, Any]) -> ContextAnalysisResult:
        """Perform comprehensive context analysis."""
        analysis_start = time.time()
        
        try:
            # Extract basic metrics
            context_str = json.dumps(context_data, default=str)
            total_chars = len(context_str)
            total_tokens = total_chars // 4  # Rough token estimate
            context_categories = self._extract_context_categories(context_data)
            
            # Run analysis components in parallel for performance
            redundancy_task = asyncio.create_task(
                self.redundancy_detector.analyze_redundancy(context_data)
            )
            recency_task = asyncio.create_task(
                self.recency_analyzer.analyze_recency(context_data)
            )
            focus_task = asyncio.create_task(
                self.focus_scorer.calculate_focus_metrics(context_data)
            )
            priority_task = asyncio.create_task(
                self.priority_analyzer.analyze_priorities(context_data)
            )
            
            # Wait for all analysis components to complete
            redundancy_report = await redundancy_task
            recency_report = await recency_task
            focus_metrics = await focus_task
            priority_report = await priority_task
            
            # Calculate optimization metrics
            optimization_potential, critical_ratio, cleanup_impact = \
                self._calculate_optimization_potential(redundancy_report, recency_report, focus_metrics)
            
            # Calculate overall health score
            health_score = self._calculate_overall_health_score(
                focus_metrics, redundancy_report, recency_report, priority_report
            )
            
            # Analysis performance metrics
            analysis_duration = time.time() - analysis_start
            performance_metrics = {
                'analysis_duration': analysis_duration,
                'total_chars_analyzed': total_chars,
                'chars_per_second': total_chars / analysis_duration if analysis_duration > 0 else 0,
                'components_analyzed': 4,
                'circuit_breaker_active': self.circuit_breaker_failures >= self.CIRCUIT_BREAKER_THRESHOLD
            }
            
            # Create comprehensive result
            result = ContextAnalysisResult(
                health_score=health_score,
                focus_metrics=focus_metrics,
                redundancy_report=redundancy_report,
                recency_report=recency_report,
                priority_report=priority_report,
                total_tokens=total_tokens,
                total_chars=total_chars,
                context_categories=context_categories,
                analysis_timestamp=datetime.now().isoformat(),
                analysis_duration=analysis_duration,
                performance_metrics=performance_metrics,
                optimization_potential=optimization_potential,
                critical_context_ratio=critical_ratio,
                cleanup_impact_estimate=cleanup_impact
            )
            
            logger.info(f"Context analysis completed in {analysis_duration:.3f}s, health score: {health_score}")
            return result
            
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            raise
    
    async def analyze_context(self, context_data: Dict[str, Any], 
                            use_cache: bool = True) -> Optional[ContextAnalysisResult]:
        """
        Perform comprehensive context analysis with safety measures.
        
        Args:
            context_data: Context data to analyze
            use_cache: Whether to use cached results if available
            
        Returns:
            ContextAnalysisResult if successful, None if failed
        """
        # Circuit breaker check
        if not self._check_circuit_breaker():
            logger.warning("Context analysis blocked by circuit breaker")
            return None
        
        # Validate input data
        is_valid, validation_message = self._validate_context_data(context_data)
        if not is_valid:
            logger.error(f"Context data validation failed: {validation_message}")
            return None
        
        # Check cache if enabled
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(context_data)
            cached_result = self.analysis_cache.get(cache_key)
            if cached_result:
                logger.debug("Returning cached analysis result")
                return cached_result
        
        try:
            # Perform analysis with timeout
            result = await asyncio.wait_for(
                self._perform_analysis(context_data),
                timeout=self.MAX_ANALYSIS_TIME
            )
            
            # Cache successful result
            if use_cache and cache_key:
                self.analysis_cache[cache_key] = result
                
                # Limit cache size
                if len(self.analysis_cache) > 100:
                    # Remove oldest entries
                    oldest_keys = list(self.analysis_cache.keys())[:20]
                    for key in oldest_keys:
                        del self.analysis_cache[key]
            
            # Record success
            self._record_success()
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Context analysis timed out after {self.MAX_ANALYSIS_TIME}s")
            self._record_failure()
            return None
            
        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            self._record_failure()
            return None
    
    def analyze_context_sync(self, context_data: Dict[str, Any], 
                           use_cache: bool = True) -> Optional[ContextAnalysisResult]:
        """Synchronous wrapper for context analysis."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.analyze_context(context_data, use_cache))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Synchronous context analysis failed: {e}")
            return None
    
    def get_analysis_summary(self, result: ContextAnalysisResult) -> Dict[str, str]:
        """Get human-readable analysis summary."""
        if not result:
            return {"status": "Analysis unavailable", "summary": "Context analysis failed"}
        
        summary = {
            "health_status": result.get_health_status(),
            "size_category": result.get_size_category(),
            "focus_summary": f"Focus Score: {result.focus_metrics.focus_score}%, "
                           f"Priority Alignment: {result.focus_metrics.priority_alignment_score}%",
            "redundancy_summary": f"Duplicate Content: {result.redundancy_report.duplicate_content_percentage}%, "
                                f"Stale Context: {result.recency_report.stale_context_percentage}%",
            "optimization_summary": f"Optimization Potential: {result.optimization_potential*100:.0f}%, "
                                  f"Could save ~{result.cleanup_impact_estimate:,} tokens"
        }
        
        return summary


# Convenience functions for easy usage
async def analyze_context(context_data: Dict[str, Any]) -> Optional[ContextAnalysisResult]:
    """Convenience function for context analysis."""
    analyzer = ContextAnalyzer()
    return await analyzer.analyze_context(context_data)


def analyze_context_sync(context_data: Dict[str, Any]) -> Optional[ContextAnalysisResult]:
    """Synchronous convenience function for context analysis."""
    analyzer = ContextAnalyzer()
    return analyzer.analyze_context_sync(context_data)


if __name__ == "__main__":
    # Test with sample data
    test_data = {
        'session_id': 'test-session-123',
        'messages': [
            'User: Help me debug this function',
            'Assistant: I can help you debug that function',
            'User: The same function is still not working',
            'Assistant: Let me look at the same function again'  # Duplicate content
        ],
        'files': [
            '/project/src/main.py',
            '/project/src/utils.py', 
            '/project/src/main.py',  # Duplicate file
            '/project/tests/test_main.py'
        ],
        'todos': [
            'Fix the authentication bug',  # Active
            'Write unit tests',  # Active
            'Update documentation',  # Active
            'Deploy to staging - COMPLETED',  # Obsolete
        ],
        'timestamp': datetime.now().isoformat(),
        'last_modified': (datetime.now() - timedelta(minutes=30)).isoformat()
    }
    
    print("Testing Context Analysis Engine...")
    
    result = analyze_context_sync(test_data)
    if result:
        print(f"\n✅ Analysis completed successfully!")
        print(f"Health Score: {result.health_score}/100 ({result.get_health_status()})")
        print(f"Size Category: {result.get_size_category()}")
        print(f"Total Tokens: {result.total_tokens:,}")
        print(f"Focus Score: {result.focus_metrics.focus_score}%")
        print(f"Duplicate Content: {result.redundancy_report.duplicate_content_percentage}%")
        print(f"Optimization Potential: {result.optimization_potential*100:.0f}%")
        print(f"Analysis Duration: {result.analysis_duration:.3f}s")
    else:
        print("❌ Analysis failed!")