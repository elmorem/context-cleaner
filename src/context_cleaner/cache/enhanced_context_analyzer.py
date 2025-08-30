"""
Enhanced Context Analyzer Integration

Integrates cache-based intelligence with the existing Context Analysis Engine
to provide usage-weighted context analysis and personalized optimization.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..core.context_analyzer import ContextAnalyzer, ContextAnalysisResult
from .usage_analyzer import UsagePatternAnalyzer, UsagePatternSummary
from .token_analyzer import TokenEfficiencyAnalyzer, TokenAnalysisSummary  
from .temporal_analyzer import TemporalContextAnalyzer, TemporalInsights
from .discovery import CacheDiscoveryService
from .models import CacheConfig

logger = logging.getLogger(__name__)


@dataclass
class UsageWeightedScore:
    """Score weighted by actual usage patterns."""
    
    base_score: float
    usage_weight: float
    final_score: float
    usage_factors: Dict[str, float]
    confidence: float
    
    @property
    def improvement_ratio(self) -> float:
        """How much usage weighting improved the score."""
        if self.base_score == 0:
            return 0.0
        return (self.final_score - self.base_score) / self.base_score


@dataclass
class CacheEnhancedAnalysis:
    """Context analysis enhanced with cache-based intelligence."""
    
    # Original analysis results
    base_analysis: ContextAnalysisResult
    
    # Cache-based insights
    usage_patterns: UsagePatternSummary
    token_efficiency: TokenAnalysisSummary
    temporal_insights: TemporalInsights
    
    # Enhanced scores
    usage_weighted_focus: UsageWeightedScore
    usage_weighted_priority: UsageWeightedScore
    usage_weighted_recency: UsageWeightedScore
    usage_weighted_redundancy: UsageWeightedScore
    
    # Personalized recommendations
    personalized_recommendations: List[str]
    workflow_optimizations: List[str]
    context_health_insights: List[str]
    
    # Overall enhancement metrics
    enhancement_confidence: float
    cache_data_quality: float
    personalization_strength: float
    
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def overall_enhancement_score(self) -> float:
        """Overall score showing how much cache data improved analysis."""
        scores = [
            self.usage_weighted_focus.improvement_ratio,
            self.usage_weighted_priority.improvement_ratio,
            self.usage_weighted_recency.improvement_ratio,
            self.usage_weighted_redundancy.improvement_ratio
        ]
        
        valid_scores = [s for s in scores if s != 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
    
    @property
    def enhanced_overall_health(self) -> float:
        """Enhanced overall context health score."""
        return (
            self.usage_weighted_focus.final_score * 0.3 +
            self.usage_weighted_priority.final_score * 0.25 +
            self.usage_weighted_recency.final_score * 0.25 +
            (1.0 - self.usage_weighted_redundancy.final_score) * 0.2
        )


class EnhancedContextAnalyzer:
    """Context analyzer enhanced with cache-based intelligence."""
    
    def __init__(self, 
                 context_analyzer: Optional[ContextAnalyzer] = None,
                 config: Optional[CacheConfig] = None):
        """Initialize the enhanced context analyzer."""
        self.context_analyzer = context_analyzer or ContextAnalyzer()
        self.config = config or CacheConfig()
        
        # Cache analyzers
        self.usage_analyzer = UsagePatternAnalyzer(config)
        self.token_analyzer = TokenEfficiencyAnalyzer(config) 
        self.temporal_analyzer = TemporalContextAnalyzer(config)
        self.discovery = CacheDiscoveryService(config)
        
        # Enhancement parameters
        self.usage_weight_factor = 0.4  # How much to weight usage patterns
        self.min_confidence_threshold = 0.3
        self.cache_data_freshness_days = 30
        
        # Cache for recent analysis to avoid recomputation
        self._cache_analysis_cache: Optional[Tuple[UsagePatternSummary, TokenAnalysisSummary, TemporalInsights]] = None
        self._cache_timestamp: Optional[datetime] = None
        
    def analyze_with_cache_intelligence(self, 
                                      context_content: str,
                                      context_files: Optional[List[str]] = None,
                                      analysis_options: Optional[Dict] = None) -> CacheEnhancedAnalysis:
        """
        Perform context analysis enhanced with cache-based intelligence.
        
        Args:
            context_content: The context content to analyze
            context_files: Optional list of context file paths
            analysis_options: Optional analysis configuration
            
        Returns:
            Enhanced analysis with usage-weighted insights
        """
        logger.info("Starting cache-enhanced context analysis...")
        
        # Perform base context analysis
        base_analysis = self.context_analyzer.analyze_context(
            context_content, 
            context_files or [], 
            analysis_options or {}
        )
        
        # Get or compute cache insights
        cache_insights = self._get_cache_insights()
        usage_patterns, token_efficiency, temporal_insights = cache_insights
        
        # Enhance analysis with cache intelligence
        enhanced_analysis = self._create_enhanced_analysis(
            base_analysis,
            usage_patterns,
            token_efficiency, 
            temporal_insights,
            context_files or []
        )
        
        logger.info(f"Enhanced analysis complete. Enhancement score: {enhanced_analysis.overall_enhancement_score:.2f}")
        
        return enhanced_analysis
    
    def _get_cache_insights(self) -> Tuple[UsagePatternSummary, TokenAnalysisSummary, TemporalInsights]:
        """Get cache insights, using cached results if available."""
        now = datetime.now()
        
        # Check if we have fresh cached results
        if (self._cache_analysis_cache and self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < 3600):  # 1 hour cache
            logger.debug("Using cached insights")
            return self._cache_analysis_cache
        
        logger.info("Computing fresh cache insights...")
        
        # Discover cache locations
        cache_locations = self.discovery.discover_cache_locations()
        
        # Limit analysis to recent sessions for performance
        max_sessions = 50  # Reasonable limit for performance
        
        # Analyze patterns in parallel (simplified sequential for now)
        usage_patterns = self.usage_analyzer.analyze_usage_patterns(
            cache_locations, max_sessions
        )
        
        token_efficiency = self.token_analyzer.analyze_token_efficiency(
            cache_locations, max_sessions
        )
        
        temporal_insights = self.temporal_analyzer.analyze_temporal_patterns(
            cache_locations, self.cache_data_freshness_days
        )
        
        # Cache the results
        self._cache_analysis_cache = (usage_patterns, token_efficiency, temporal_insights)
        self._cache_timestamp = now
        
        return self._cache_analysis_cache
    
    def _create_enhanced_analysis(self,
                                base_analysis: ContextAnalysisResult,
                                usage_patterns: UsagePatternSummary,
                                token_efficiency: TokenAnalysisSummary,
                                temporal_insights: TemporalInsights,
                                context_files: List[str]) -> CacheEnhancedAnalysis:
        """Create enhanced analysis by combining base analysis with cache insights."""
        
        # Calculate usage-weighted scores
        focus_score = self._calculate_usage_weighted_focus(
            base_analysis.focus_score, usage_patterns, context_files
        )
        
        priority_score = self._calculate_usage_weighted_priority(
            base_analysis.priority_score, usage_patterns, temporal_insights, context_files
        )
        
        recency_score = self._calculate_usage_weighted_recency(
            base_analysis.recency_score, usage_patterns, temporal_insights, context_files
        )
        
        redundancy_score = self._calculate_usage_weighted_redundancy(
            base_analysis.redundancy_score, usage_patterns, token_efficiency
        )
        
        # Generate personalized recommendations
        personalized_recommendations = self._generate_personalized_recommendations(
            base_analysis, usage_patterns, token_efficiency, temporal_insights
        )
        
        workflow_optimizations = self._generate_workflow_optimizations(
            usage_patterns, temporal_insights
        )
        
        context_health_insights = self._generate_context_health_insights(
            base_analysis, usage_patterns, token_efficiency, temporal_insights
        )
        
        # Calculate enhancement metrics
        enhancement_confidence = self._calculate_enhancement_confidence(
            usage_patterns, token_efficiency, temporal_insights
        )
        
        cache_data_quality = self._assess_cache_data_quality(
            usage_patterns, token_efficiency, temporal_insights
        )
        
        personalization_strength = self._calculate_personalization_strength(
            usage_patterns, temporal_insights
        )
        
        return CacheEnhancedAnalysis(
            base_analysis=base_analysis,
            usage_patterns=usage_patterns,
            token_efficiency=token_efficiency,
            temporal_insights=temporal_insights,
            usage_weighted_focus=focus_score,
            usage_weighted_priority=priority_score,
            usage_weighted_recency=recency_score,
            usage_weighted_redundancy=redundancy_score,
            personalized_recommendations=personalized_recommendations,
            workflow_optimizations=workflow_optimizations,
            context_health_insights=context_health_insights,
            enhancement_confidence=enhancement_confidence,
            cache_data_quality=cache_data_quality,
            personalization_strength=personalization_strength
        )
    
    def _calculate_usage_weighted_focus(self,
                                      base_focus: float,
                                      usage_patterns: UsagePatternSummary,
                                      context_files: List[str]) -> UsageWeightedScore:
        """Calculate focus score weighted by actual file usage patterns."""
        usage_factors = {}
        usage_weight = 0.0
        
        if usage_patterns.file_usage_metrics:
            # Check if context files are heavily used
            {f.file_path for f in usage_patterns.heavily_used_files}
            
            context_file_usage = 0.0
            for file_path in context_files:
                if file_path in usage_patterns.file_usage_metrics:
                    metrics = usage_patterns.file_usage_metrics[file_path]
                    if metrics.usage_intensity in ["Heavy", "Moderate"]:
                        context_file_usage += 0.3
                    elif metrics.usage_intensity == "Light":
                        context_file_usage += 0.1
                    
                    # Bonus for recently accessed files
                    if metrics.staleness_days < 7:
                        context_file_usage += 0.2
            
            # Check workflow alignment
            workflow_alignment = 0.0
            for pattern in usage_patterns.top_workflow_patterns[:3]:
                if any(f in pattern.file_sequence for f in context_files):
                    workflow_alignment += pattern.confidence_score * 0.2
            
            usage_factors['file_usage'] = context_file_usage
            usage_factors['workflow_alignment'] = workflow_alignment
            usage_weight = (context_file_usage + workflow_alignment) / 2
        
        # Blend base score with usage-weighted adjustment
        if usage_weight > 0.1:
            final_score = base_focus * (1 - self.usage_weight_factor) + usage_weight * self.usage_weight_factor
        else:
            final_score = base_focus
        
        confidence = min(usage_patterns.total_sessions_analyzed / 20, 1.0)
        
        return UsageWeightedScore(
            base_score=base_focus,
            usage_weight=usage_weight,
            final_score=final_score,
            usage_factors=usage_factors,
            confidence=confidence
        )
    
    def _calculate_usage_weighted_priority(self,
                                         base_priority: float,
                                         usage_patterns: UsagePatternSummary,
                                         temporal_insights: TemporalInsights,
                                         context_files: List[str]) -> UsageWeightedScore:
        """Calculate priority score weighted by usage and temporal patterns."""
        usage_factors = {}
        usage_weight = 0.0
        
        # Priority boost for files in active workflows
        workflow_priority = 0.0
        for pattern in usage_patterns.top_workflow_patterns[:5]:
            if pattern.is_frequent and any(f in pattern.file_sequence for f in context_files):
                workflow_priority += pattern.confidence_score * 0.2
        
        # Priority boost for files accessed during productive hours
        productive_hours = set(temporal_insights.most_productive_hours)
        current_hour = datetime.now().hour
        
        temporal_priority = 0.0
        if current_hour in productive_hours:
            temporal_priority = 0.3  # Boost priority during productive hours
        
        # Priority adjustment based on recent topic transitions
        topic_relevance = 0.0
        recent_transitions = [t for t in temporal_insights.topic_transitions 
                            if (datetime.now() - t.transition_time).days < 7]
        
        if recent_transitions:
            # Boost priority if context relates to recent topics
            recent_topics = set(t.to_topic for t in recent_transitions[-5:])
            if any(self._file_relates_to_topic(f, recent_topics) for f in context_files):
                topic_relevance = 0.2
        
        usage_factors['workflow_priority'] = workflow_priority
        usage_factors['temporal_priority'] = temporal_priority  
        usage_factors['topic_relevance'] = topic_relevance
        
        usage_weight = (workflow_priority + temporal_priority + topic_relevance) / 3
        
        # Blend scores
        if usage_weight > 0.1:
            final_score = base_priority * (1 - self.usage_weight_factor) + usage_weight * self.usage_weight_factor
        else:
            final_score = base_priority
        
        confidence = min((len(usage_patterns.workflow_patterns) + len(recent_transitions)) / 20, 1.0)
        
        return UsageWeightedScore(
            base_score=base_priority,
            usage_weight=usage_weight,
            final_score=final_score,
            usage_factors=usage_factors,
            confidence=confidence
        )
    
    def _calculate_usage_weighted_recency(self,
                                        base_recency: float,
                                        usage_patterns: UsagePatternSummary,
                                        temporal_insights: TemporalInsights,
                                        context_files: List[str]) -> UsageWeightedScore:
        """Calculate recency score weighted by actual access patterns."""
        usage_factors = {}
        usage_weight = 0.0
        
        # Real access recency from cache data
        actual_recency = 0.0
        if usage_patterns.file_usage_metrics:
            recent_accesses = 0
            for file_path in context_files:
                if file_path in usage_patterns.file_usage_metrics:
                    metrics = usage_patterns.file_usage_metrics[file_path]
                    if metrics.staleness_days < 1:
                        recent_accesses += 1.0
                    elif metrics.staleness_days < 7:
                        recent_accesses += 0.7
                    elif metrics.staleness_days < 30:
                        recent_accesses += 0.3
            
            actual_recency = recent_accesses / max(len(context_files), 1)
        
        # Session boundary consideration
        session_recency = 0.0
        strong_boundaries = [b for b in temporal_insights.session_boundaries if b.is_strong_boundary]
        if strong_boundaries:
            last_boundary = max(strong_boundaries, key=lambda x: x.boundary_time)
            hours_since = (datetime.now() - last_boundary.boundary_time).total_seconds() / 3600
            if hours_since < 24:
                session_recency = 1.0 - (hours_since / 24)
        
        usage_factors['actual_recency'] = actual_recency
        usage_factors['session_recency'] = session_recency
        
        usage_weight = (actual_recency + session_recency) / 2
        
        # Blend scores  
        if usage_weight > 0.1:
            final_score = base_recency * (1 - self.usage_weight_factor) + usage_weight * self.usage_weight_factor
        else:
            final_score = base_recency
        
        confidence = min(len(usage_patterns.file_usage_metrics) / 10, 1.0)
        
        return UsageWeightedScore(
            base_score=base_recency,
            usage_weight=usage_weight,
            final_score=final_score,
            usage_factors=usage_factors,
            confidence=confidence
        )
    
    def _calculate_usage_weighted_redundancy(self,
                                           base_redundancy: float,
                                           usage_patterns: UsagePatternSummary,
                                           token_efficiency: TokenAnalysisSummary) -> UsageWeightedScore:
        """Calculate redundancy score weighted by token efficiency patterns."""
        usage_factors = {}
        usage_weight = base_redundancy  # Start with base
        
        # Adjust based on detected waste patterns
        waste_adjustment = 0.0
        if token_efficiency.waste_patterns:
            high_impact_waste = [p for p in token_efficiency.waste_patterns if p.severity_level == "High"]
            if high_impact_waste:
                waste_adjustment += 0.3  # Increase redundancy score due to detected waste
            
            repetitive_patterns = [p for p in token_efficiency.waste_patterns if "repetitive" in p.pattern_type]
            if repetitive_patterns:
                waste_adjustment += 0.2
        
        # Adjust based on repetitive operations in usage patterns
        repetitive_ops_adjustment = 0.0
        if len(usage_patterns.common_tool_sequences) > 10:
            repetitive_ops_adjustment = 0.15
        
        usage_factors['waste_patterns'] = waste_adjustment
        usage_factors['repetitive_operations'] = repetitive_ops_adjustment
        
        usage_weight = base_redundancy + waste_adjustment + repetitive_ops_adjustment
        usage_weight = min(usage_weight, 1.0)  # Cap at 1.0
        
        final_score = usage_weight
        confidence = min(len(token_efficiency.waste_patterns) / 5, 1.0)
        
        return UsageWeightedScore(
            base_score=base_redundancy,
            usage_weight=usage_weight - base_redundancy,
            final_score=final_score,
            usage_factors=usage_factors,
            confidence=confidence
        )
    
    def _file_relates_to_topic(self, file_path: str, topics: set) -> bool:
        """Check if a file path relates to any of the given topics."""
        file_lower = file_path.lower()
        
        for topic in topics:
            if topic in file_lower:
                return True
            
            # Check for topic-related keywords in path
            topic_keywords = {
                'coding': ['src', 'code', '.py', '.js', '.java'],
                'testing': ['test', 'spec', 'mock'],
                'documentation': ['doc', 'readme', '.md'],
                'configuration': ['config', 'settings', '.yaml', '.json']
            }
            
            if topic in topic_keywords:
                for keyword in topic_keywords[topic]:
                    if keyword in file_lower:
                        return True
        
        return False
    
    def _generate_personalized_recommendations(self,
                                             base_analysis: ContextAnalysisResult,
                                             usage_patterns: UsagePatternSummary,
                                             token_efficiency: TokenAnalysisSummary,
                                             temporal_insights: TemporalInsights) -> List[str]:
        """Generate personalized recommendations based on usage patterns."""
        recommendations = []
        
        # Workflow-based recommendations
        if usage_patterns.top_workflow_patterns:
            frequent_pattern = usage_patterns.top_workflow_patterns[0]
            if frequent_pattern.complexity_level == "Complex":
                recommendations.append(
                    f"Your most frequent workflow '{frequent_pattern.name}' is complex "
                    f"({len(frequent_pattern.file_sequence)} steps). Consider creating shortcuts or templates."
                )
        
        # Token efficiency recommendations
        if token_efficiency.overall_efficiency_score < 60:
            recommendations.append(
                f"Token efficiency could be improved (current: {token_efficiency.overall_efficiency_score:.0f}/100). "
                "Focus on reducing repetitive operations and improving context organization."
            )
        
        # Temporal pattern recommendations
        if temporal_insights.context_switching_cost > 0.6:
            recommendations.append(
                "High context switching detected. Consider batching similar tasks "
                f"during your most productive hours: {', '.join(map(str, temporal_insights.most_productive_hours[:3]))}"
            )
        
        # Session length recommendations
        if temporal_insights.average_session_length > temporal_insights.optimal_session_length * 1.5:
            recommendations.append(
                f"Your sessions average {temporal_insights.average_session_length:.1f}h but optimal appears to be "
                f"{temporal_insights.optimal_session_length:.1f}h. Consider shorter, focused sessions."
            )
        
        return recommendations[:5]  # Limit to top 5
    
    def _generate_workflow_optimizations(self,
                                       usage_patterns: UsagePatternSummary,
                                       temporal_insights: TemporalInsights) -> List[str]:
        """Generate workflow optimization suggestions."""
        optimizations = []
        
        # File organization optimizations
        heavily_used = usage_patterns.heavily_used_files
        if len(heavily_used) > 15:
            optimizations.append(
                f"Consider organizing your {len(heavily_used)} frequently-used files "
                "into a dedicated workspace or pinned context for faster access."
            )
        
        # Workflow pattern optimizations
        complex_patterns = [p for p in usage_patterns.top_workflow_patterns if p.complexity_level == "Complex"]
        if complex_patterns:
            optimizations.append(
                f"Found {len(complex_patterns)} complex workflow patterns. "
                "Consider creating automation or templates for these repetitive sequences."
            )
        
        # Temporal optimizations
        if temporal_insights.peak_activity_periods:
            peak_start = temporal_insights.peak_activity_periods[0][0].hour
            peak_end = temporal_insights.peak_activity_periods[0][1].hour
            optimizations.append(
                f"Your peak productivity appears to be {peak_start}:00-{peak_end}:00. "
                "Schedule complex work during these hours for better efficiency."
            )
        
        return optimizations
    
    def _generate_context_health_insights(self,
                                        base_analysis: ContextAnalysisResult,
                                        usage_patterns: UsagePatternSummary,
                                        token_efficiency: TokenAnalysisSummary,
                                        temporal_insights: TemporalInsights) -> List[str]:
        """Generate context health insights based on combined analysis."""
        insights = []
        
        # Overall health assessment
        if temporal_insights.overall_temporal_health == "Excellent":
            insights.append("Your context management patterns show excellent temporal health.")
        elif temporal_insights.overall_temporal_health == "Needs Improvement":
            insights.append("Context management could benefit from more structured session boundaries.")
        
        # Cache efficiency insights
        cache_grade = token_efficiency.cache_efficiency.cache_effectiveness_grade
        if cache_grade in ["Poor", "Very Poor"]:
            insights.append(
                f"Cache efficiency is {cache_grade.lower()}. Focus on organizing context "
                "to maximize reuse of previously processed information."
            )
        elif cache_grade == "Excellent":
            insights.append("Your context structure maximizes cache efficiency - great work!")
        
        # Usage pattern insights
        if usage_patterns.context_switch_frequency > 8:
            insights.append(
                f"High context switching ({usage_patterns.context_switch_frequency:.1f}/session) "
                "may be impacting focus. Consider grouping related tasks."
            )
        
        return insights
    
    def _calculate_enhancement_confidence(self,
                                        usage_patterns: UsagePatternSummary,
                                        token_efficiency: TokenAnalysisSummary,
                                        temporal_insights: TemporalInsights) -> float:
        """Calculate confidence in the enhancement analysis."""
        factors = []
        
        # Data volume factor
        session_factor = min(usage_patterns.total_sessions_analyzed / 20, 1.0)
        factors.append(session_factor)
        
        # Data recency factor
        analysis_age = (datetime.now() - temporal_insights.analysis_period[1]).days
        recency_factor = max(0, 1.0 - analysis_age / 30)  # Decay over 30 days
        factors.append(recency_factor)
        
        # Pattern strength factor
        strong_patterns = len([p for p in usage_patterns.workflow_patterns if p.is_frequent])
        pattern_factor = min(strong_patterns / 5, 1.0)
        factors.append(pattern_factor)
        
        return sum(factors) / len(factors)
    
    def _assess_cache_data_quality(self,
                                 usage_patterns: UsagePatternSummary,
                                 token_efficiency: TokenAnalysisSummary,
                                 temporal_insights: TemporalInsights) -> float:
        """Assess the quality of available cache data."""
        quality_factors = []
        
        # Completeness factor
        has_usage_data = usage_patterns.total_sessions_analyzed > 0
        has_token_data = token_efficiency.total_sessions_analyzed > 0
        has_temporal_data = len(temporal_insights.session_boundaries) > 0
        
        completeness = (has_usage_data + has_token_data + has_temporal_data) / 3
        quality_factors.append(completeness)
        
        # Consistency factor (do all analyzers agree on session count?)
        session_counts = [
            usage_patterns.total_sessions_analyzed,
            token_efficiency.total_sessions_analyzed,
            len(temporal_insights.session_boundaries) + 1  # boundaries + 1 = sessions
        ]
        
        non_zero_counts = [c for c in session_counts if c > 0]
        if len(non_zero_counts) > 1:
            consistency = 1.0 - (max(non_zero_counts) - min(non_zero_counts)) / max(non_zero_counts)
        else:
            consistency = 1.0
        
        quality_factors.append(consistency)
        
        return sum(quality_factors) / len(quality_factors)
    
    def _calculate_personalization_strength(self,
                                          usage_patterns: UsagePatternSummary,
                                          temporal_insights: TemporalInsights) -> float:
        """Calculate how personalized the analysis can be."""
        personalization_factors = []
        
        # Pattern diversity factor
        unique_patterns = len(set(p.name for p in usage_patterns.workflow_patterns))
        diversity_factor = min(unique_patterns / 8, 1.0)
        personalization_factors.append(diversity_factor)
        
        # Temporal stability factor  
        if temporal_insights.overall_temporal_health in ["Excellent", "Good"]:
            stability_factor = 1.0
        elif temporal_insights.overall_temporal_health == "Fair":
            stability_factor = 0.7
        else:
            stability_factor = 0.4
        
        personalization_factors.append(stability_factor)
        
        # Usage consistency factor
        heavily_used_ratio = len(usage_patterns.heavily_used_files) / max(usage_patterns.total_files_accessed, 1)
        consistency_factor = min(heavily_used_ratio * 2, 1.0)  # Up to 50% heavily used = max score
        personalization_factors.append(consistency_factor)
        
        return sum(personalization_factors) / len(personalization_factors)