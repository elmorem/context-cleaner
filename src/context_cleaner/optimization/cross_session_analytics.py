"""
Cross-Session Analytics for Multi-Session Pattern Correlation

This module provides advanced analytics that correlate patterns across
multiple sessions to identify optimization opportunities and user preferences.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import json
import statistics
try:
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    # Provide fallback implementations
    class KMeans:
        def __init__(self, *args, **kwargs):
            pass
        def fit_predict(self, data):
            return [0] * len(data) if data else []
    
    class StandardScaler:
        def __init__(self):
            pass
        def fit_transform(self, data):
            return data if data else []
    
    np = None

from ..cache import (
    CorrelationInsights, CrossSessionPattern, SessionCluster, 
    LongTermTrend, SessionAnalysis, UsagePatternSummary,
    TokenAnalysisSummary, TemporalInsights
)


@dataclass
class SessionMetrics:
    """Metrics for a single session."""
    session_id: str
    timestamp: datetime
    duration_minutes: float
    file_count: int
    token_count: int
    efficiency_score: float
    focus_score: float
    workflow_type: str
    tools_used: List[str]
    file_types: List[str]
    optimization_actions: List[str]


@dataclass 
class PatternEvolution:
    """How patterns evolve over time."""
    pattern_id: str
    first_seen: datetime
    last_seen: datetime
    frequency_trend: List[float]
    effectiveness_trend: List[float]
    adaptation_score: float
    stability_score: float


@dataclass
class WorkflowTemplate:
    """Reusable workflow template based on patterns."""
    template_id: str
    name: str
    description: str
    common_files: List[str]
    typical_sequence: List[str]
    optimization_strategy: Dict[str, Any]
    success_rate: float
    usage_frequency: float


@dataclass
class CrossSessionInsights:
    """Comprehensive cross-session analysis results."""
    analysis_timestamp: datetime
    sessions_analyzed: int
    time_span_days: int
    
    # Pattern correlations
    correlation_insights: CorrelationInsights
    pattern_evolution: List[PatternEvolution]
    workflow_templates: List[WorkflowTemplate]
    
    # Performance trends
    efficiency_trends: Dict[str, List[float]]
    optimization_effectiveness: Dict[str, float]
    user_adaptation_score: float
    
    # Predictive insights
    predicted_patterns: List[str]
    optimization_recommendations: List[Dict[str, Any]]
    automation_opportunities: List[Dict[str, Any]]
    
    # Session clustering
    session_clusters: List[SessionCluster]
    cluster_characteristics: Dict[str, Dict[str, Any]]


class CrossSessionAnalyticsEngine:
    """
    Advanced analytics engine for cross-session pattern correlation
    and multi-session optimization insights.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the cross-session analytics engine."""
        self.storage_path = storage_path or Path.home() / ".context_cleaner" / "cross_session"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._session_cache: Dict[str, SessionMetrics] = {}
        self._pattern_history: Dict[str, List[Any]] = defaultdict(list)
        self._analysis_cache: Dict[str, CrossSessionInsights] = {}
    
    async def analyze_cross_session_patterns(
        self,
        sessions_data: List[Any],
        correlation_insights: CorrelationInsights,
        time_window_days: int = 30,
        min_sessions: int = 5
    ) -> CrossSessionInsights:
        """
        Perform comprehensive cross-session pattern analysis.
        
        Args:
            sessions_data: List of session analysis results
            correlation_insights: Existing correlation insights
            time_window_days: Time window for analysis
            min_sessions: Minimum sessions required for reliable analysis
            
        Returns:
            Comprehensive cross-session insights
        """
        if len(sessions_data) < min_sessions:
            return self._create_minimal_insights(sessions_data, correlation_insights)
        
        # Convert sessions to metrics
        session_metrics = await self._extract_session_metrics(sessions_data)
        
        # Filter to time window
        cutoff_date = datetime.now() - timedelta(days=time_window_days)
        recent_sessions = [
            s for s in session_metrics 
            if s.timestamp >= cutoff_date
        ]
        
        if len(recent_sessions) < min_sessions:
            recent_sessions = session_metrics[-min_sessions:]
        
        # Perform various analyses
        pattern_evolution = await self._analyze_pattern_evolution(recent_sessions)
        workflow_templates = await self._extract_workflow_templates(recent_sessions)
        efficiency_trends = await self._calculate_efficiency_trends(recent_sessions)
        optimization_effectiveness = await self._measure_optimization_effectiveness(recent_sessions)
        user_adaptation_score = self._calculate_adaptation_score(recent_sessions)
        predicted_patterns = await self._predict_future_patterns(recent_sessions, pattern_evolution)
        optimization_recommendations = await self._generate_cross_session_recommendations(
            recent_sessions, pattern_evolution, efficiency_trends
        )
        automation_opportunities = await self._identify_automation_opportunities(
            workflow_templates, recent_sessions
        )
        session_clusters = await self._cluster_sessions(recent_sessions)
        cluster_characteristics = await self._analyze_cluster_characteristics(
            session_clusters, recent_sessions
        )
        
        insights = CrossSessionInsights(
            analysis_timestamp=datetime.now(),
            sessions_analyzed=len(recent_sessions),
            time_span_days=min(time_window_days, (datetime.now() - recent_sessions[0].timestamp).days),
            correlation_insights=correlation_insights,
            pattern_evolution=pattern_evolution,
            workflow_templates=workflow_templates,
            efficiency_trends=efficiency_trends,
            optimization_effectiveness=optimization_effectiveness,
            user_adaptation_score=user_adaptation_score,
            predicted_patterns=predicted_patterns,
            optimization_recommendations=optimization_recommendations,
            automation_opportunities=automation_opportunities,
            session_clusters=session_clusters,
            cluster_characteristics=cluster_characteristics
        )
        
        # Cache insights
        cache_key = f"insights_{datetime.now().strftime('%Y%m%d')}"
        self._analysis_cache[cache_key] = insights
        
        # Persist insights
        await self._persist_insights(insights)
        
        return insights
    
    async def _extract_session_metrics(self, sessions_data: List[Any]) -> List[SessionMetrics]:
        """Extract standardized metrics from session data."""
        metrics = []
        
        for session in sessions_data:
            try:
                # Extract basic session info
                session_id = getattr(session, 'session_id', f"session_{len(metrics)}")
                timestamp = getattr(session, 'timestamp', datetime.now())
                
                # Calculate session duration (rough estimate)
                duration_minutes = getattr(session, 'duration_minutes', 60.0)
                
                # Extract file and token info
                file_count = len(getattr(session, 'files_accessed', []))
                token_count = getattr(session, 'total_tokens', 0)
                
                # Extract or estimate scores
                efficiency_score = getattr(session, 'efficiency_score', 0.7)
                focus_score = getattr(session, 'focus_score', 0.6)
                
                # Extract workflow info
                workflow_type = getattr(session, 'workflow_type', 'general')
                tools_used = getattr(session, 'tools_used', ['read', 'edit'])
                file_types = getattr(session, 'file_types', ['.py'])
                optimization_actions = getattr(session, 'optimization_actions', [])
                
                metrics.append(SessionMetrics(
                    session_id=session_id,
                    timestamp=timestamp,
                    duration_minutes=duration_minutes,
                    file_count=file_count,
                    token_count=token_count,
                    efficiency_score=efficiency_score,
                    focus_score=focus_score,
                    workflow_type=workflow_type,
                    tools_used=tools_used,
                    file_types=file_types,
                    optimization_actions=optimization_actions
                ))
                
            except Exception:
                # Skip malformed sessions
                continue
        
        return sorted(metrics, key=lambda m: m.timestamp)
    
    async def _analyze_pattern_evolution(self, sessions: List[SessionMetrics]) -> List[PatternEvolution]:
        """Analyze how patterns evolve over time."""
        pattern_evolutions = []
        
        # Group sessions by workflow type to track evolution
        workflow_sessions = defaultdict(list)
        for session in sessions:
            workflow_sessions[session.workflow_type].append(session)
        
        for workflow_type, workflow_sessions_list in workflow_sessions.items():
            if len(workflow_sessions_list) < 3:
                continue
                
            # Calculate frequency trend (sessions per week)
            weeks = []
            session_counts = []
            
            # Group by week
            weekly_sessions = defaultdict(int)
            for session in workflow_sessions_list:
                week_key = session.timestamp.strftime('%Y-W%U')
                weekly_sessions[week_key] += 1
            
            # Create frequency trend
            sorted_weeks = sorted(weekly_sessions.keys())
            frequency_trend = [weekly_sessions[week] for week in sorted_weeks[-8:]]  # Last 8 weeks
            
            # Calculate effectiveness trend
            effectiveness_scores = [s.efficiency_score for s in workflow_sessions_list[-8:]]
            effectiveness_trend = effectiveness_scores
            
            # Calculate adaptation and stability scores
            if len(effectiveness_scores) > 1:
                adaptation_score = self._calculate_trend_slope(effectiveness_scores)
                stability_score = 1.0 - statistics.stdev(effectiveness_scores) if len(effectiveness_scores) > 1 else 1.0
            else:
                adaptation_score = 0.0
                stability_score = 1.0
            
            pattern_evolutions.append(PatternEvolution(
                pattern_id=f"workflow_{workflow_type}",
                first_seen=workflow_sessions_list[0].timestamp,
                last_seen=workflow_sessions_list[-1].timestamp,
                frequency_trend=frequency_trend,
                effectiveness_trend=effectiveness_trend,
                adaptation_score=adaptation_score,
                stability_score=stability_score
            ))
        
        return pattern_evolutions
    
    async def _extract_workflow_templates(self, sessions: List[SessionMetrics]) -> List[WorkflowTemplate]:
        """Extract reusable workflow templates from session patterns."""
        templates = []
        
        # Group sessions by workflow type
        workflow_groups = defaultdict(list)
        for session in sessions:
            workflow_groups[session.workflow_type].append(session)
        
        for workflow_type, workflow_sessions in workflow_groups.items():
            if len(workflow_sessions) < 3:
                continue
            
            # Find common patterns
            all_tools = []
            all_file_types = []
            all_optimization_actions = []
            
            for session in workflow_sessions:
                all_tools.extend(session.tools_used)
                all_file_types.extend(session.file_types)
                all_optimization_actions.extend(session.optimization_actions)
            
            # Get most common elements
            common_tools = [tool for tool, count in Counter(all_tools).most_common(5)]
            common_file_types = [ft for ft, count in Counter(all_file_types).most_common(3)]
            common_actions = [action for action, count in Counter(all_optimization_actions).most_common(3)]
            
            # Calculate success rate (based on efficiency scores)
            efficiency_scores = [s.efficiency_score for s in workflow_sessions]
            success_rate = statistics.mean(efficiency_scores) if efficiency_scores else 0.5
            
            # Calculate usage frequency (sessions per week)
            days_span = (workflow_sessions[-1].timestamp - workflow_sessions[0].timestamp).days or 1
            usage_frequency = len(workflow_sessions) / (days_span / 7.0)
            
            # Create optimization strategy
            optimization_strategy = {
                "preferred_tools": common_tools,
                "target_efficiency": success_rate * 1.1,  # Target 10% improvement
                "common_optimizations": common_actions,
                "typical_session_length": statistics.mean([s.duration_minutes for s in workflow_sessions])
            }
            
            templates.append(WorkflowTemplate(
                template_id=f"template_{workflow_type}",
                name=f"{workflow_type.title()} Workflow",
                description=f"Common {workflow_type} workflow pattern with {len(workflow_sessions)} occurrences",
                common_files=common_file_types,
                typical_sequence=common_tools,
                optimization_strategy=optimization_strategy,
                success_rate=success_rate,
                usage_frequency=usage_frequency
            ))
        
        return sorted(templates, key=lambda t: t.usage_frequency, reverse=True)
    
    async def _calculate_efficiency_trends(self, sessions: List[SessionMetrics]) -> Dict[str, List[float]]:
        """Calculate efficiency trends over time."""
        trends = {
            "overall_efficiency": [],
            "focus_improvement": [],
            "session_productivity": [],
            "optimization_impact": []
        }
        
        # Group sessions by day
        daily_sessions = defaultdict(list)
        for session in sessions:
            day_key = session.timestamp.date()
            daily_sessions[day_key].append(session)
        
        # Calculate daily trends
        sorted_days = sorted(daily_sessions.keys())
        
        for day in sorted_days[-14:]:  # Last 14 days
            day_sessions = daily_sessions[day]
            
            if day_sessions:
                # Overall efficiency
                avg_efficiency = statistics.mean([s.efficiency_score for s in day_sessions])
                trends["overall_efficiency"].append(avg_efficiency)
                
                # Focus improvement
                avg_focus = statistics.mean([s.focus_score for s in day_sessions])
                trends["focus_improvement"].append(avg_focus)
                
                # Session productivity (files per hour)
                avg_productivity = statistics.mean([
                    s.file_count / (s.duration_minutes / 60.0) if s.duration_minutes > 0 else 0
                    for s in day_sessions
                ])
                trends["session_productivity"].append(avg_productivity)
                
                # Optimization impact (sessions with optimization actions)
                optimized_sessions = [s for s in day_sessions if s.optimization_actions]
                optimization_impact = len(optimized_sessions) / len(day_sessions) if day_sessions else 0
                trends["optimization_impact"].append(optimization_impact)
            else:
                # Fill gaps with previous values or defaults
                trends["overall_efficiency"].append(trends["overall_efficiency"][-1] if trends["overall_efficiency"] else 0.7)
                trends["focus_improvement"].append(trends["focus_improvement"][-1] if trends["focus_improvement"] else 0.6)
                trends["session_productivity"].append(trends["session_productivity"][-1] if trends["session_productivity"] else 2.0)
                trends["optimization_impact"].append(trends["optimization_impact"][-1] if trends["optimization_impact"] else 0.3)
        
        return trends
    
    async def _measure_optimization_effectiveness(self, sessions: List[SessionMetrics]) -> Dict[str, float]:
        """Measure effectiveness of different optimization strategies."""
        effectiveness = {}
        
        # Group sessions by optimization actions
        action_groups = defaultdict(list)
        for session in sessions:
            for action in session.optimization_actions:
                action_groups[action].append(session)
        
        # Calculate effectiveness for each action type
        for action, action_sessions in action_groups.items():
            if len(action_sessions) < 2:
                continue
            
            # Compare with baseline (sessions without this action)
            baseline_sessions = [s for s in sessions if action not in s.optimization_actions]
            
            if baseline_sessions:
                action_efficiency = statistics.mean([s.efficiency_score for s in action_sessions])
                baseline_efficiency = statistics.mean([s.efficiency_score for s in baseline_sessions])
                
                effectiveness[action] = (action_efficiency - baseline_efficiency) / baseline_efficiency
            else:
                effectiveness[action] = statistics.mean([s.efficiency_score for s in action_sessions]) - 0.5
        
        return effectiveness
    
    def _calculate_adaptation_score(self, sessions: List[SessionMetrics]) -> float:
        """Calculate how well the user is adapting to optimizations."""
        if len(sessions) < 5:
            return 0.5
        
        # Look at efficiency trend over time
        efficiency_scores = [s.efficiency_score for s in sessions[-10:]]  # Last 10 sessions
        
        if len(efficiency_scores) > 1:
            # Calculate trend slope
            x = list(range(len(efficiency_scores)))
            slope = self._calculate_trend_slope(efficiency_scores)
            
            # Convert slope to adaptation score (0-1 range)
            adaptation_score = max(0, min(1, 0.5 + slope * 2))
            return adaptation_score
        
        return 0.5
    
    async def _predict_future_patterns(
        self, 
        sessions: List[SessionMetrics],
        pattern_evolution: List[PatternEvolution]
    ) -> List[str]:
        """Predict future patterns based on historical data."""
        predictions = []
        
        # Predict workflow trends
        workflow_counts = Counter([s.workflow_type for s in sessions[-10:]])  # Recent sessions
        
        for workflow_type, count in workflow_counts.most_common(3):
            # Find corresponding evolution pattern
            evolution = next(
                (pe for pe in pattern_evolution if pe.pattern_id == f"workflow_{workflow_type}"),
                None
            )
            
            if evolution and evolution.adaptation_score > 0:
                if evolution.frequency_trend and len(evolution.frequency_trend) > 1:
                    recent_trend = evolution.frequency_trend[-3:]  # Last 3 data points
                    if len(recent_trend) > 1 and recent_trend[-1] > recent_trend[0]:
                        predictions.append(f"Increasing use of {workflow_type} workflows")
                
                if evolution.effectiveness_trend and len(evolution.effectiveness_trend) > 1:
                    recent_effectiveness = evolution.effectiveness_trend[-3:]
                    if len(recent_effectiveness) > 1 and recent_effectiveness[-1] > recent_effectiveness[0]:
                        predictions.append(f"Improving effectiveness in {workflow_type}")
        
        # Predict optimization needs
        recent_efficiency = [s.efficiency_score for s in sessions[-5:]]
        if recent_efficiency and statistics.mean(recent_efficiency) < 0.7:
            predictions.append("Efficiency optimization needed")
        
        recent_focus = [s.focus_score for s in sessions[-5:]]
        if recent_focus and statistics.mean(recent_focus) < 0.6:
            predictions.append("Focus improvement opportunities")
        
        return predictions[:5]  # Top 5 predictions
    
    async def _generate_cross_session_recommendations(
        self,
        sessions: List[SessionMetrics],
        pattern_evolution: List[PatternEvolution],
        efficiency_trends: Dict[str, List[float]]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on cross-session analysis."""
        recommendations = []
        
        # Workflow template recommendations
        workflow_frequencies = Counter([s.workflow_type for s in sessions])
        for workflow_type, frequency in workflow_frequencies.most_common(3):
            if frequency >= 3:  # At least 3 occurrences
                workflow_sessions = [s for s in sessions if s.workflow_type == workflow_type]
                avg_efficiency = statistics.mean([s.efficiency_score for s in workflow_sessions])
                
                if avg_efficiency < 0.8:  # Room for improvement
                    recommendations.append({
                        "type": "workflow_optimization",
                        "title": f"Optimize {workflow_type} Workflow",
                        "description": f"Create template for {workflow_type} workflows (used {frequency} times)",
                        "impact": "Medium",
                        "effort": "Low",
                        "potential_improvement": f"{(0.8 - avg_efficiency) * 100:.1f}% efficiency gain"
                    })
        
        # Pattern evolution recommendations
        for evolution in pattern_evolution:
            if evolution.adaptation_score < 0.3:  # Poor adaptation
                recommendations.append({
                    "type": "pattern_improvement",
                    "title": f"Improve {evolution.pattern_id} Pattern",
                    "description": "This pattern shows declining effectiveness",
                    "impact": "High",
                    "effort": "Medium", 
                    "potential_improvement": "Better long-term optimization outcomes"
                })
            elif evolution.adaptation_score > 0.8:  # Great adaptation
                recommendations.append({
                    "type": "pattern_expansion",
                    "title": f"Expand {evolution.pattern_id} Pattern",
                    "description": "This pattern is working well - consider applying to more contexts",
                    "impact": "Medium",
                    "effort": "Low",
                    "potential_improvement": "Broader productivity gains"
                })
        
        # Efficiency trend recommendations
        overall_trend = efficiency_trends.get("overall_efficiency", [])
        if len(overall_trend) > 5:
            recent_trend = self._calculate_trend_slope(overall_trend[-5:])
            if recent_trend < -0.1:  # Declining efficiency
                recommendations.append({
                    "type": "efficiency_recovery",
                    "title": "Address Declining Efficiency",
                    "description": "Recent sessions show declining efficiency trend",
                    "impact": "High",
                    "effort": "Medium",
                    "potential_improvement": "Reverse negative trend, restore productivity"
                })
        
        return sorted(recommendations, key=lambda r: {"High": 3, "Medium": 2, "Low": 1}[r["impact"]], reverse=True)
    
    async def _identify_automation_opportunities(
        self,
        workflow_templates: List[WorkflowTemplate],
        sessions: List[SessionMetrics]
    ) -> List[Dict[str, Any]]:
        """Identify opportunities for automation based on patterns."""
        opportunities = []
        
        for template in workflow_templates:
            if template.usage_frequency > 1.0:  # More than once per week
                # High frequency templates are good automation candidates
                opportunities.append({
                    "type": "workflow_automation",
                    "template_id": template.template_id,
                    "name": f"Automate {template.name}",
                    "description": f"Used {template.usage_frequency:.1f} times per week",
                    "automation_potential": min(1.0, template.usage_frequency / 5.0),
                    "estimated_time_savings": f"{template.optimization_strategy.get('typical_session_length', 60) * 0.3:.0f} minutes per session",
                    "confidence": template.success_rate
                })
        
        # Look for repetitive optimization actions
        action_frequency = Counter()
        for session in sessions:
            for action in session.optimization_actions:
                action_frequency[action] += 1
        
        for action, frequency in action_frequency.most_common(5):
            if frequency >= 5:  # Action used 5+ times
                opportunities.append({
                    "type": "action_automation", 
                    "name": f"Automate {action}",
                    "description": f"This optimization has been manually applied {frequency} times",
                    "automation_potential": min(1.0, frequency / 20.0),
                    "estimated_time_savings": "2-5 minutes per occurrence",
                    "confidence": 0.8
                })
        
        return sorted(opportunities, key=lambda o: o["automation_potential"], reverse=True)
    
    async def _cluster_sessions(self, sessions: List[SessionMetrics]) -> List[SessionCluster]:
        """Cluster sessions based on characteristics."""
        if len(sessions) < 5:
            return []
        
        try:
            # Prepare features for clustering
            features = []
            for session in sessions:
                feature_vector = [
                    session.duration_minutes,
                    session.file_count,
                    session.token_count / 1000.0,  # Scale down
                    session.efficiency_score,
                    session.focus_score,
                    len(session.tools_used),
                    len(session.file_types),
                    len(session.optimization_actions)
                ]
                features.append(feature_vector)
            
            # Standardize features
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            
            # Determine optimal number of clusters (2-5)
            n_clusters = min(5, max(2, len(sessions) // 3))
            
            # Perform clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            cluster_labels = kmeans.fit_predict(features_scaled)
            
            # Create cluster objects
            clusters = []
            for i in range(n_clusters):
                cluster_sessions = [sessions[j] for j, label in enumerate(cluster_labels) if label == i]
                
                if cluster_sessions:
                    # Calculate cluster characteristics
                    avg_duration = statistics.mean([s.duration_minutes for s in cluster_sessions])
                    avg_efficiency = statistics.mean([s.efficiency_score for s in cluster_sessions])
                    common_workflow = Counter([s.workflow_type for s in cluster_sessions]).most_common(1)[0][0]
                    
                    clusters.append(SessionCluster(
                        cluster_id=f"cluster_{i}",
                        session_ids=[s.session_id for s in cluster_sessions],
                        common_patterns=[common_workflow],
                        similarity_score=0.8,  # Simplified
                        session_count=len(cluster_sessions)
                    ))
            
            return clusters
            
        except Exception:
            # Fallback to simple clustering if sklearn fails
            return []
    
    async def _analyze_cluster_characteristics(
        self,
        clusters: List[SessionCluster], 
        sessions: List[SessionMetrics]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze characteristics of each session cluster."""
        cluster_chars = {}
        
        for cluster in clusters:
            cluster_sessions = [s for s in sessions if s.session_id in cluster.session_ids]
            
            if cluster_sessions:
                characteristics = {
                    "average_duration": statistics.mean([s.duration_minutes for s in cluster_sessions]),
                    "average_efficiency": statistics.mean([s.efficiency_score for s in cluster_sessions]),
                    "average_focus": statistics.mean([s.focus_score for s in cluster_sessions]),
                    "common_workflows": Counter([s.workflow_type for s in cluster_sessions]).most_common(3),
                    "common_tools": Counter([tool for s in cluster_sessions for tool in s.tools_used]).most_common(5),
                    "optimization_frequency": statistics.mean([len(s.optimization_actions) for s in cluster_sessions]),
                    "session_count": len(cluster_sessions)
                }
                
                cluster_chars[cluster.cluster_id] = characteristics
        
        return cluster_chars
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate the slope of a trend line."""
        if len(values) < 2:
            return 0.0
        
        x = list(range(len(values)))
        n = len(values)
        
        # Linear regression slope calculation
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope
    
    def _create_minimal_insights(
        self, 
        sessions_data: List[Any],
        correlation_insights: CorrelationInsights
    ) -> CrossSessionInsights:
        """Create minimal insights when insufficient data is available."""
        return CrossSessionInsights(
            analysis_timestamp=datetime.now(),
            sessions_analyzed=len(sessions_data),
            time_span_days=7,
            correlation_insights=correlation_insights,
            pattern_evolution=[],
            workflow_templates=[],
            efficiency_trends={
                "overall_efficiency": [0.7],
                "focus_improvement": [0.6],
                "session_productivity": [2.0],
                "optimization_impact": [0.3]
            },
            optimization_effectiveness={},
            user_adaptation_score=0.5,
            predicted_patterns=["Insufficient data for predictions"],
            optimization_recommendations=[{
                "type": "data_collection",
                "title": "Continue Using Context Cleaner",
                "description": "More sessions needed for comprehensive analysis",
                "impact": "High",
                "effort": "Low",
                "potential_improvement": "Enable full cross-session analytics"
            }],
            automation_opportunities=[],
            session_clusters=[],
            cluster_characteristics={}
        )
    
    async def _persist_insights(self, insights: CrossSessionInsights) -> None:
        """Persist insights to storage for historical analysis."""
        try:
            insights_path = self.storage_path / f"insights_{insights.analysis_timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(insights_path, 'w') as f:
                json.dump(asdict(insights), f, default=str, indent=2)
                
            # Keep only last 30 days of insights
            cutoff_date = datetime.now() - timedelta(days=30)
            for file_path in self.storage_path.glob("insights_*.json"):
                try:
                    file_date_str = file_path.stem.split('_', 1)[1]
                    file_date = datetime.strptime(file_date_str, '%Y%m%d_%H%M%S')
                    if file_date < cutoff_date:
                        file_path.unlink()
                except Exception:
                    continue
                    
        except Exception:
            pass  # Silent fail for persistence
    
    async def load_historical_insights(self, days_back: int = 7) -> List[CrossSessionInsights]:
        """Load historical insights for trend analysis."""
        insights = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        try:
            for file_path in sorted(self.storage_path.glob("insights_*.json")):
                try:
                    file_date_str = file_path.stem.split('_', 1)[1]
                    file_date = datetime.strptime(file_date_str, '%Y%m%d_%H%M%S')
                    
                    if file_date >= cutoff_date:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            # Note: This would need proper deserialization in production
                            insights.append(data)
                            
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return insights[-10:]  # Return last 10 insights