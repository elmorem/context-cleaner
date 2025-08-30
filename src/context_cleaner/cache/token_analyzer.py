"""
Token Efficiency Analyzer

Analyzes token usage patterns, cache efficiency, and identifies opportunities
for optimization based on actual Claude Code token consumption data.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter
import statistics

from .models import SessionAnalysis, CacheConfig
from .session_parser import SessionCacheParser
from .discovery import CacheDiscoveryService, CacheLocation

logger = logging.getLogger(__name__)


@dataclass
class TokenWastePattern:
    """Represents a pattern of token waste."""
    
    pattern_type: str  # 'repetitive_reads', 'inefficient_cache', 'context_bloat', etc.
    description: str
    estimated_waste_tokens: int
    frequency: int
    sessions_affected: List[str]
    optimization_suggestion: str
    potential_savings_percent: float
    
    @property
    def severity_level(self) -> str:
        """Get severity level based on waste amount."""
        if self.estimated_waste_tokens > 10000:
            return "High"
        elif self.estimated_waste_tokens > 5000:
            return "Medium"
        else:
            return "Low"


@dataclass
class CacheEfficiencyMetrics:
    """Comprehensive cache efficiency metrics."""
    
    total_input_tokens: int
    total_output_tokens: int
    total_cache_creation_tokens: int
    total_cache_read_tokens: int
    ephemeral_5m_tokens: int
    ephemeral_1h_tokens: int
    
    overall_cache_hit_ratio: float
    average_cache_efficiency: float
    cache_utilization_score: float
    
    sessions_with_good_cache_usage: int
    sessions_with_poor_cache_usage: int
    sessions_with_no_cache_usage: int
    
    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def cache_effectiveness_grade(self) -> str:
        """Grade cache effectiveness."""
        if self.overall_cache_hit_ratio >= 0.8:
            return "Excellent"
        elif self.overall_cache_hit_ratio >= 0.6:
            return "Good" 
        elif self.overall_cache_hit_ratio >= 0.4:
            return "Fair"
        elif self.overall_cache_hit_ratio >= 0.2:
            return "Poor"
        else:
            return "Very Poor"
    
    @property
    def estimated_cost_savings_percent(self) -> float:
        """Estimate cost savings from cache usage."""
        # Simplified calculation - cache reads are typically much cheaper
        if self.total_cache_creation_tokens == 0:
            return 0.0
        
        cache_savings_ratio = self.total_cache_read_tokens / (
            self.total_cache_creation_tokens + self.total_cache_read_tokens
        )
        
        # Assume cache reads are ~90% cheaper than creation
        return cache_savings_ratio * 90


@dataclass
class TokenUsageInsights:
    """Insights about token usage patterns."""
    
    average_tokens_per_session: float
    average_tokens_per_message: float
    peak_token_sessions: List[Tuple[str, int]]  # (session_id, tokens)
    most_token_efficient_sessions: List[Tuple[str, float]]  # (session_id, efficiency_score)
    
    repetitive_operations: List[Tuple[str, int]]  # (operation_pattern, frequency)
    context_bloat_indicators: List[str]
    optimization_opportunities: List[str]
    
    token_distribution: Dict[str, float]  # input/output/cache ratios
    session_length_correlation: float  # correlation between session length and token efficiency
    
    @property
    def efficiency_summary(self) -> str:
        """Get efficiency summary."""
        if self.average_tokens_per_message < 100:
            return "Highly Efficient"
        elif self.average_tokens_per_message < 300:
            return "Efficient"
        elif self.average_tokens_per_message < 600:
            return "Moderate"
        else:
            return "Inefficient"


@dataclass
class TokenAnalysisSummary:
    """Comprehensive token analysis summary."""
    
    cache_efficiency: CacheEfficiencyMetrics
    usage_insights: TokenUsageInsights
    waste_patterns: List[TokenWastePattern]
    optimization_recommendations: List[str]
    total_sessions_analyzed: int
    analysis_period: Tuple[datetime, datetime]
    potential_monthly_savings: Dict[str, float]  # tokens and estimated cost
    analysis_date: datetime = field(default_factory=datetime.now)
    
    @property
    def overall_efficiency_score(self) -> float:
        """Calculate overall efficiency score (0-100)."""
        cache_score = self.cache_efficiency.overall_cache_hit_ratio * 40
        if self.usage_insights.average_tokens_per_message > 0:
            usage_score = min(1000 / self.usage_insights.average_tokens_per_message, 1) * 30
        else:
            usage_score = 0
        waste_score = max(0, 1 - sum(p.estimated_waste_tokens for p in self.waste_patterns) / 100000) * 30
        
        return min(100, cache_score + usage_score + waste_score)


class TokenEfficiencyAnalyzer:
    """Analyzes token usage efficiency and identifies optimization opportunities."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize the token efficiency analyzer."""
        self.config = config or CacheConfig()
        self.parser = SessionCacheParser(config)
        self.discovery = CacheDiscoveryService(config)
        
        # Analysis thresholds
        self.high_token_threshold = 1000  # tokens per message
        self.low_efficiency_threshold = 0.3  # cache hit ratio
        self.repetition_threshold = 3  # minimum repetitions to flag
        
    def analyze_token_efficiency(self, 
                                cache_locations: Optional[List[CacheLocation]] = None,
                                max_sessions: Optional[int] = None) -> TokenAnalysisSummary:
        """
        Analyze token efficiency across cache locations.
        
        Args:
            cache_locations: Specific cache locations to analyze
            max_sessions: Maximum number of sessions to analyze per location
            
        Returns:
            Comprehensive token analysis summary
        """
        logger.info("Starting token efficiency analysis...")
        
        if cache_locations is None:
            cache_locations = self.discovery.discover_cache_locations()
        
        all_sessions = []
        
        # Parse sessions from all locations
        for location in cache_locations:
            logger.info(f"Analyzing tokens in cache location: {location.project_name}")
            
            session_files = location.session_files
            if max_sessions:
                # Sort by modification time, take most recent
                session_files = sorted(session_files, 
                                     key=lambda x: x.stat().st_mtime, 
                                     reverse=True)[:max_sessions]
            
            for session_file in session_files:
                try:
                    analysis = self.parser.parse_session_file(session_file)
                    if analysis and self._has_token_metrics(analysis):
                        all_sessions.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to parse session {session_file}: {e}")
                    continue
        
        logger.info(f"Successfully analyzed {len(all_sessions)} sessions with token metrics")
        
        if not all_sessions:
            return self._create_empty_summary()
        
        # Perform analysis
        cache_efficiency = self._analyze_cache_efficiency(all_sessions)
        usage_insights = self._analyze_usage_patterns(all_sessions)
        waste_patterns = self._detect_waste_patterns(all_sessions)
        recommendations = self._generate_optimization_recommendations(
            cache_efficiency, usage_insights, waste_patterns
        )
        
        # Calculate analysis period
        start_times = [s.start_time for s in all_sessions if s.start_time]
        end_times = [s.end_time for s in all_sessions if s.end_time]
        
        period = (min(start_times), max(end_times)) if start_times and end_times else (datetime.now(), datetime.now())
        
        # Estimate potential savings
        monthly_savings = self._estimate_monthly_savings(cache_efficiency, usage_insights, waste_patterns)
        
        summary = TokenAnalysisSummary(
            cache_efficiency=cache_efficiency,
            usage_insights=usage_insights,
            waste_patterns=waste_patterns,
            optimization_recommendations=recommendations,
            total_sessions_analyzed=len(all_sessions),
            analysis_period=period,
            potential_monthly_savings=monthly_savings
        )
        
        logger.info(f"Token analysis complete. Overall efficiency score: {summary.overall_efficiency_score:.1f}/100")
        
        return summary
    
    def _has_token_metrics(self, session: SessionAnalysis) -> bool:
        """Check if session has usable token metrics."""
        return (
            session.total_tokens > 0 or
            any(msg.token_metrics for msg in session.messages if hasattr(session, 'messages'))
        )
    
    def _create_empty_summary(self) -> TokenAnalysisSummary:
        """Create empty summary when no data is available."""
        empty_cache_metrics = CacheEfficiencyMetrics(
            total_input_tokens=0,
            total_output_tokens=0,
            total_cache_creation_tokens=0,
            total_cache_read_tokens=0,
            ephemeral_5m_tokens=0,
            ephemeral_1h_tokens=0,
            overall_cache_hit_ratio=0.0,
            average_cache_efficiency=0.0,
            cache_utilization_score=0.0,
            sessions_with_good_cache_usage=0,
            sessions_with_poor_cache_usage=0,
            sessions_with_no_cache_usage=0
        )
        
        empty_usage_insights = TokenUsageInsights(
            average_tokens_per_session=0.0,
            average_tokens_per_message=0.0,
            peak_token_sessions=[],
            most_token_efficient_sessions=[],
            repetitive_operations=[],
            context_bloat_indicators=[],
            optimization_opportunities=[],
            token_distribution={},
            session_length_correlation=0.0
        )
        
        return TokenAnalysisSummary(
            cache_efficiency=empty_cache_metrics,
            usage_insights=empty_usage_insights,
            waste_patterns=[],
            optimization_recommendations=["No token data available for analysis"],
            total_sessions_analyzed=0,
            analysis_period=(datetime.now(), datetime.now()),
            potential_monthly_savings={}
        )
    
    def _analyze_cache_efficiency(self, sessions: List[SessionAnalysis]) -> CacheEfficiencyMetrics:
        """Analyze cache efficiency across sessions."""
        total_input = 0
        total_output = 0
        total_cache_creation = 0
        total_cache_read = 0
        total_ephemeral_5m = 0
        total_ephemeral_1h = 0
        
        cache_hit_ratios = []
        efficiency_scores = []
        
        good_cache_sessions = 0
        poor_cache_sessions = 0
        no_cache_sessions = 0
        
        for session in sessions:
            # Aggregate from session totals (simplified)
            session_tokens = session.total_tokens
            
            # Estimate token distribution (this would be more accurate with actual message-level metrics)
            estimated_input = int(session_tokens * 0.6)  # Rough estimate
            estimated_output = int(session_tokens * 0.4)
            
            total_input += estimated_input
            total_output += estimated_output
            
            # For detailed cache metrics, we'd need to parse individual messages
            # This is a simplified version using session-level data
            if hasattr(session, 'cache_efficiency'):
                cache_ratio = session.cache_efficiency
                cache_hit_ratios.append(cache_ratio)
                efficiency_scores.append(cache_ratio)
                
                if cache_ratio >= 0.6:
                    good_cache_sessions += 1
                elif cache_ratio >= 0.2:
                    poor_cache_sessions += 1
                else:
                    no_cache_sessions += 1
            else:
                no_cache_sessions += 1
        
        # Calculate averages
        avg_cache_hit_ratio = statistics.mean(cache_hit_ratios) if cache_hit_ratios else 0.0
        avg_efficiency = statistics.mean(efficiency_scores) if efficiency_scores else 0.0
        
        # Calculate utilization score
        total_sessions = len(sessions)
        utilization_score = (good_cache_sessions + poor_cache_sessions * 0.5) / total_sessions if total_sessions > 0 else 0.0
        
        return CacheEfficiencyMetrics(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cache_creation_tokens=total_cache_creation,
            total_cache_read_tokens=total_cache_read,
            ephemeral_5m_tokens=total_ephemeral_5m,
            ephemeral_1h_tokens=total_ephemeral_1h,
            overall_cache_hit_ratio=avg_cache_hit_ratio,
            average_cache_efficiency=avg_efficiency,
            cache_utilization_score=utilization_score,
            sessions_with_good_cache_usage=good_cache_sessions,
            sessions_with_poor_cache_usage=poor_cache_sessions,
            sessions_with_no_cache_usage=no_cache_sessions
        )
    
    def _analyze_usage_patterns(self, sessions: List[SessionAnalysis]) -> TokenUsageInsights:
        """Analyze token usage patterns."""
        session_tokens = [s.total_tokens for s in sessions if s.total_tokens > 0]
        [s.total_messages for s in sessions if s.total_messages > 0]
        
        if not session_tokens:
            return TokenUsageInsights(
                average_tokens_per_session=0.0,
                average_tokens_per_message=0.0,
                peak_token_sessions=[],
                most_token_efficient_sessions=[],
                repetitive_operations=[],
                context_bloat_indicators=[],
                optimization_opportunities=[],
                token_distribution={},
                session_length_correlation=0.0
            )
        
        avg_tokens_per_session = statistics.mean(session_tokens)
        
        # Calculate tokens per message
        tokens_per_message = []
        for session in sessions:
            if session.total_messages > 0 and session.total_tokens > 0:
                ratio = session.total_tokens / session.total_messages
                tokens_per_message.append(ratio)
        
        avg_tokens_per_message = statistics.mean(tokens_per_message) if tokens_per_message else 0.0
        
        # Find peak token sessions
        session_token_pairs = [(s.session_id, s.total_tokens) for s in sessions]
        peak_sessions = sorted(session_token_pairs, key=lambda x: x[1], reverse=True)[:5]
        
        # Find most efficient sessions
        efficiency_pairs = []
        for session in sessions:
            if session.total_messages > 0 and session.total_tokens > 0:
                efficiency = session.total_messages / session.total_tokens  # messages per token
                efficiency_pairs.append((session.session_id, efficiency))
        
        efficient_sessions = sorted(efficiency_pairs, key=lambda x: x[1], reverse=True)[:5]
        
        # Detect repetitive operations
        repetitive_ops = self._detect_repetitive_operations(sessions)
        
        # Detect context bloat indicators
        bloat_indicators = self._detect_context_bloat(sessions)
        
        # Generate optimization opportunities
        opportunities = self._identify_optimization_opportunities(sessions)
        
        # Calculate token distribution
        sum(session_tokens)
        distribution = {
            'input_ratio': 0.6,  # Estimated - would be more accurate with message-level data
            'output_ratio': 0.4,
            'cache_ratio': sum(getattr(s, 'cache_efficiency', 0) for s in sessions) / len(sessions)
        }
        
        # Calculate correlation between session length and efficiency
        correlation = self._calculate_length_efficiency_correlation(sessions)
        
        return TokenUsageInsights(
            average_tokens_per_session=avg_tokens_per_session,
            average_tokens_per_message=avg_tokens_per_message,
            peak_token_sessions=peak_sessions,
            most_token_efficient_sessions=efficient_sessions,
            repetitive_operations=repetitive_ops,
            context_bloat_indicators=bloat_indicators,
            optimization_opportunities=opportunities,
            token_distribution=distribution,
            session_length_correlation=correlation
        )
    
    def _detect_repetitive_operations(self, sessions: List[SessionAnalysis]) -> List[Tuple[str, int]]:
        """Detect repetitive operations that may waste tokens."""
        operation_patterns = Counter()
        
        for session in sessions:
            # Create patterns from file operations
            for i, op in enumerate(session.file_operations[:-1]):
                next_op = session.file_operations[i + 1]
                
                # Pattern: same file accessed multiple times in sequence
                if op.file_path == next_op.file_path and op.tool_name == next_op.tool_name:
                    pattern = f"repeated_{op.tool_name}_{op.file_path}"
                    operation_patterns[pattern] += 1
                
                # Pattern: read -> edit -> read on same file
                if (i < len(session.file_operations) - 2 and
                    op.tool_name == "Read" and next_op.tool_name == "Edit" and
                    op.file_path == next_op.file_path):
                    
                    third_op = session.file_operations[i + 2]
                    if third_op.tool_name == "Read" and third_op.file_path == op.file_path:
                        pattern = "read_edit_read_cycle"
                        operation_patterns[pattern] += 1
        
        # Return patterns that occur frequently
        return [(pattern, count) for pattern, count in operation_patterns.most_common(10) 
                if count >= self.repetition_threshold]
    
    def _detect_context_bloat(self, sessions: List[SessionAnalysis]) -> List[str]:
        """Detect indicators of context bloat."""
        indicators = []
        
        # Check for very long sessions
        long_sessions = [s for s in sessions if s.duration_hours > 4]
        if len(long_sessions) > len(sessions) * 0.2:  # More than 20% are long
            indicators.append("Frequent long sessions (>4 hours) may indicate context bloat")
        
        # Check for high token-to-message ratios
        high_ratio_sessions = []
        for session in sessions:
            if session.total_messages > 0:
                ratio = session.total_tokens / session.total_messages
                if ratio > self.high_token_threshold:
                    high_ratio_sessions.append(session)
        
        if len(high_ratio_sessions) > len(sessions) * 0.1:  # More than 10%
            indicators.append(f"High token-to-message ratios detected in {len(high_ratio_sessions)} sessions")
        
        # Check for sessions with many file operations but low productivity
        inefficient_sessions = []
        for session in sessions:
            if len(session.file_operations) > 20 and session.total_messages < 30:
                inefficient_sessions.append(session)
        
        if inefficient_sessions:
            indicators.append(f"Found {len(inefficient_sessions)} sessions with high file operations but low message count")
        
        return indicators
    
    def _identify_optimization_opportunities(self, sessions: List[SessionAnalysis]) -> List[str]:
        """Identify specific optimization opportunities."""
        opportunities = []
        
        # Check for cache optimization opportunities
        low_cache_sessions = [s for s in sessions if getattr(s, 'cache_efficiency', 0) < self.low_efficiency_threshold]
        if len(low_cache_sessions) > len(sessions) * 0.3:
            opportunities.append("Improve context caching - many sessions have low cache efficiency")
        
        # Check for file access pattern optimization
        total_file_ops = sum(len(s.file_operations) for s in sessions)
        avg_ops_per_session = total_file_ops / len(sessions) if sessions else 0
        
        if avg_ops_per_session > 15:
            opportunities.append("Consider batching file operations or using more targeted file access patterns")
        
        # Check for session length optimization
        very_short_sessions = [s for s in sessions if s.duration_hours < 0.1]  # Less than 6 minutes
        if len(very_short_sessions) > len(sessions) * 0.3:
            opportunities.append("Many very short sessions detected - consider consolidating related work")
        
        return opportunities
    
    def _calculate_length_efficiency_correlation(self, sessions: List[SessionAnalysis]) -> float:
        """Calculate correlation between session length and token efficiency."""
        if len(sessions) < 2:
            return 0.0
        
        lengths = []
        efficiencies = []
        
        for session in sessions:
            if session.total_messages > 0 and session.total_tokens > 0:
                lengths.append(session.duration_hours)
                efficiency = session.total_messages / session.total_tokens
                efficiencies.append(efficiency)
        
        if len(lengths) < 2:
            return 0.0
        
        # Simple correlation calculation
        try:
            n = len(lengths)
            sum_x = sum(lengths)
            sum_y = sum(efficiencies)
            sum_xy = sum(x * y for x, y in zip(lengths, efficiencies))
            sum_x2 = sum(x * x for x in lengths)
            sum_y2 = sum(y * y for y in efficiencies)
            
            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)) ** 0.5
            
            if denominator == 0:
                return 0.0
            
            return numerator / denominator
        except Exception:
            return 0.0
    
    def _detect_waste_patterns(self, sessions: List[SessionAnalysis]) -> List[TokenWastePattern]:
        """Detect specific patterns that waste tokens."""
        patterns = []
        
        # Pattern 1: Repetitive file reads
        repetitive_reads = self._detect_repetitive_reads(sessions)
        if repetitive_reads:
            patterns.append(TokenWastePattern(
                pattern_type="repetitive_reads",
                description=f"Detected {repetitive_reads['count']} instances of repetitive file reads",
                estimated_waste_tokens=repetitive_reads['estimated_waste'],
                frequency=repetitive_reads['count'],
                sessions_affected=repetitive_reads['sessions'],
                optimization_suggestion="Use context caching or consolidate file access patterns",
                potential_savings_percent=15.0
            ))
        
        # Pattern 2: Inefficient cache usage
        cache_inefficiency = self._detect_cache_inefficiency(sessions)
        if cache_inefficiency:
            patterns.append(TokenWastePattern(
                pattern_type="inefficient_cache",
                description="Poor cache utilization leading to repeated context processing",
                estimated_waste_tokens=cache_inefficiency['estimated_waste'],
                frequency=cache_inefficiency['count'],
                sessions_affected=cache_inefficiency['sessions'],
                optimization_suggestion="Improve context structure to maximize cache hits",
                potential_savings_percent=25.0
            ))
        
        # Pattern 3: Context bloat
        context_bloat = self._detect_token_bloat_pattern(sessions)
        if context_bloat:
            patterns.append(TokenWastePattern(
                pattern_type="context_bloat",
                description="Sessions with unusually high token usage per message",
                estimated_waste_tokens=context_bloat['estimated_waste'],
                frequency=context_bloat['count'],
                sessions_affected=context_bloat['sessions'],
                optimization_suggestion="Clean up context regularly and remove unnecessary information",
                potential_savings_percent=20.0
            ))
        
        return patterns
    
    def _detect_repetitive_reads(self, sessions: List[SessionAnalysis]) -> Optional[Dict]:
        """Detect repetitive file read patterns."""
        repetitive_count = 0
        affected_sessions = []
        estimated_waste = 0
        
        for session in sessions:
            file_read_counts = Counter()
            for op in session.file_operations:
                if op.tool_name == "Read":
                    file_read_counts[op.file_path] += 1
            
            # Find files read multiple times
            repetitive_files = [f for f, count in file_read_counts.items() if count > 2]
            if repetitive_files:
                repetitive_count += len(repetitive_files)
                affected_sessions.append(session.session_id)
                # Estimate waste: assume each extra read costs ~200 tokens
                extra_reads = sum(file_read_counts[f] - 1 for f in repetitive_files)
                estimated_waste += extra_reads * 200
        
        if repetitive_count > 0:
            return {
                'count': repetitive_count,
                'sessions': affected_sessions,
                'estimated_waste': estimated_waste
            }
        
        return None
    
    def _detect_cache_inefficiency(self, sessions: List[SessionAnalysis]) -> Optional[Dict]:
        """Detect cache inefficiency patterns."""
        inefficient_sessions = []
        total_inefficiency = 0
        
        for session in sessions:
            cache_efficiency = getattr(session, 'cache_efficiency', 0)
            if cache_efficiency < self.low_efficiency_threshold and session.total_tokens > 1000:
                inefficient_sessions.append(session.session_id)
                # Estimate waste based on missed cache opportunities
                missed_efficiency = self.low_efficiency_threshold - cache_efficiency
                estimated_session_waste = int(session.total_tokens * missed_efficiency * 0.5)
                total_inefficiency += estimated_session_waste
        
        if inefficient_sessions:
            return {
                'count': len(inefficient_sessions),
                'sessions': inefficient_sessions,
                'estimated_waste': total_inefficiency
            }
        
        return None
    
    def _detect_token_bloat_pattern(self, sessions: List[SessionAnalysis]) -> Optional[Dict]:
        """Detect context bloat patterns."""
        bloated_sessions = []
        total_bloat = 0
        
        avg_tokens_per_msg = []
        for session in sessions:
            if session.total_messages > 0:
                ratio = session.total_tokens / session.total_messages
                avg_tokens_per_msg.append(ratio)
        
        if not avg_tokens_per_msg:
            return None
        
        # Calculate threshold as 1.5x the median
        median_ratio = statistics.median(avg_tokens_per_msg)
        bloat_threshold = median_ratio * 1.5
        
        for session in sessions:
            if session.total_messages > 0:
                ratio = session.total_tokens / session.total_messages
                if ratio > bloat_threshold and ratio > 500:  # Absolute minimum threshold
                    bloated_sessions.append(session.session_id)
                    # Estimate bloat as excess tokens over median
                    excess_tokens = session.total_tokens - (session.total_messages * median_ratio)
                    total_bloat += max(0, int(excess_tokens))
        
        if bloated_sessions:
            return {
                'count': len(bloated_sessions),
                'sessions': bloated_sessions,
                'estimated_waste': total_bloat
            }
        
        return None
    
    def _generate_optimization_recommendations(self, 
                                            cache_efficiency: CacheEfficiencyMetrics,
                                            usage_insights: TokenUsageInsights,
                                            waste_patterns: List[TokenWastePattern]) -> List[str]:
        """Generate optimization recommendations based on analysis."""
        recommendations = []
        
        # Cache efficiency recommendations
        if cache_efficiency.overall_cache_hit_ratio < 0.6:
            recommendations.append(
                f"Improve cache efficiency (currently {cache_efficiency.overall_cache_hit_ratio:.1%}). "
                "Consider organizing context to maximize cache reuse."
            )
        
        # Token usage recommendations
        if usage_insights.average_tokens_per_message > 500:
            recommendations.append(
                f"High token usage per message ({usage_insights.average_tokens_per_message:.0f} tokens). "
                "Consider breaking down complex requests and cleaning context regularly."
            )
        
        # Waste pattern recommendations
        high_impact_patterns = [p for p in waste_patterns if p.severity_level == "High"]
        if high_impact_patterns:
            recommendations.append(
                f"Address high-impact waste patterns: {', '.join(p.pattern_type for p in high_impact_patterns)}. "
                f"Potential savings: {sum(p.potential_savings_percent for p in high_impact_patterns):.0f}%"
            )
        
        # Session length recommendations
        if usage_insights.session_length_correlation < -0.3:
            recommendations.append(
                "Long sessions appear to be less token-efficient. "
                "Consider breaking work into shorter, focused sessions."
            )
        
        # Repetitive operations recommendations
        if len(usage_insights.repetitive_operations) > 5:
            recommendations.append(
                f"Found {len(usage_insights.repetitive_operations)} repetitive operation patterns. "
                "Consider creating templates or improving workflow organization."
            )
        
        return recommendations
    
    def _estimate_monthly_savings(self, 
                                cache_efficiency: CacheEfficiencyMetrics,
                                usage_insights: TokenUsageInsights,
                                waste_patterns: List[TokenWastePattern]) -> Dict[str, float]:
        """Estimate potential monthly savings from optimizations."""
        total_waste_tokens = sum(p.estimated_waste_tokens for p in waste_patterns)
        
        # Extrapolate to monthly usage (rough estimate)
        monthly_multiplier = 30  # Assume analysis covers ~1 day worth
        monthly_waste_tokens = total_waste_tokens * monthly_multiplier
        
        # Estimate cost savings (assuming $0.01 per 1K tokens - adjust based on actual pricing)
        token_cost_per_1k = 0.01
        monthly_token_cost_savings = (monthly_waste_tokens / 1000) * token_cost_per_1k
        
        # Cache efficiency savings
        cache_savings_tokens = cache_efficiency.total_tokens * cache_efficiency.estimated_cost_savings_percent / 100
        monthly_cache_savings = (cache_savings_tokens * monthly_multiplier / 1000) * token_cost_per_1k
        
        return {
            'waste_elimination_tokens': monthly_waste_tokens,
            'waste_elimination_cost': monthly_token_cost_savings,
            'cache_efficiency_tokens': cache_savings_tokens * monthly_multiplier,
            'cache_efficiency_cost': monthly_cache_savings,
            'total_potential_tokens': monthly_waste_tokens + (cache_savings_tokens * monthly_multiplier),
            'total_potential_cost': monthly_token_cost_savings + monthly_cache_savings
        }