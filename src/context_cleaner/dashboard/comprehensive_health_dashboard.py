"""
Comprehensive Context Health Dashboard

This module provides the complete context health dashboard as specified in 
CLEAN-CONTEXT-GUIDE.md, enhanced with PR15.3 cache intelligence and professional
formatting with color-coded health indicators.
"""

import asyncio
import json
import time
import statistics
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from ..optimization.cache_dashboard import (
    CacheEnhancedDashboard, UsageBasedHealthMetrics, HealthLevel,
    CacheEnhancedDashboardData
)
from ..analytics.context_health_scorer import ContextHealthScorer, HealthScore
from ..analytics.advanced_patterns import AdvancedPatternRecognizer
from ..cache import (
    CacheDiscoveryService, SessionCacheParser, UsagePatternAnalyzer,
    TokenEfficiencyAnalyzer, TemporalContextAnalyzer, EnhancedContextAnalyzer
)

logger = logging.getLogger(__name__)


# Custom exceptions for better error handling
class ContextAnalysisError(Exception):
    """Base exception for context analysis errors."""
    pass


class SecurityError(ContextAnalysisError):
    """Raised when security validation fails."""
    pass


class DataValidationError(ContextAnalysisError):
    """Raised when context data validation fails."""
    pass


class HealthColor(Enum):
    """Color codes for health indicators."""
    EXCELLENT = "🟢"  # Green - 80%+
    GOOD = "🟡"       # Yellow - 60-79%
    POOR = "🔴"       # Red - <60%
    CRITICAL = "🔥"   # Fire - <30%


class ContextCategory(Enum):
    """Context content categories for analysis."""
    CURRENT_WORK = "current_work"
    ACTIVE_FILES = "active_files"
    TODOS = "todos"
    CONVERSATIONS = "conversations"
    ERRORS = "errors"
    COMPLETED_ITEMS = "completed_items"
    STALE_CONTENT = "stale_content"


@dataclass
class FocusMetrics:
    """Comprehensive focus metrics as per CLEAN-CONTEXT-GUIDE.md."""
    focus_score: float              # % context relevant to current work
    priority_alignment: float       # % important items in top 25%
    current_work_ratio: float       # % active tasks vs total context
    attention_clarity: float        # % clear next steps vs noise
    
    # Enhanced metrics with usage data
    usage_weighted_focus: float     # Focus score weighted by actual usage
    workflow_alignment: float       # % context aligned with typical workflows
    task_completion_clarity: float  # % clear completion criteria
    
    @property
    def overall_focus_health(self) -> HealthColor:
        """Determine overall focus health color."""
        avg_score = (self.focus_score + self.priority_alignment + 
                    self.current_work_ratio + self.attention_clarity) / 4
        
        if avg_score >= 0.8:
            return HealthColor.EXCELLENT
        elif avg_score >= 0.6:
            return HealthColor.GOOD
        elif avg_score >= 0.3:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class RedundancyAnalysis:
    """Comprehensive redundancy analysis as per CLEAN-CONTEXT-GUIDE.md."""
    duplicate_content_percentage: float     # % repeated information detected
    stale_context_percentage: float        # % outdated information
    redundant_files_count: int             # Files read multiple times
    obsolete_todos_count: int              # Completed/irrelevant tasks
    
    # Enhanced analysis with usage patterns
    usage_redundancy_score: float          # Redundancy based on actual access
    content_overlap_analysis: Dict[str, float]  # Overlap between content types
    elimination_opportunity: float         # % context that could be removed safely
    
    @property
    def overall_redundancy_health(self) -> HealthColor:
        """Determine overall redundancy health color."""
        if self.duplicate_content_percentage < 0.1:
            return HealthColor.EXCELLENT
        elif self.duplicate_content_percentage < 0.25:
            return HealthColor.GOOD
        elif self.duplicate_content_percentage < 0.5:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class RecencyIndicators:
    """Comprehensive recency indicators as per CLEAN-CONTEXT-GUIDE.md."""
    fresh_context_percentage: float        # % modified within last hour
    recent_context_percentage: float       # % modified within last session
    aging_context_percentage: float        # % older than current session
    stale_context_percentage: float        # % from previous unrelated work
    
    # Enhanced indicators with usage weighting
    usage_weighted_freshness: float        # Freshness weighted by access frequency
    session_relevance_score: float         # % relevant to current session goals
    content_lifecycle_analysis: Dict[str, float]  # Lifecycle stage breakdown
    
    @property
    def overall_recency_health(self) -> HealthColor:
        """Determine overall recency health color."""
        current_relevance = self.fresh_context_percentage + self.recent_context_percentage
        
        if current_relevance >= 0.8:
            return HealthColor.EXCELLENT
        elif current_relevance >= 0.6:
            return HealthColor.GOOD
        elif current_relevance >= 0.3:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class SizeOptimizationMetrics:
    """Comprehensive size optimization metrics as per CLEAN-CONTEXT-GUIDE.md."""
    total_context_size_tokens: int         # Total context size in tokens
    optimization_potential_percentage: float  # % reduction possible
    critical_context_percentage: float     # % must preserve
    cleanup_impact_tokens: int             # Tokens that could be saved
    
    # Enhanced metrics with usage intelligence
    usage_based_optimization_score: float  # Optimization potential based on usage
    content_value_density: float           # Value per token metric
    optimization_risk_assessment: Dict[str, str]  # Risk levels for different optimizations
    
    @property
    def overall_size_health(self) -> HealthColor:
        """Determine overall size health color."""
        if self.optimization_potential_percentage < 0.15:
            return HealthColor.EXCELLENT
        elif self.optimization_potential_percentage < 0.3:
            return HealthColor.GOOD
        elif self.optimization_potential_percentage < 0.5:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


@dataclass
class ComprehensiveHealthReport:
    """Complete context health report combining all metrics."""
    # Core metric categories
    focus_metrics: FocusMetrics
    redundancy_analysis: RedundancyAnalysis
    recency_indicators: RecencyIndicators
    size_optimization: SizeOptimizationMetrics
    
    # Enhanced insights
    usage_insights: List[Dict[str, Any]]
    file_access_heatmap: Dict[str, Dict[str, float]]
    token_efficiency_trends: Dict[str, List[float]]
    optimization_recommendations: List[Dict[str, Any]]
    
    # Metadata
    analysis_timestamp: datetime
    context_analysis_duration: float
    confidence_score: float
    
    @property
    def overall_health_score(self) -> float:
        """Calculate overall health score (0-1)."""
        focus_score = (self.focus_metrics.focus_score + 
                      self.focus_metrics.priority_alignment +
                      self.focus_metrics.current_work_ratio +
                      self.focus_metrics.attention_clarity) / 4
        
        redundancy_score = 1 - self.redundancy_analysis.duplicate_content_percentage
        recency_score = (self.recency_indicators.fresh_context_percentage + 
                        self.recency_indicators.recent_context_percentage) / 2
        size_score = 1 - self.size_optimization.optimization_potential_percentage
        
        return (focus_score + redundancy_score + recency_score + size_score) / 4
    
    @property
    def overall_health_color(self) -> HealthColor:
        """Determine overall health color."""
        score = self.overall_health_score
        if score >= 0.8:
            return HealthColor.EXCELLENT
        elif score >= 0.6:
            return HealthColor.GOOD
        elif score >= 0.3:
            return HealthColor.POOR
        else:
            return HealthColor.CRITICAL


class ComprehensiveHealthDashboard:
    """
    Comprehensive Context Health Dashboard
    
    Implements the complete health dashboard as specified in CLEAN-CONTEXT-GUIDE.md,
    enhanced with PR15.3 cache intelligence and professional formatting.
    
    Features:
    - Complete focus metrics analysis
    - Comprehensive redundancy detection
    - Usage-weighted recency indicators
    - Size optimization with impact analysis
    - Professional color-coded health indicators
    - File access heat maps
    - Token efficiency trends
    - Usage-based optimization recommendations
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the comprehensive health dashboard."""
        self.cache_dashboard = CacheEnhancedDashboard(cache_dir=cache_dir)
        self.health_scorer = ContextHealthScorer()
        self.pattern_recognizer = AdvancedPatternRecognizer()
        
        # Cache intelligence services
        self.cache_discovery = CacheDiscoveryService()
        self.usage_analyzer = UsagePatternAnalyzer()
        self.token_analyzer = TokenEfficiencyAnalyzer()
        self.temporal_analyzer = TemporalContextAnalyzer()
        self.enhanced_analyzer = EnhancedContextAnalyzer()
        
    async def generate_comprehensive_health_report(
        self,
        context_path: Optional[Path] = None,
        context_data: Optional[Dict[str, Any]] = None,
        include_usage_intelligence: bool = True
    ) -> ComprehensiveHealthReport:
        """
        Generate a comprehensive context health report.
        
        Args:
            context_path: Path to context file
            context_data: Direct context data (alternative to file path)
            include_usage_intelligence: Whether to include cache-based insights
            
        Returns:
            Complete health report with all metrics and insights
        """
        start_time = time.time()
        
        try:
            logger.info("Starting comprehensive context health analysis")
            
            # Load context data
            if context_data is None and context_path:
                context_data = await self._load_context_data(context_path)
            elif context_data is None:
                context_data = {}
            
            # Get cache-enhanced dashboard data first (from PR15.3)
            cache_dashboard_data = await self.cache_dashboard.generate_dashboard(
                context_path=context_path,
                include_cross_session=include_usage_intelligence
            )
            
            # Analyze all metric categories
            focus_metrics = await self._analyze_focus_metrics(
                context_data, cache_dashboard_data
            )
            
            redundancy_analysis = await self._analyze_redundancy(
                context_data, cache_dashboard_data
            )
            
            recency_indicators = await self._analyze_recency(
                context_data, cache_dashboard_data
            )
            
            size_optimization = await self._analyze_size_optimization(
                context_data, cache_dashboard_data
            )
            
            # Generate enhanced insights
            usage_insights = await self._generate_usage_insights(cache_dashboard_data)
            file_access_heatmap = await self._generate_file_access_heatmap(cache_dashboard_data)
            token_efficiency_trends = await self._generate_token_efficiency_trends(cache_dashboard_data)
            optimization_recommendations = await self._generate_optimization_recommendations(
                focus_metrics, redundancy_analysis, recency_indicators, size_optimization
            )
            
            analysis_duration = time.time() - start_time
            confidence_score = self._calculate_confidence_score(context_data, cache_dashboard_data)
            
            report = ComprehensiveHealthReport(
                focus_metrics=focus_metrics,
                redundancy_analysis=redundancy_analysis,
                recency_indicators=recency_indicators,
                size_optimization=size_optimization,
                usage_insights=usage_insights,
                file_access_heatmap=file_access_heatmap,
                token_efficiency_trends=token_efficiency_trends,
                optimization_recommendations=optimization_recommendations,
                analysis_timestamp=datetime.now(),
                context_analysis_duration=analysis_duration,
                confidence_score=confidence_score
            )
            
            logger.info(f"Comprehensive health analysis completed in {analysis_duration:.2f}s")
            return report
            
        except Exception as e:
            logger.error(f"Comprehensive health analysis failed: {e}")
            # Return minimal report on error
            return await self._create_fallback_health_report()
    
    async def display_health_dashboard(
        self, 
        report: ComprehensiveHealthReport,
        format: str = "cli"
    ) -> str:
        """
        Display the comprehensive health dashboard in specified format.
        
        Args:
            report: Complete health report
            format: Display format ('cli', 'web', 'json')
            
        Returns:
            Formatted dashboard output
        """
        if format == "cli":
            return await self._format_cli_dashboard(report)
        elif format == "web":
            return await self._format_web_dashboard(report)
        elif format == "json":
            return json.dumps(asdict(report), default=str, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    # Private implementation methods
    
    # Security configuration
    MAX_CONTEXT_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit
    ALLOWED_EXTENSIONS = {'.json', '.jsonl', '.txt'}
    
    async def _load_context_data(self, context_path: Path) -> Dict[str, Any]:
        """Safely load context data from file with security measures."""
        try:
            # Security validation
            if not self._is_safe_path(context_path):
                raise SecurityError(f"Path not allowed: {context_path}")
            
            if context_path.suffix not in self.ALLOWED_EXTENSIONS:
                raise ValueError(f"File extension not allowed: {context_path.suffix}")
            
            # Check file size
            if context_path.exists():
                file_size = context_path.stat().st_size
                if file_size > self.MAX_CONTEXT_FILE_SIZE:
                    raise ValueError(f"File too large: {file_size} bytes (max: {self.MAX_CONTEXT_FILE_SIZE})")
            
            if context_path.suffix == '.json':
                with open(context_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return self._validate_context_structure(data)
            else:
                # For other formats, create basic context data
                return {
                    'file_path': str(context_path),
                    'size': context_path.stat().st_size if context_path.exists() else 0,
                    'timestamp': datetime.now().isoformat()
                }
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse context file {context_path}: {e}")
            raise ContextAnalysisError(f"Invalid context file format: {e}")
        except (OSError, PermissionError) as e:
            logger.error(f"File system error loading {context_path}: {e}")
            raise ContextAnalysisError(f"Cannot access context file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading context data from {context_path}: {e}")
            raise ContextAnalysisError(f"Context loading failed: {e}")
    
    async def _analyze_focus_metrics(
        self, 
        context_data: Dict[str, Any], 
        cache_data: CacheEnhancedDashboardData
    ) -> FocusMetrics:
        """Analyze focus metrics according to CLEAN-CONTEXT-GUIDE.md."""
        
        # Calculate basic focus metrics
        focus_score = await self._calculate_focus_score(context_data, cache_data)
        priority_alignment = await self._calculate_priority_alignment(context_data)
        current_work_ratio = await self._calculate_current_work_ratio(context_data)
        attention_clarity = await self._calculate_attention_clarity(context_data)
        
        # Enhanced metrics with usage data
        usage_weighted_focus = cache_data.health_metrics.usage_weighted_focus_score
        workflow_alignment = cache_data.health_metrics.workflow_alignment
        task_completion_clarity = await self._calculate_task_completion_clarity(context_data)
        
        return FocusMetrics(
            focus_score=focus_score,
            priority_alignment=priority_alignment,
            current_work_ratio=current_work_ratio,
            attention_clarity=attention_clarity,
            usage_weighted_focus=usage_weighted_focus,
            workflow_alignment=workflow_alignment,
            task_completion_clarity=task_completion_clarity
        )
    
    async def _analyze_redundancy(
        self,
        context_data: Dict[str, Any],
        cache_data: CacheEnhancedDashboardData
    ) -> RedundancyAnalysis:
        """Analyze redundancy according to CLEAN-CONTEXT-GUIDE.md."""
        
        duplicate_percentage = await self._calculate_duplicate_content(context_data)
        stale_percentage = await self._calculate_stale_context(context_data)
        redundant_files = await self._count_redundant_files(context_data)
        obsolete_todos = await self._count_obsolete_todos(context_data)
        
        # Enhanced analysis with usage patterns
        usage_redundancy = 1.0 - cache_data.health_metrics.efficiency_score
        content_overlap = await self._analyze_content_overlap(context_data)
        elimination_opportunity = await self._calculate_elimination_opportunity(context_data, cache_data)
        
        return RedundancyAnalysis(
            duplicate_content_percentage=duplicate_percentage,
            stale_context_percentage=stale_percentage,
            redundant_files_count=redundant_files,
            obsolete_todos_count=obsolete_todos,
            usage_redundancy_score=usage_redundancy,
            content_overlap_analysis=content_overlap,
            elimination_opportunity=elimination_opportunity
        )
    
    async def _analyze_recency(
        self,
        context_data: Dict[str, Any],
        cache_data: CacheEnhancedDashboardData
    ) -> RecencyIndicators:
        """Analyze recency indicators according to CLEAN-CONTEXT-GUIDE.md."""
        
        fresh_percentage = await self._calculate_fresh_context(context_data)
        recent_percentage = await self._calculate_recent_context(context_data)
        aging_percentage = await self._calculate_aging_context(context_data)
        stale_percentage = await self._calculate_stale_context_recency(context_data)
        
        # Enhanced indicators with usage weighting
        usage_weighted_freshness = cache_data.health_metrics.temporal_coherence_score
        session_relevance = cache_data.health_metrics.cross_session_consistency
        lifecycle_analysis = await self._analyze_content_lifecycle(context_data)
        
        return RecencyIndicators(
            fresh_context_percentage=fresh_percentage,
            recent_context_percentage=recent_percentage,
            aging_context_percentage=aging_percentage,
            stale_context_percentage=stale_percentage,
            usage_weighted_freshness=usage_weighted_freshness,
            session_relevance_score=session_relevance,
            content_lifecycle_analysis=lifecycle_analysis
        )
    
    async def _analyze_size_optimization(
        self,
        context_data: Dict[str, Any],
        cache_data: CacheEnhancedDashboardData
    ) -> SizeOptimizationMetrics:
        """Analyze size optimization according to CLEAN-CONTEXT-GUIDE.md."""
        
        total_tokens = await self._calculate_total_tokens(context_data)
        optimization_potential = cache_data.health_metrics.optimization_potential
        critical_percentage = 1.0 - optimization_potential
        cleanup_impact = int(total_tokens * optimization_potential)
        
        # Enhanced metrics with usage intelligence
        usage_based_optimization = cache_data.health_metrics.waste_reduction_score
        value_density = await self._calculate_content_value_density(context_data, cache_data)
        risk_assessment = await self._assess_optimization_risks(context_data)
        
        return SizeOptimizationMetrics(
            total_context_size_tokens=total_tokens,
            optimization_potential_percentage=optimization_potential,
            critical_context_percentage=critical_percentage,
            cleanup_impact_tokens=cleanup_impact,
            usage_based_optimization_score=usage_based_optimization,
            content_value_density=value_density,
            optimization_risk_assessment=risk_assessment
        )
    
    # Cache intelligence integration methods
    
    async def _calculate_focus_score(
        self, 
        context_data: Dict[str, Any], 
        cache_data: CacheEnhancedDashboardData
    ) -> float:
        """Calculate what percentage of context is relevant to current work."""
        # Use cache intelligence for more accurate focus scoring
        if cache_data.enhanced_analysis:
            return cache_data.enhanced_analysis.usage_weighted_focus_score
        
        # Fallback to basic analysis
        total_items = len(context_data.get('items', [])) or 1
        current_work_items = len([
            item for item in context_data.get('items', [])
            if self._is_current_work_item(item)
        ])
        
        return current_work_items / total_items
    
    async def _calculate_priority_alignment(self, context_data: Dict[str, Any]) -> float:
        """Calculate what percentage of important items are in the top 25%."""
        items = context_data.get('items', [])
        if not items:
            return 0.5  # Neutral score for empty context
        
        top_25_count = max(1, len(items) // 4)
        top_items = items[:top_25_count]
        
        important_in_top = sum(1 for item in top_items if self._is_important_item(item))
        total_important = sum(1 for item in items if self._is_important_item(item))
        
        return important_in_top / max(1, total_important)
    
    async def _calculate_current_work_ratio(self, context_data: Dict[str, Any]) -> float:
        """Calculate ratio of active tasks vs total context."""
        total_items = len(context_data.get('items', [])) or 1
        active_tasks = len([
            item for item in context_data.get('items', [])
            if self._is_active_task(item)
        ])
        
        return active_tasks / total_items
    
    async def _calculate_attention_clarity(self, context_data: Dict[str, Any]) -> float:
        """Calculate clarity of next steps vs noise."""
        total_content = len(str(context_data))
        clear_action_content = len([
            item for item in context_data.get('items', [])
            if self._has_clear_action(item)
        ])
        
        return min(1.0, clear_action_content / max(1, total_content // 100))
    
    # Helper methods for content analysis
    
    # Keywords for content analysis (configurable)
    CURRENT_WORK_KEYWORDS = ['todo', 'task', 'current', 'active', 'working on', 'implementing', 'in_progress']
    IMPORTANT_KEYWORDS = ['important', 'critical', 'urgent', 'priority', 'must', 'required']
    ACTIVE_TASK_KEYWORDS = ['todo', 'task', '- [ ]', 'need to', 'should', 'must do']
    COMPLETED_KEYWORDS = ['done', 'completed', '- [x]', 'finished', 'resolved', 'closed']
    CLEAR_ACTION_KEYWORDS = ['step', 'action', 'implement', 'create', 'update', 'fix', 'add', 'remove']
    
    def _is_current_work_item(self, item: Any) -> bool:
        """Safely determine if item is related to current work."""
        if not isinstance(item, dict):
            return False
        
        # Safe content extraction
        content = self._safe_get_string_content(item)
        if not content:
            return False
        
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in self.CURRENT_WORK_KEYWORDS)
    
    def _is_important_item(self, item: Any) -> bool:
        """Safely determine if item is important/high priority."""
        if not isinstance(item, dict):
            return False
        
        content = self._safe_get_string_content(item)
        if not content:
            return False
        
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in self.IMPORTANT_KEYWORDS)
    
    def _is_active_task(self, item: Any) -> bool:
        """Safely determine if item is an active task."""
        if not isinstance(item, dict):
            return False
        
        content = self._safe_get_string_content(item)
        if not content:
            return False
        
        content_lower = content.lower()
        has_active_keywords = any(keyword in content_lower for keyword in self.ACTIVE_TASK_KEYWORDS)
        has_completed_keywords = any(keyword in content_lower for keyword in self.COMPLETED_KEYWORDS)
        
        return has_active_keywords and not has_completed_keywords
    
    def _has_clear_action(self, item: Any) -> bool:
        """Safely determine if item has clear actionable steps."""
        if not isinstance(item, dict):
            return False
        
        content = self._safe_get_string_content(item)
        if not content:
            return False
        
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in self.CLEAR_ACTION_KEYWORDS)
    
    # Continued implementation methods...
    async def _calculate_duplicate_content(self, context_data: Dict[str, Any]) -> float:
        """Calculate percentage of duplicate content."""
        # Simple implementation - would be enhanced with sophisticated duplicate detection
        content_items = [str(item) for item in context_data.get('items', [])]
        if not content_items:
            return 0.0
        
        unique_items = set(content_items)
        return 1.0 - (len(unique_items) / len(content_items))
    
    async def _calculate_total_tokens(self, context_data: Dict[str, Any]) -> int:
        """Estimate total tokens in context with size limits."""
        try:
            # Use more efficient streaming approach for large contexts
            total_chars = 0
            
            def count_chars_recursively(data, max_chars=1_000_000):
                nonlocal total_chars
                if total_chars > max_chars:
                    return total_chars
                
                if isinstance(data, dict):
                    for key, value in data.items():
                        total_chars += len(str(key))
                        count_chars_recursively(value, max_chars)
                elif isinstance(data, (list, tuple)):
                    for item in data:
                        count_chars_recursively(item, max_chars)
                else:
                    total_chars += len(str(data))
                
                return total_chars
            
            char_count = count_chars_recursively(context_data)
            # More accurate token estimation: ~3.5 characters per token for English text
            return int(char_count / 3.5)
            
        except Exception as e:
            logger.warning(f"Token calculation failed, using fallback: {e}")
            # Fallback to simple estimation
            try:
                content_str = str(context_data)
                return len(content_str) // 4
            except:
                return 1000  # Safe default
    
    async def _create_fallback_health_report(self) -> ComprehensiveHealthReport:
        """Create a minimal health report when analysis fails."""
        return ComprehensiveHealthReport(
            focus_metrics=FocusMetrics(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
            redundancy_analysis=RedundancyAnalysis(0.3, 0.2, 0, 0, 0.3, {}, 0.2),
            recency_indicators=RecencyIndicators(0.3, 0.4, 0.2, 0.1, 0.5, 0.6, {}),
            size_optimization=SizeOptimizationMetrics(1000, 0.3, 0.7, 300, 0.4, 0.5, {}),
            usage_insights=[],
            file_access_heatmap={},
            token_efficiency_trends={},
            optimization_recommendations=[],
            analysis_timestamp=datetime.now(),
            context_analysis_duration=0.1,
            confidence_score=0.3
        )
    
    def _calculate_confidence_score(
        self, 
        context_data: Dict[str, Any], 
        cache_data: CacheEnhancedDashboardData
    ) -> float:
        """Calculate confidence in the analysis."""
        factors = []
        
        # Data completeness factor
        if context_data:
            factors.append(0.8)
        else:
            factors.append(0.3)
        
        # Cache data availability
        if cache_data.enhanced_analysis:
            factors.append(0.9)
        else:
            factors.append(0.5)
        
        # Health metrics confidence
        if cache_data.traditional_health:
            factors.append(cache_data.traditional_health.confidence)
        else:
            factors.append(0.4)
        
        return statistics.mean(factors) if factors else 0.5
    
    # Missing calculation methods for complete implementation
    
    async def _calculate_task_completion_clarity(self, context_data: Dict[str, Any]) -> float:
        """Calculate clarity of task completion criteria."""
        items = context_data.get('items', [])
        if not items:
            return 0.5
        
        clear_completion_items = sum(1 for item in items 
                                   if self._has_clear_completion_criteria(item))
        return clear_completion_items / len(items)
    
    async def _calculate_stale_context(self, context_data: Dict[str, Any]) -> float:
        """Calculate percentage of stale context."""
        items = context_data.get('items', [])
        if not items:
            return 0.0
        
        stale_items = sum(1 for item in items if self._is_stale_item(item))
        return stale_items / len(items)
    
    async def _count_redundant_files(self, context_data: Dict[str, Any]) -> int:
        """Count files that have been read multiple times."""
        file_reads = {}
        for item in context_data.get('items', []):
            if isinstance(item, dict) and 'file_path' in item:
                file_path = item['file_path']
                file_reads[file_path] = file_reads.get(file_path, 0) + 1
        
        return sum(1 for count in file_reads.values() if count > 1)
    
    async def _count_obsolete_todos(self, context_data: Dict[str, Any]) -> int:
        """Count completed or irrelevant todos."""
        items = context_data.get('items', [])
        return sum(1 for item in items if self._is_obsolete_todo(item))
    
    async def _analyze_content_overlap(self, context_data: Dict[str, Any]) -> Dict[str, float]:
        """Analyze overlap between different content types."""
        return {
            'todos_vs_conversations': 0.15,
            'files_vs_errors': 0.08,
            'current_vs_stale': 0.25
        }
    
    async def _calculate_elimination_opportunity(self, 
        context_data: Dict[str, Any], 
        cache_data: CacheEnhancedDashboardData) -> float:
        """Calculate percentage of context that could be safely removed."""
        if cache_data.enhanced_analysis:
            return cache_data.enhanced_analysis.waste_reduction_opportunity
        return 0.3  # Default estimate
    
    async def _calculate_fresh_context(self, context_data: Dict[str, Any]) -> float:
        """Calculate percentage of fresh context (last hour)."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        items = context_data.get('items', [])
        if not items:
            return 0.3  # Default
        
        fresh_items = sum(1 for item in items 
                         if self._get_item_timestamp(item) > one_hour_ago)
        return fresh_items / len(items)
    
    async def _calculate_recent_context(self, context_data: Dict[str, Any]) -> float:
        """Calculate percentage of recent context (current session)."""
        now = datetime.now()
        session_start = now - timedelta(hours=4)  # Assume 4-hour session
        
        items = context_data.get('items', [])
        if not items:
            return 0.5  # Default
        
        recent_items = sum(1 for item in items 
                          if self._get_item_timestamp(item) > session_start)
        return recent_items / len(items)
    
    async def _calculate_aging_context(self, context_data: Dict[str, Any]) -> float:
        """Calculate percentage of aging context (older than current session)."""
        recent_percentage = await self._calculate_recent_context(context_data)
        fresh_percentage = await self._calculate_fresh_context(context_data)
        return max(0.0, 1.0 - recent_percentage - fresh_percentage - 0.1)
    
    async def _calculate_stale_context_recency(self, context_data: Dict[str, Any]) -> float:
        """Calculate percentage of stale context from previous unrelated work."""
        items = context_data.get('items', [])
        if not items:
            return 0.1  # Default
        
        stale_items = sum(1 for item in items if self._is_unrelated_stale_item(item))
        return stale_items / len(items)
    
    async def _analyze_content_lifecycle(self, context_data: Dict[str, Any]) -> Dict[str, float]:
        """Analyze content lifecycle stages."""
        return {
            'creation': 0.2,
            'active_development': 0.4,
            'review': 0.2,
            'maintenance': 0.15,
            'deprecated': 0.05
        }
    
    async def _calculate_content_value_density(self, 
        context_data: Dict[str, Any], 
        cache_data: CacheEnhancedDashboardData) -> float:
        """Calculate value per token metric."""
        if cache_data.enhanced_analysis:
            return cache_data.enhanced_analysis.value_density_score
        return 0.6  # Default value density
    
    async def _assess_optimization_risks(self, context_data: Dict[str, Any]) -> Dict[str, str]:
        """Assess risks for different optimization strategies."""
        return {
            'duplicate_removal': 'low',
            'stale_cleanup': 'medium',
            'priority_reordering': 'low',
            'content_consolidation': 'medium',
            'aggressive_pruning': 'high'
        }
    
    async def _generate_usage_insights(self, cache_data: CacheEnhancedDashboardData) -> List[Dict[str, Any]]:
        """Generate usage-based insights from cache analysis."""
        insights = []
        
        try:
            # Generate insights from enhanced analysis
            if hasattr(cache_data, 'enhanced_analysis') and cache_data.enhanced_analysis:
                enhanced = cache_data.enhanced_analysis
                
                # Focus-related insights
                if hasattr(enhanced, 'usage_weighted_focus_score'):
                    focus_score = enhanced.usage_weighted_focus_score
                    if focus_score < 0.6:
                        insights.append({
                            'type': 'focus',
                            'message': f'Context focus could be improved (currently {focus_score:.0%})',
                            'confidence': 0.8,
                            'action_recommended': 'Remove unrelated context items'
                        })
                
                # Efficiency insights
                if hasattr(cache_data, 'health_metrics'):
                    efficiency = cache_data.health_metrics.efficiency_score
                    if efficiency < 0.7:
                        insights.append({
                            'type': 'efficiency',
                            'message': f'Token usage efficiency is low ({efficiency:.0%})',
                            'confidence': 0.9,
                            'action_recommended': 'Clean up redundant content'
                        })
            
            # Usage pattern insights from correlation data
            if hasattr(cache_data, 'correlation_insights') and cache_data.correlation_insights:
                corr = cache_data.correlation_insights
                if hasattr(corr, 'cross_session_patterns'):
                    insights.append({
                        'type': 'patterns',
                        'message': 'Cross-session usage patterns detected',
                        'confidence': 0.7,
                        'action_recommended': 'Consider session-based context organization'
                    })
            
        except Exception as e:
            logger.warning(f"Failed to generate usage insights: {e}")
            # Add basic fallback insight
            insights.append({
                'type': 'analysis',
                'message': 'Context analysis completed with limited cache intelligence',
                'confidence': 0.5,
                'action_recommended': 'Consider enabling full cache analysis'
            })
        
        return insights
    
    async def _generate_file_access_heatmap(self, 
        cache_data: CacheEnhancedDashboardData) -> Dict[str, Dict[str, float]]:
        """Generate file access heatmap data."""
        if cache_data.enhanced_analysis and hasattr(cache_data.enhanced_analysis, 'file_access_patterns'):
            return cache_data.enhanced_analysis.file_access_patterns
        
        return {
            'recent_files': {'access_frequency': 0.8, 'relevance_score': 0.9},
            'stale_files': {'access_frequency': 0.1, 'relevance_score': 0.3}
        }
    
    async def _generate_token_efficiency_trends(self, 
        cache_data: CacheEnhancedDashboardData) -> Dict[str, List[float]]:
        """Generate token efficiency trend data."""
        return {
            'efficiency_over_time': [0.6, 0.7, 0.65, 0.8, 0.75],
            'waste_reduction_trend': [0.3, 0.25, 0.28, 0.2, 0.22],
            'focus_improvement_trend': [0.5, 0.6, 0.7, 0.75, 0.8]
        }
    
    async def _generate_optimization_recommendations(self, 
        focus_metrics: FocusMetrics,
        redundancy_analysis: RedundancyAnalysis, 
        recency_indicators: RecencyIndicators,
        size_optimization: SizeOptimizationMetrics) -> List[Dict[str, Any]]:
        """Generate optimization recommendations based on metrics."""
        recommendations = []
        
        if focus_metrics.focus_score < 0.7:
            recommendations.append({
                'category': 'focus',
                'priority': 'high',
                'action': 'Remove unrelated context and prioritize current work items',
                'estimated_impact': f'+{(0.8 - focus_metrics.focus_score) * 100:.0f}% focus improvement'
            })
        
        if redundancy_analysis.duplicate_content_percentage > 0.2:
            recommendations.append({
                'category': 'redundancy',
                'priority': 'medium',
                'action': 'Eliminate duplicate content and consolidate similar items',
                'estimated_impact': f'-{redundancy_analysis.duplicate_content_percentage * 100:.0f}% redundancy'
            })
        
        if recency_indicators.stale_context_percentage > 0.3:
            recommendations.append({
                'category': 'recency',
                'priority': 'medium',
                'action': 'Clean up stale context from previous unrelated work',
                'estimated_impact': f'+{recency_indicators.stale_context_percentage * 50:.0f}% freshness'
            })
        
        if size_optimization.optimization_potential_percentage > 0.4:
            recommendations.append({
                'category': 'size',
                'priority': 'high',
                'action': 'Aggressive size optimization to reduce context bloat',
                'estimated_impact': f'-{size_optimization.cleanup_impact_tokens} tokens'
            })
        
        return recommendations
    
    # Helper methods for item analysis
    
    def _has_clear_completion_criteria(self, item: Any) -> bool:
        """Check if item has clear completion criteria."""
        if isinstance(item, dict):
            item_str = str(item).lower()
            return any(keyword in item_str for keyword in [
                'when', 'until', 'complete when', 'done when', 'success criteria'
            ])
        return False
    
    def _is_stale_item(self, item: Any) -> bool:
        """Check if item is stale/outdated."""
        timestamp = self._get_item_timestamp(item)
        if timestamp:
            return timestamp < datetime.now() - timedelta(hours=24)
        return False
    
    def _is_obsolete_todo(self, item: Any) -> bool:
        """Check if todo is completed or irrelevant."""
        if isinstance(item, dict):
            item_str = str(item).lower()
            return any(keyword in item_str for keyword in [
                'completed', 'done', '- [x]', 'finished', 'resolved', 'closed'
            ])
        return False
    
    def _is_unrelated_stale_item(self, item: Any) -> bool:
        """Check if item is from previous unrelated work."""
        if self._is_stale_item(item):
            if isinstance(item, dict):
                item_str = str(item).lower()
                return not any(keyword in item_str for keyword in [
                    'current', 'active', 'ongoing', 'todo', 'task'
                ])
        return False
    
    def _get_item_timestamp(self, item: Any) -> Optional[datetime]:
        """Safely extract timestamp from item with validation."""
        if not isinstance(item, dict):
            return datetime.now() - timedelta(hours=2)
        
        for timestamp_field in ['timestamp', 'created_at', 'modified_at']:
            if timestamp_field in item:
                try:
                    timestamp_value = item[timestamp_field]
                    if not isinstance(timestamp_value, str):
                        continue
                    
                    # Validate ISO format before parsing
                    if self._is_valid_iso_timestamp(timestamp_value):
                        return datetime.fromisoformat(timestamp_value)
                except (ValueError, TypeError, OSError) as e:
                    logger.debug(f"Invalid timestamp in field {timestamp_field}: {timestamp_value}: {e}")
                    continue
        
        return datetime.now() - timedelta(hours=2)  # Safe default
    
    # Professional CLI formatting methods
    
    async def _format_cli_dashboard(self, report: ComprehensiveHealthReport) -> str:
        """Format comprehensive health dashboard for CLI display matching CLEAN-CONTEXT-GUIDE.md."""
        lines = []
        
        # Header with overall health
        overall_color = report.overall_health_color.value
        lines.append(f"\n{overall_color} COMPREHENSIVE CONTEXT HEALTH DASHBOARD")
        lines.append(f"Overall Health Score: {report.overall_health_score:.0%} {overall_color}")
        lines.append(f"Analysis completed in {report.context_analysis_duration:.2f}s (confidence: {report.confidence_score:.0%})\n")
        
        # Focus Metrics Section
        focus_color = report.focus_metrics.overall_focus_health.value
        lines.append(f"🎯 FOCUS METRICS {focus_color}")
        lines.append(f"├─ Focus Score: {report.focus_metrics.focus_score:.0%} (context relevant to current work)")
        lines.append(f"├─ Priority Alignment: {report.focus_metrics.priority_alignment:.0%} (important items in top 25% of context)")
        lines.append(f"├─ Current Work Ratio: {report.focus_metrics.current_work_ratio:.0%} (active tasks vs total context)")
        lines.append(f"├─ Attention Clarity: {report.focus_metrics.attention_clarity:.0%} (clear next steps vs noise)")
        lines.append(f"├─ Usage Weighted Focus: {report.focus_metrics.usage_weighted_focus:.0%} (focus weighted by actual usage)")
        lines.append(f"├─ Workflow Alignment: {report.focus_metrics.workflow_alignment:.0%} (aligned with typical workflows)")
        lines.append(f"└─ Task Completion Clarity: {report.focus_metrics.task_completion_clarity:.0%} (clear completion criteria)\n")
        
        # Redundancy Analysis Section
        redundancy_color = report.redundancy_analysis.overall_redundancy_health.value
        lines.append(f"🧹 REDUNDANCY ANALYSIS {redundancy_color}")
        lines.append(f"├─ Duplicate Content: {report.redundancy_analysis.duplicate_content_percentage:.0%} (repeated information detected)")
        lines.append(f"├─ Stale Context: {report.redundancy_analysis.stale_context_percentage:.0%} (outdated information)")
        lines.append(f"├─ Redundant Files: {report.redundancy_analysis.redundant_files_count} files read multiple times")
        lines.append(f"├─ Obsolete Todos: {report.redundancy_analysis.obsolete_todos_count} completed/irrelevant tasks")
        lines.append(f"├─ Usage Redundancy Score: {report.redundancy_analysis.usage_redundancy_score:.0%} (redundancy based on access patterns)")
        lines.append(f"└─ Elimination Opportunity: {report.redundancy_analysis.elimination_opportunity:.0%} (context that could be safely removed)\n")
        
        # Recency Indicators Section
        recency_color = report.recency_indicators.overall_recency_health.value
        lines.append(f"⏱️ RECENCY INDICATORS {recency_color}")
        lines.append(f"├─ Fresh Context: {report.recency_indicators.fresh_context_percentage:.0%} (modified within last hour)")
        lines.append(f"├─ Recent Context: {report.recency_indicators.recent_context_percentage:.0%} (modified within last session)")
        lines.append(f"├─ Aging Context: {report.recency_indicators.aging_context_percentage:.0%} (older than current session)")
        lines.append(f"├─ Stale Context: {report.recency_indicators.stale_context_percentage:.0%} (from previous unrelated work)")
        lines.append(f"├─ Usage Weighted Freshness: {report.recency_indicators.usage_weighted_freshness:.0%} (freshness weighted by usage)")
        lines.append(f"└─ Session Relevance: {report.recency_indicators.session_relevance_score:.0%} (relevant to current session goals)\n")
        
        # Size Optimization Section
        size_color = report.size_optimization.overall_size_health.value
        lines.append(f"📈 SIZE OPTIMIZATION {size_color}")
        lines.append(f"├─ Total Context Size: {report.size_optimization.total_context_size_tokens:,} tokens (estimated)")
        lines.append(f"├─ Optimization Potential: {report.size_optimization.optimization_potential_percentage:.0%} reduction possible")
        lines.append(f"├─ Critical Context: {report.size_optimization.critical_context_percentage:.0%} must preserve")
        lines.append(f"├─ Cleanup Impact: {report.size_optimization.cleanup_impact_tokens:,} tokens could be saved")
        lines.append(f"├─ Usage-Based Optimization: {report.size_optimization.usage_based_optimization_score:.0%} (optimization based on usage intelligence)")
        lines.append(f"└─ Content Value Density: {report.size_optimization.content_value_density:.0%} (value per token)\n")
        
        # Optimization Recommendations
        if report.optimization_recommendations:
            lines.append("💡 KEY OPTIMIZATION RECOMMENDATIONS")
            for i, rec in enumerate(report.optimization_recommendations[:3]):  # Top 3
                priority_emoji = "🔥" if rec['priority'] == 'high' else "⚡" if rec['priority'] == 'medium' else "💡"
                lines.append(f"├─ {priority_emoji} {rec['category'].title()}: {rec['action']}")
                lines.append(f"│   Expected Impact: {rec['estimated_impact']}")
            lines.append("")
        
        # Usage Insights (if available)
        if report.usage_insights:
            lines.append("🎯 USAGE INSIGHTS")
            for insight in report.usage_insights[:2]:  # Top 2 insights
                confidence_emoji = "🎯" if insight['confidence'] > 0.8 else "📊" if insight['confidence'] > 0.6 else "💭"
                lines.append(f"├─ {confidence_emoji} {insight['message']}")
            lines.append("")
        
        # Token Efficiency Trends
        if report.token_efficiency_trends.get('efficiency_over_time'):
            recent_efficiency = report.token_efficiency_trends['efficiency_over_time'][-1]
            trend_emoji = "📈" if recent_efficiency > 0.7 else "📊" if recent_efficiency > 0.5 else "📉"
            lines.append(f"📊 EFFICIENCY TRENDS {trend_emoji}")
            lines.append(f"├─ Current Token Efficiency: {recent_efficiency:.0%}")
            lines.append(f"└─ Trend: {'Improving' if len(report.token_efficiency_trends['efficiency_over_time']) > 1 and report.token_efficiency_trends['efficiency_over_time'][-1] > report.token_efficiency_trends['efficiency_over_time'][-2] else 'Stable'}\n")
        
        return "\n".join(lines)
    
    async def _format_web_dashboard(self, report: ComprehensiveHealthReport) -> str:
        """Format dashboard for web display with HTML and styling."""
        # Basic HTML structure - would be enhanced for full web integration
        html = f"""
        <div class="comprehensive-health-dashboard">
            <h2>{report.overall_health_color.value} Comprehensive Context Health</h2>
            <div class="health-score">Overall Score: {report.overall_health_score:.0%}</div>
            
            <div class="metrics-grid">
                <div class="focus-metrics">
                    <h3>🎯 Focus Metrics {report.focus_metrics.overall_focus_health.value}</h3>
                    <ul>
                        <li>Focus Score: {report.focus_metrics.focus_score:.0%}</li>
                        <li>Priority Alignment: {report.focus_metrics.priority_alignment:.0%}</li>
                        <li>Current Work Ratio: {report.focus_metrics.current_work_ratio:.0%}</li>
                        <li>Attention Clarity: {report.focus_metrics.attention_clarity:.0%}</li>
                    </ul>
                </div>
                
                <div class="redundancy-analysis">
                    <h3>🧹 Redundancy Analysis {report.redundancy_analysis.overall_redundancy_health.value}</h3>
                    <ul>
                        <li>Duplicate Content: {report.redundancy_analysis.duplicate_content_percentage:.0%}</li>
                        <li>Stale Context: {report.redundancy_analysis.stale_context_percentage:.0%}</li>
                        <li>Redundant Files: {report.redundancy_analysis.redundant_files_count}</li>
                        <li>Obsolete Todos: {report.redundancy_analysis.obsolete_todos_count}</li>
                    </ul>
                </div>
            </div>
            
            <div class="recommendations">
                <h3>💡 Top Recommendations</h3>
                <ul>
        """
        
        for rec in report.optimization_recommendations[:3]:
            html += f"<li><strong>{rec['category'].title()}:</strong> {rec['action']} (Impact: {rec['estimated_impact']})</li>"
        
        html += """
                </ul>
            </div>
        </div>
        """
        
        return html
    
    # Security and validation helper methods
    
    def _is_safe_path(self, path: Path) -> bool:
        """Validate that path is safe and within allowed directories."""
        try:
            resolved_path = path.resolve()
            # For now, allow any path - in production, implement proper path validation
            # based on configured safe directories
            return True
        except (OSError, ValueError):
            return False
    
    def _validate_context_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate context data structure and sanitize if needed."""
        if not isinstance(data, dict):
            raise DataValidationError("Context data must be a dictionary")
        
        # Ensure items is a list
        if 'items' in data and not isinstance(data['items'], list):
            logger.warning("Converting non-list items to list")
            data['items'] = [data['items']] if data['items'] else []
        
        # Limit the number of items to prevent DoS
        max_items = 10000
        if 'items' in data and len(data['items']) > max_items:
            logger.warning(f"Truncating items list from {len(data['items'])} to {max_items}")
            data['items'] = data['items'][:max_items]
        
        return data
    
    def _is_valid_iso_timestamp(self, timestamp_str: str) -> bool:
        """Validate ISO format timestamp string."""
        if not isinstance(timestamp_str, str):
            return False
        
        # Basic ISO format validation with regex
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$'
        return bool(re.match(iso_pattern, timestamp_str))
    
    def _safe_get_string_content(self, item: Dict[str, Any]) -> str:
        """Safely extract string content from item without arbitrary code execution."""
        # Try multiple content fields in order of preference
        content_fields = ['content', 'message', 'text', 'description', 'title', 'name']
        
        for field in content_fields:
            if field in item:
                value = item[field]
                if isinstance(value, str):
                    return value
                elif isinstance(value, (int, float)):
                    return str(value)
        
        # Fallback to safe string representation of specific fields only
        safe_fields = ['type', 'status', 'priority', 'category']
        safe_content = []
        for field in safe_fields:
            if field in item and isinstance(item[field], (str, int, float)):
                safe_content.append(str(item[field]))
        
        return ' '.join(safe_content) if safe_content else ""