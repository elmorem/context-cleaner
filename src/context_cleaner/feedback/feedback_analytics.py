"""
Feedback Analytics and Aggregation System

Advanced analytics for processing and analyzing user feedback data to extract
actionable insights for Context Cleaner improvement and optimization.
"""

import json
import logging
import statistics
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
# Remove unused pandas/numpy imports that create unnecessary dependencies

from .user_feedback_collector import UserFeedbackCollector
from .feedback_collector import FeedbackCollector
from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


class FeedbackAnalytics:
    """
    Advanced analytics engine for feedback data analysis and insight generation.
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize feedback analytics."""
        self.config = config or ContextCleanerConfig.from_env()
        
        # Initialize feedback collectors
        self.user_feedback = UserFeedbackCollector(config)
        self.structured_feedback = FeedbackCollector(config)
        
        # Analytics cache
        self._analytics_cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_ttl_minutes = 30
        
        logger.info("Feedback analytics initialized")
    
    def generate_comprehensive_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive analytics across all feedback sources."""
        cache_key = f"comprehensive_{days}d"
        
        # Check cache
        if self._is_cached(cache_key):
            return self._analytics_cache[cache_key]
        
        try:
            # Collect data from all sources
            user_summary = self.user_feedback.get_feedback_summary()
            structured_summary = self.structured_feedback.get_feedback_summary(days)
            
            # Performance trend analysis
            performance_trends = self._analyze_performance_trends(days)
            
            # User experience analysis
            ux_analysis = self._analyze_user_experience(user_summary, structured_summary)
            
            # Feature usage analysis
            feature_analysis = self._analyze_feature_usage(user_summary, structured_summary)
            
            # Issue priority analysis
            issue_analysis = self._analyze_issues_and_priorities(structured_summary)
            
            # Optimization effectiveness
            optimization_analysis = self._analyze_optimization_effectiveness(
                user_summary, 
                structured_summary
            )
            
            # Generate insights and recommendations
            insights = self._generate_insights(
                performance_trends,
                ux_analysis,
                feature_analysis,
                issue_analysis,
                optimization_analysis
            )
            
            analytics = {
                'analysis_period_days': days,
                'generated_at': datetime.now().isoformat(),
                'data_summary': {
                    'user_feedback_events': user_summary.get('events_last_24h', 0),
                    'structured_feedback_items': structured_summary.get('total_items', 0),
                    'total_data_points': user_summary.get('events_last_24h', 0) + structured_summary.get('total_items', 0)
                },
                'performance_trends': performance_trends,
                'user_experience': ux_analysis,
                'feature_usage': feature_analysis,
                'issue_analysis': issue_analysis,
                'optimization_effectiveness': optimization_analysis,
                'insights': insights,
                'recommendations': self._generate_recommendations(insights),
                'health_score': self._calculate_overall_health_score(
                    performance_trends,
                    ux_analysis,
                    issue_analysis
                )
            }
            
            # Cache results
            self._cache_analytics(cache_key, analytics)
            
            return analytics
        
        except Exception as e:
            logger.error(f"Failed to generate comprehensive analytics: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat(),
                'analysis_period_days': days
            }
    
    def _analyze_performance_trends(self, days: int) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        try:
            user_summary = self.user_feedback.get_feedback_summary()
            performance_impact = user_summary.get('performance_impact', {})
            
            # Memory trends
            avg_memory_saved = performance_impact.get('avg_memory_saved_mb', 0)
            memory_trend = self._categorize_performance_metric(avg_memory_saved, 'memory')
            
            # CPU trends  
            avg_cpu_improvement = performance_impact.get('avg_cpu_improvement_percent', 0)
            cpu_trend = self._categorize_performance_metric(avg_cpu_improvement, 'cpu')
            
            # Overall performance score
            performance_score = self._calculate_performance_score(
                avg_memory_saved, 
                avg_cpu_improvement
            )
            
            return {
                'memory': {
                    'avg_saved_mb': avg_memory_saved,
                    'trend': memory_trend,
                    'significance': 'high' if avg_memory_saved > 10 else 'medium' if avg_memory_saved > 5 else 'low'
                },
                'cpu': {
                    'avg_improvement_percent': avg_cpu_improvement,
                    'trend': cpu_trend,
                    'significance': 'high' if avg_cpu_improvement > 2 else 'medium' if avg_cpu_improvement > 1 else 'low'
                },
                'overall_performance_score': performance_score,
                'measurement_count': performance_impact.get('measurements_count', 0),
                'reliability': 'high' if performance_impact.get('measurements_count', 0) > 20 else 'medium'
            }
            
        except Exception as e:
            logger.warning(f"Performance trend analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_user_experience(self, user_summary: Dict[str, Any], 
                               structured_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user experience metrics."""
        try:
            # Satisfaction scores
            avg_satisfaction = structured_summary.get('metrics', {}).get('avg_satisfaction_rating')
            satisfaction_analysis = {
                'average_rating': avg_satisfaction,
                'category': self._categorize_satisfaction(avg_satisfaction) if avg_satisfaction else 'unknown',
                'has_data': avg_satisfaction is not None
            }
            
            # Error rates
            error_events = 0
            success_events = 0
            
            for feature, count in user_summary.get('top_features', {}).items():
                if 'error' in feature.lower() or 'failed' in feature.lower():
                    error_events += count
                else:
                    success_events += count
            
            error_rate = error_events / (error_events + success_events) if (error_events + success_events) > 0 else 0
            
            # Usage consistency
            session_duration = user_summary.get('session_duration_hours', 0)
            usage_pattern = self._categorize_usage_pattern(session_duration)
            
            return {
                'satisfaction': satisfaction_analysis,
                'error_rate': {
                    'rate': error_rate,
                    'category': 'high' if error_rate > 0.1 else 'medium' if error_rate > 0.05 else 'low',
                    'total_errors': error_events,
                    'total_successes': success_events
                },
                'usage_pattern': {
                    'session_duration_hours': session_duration,
                    'pattern': usage_pattern,
                    'engagement_level': self._categorize_engagement(session_duration)
                },
                'overall_ux_score': self._calculate_ux_score(
                    avg_satisfaction,
                    error_rate,
                    session_duration
                )
            }
            
        except Exception as e:
            logger.warning(f"User experience analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_feature_usage(self, user_summary: Dict[str, Any], 
                             structured_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze feature usage patterns."""
        try:
            # Top features from user feedback
            user_features = user_summary.get('top_features', {})
            
            # Most used categories from structured feedback
            structured_categories = structured_summary.get('most_used_features', {})
            
            # Combine and analyze
            all_features = {}
            all_features.update(user_features)
            for feature, count in structured_categories.items():
                all_features[feature] = all_features.get(feature, 0) + count
            
            # Sort by usage
            sorted_features = sorted(all_features.items(), key=lambda x: x[1], reverse=True)
            
            # Calculate feature diversity
            total_usage = sum(all_features.values())
            feature_diversity = len(all_features) if total_usage > 0 else 0
            
            # Identify dominant features (>30% of usage)
            dominant_features = [
                feature for feature, count in sorted_features 
                if count / total_usage > 0.3
            ] if total_usage > 0 else []
            
            return {
                'top_features': dict(sorted_features[:10]),
                'total_feature_usage': total_usage,
                'feature_diversity': feature_diversity,
                'dominant_features': dominant_features,
                'usage_distribution': {
                    'concentrated': len(dominant_features) > 0,
                    'diverse': feature_diversity > 5,
                    'balanced': 0.1 <= (dominant_features[0][1] / total_usage if dominant_features else 0) <= 0.5
                },
                'adoption_metrics': {
                    'active_features': len([f for f, c in all_features.items() if c > 0]),
                    'feature_penetration': feature_diversity / 10 if feature_diversity <= 10 else 1.0  # Assuming 10 total features
                }
            }
            
        except Exception as e:
            logger.warning(f"Feature usage analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_issues_and_priorities(self, structured_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze issues and their priorities."""
        try:
            total_items = structured_summary.get('total_items', 0)
            critical_issues = structured_summary.get('critical_issues', 0)
            
            by_severity = structured_summary.get('summary', {}).get('by_severity', {})
            by_type = structured_summary.get('summary', {}).get('by_type', {})
            
            # Calculate issue distribution
            issue_types = ['performance_issue', 'bug_report']
            total_issues = sum(by_type.get(issue_type, 0) for issue_type in issue_types)
            
            positive_types = ['productivity_improvement', 'user_satisfaction']
            total_positive = sum(by_type.get(pos_type, 0) for pos_type in positive_types)
            
            # Priority analysis
            priority_score = self._calculate_priority_score(by_severity)
            
            # Issue velocity (how quickly issues are being reported)
            issue_velocity = total_issues / 7 if total_items > 0 else 0  # per day
            
            return {
                'issue_summary': {
                    'total_issues': total_issues,
                    'critical_issues': critical_issues,
                    'positive_feedback': total_positive,
                    'issue_ratio': total_issues / total_items if total_items > 0 else 0
                },
                'severity_distribution': by_severity,
                'priority_score': priority_score,
                'issue_velocity': issue_velocity,
                'health_indicators': {
                    'critical_alert': critical_issues > 0,
                    'high_issue_rate': (total_issues / total_items) > 0.5 if total_items > 0 else False,
                    'positive_trend': total_positive > total_issues
                },
                'priority_recommendations': self._generate_priority_recommendations(
                    critical_issues,
                    total_issues,
                    by_severity
                )
            }
            
        except Exception as e:
            logger.warning(f"Issue analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_optimization_effectiveness(self, user_summary: Dict[str, Any], 
                                          structured_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze optimization effectiveness."""
        try:
            # Optimization counts
            by_type = structured_summary.get('summary', {}).get('by_type', {})
            optimizations = by_type.get('optimization_result', 0)
            improvements = by_type.get('productivity_improvement', 0)
            performance_issues = by_type.get('performance_issue', 0)
            
            # Effectiveness ratio
            total_optimization_events = optimizations + improvements + performance_issues
            success_rate = (optimizations + improvements) / total_optimization_events if total_optimization_events > 0 else 0
            
            # Performance impact from user feedback
            performance_impact = user_summary.get('performance_impact', {})
            avg_memory_saved = performance_impact.get('avg_memory_saved_mb', 0)
            avg_cpu_improvement = performance_impact.get('avg_cpu_improvement_percent', 0)
            
            # Calculate optimization score
            optimization_score = self._calculate_optimization_score(
                success_rate,
                avg_memory_saved,
                avg_cpu_improvement
            )
            
            return {
                'success_metrics': {
                    'optimization_events': optimizations,
                    'improvement_events': improvements,
                    'issue_events': performance_issues,
                    'success_rate': success_rate
                },
                'performance_impact': {
                    'memory_saved_mb': avg_memory_saved,
                    'cpu_improved_percent': avg_cpu_improvement,
                    'impact_score': (avg_memory_saved * 0.1) + (avg_cpu_improvement * 2)  # Weighted score
                },
                'optimization_score': optimization_score,
                'effectiveness_category': self._categorize_effectiveness(optimization_score),
                'trends': {
                    'improving': improvements > performance_issues,
                    'stable': abs(improvements - performance_issues) <= 2,
                    'needs_attention': performance_issues > improvements * 2
                }
            }
            
        except Exception as e:
            logger.warning(f"Optimization effectiveness analysis failed: {e}")
            return {'error': str(e)}
    
    def _generate_insights(self, performance_trends: Dict[str, Any],
                          ux_analysis: Dict[str, Any],
                          feature_analysis: Dict[str, Any],
                          issue_analysis: Dict[str, Any],
                          optimization_analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable insights from all analyses."""
        insights = []
        
        try:
            # Performance insights
            if performance_trends.get('overall_performance_score', 0) > 7:
                insights.append("Performance optimizations are highly effective")
            elif performance_trends.get('overall_performance_score', 0) < 4:
                insights.append("Performance optimization system needs significant improvement")
            
            # User experience insights
            ux_score = ux_analysis.get('overall_ux_score', 5)
            if ux_score > 8:
                insights.append("User experience is excellent - high satisfaction and low error rates")
            elif ux_score < 5:
                insights.append("User experience needs improvement - consider UX redesign")
            
            # Feature usage insights
            usage_dist = feature_analysis.get('usage_distribution', {})
            if usage_dist.get('concentrated'):
                insights.append("Feature usage is concentrated - consider promoting underused features")
            elif usage_dist.get('diverse'):
                insights.append("Users are actively using diverse features - good adoption")
            
            # Issue insights
            health_indicators = issue_analysis.get('health_indicators', {})
            if health_indicators.get('critical_alert'):
                insights.append("Critical issues detected - immediate attention required")
            elif health_indicators.get('positive_trend'):
                insights.append("More positive feedback than issues - system performing well")
            
            # Optimization insights
            opt_category = optimization_analysis.get('effectiveness_category', 'unknown')
            if opt_category == 'excellent':
                insights.append("Optimization system is highly effective - maintain current approach")
            elif opt_category == 'poor':
                insights.append("Optimization effectiveness is poor - review algorithms and thresholds")
            
            # Meta insights
            total_data = performance_trends.get('measurement_count', 0) + issue_analysis.get('issue_summary', {}).get('total_issues', 0)
            if total_data < 10:
                insights.append("Limited feedback data available - encourage more user engagement")
            elif total_data > 100:
                insights.append("Rich feedback data available - high confidence in insights")
        
        except Exception as e:
            logger.warning(f"Insight generation failed: {e}")
            insights.append(f"Error generating insights: {e}")
        
        return insights if insights else ["Insufficient data for meaningful insights"]
    
    def _generate_recommendations(self, insights: List[str]) -> List[Dict[str, Any]]:
        """Generate specific actionable recommendations."""
        recommendations = []
        
        # Map insights to recommendations
        insight_recommendations = {
            "performance optimization system needs significant improvement": {
                "action": "Review and tune optimization algorithms",
                "priority": "high",
                "timeline": "immediate",
                "specifics": ["Check memory/CPU thresholds", "Review optimization triggers", "Validate measurement accuracy"]
            },
            "user experience needs improvement": {
                "action": "Conduct UX review and improvement initiative", 
                "priority": "high",
                "timeline": "2-4 weeks",
                "specifics": ["Analyze error patterns", "Simplify complex workflows", "Improve feedback mechanisms"]
            },
            "critical issues detected": {
                "action": "Address critical issues immediately",
                "priority": "critical",
                "timeline": "immediate",
                "specifics": ["Review critical issue reports", "Implement hotfixes", "Monitor closely"]
            },
            "feature usage is concentrated": {
                "action": "Promote underused features and improve discoverability",
                "priority": "medium",
                "timeline": "4-8 weeks", 
                "specifics": ["Add feature tutorials", "Improve onboarding", "Consider feature consolidation"]
            },
            "limited feedback data available": {
                "action": "Increase user engagement and feedback collection",
                "priority": "medium",
                "timeline": "ongoing",
                "specifics": ["Improve feedback UX", "Add feedback prompts", "Incentivize participation"]
            }
        }
        
        # Generate recommendations based on insights
        for insight in insights:
            for key_phrase, rec_details in insight_recommendations.items():
                if key_phrase.lower() in insight.lower():
                    recommendations.append({
                        "insight": insight,
                        "recommendation": rec_details["action"],
                        "priority": rec_details["priority"],
                        "timeline": rec_details["timeline"],
                        "specific_actions": rec_details["specifics"]
                    })
                    break
        
        # Add default recommendation if none matched
        if not recommendations:
            recommendations.append({
                "insight": "General system monitoring",
                "recommendation": "Continue monitoring and data collection",
                "priority": "low",
                "timeline": "ongoing",
                "specific_actions": ["Maintain current feedback systems", "Review monthly analytics"]
            })
        
        return recommendations
    
    # Helper methods for calculations and categorizations
    
    def _categorize_performance_metric(self, value: float, metric_type: str) -> str:
        """Categorize performance metric as improving/stable/declining."""
        if metric_type == 'memory':
            if value > 10:
                return 'significantly_improving'
            elif value > 5:
                return 'improving'
            elif value > -5:
                return 'stable'
            else:
                return 'declining'
        
        elif metric_type == 'cpu':
            if value > 2:
                return 'significantly_improving'
            elif value > 1:
                return 'improving'
            elif value > -1:
                return 'stable'
            else:
                return 'declining'
        
        return 'unknown'
    
    def _calculate_performance_score(self, memory_saved: float, cpu_improvement: float) -> int:
        """Calculate overall performance score (0-10)."""
        memory_score = min(10, max(0, memory_saved / 2))  # 20MB = 10 points
        cpu_score = min(10, max(0, cpu_improvement * 2))  # 5% = 10 points
        return int((memory_score + cpu_score) / 2)
    
    def _categorize_satisfaction(self, rating: Optional[float]) -> str:
        """Categorize satisfaction rating."""
        if rating is None:
            return 'unknown'
        elif rating >= 4.5:
            return 'excellent'
        elif rating >= 4.0:
            return 'good'
        elif rating >= 3.0:
            return 'acceptable'
        elif rating >= 2.0:
            return 'poor'
        else:
            return 'critical'
    
    def _categorize_usage_pattern(self, hours: float) -> str:
        """Categorize usage pattern based on session duration."""
        if hours < 0.5:
            return 'brief'
        elif hours < 2:
            return 'short'
        elif hours < 6:
            return 'medium'
        elif hours < 12:
            return 'long'
        else:
            return 'extended'
    
    def _categorize_engagement(self, hours: float) -> str:
        """Categorize user engagement level."""
        if hours < 0.25:
            return 'low'
        elif hours < 2:
            return 'moderate'
        elif hours < 8:
            return 'high'
        else:
            return 'very_high'
    
    def _calculate_ux_score(self, satisfaction: Optional[float], error_rate: float, 
                           session_duration: float) -> int:
        """Calculate overall UX score (0-10)."""
        # Satisfaction component (0-10)
        sat_score = (satisfaction * 2) if satisfaction else 5
        
        # Error rate component (0-10, inverted)
        error_score = 10 * (1 - min(1, error_rate * 10))
        
        # Engagement component (0-10)
        engagement_score = min(10, session_duration * 2)
        
        return int((sat_score + error_score + engagement_score) / 3)
    
    def _calculate_priority_score(self, by_severity: Dict[str, int]) -> int:
        """Calculate priority score based on severity distribution."""
        weights = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1}
        total_weighted = sum(by_severity.get(sev, 0) * weight for sev, weight in weights.items())
        total_items = sum(by_severity.values()) if by_severity else 1
        return int(total_weighted / total_items) if total_items > 0 else 0
    
    def _generate_priority_recommendations(self, critical: int, total_issues: int, 
                                         by_severity: Dict[str, int]) -> List[str]:
        """Generate priority-based recommendations."""
        recommendations = []
        
        if critical > 0:
            recommendations.append(f"Address {critical} critical issues immediately")
        
        high_issues = by_severity.get('high', 0)
        if high_issues > 5:
            recommendations.append(f"Plan sprint to address {high_issues} high-priority issues")
        
        if total_issues > 20:
            recommendations.append("Consider increasing development resources for issue resolution")
        
        return recommendations if recommendations else ["Continue current issue management approach"]
    
    def _calculate_optimization_score(self, success_rate: float, memory_saved: float, 
                                    cpu_improvement: float) -> int:
        """Calculate optimization effectiveness score (0-10)."""
        success_component = success_rate * 10
        impact_component = min(10, (memory_saved * 0.2) + (cpu_improvement))
        return int((success_component + impact_component) / 2)
    
    def _categorize_effectiveness(self, score: int) -> str:
        """Categorize optimization effectiveness."""
        if score >= 9:
            return 'excellent'
        elif score >= 7:
            return 'good'
        elif score >= 5:
            return 'acceptable'
        elif score >= 3:
            return 'needs_improvement'
        else:
            return 'poor'
    
    def _calculate_overall_health_score(self, performance_trends: Dict[str, Any],
                                      ux_analysis: Dict[str, Any],
                                      issue_analysis: Dict[str, Any]) -> int:
        """Calculate overall system health score (0-100)."""
        try:
            performance_score = performance_trends.get('overall_performance_score', 5) * 10
            ux_score = ux_analysis.get('overall_ux_score', 5) * 10
            
            # Issue score (inverted - fewer issues = higher score)
            issue_ratio = issue_analysis.get('issue_summary', {}).get('issue_ratio', 0.5)
            issue_score = (1 - min(1, issue_ratio)) * 100
            
            # Weighted average
            health_score = int((performance_score * 0.4) + (ux_score * 0.4) + (issue_score * 0.2))
            return max(0, min(100, health_score))
        
        except Exception:
            return 50  # Default neutral score
    
    def _is_cached(self, cache_key: str) -> bool:
        """Check if analytics result is cached and valid."""
        if cache_key not in self._analytics_cache:
            return False
        
        expiry = self._cache_expiry.get(cache_key)
        if not expiry or datetime.now() > expiry:
            # Remove expired cache
            self._analytics_cache.pop(cache_key, None)
            self._cache_expiry.pop(cache_key, None)
            return False
        
        return True
    
    def _cache_analytics(self, cache_key: str, analytics: Dict[str, Any]):
        """Cache analytics results."""
        self._analytics_cache[cache_key] = analytics
        self._cache_expiry[cache_key] = datetime.now() + timedelta(minutes=self._cache_ttl_minutes)
    
    def export_analytics_report(self, days: int = 30, format_type: str = 'json') -> str:
        """Export comprehensive analytics report."""
        analytics = self.generate_comprehensive_analytics(days)
        
        if format_type == 'json':
            return json.dumps(analytics, indent=2, default=str)
        
        elif format_type == 'summary':
            # Generate human-readable summary
            summary = f"""
Context Cleaner Feedback Analytics Report
Generated: {analytics.get('generated_at', 'Unknown')}
Analysis Period: {days} days

OVERALL HEALTH SCORE: {analytics.get('health_score', 'N/A')}/100

PERFORMANCE TRENDS:
- Memory Savings: {analytics.get('performance_trends', {}).get('memory', {}).get('avg_saved_mb', 'N/A')} MB avg
- CPU Improvement: {analytics.get('performance_trends', {}).get('cpu', {}).get('avg_improvement_percent', 'N/A')}% avg
- Performance Score: {analytics.get('performance_trends', {}).get('overall_performance_score', 'N/A')}/10

USER EXPERIENCE:
- UX Score: {analytics.get('user_experience', {}).get('overall_ux_score', 'N/A')}/10
- Error Rate: {analytics.get('user_experience', {}).get('error_rate', {}).get('rate', 'N/A')}
- Engagement: {analytics.get('user_experience', {}).get('usage_pattern', {}).get('engagement_level', 'N/A')}

KEY INSIGHTS:
"""
            for insight in analytics.get('insights', []):
                summary += f"- {insight}\n"
            
            summary += "\nRECOMMENDATIONS:\n"
            for rec in analytics.get('recommendations', []):
                summary += f"- [{rec.get('priority', 'unknown').upper()}] {rec.get('recommendation', 'N/A')}\n"
            
            return summary
        
        else:
            raise ValueError(f"Unsupported format type: {format_type}")


def main():
    """CLI interface for feedback analytics."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Context Cleaner Feedback Analytics')
    parser.add_argument('--days', type=int, default=30, help='Analysis period in days')
    parser.add_argument('--format', choices=['json', 'summary'], default='summary', help='Output format')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    analytics = FeedbackAnalytics()
    report = analytics.export_analytics_report(args.days, args.format)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Analytics report saved to: {args.output}")
    else:
        print(report)


if __name__ == '__main__':
    main()