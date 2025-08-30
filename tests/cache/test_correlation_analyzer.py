#!/usr/bin/env python3
"""
Tests for Cross-Session Correlation Analyzer

Tests for long-term pattern recognition, session clustering, and workflow continuation detection
across multiple Claude Code conversation sessions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import numpy as np

from src.context_cleaner.cache.correlation_analyzer import (
    CrossSessionCorrelationAnalyzer, SessionCluster, CrossSessionPattern, 
    LongTermTrend, CorrelationInsights
)
from src.context_cleaner.cache.models import SessionMessage, ToolUsage, SessionAnalysis


class TestCrossSessionCorrelationAnalyzer:
    """Test suite for CrossSessionCorrelationAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = CrossSessionCorrelationAnalyzer()
        
        # Create sample multi-session data
        now = datetime.now()
        base_time = now - timedelta(days=7)
        
        # Create multiple sessions with patterns
        self.sample_sessions = []
        
        # Session 1: Python development
        session1 = SessionAnalysis(
            session_id="session_1",
            start_time=base_time,
            end_time=base_time + timedelta(hours=2),
            messages=[
                SessionMessage(
                    timestamp=base_time,
                    role="user",
                    content="Help me debug this Python script",
                    tool_calls=[],
                    metadata={"topics": ["python", "debugging"]}
                ),
                SessionMessage(
                    timestamp=base_time + timedelta(minutes=5),
                    role="assistant",
                    content="I'll help debug the script",
                    tool_calls=[ToolUsage(tool="Read", parameters={"file_path": "app.py"}, result="success")],
                    metadata={"topics": ["python", "debugging"]}
                )
            ],
            tool_usage_summary={"Read": 3, "Edit": 2, "Bash": 1},
            file_paths=["/project/app.py", "/project/utils.py"],
            total_tokens=2500,
            cache_hits=8,
            cache_misses=2,
            topics=["python", "debugging"]
        )
        
        # Session 2: Similar Python work (next day)
        session2 = SessionAnalysis(
            session_id="session_2", 
            start_time=base_time + timedelta(days=1),
            end_time=base_time + timedelta(days=1, hours=1.5),
            messages=[
                SessionMessage(
                    timestamp=base_time + timedelta(days=1),
                    role="user",
                    content="Continue working on the Python project",
                    tool_calls=[],
                    metadata={"topics": ["python", "development"]}
                )
            ],
            tool_usage_summary={"Read": 2, "Edit": 3, "Bash": 2},
            file_paths=["/project/app.py", "/project/tests.py"],
            total_tokens=1800,
            cache_hits=12,
            cache_misses=1,
            topics=["python", "development"]
        )
        
        # Session 3: React frontend (different topic)
        session3 = SessionAnalysis(
            session_id="session_3",
            start_time=base_time + timedelta(days=2),
            end_time=base_time + timedelta(days=2, hours=1),
            messages=[
                SessionMessage(
                    timestamp=base_time + timedelta(days=2),
                    role="user", 
                    content="Let's work on the React frontend",
                    tool_calls=[],
                    metadata={"topics": ["react", "frontend"]}
                )
            ],
            tool_usage_summary={"Read": 4, "Edit": 1, "Bash": 1},
            file_paths=["/frontend/App.js", "/frontend/components/Nav.js"],
            total_tokens=2200,
            cache_hits=6,
            cache_misses=4,
            topics=["react", "frontend"]
        )
        
        # Session 4: Back to Python (return pattern)
        session4 = SessionAnalysis(
            session_id="session_4",
            start_time=base_time + timedelta(days=3),
            end_time=base_time + timedelta(days=3, hours=2.5),
            messages=[
                SessionMessage(
                    timestamp=base_time + timedelta(days=3),
                    role="user",
                    content="Back to the Python debugging issue",
                    tool_calls=[],
                    metadata={"topics": ["python", "debugging"]}
                )
            ],
            tool_usage_summary={"Read": 3, "Edit": 4, "Bash": 3},
            file_paths=["/project/app.py", "/project/debug.py"],
            total_tokens=3000,
            cache_hits=15,
            cache_misses=2,
            topics=["python", "debugging"]
        )
        
        self.sample_sessions = [session1, session2, session3, session4]
    
    def test_analyze_cross_session_correlations(self):
        """Test full cross-session correlation analysis."""
        insights = self.analyzer.analyze_cross_session_correlations(self.sample_sessions)
        
        assert isinstance(insights, CorrelationInsights)
        assert isinstance(insights.session_clusters, list)
        assert isinstance(insights.cross_session_patterns, list)
        assert isinstance(insights.long_term_trends, list)
        assert isinstance(insights.workflow_continuations, list)
        assert isinstance(insights.topic_evolution_chains, list)
        assert isinstance(insights.productivity_correlations, dict)
        assert isinstance(insights.file_relationship_map, dict)
        assert isinstance(insights.temporal_correlation_matrix, list)
        assert isinstance(insights.predictive_insights, list)
        assert 0 <= insights.overall_correlation_strength <= 1
        assert insights.analysis_confidence >= 0
        assert isinstance(insights.analysis_period, tuple)
    
    def test_cluster_similar_sessions(self):
        """Test session clustering functionality."""
        clusters = self.analyzer._cluster_similar_sessions(self.sample_sessions)
        
        assert isinstance(clusters, list)
        assert all(isinstance(cluster, SessionCluster) for cluster in clusters)
        
        for cluster in clusters:
            assert len(cluster.session_ids) >= 1
            assert 0 <= cluster.similarity_score <= 1
            assert 0 <= cluster.cohesion_score <= 1
            assert cluster.cluster_type in ["topic_based", "workflow_based", "temporal_based", "mixed"]
    
    def test_detect_cross_session_patterns(self):
        """Test cross-session pattern detection."""
        patterns = self.analyzer._detect_cross_session_patterns(self.sample_sessions)
        
        assert isinstance(patterns, list)
        assert all(isinstance(pattern, CrossSessionPattern) for pattern in patterns)
        
        for pattern in patterns:
            assert pattern.pattern_type in ["workflow_continuation", "topic_return", "tool_sequence", "file_progression", "temporal_rhythm"]
            assert len(pattern.session_sequence) >= 2
            assert 0 <= pattern.consistency_score <= 1
            assert 0 <= pattern.correlation_strength <= 1
    
    def test_identify_long_term_trends(self):
        """Test long-term trend identification."""
        trends = self.analyzer._identify_long_term_trends(self.sample_sessions)
        
        assert isinstance(trends, list)
        assert all(isinstance(trend, LongTermTrend) for trend in trends)
        
        for trend in trends:
            assert trend.trend_type in ["productivity", "topic_focus", "tool_usage", "session_length", "complexity"]
            assert trend.direction in ["increasing", "decreasing", "stable", "cyclical"]
            assert 0 <= trend.strength <= 1
            assert 0 <= trend.confidence <= 1
    
    def test_detect_workflow_continuations(self):
        """Test workflow continuation detection."""
        continuations = self.analyzer._detect_workflow_continuations(self.sample_sessions)
        
        assert isinstance(continuations, list)
        assert all(isinstance(cont, str) for cont in continuations)
    
    def test_analyze_topic_evolution_chains(self):
        """Test topic evolution chain analysis."""
        chains = self.analyzer._analyze_topic_evolution_chains(self.sample_sessions)
        
        assert isinstance(chains, list)
        assert all(isinstance(chain, str) for chain in chains)
    
    def test_calculate_productivity_correlations(self):
        """Test productivity correlation calculations."""
        correlations = self.analyzer._calculate_productivity_correlations(self.sample_sessions)
        
        assert isinstance(correlations, dict)
        assert all(isinstance(k, str) for k in correlations.keys())
        assert all(isinstance(v, float) and -1 <= v <= 1 for v in correlations.values())
    
    def test_build_file_relationship_map(self):
        """Test file relationship mapping."""
        file_map = self.analyzer._build_file_relationship_map(self.sample_sessions)
        
        assert isinstance(file_map, dict)
        if file_map:
            # Check structure
            for file_path, relationships in file_map.items():
                assert isinstance(file_path, str)
                assert isinstance(relationships, dict)
    
    def test_compute_temporal_correlation_matrix(self):
        """Test temporal correlation matrix computation."""
        matrix = self.analyzer._compute_temporal_correlation_matrix(self.sample_sessions)
        
        assert isinstance(matrix, list)
        if matrix:
            assert all(isinstance(row, list) for row in matrix)
            # Should be square matrix
            assert len(matrix) == len(matrix[0])
    
    def test_generate_predictive_insights(self):
        """Test predictive insight generation."""
        insights = self.analyzer._generate_predictive_insights(
            self.sample_sessions, [], [], []
        )
        
        assert isinstance(insights, list)
        assert all(isinstance(insight, str) for insight in insights)
    
    def test_calculate_session_similarity(self):
        """Test session similarity calculation."""
        similarity = self.analyzer._calculate_session_similarity(
            self.sample_sessions[0], self.sample_sessions[1]
        )
        
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
        
        # Test sessions with same topic should have higher similarity
        python_similarity = self.analyzer._calculate_session_similarity(
            self.sample_sessions[0], self.sample_sessions[3]  # Both Python
        )
        
        different_topic_similarity = self.analyzer._calculate_session_similarity(
            self.sample_sessions[0], self.sample_sessions[2]  # Python vs React
        )
        
        assert python_similarity >= different_topic_similarity
    
    def test_calculate_topic_overlap(self):
        """Test topic overlap calculation."""
        overlap = self.analyzer._calculate_topic_overlap(
            ["python", "debugging"], ["python", "development"]
        )
        
        assert isinstance(overlap, float)
        assert 0 <= overlap <= 1
        assert overlap > 0  # Should have some overlap
        
        # Test no overlap
        no_overlap = self.analyzer._calculate_topic_overlap(
            ["python", "debugging"], ["react", "frontend"]
        )
        assert no_overlap == 0
    
    def test_calculate_tool_usage_similarity(self):
        """Test tool usage similarity calculation."""
        similarity = self.analyzer._calculate_tool_usage_similarity(
            {"Read": 3, "Edit": 2, "Bash": 1},
            {"Read": 2, "Edit": 3, "Bash": 2}
        )
        
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
    
    def test_calculate_file_overlap(self):
        """Test file path overlap calculation."""
        overlap = self.analyzer._calculate_file_overlap(
            ["/project/app.py", "/project/utils.py"],
            ["/project/app.py", "/project/tests.py"]
        )
        
        assert isinstance(overlap, float)
        assert 0 <= overlap <= 1
        assert overlap > 0  # Should have some overlap
    
    def test_calculate_temporal_distance(self):
        """Test temporal distance calculation."""
        now = datetime.now()
        session1_time = now - timedelta(hours=1)
        session2_time = now
        
        distance = self.analyzer._calculate_temporal_distance(session1_time, session2_time)
        
        assert isinstance(distance, float)
        assert distance >= 0
    
    def test_detect_return_patterns(self):
        """Test return pattern detection."""
        patterns = self.analyzer._detect_return_patterns(self.sample_sessions)
        
        assert isinstance(patterns, list)
        assert all(isinstance(pattern, str) for pattern in patterns)
    
    def test_analyze_tool_sequence_patterns(self):
        """Test tool sequence pattern analysis."""
        patterns = self.analyzer._analyze_tool_sequence_patterns(self.sample_sessions)
        
        assert isinstance(patterns, list)
        assert all(isinstance(pattern, str) for pattern in patterns)
    
    def test_calculate_pattern_strength(self):
        """Test pattern strength calculation."""
        strength = self.analyzer._calculate_pattern_strength(
            session_count=3, consistency=0.8, span_days=5.0
        )
        
        assert isinstance(strength, float)
        assert 0 <= strength <= 1
    
    def test_calculate_trend_strength(self):
        """Test trend strength calculation."""
        values = [1.0, 1.2, 1.5, 1.8, 2.0]  # Increasing trend
        strength = self.analyzer._calculate_trend_strength(values)
        
        assert isinstance(strength, float)
        assert 0 <= strength <= 1
        assert strength > 0.5  # Should detect increasing trend
    
    def test_detect_cyclical_patterns(self):
        """Test cyclical pattern detection."""
        values = [1.0, 2.0, 1.0, 2.0, 1.0, 2.0]  # Clear cycle
        is_cyclical = self.analyzer._detect_cyclical_patterns(values)
        
        assert isinstance(is_cyclical, bool)
    
    def test_calculate_correlation_coefficient(self):
        """Test correlation coefficient calculation."""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]  # Perfect positive correlation
        
        correlation = self.analyzer._calculate_correlation_coefficient(x, y)
        
        assert isinstance(correlation, float)
        assert -1 <= correlation <= 1
        assert correlation > 0.9  # Should be close to 1
    
    def test_empty_sessions(self):
        """Test handling of empty session list."""
        insights = self.analyzer.analyze_cross_session_correlations([])
        
        assert isinstance(insights, CorrelationInsights)
        assert insights.overall_correlation_strength == 0.0
        assert insights.analysis_confidence == 0.0
    
    def test_single_session(self):
        """Test handling of single session."""
        insights = self.analyzer.analyze_cross_session_correlations([self.sample_sessions[0]])
        
        assert isinstance(insights, CorrelationInsights)
        assert insights.overall_correlation_strength >= 0.0
    
    def test_session_cluster_properties(self):
        """Test SessionCluster property methods."""
        cluster = SessionCluster(
            cluster_id="test_cluster",
            session_ids=["session1", "session2", "session3"],
            cluster_type="topic_based",
            dominant_topics=["python", "debugging"],
            similarity_score=0.8,
            cohesion_score=0.9,
            common_patterns=["debug_workflow"],
            representative_session="session1",
            cluster_timespan=timedelta(days=3),
            productivity_score=0.7
        )
        
        # Test size property
        assert cluster.size == 3
        
        # Test strong cohesion property
        assert cluster.has_strong_cohesion == True
        
        # Test weak cohesion
        weak_cluster = SessionCluster(
            cluster_id="weak_cluster",
            session_ids=["session1"],
            cluster_type="mixed",
            dominant_topics=[],
            similarity_score=0.4,
            cohesion_score=0.3,
            common_patterns=[],
            representative_session="session1",
            cluster_timespan=timedelta(hours=1),
            productivity_score=0.5
        )
        
        assert weak_cluster.has_strong_cohesion == False
    
    def test_cross_session_pattern_properties(self):
        """Test CrossSessionPattern property methods."""
        pattern = CrossSessionPattern(
            pattern_id="test_pattern",
            pattern_type="workflow_continuation",
            description="Python debugging workflow",
            session_sequence=["session1", "session2", "session4"],
            time_intervals=[1.0, 2.0],
            consistency_score=0.9,
            evolution_trend="stable",
            key_indicators=["python_files", "debug_tools"],
            correlation_strength=0.8,
            first_occurrence=datetime.now() - timedelta(days=7),
            last_occurrence=datetime.now() - timedelta(days=1),
            frequency_days=2.0
        )
        
        # Test reliability property
        assert pattern.is_reliable == True
        
        # Test unreliable pattern
        unreliable_pattern = CrossSessionPattern(
            pattern_id="unreliable",
            pattern_type="tool_sequence",
            description="Weak pattern",
            session_sequence=["session1", "session2"],
            time_intervals=[1.0],
            consistency_score=0.4,
            evolution_trend="decreasing", 
            key_indicators=[],
            correlation_strength=0.3,
            first_occurrence=datetime.now() - timedelta(days=1),
            last_occurrence=datetime.now(),
            frequency_days=1.0
        )
        
        assert unreliable_pattern.is_reliable == False
    
    def test_long_term_trend_properties(self):
        """Test LongTermTrend property methods."""
        trend = LongTermTrend(
            trend_id="productivity_trend",
            trend_type="productivity",
            description="Increasing productivity over time",
            direction="increasing",
            strength=0.8,
            confidence=0.9,
            time_series_data=[1.0, 1.2, 1.5, 1.8, 2.0],
            significance_level=0.05,
            affected_sessions=["s1", "s2", "s3", "s4", "s5"],
            trend_period=timedelta(days=30),
            key_factors=["experience", "tool_familiarity"]
        )
        
        # Test significance property
        assert trend.is_statistically_significant == True
        
        # Test strong trend property  
        assert trend.is_strong_trend == True
        
        # Test weak trend
        weak_trend = LongTermTrend(
            trend_id="weak_trend",
            trend_type="session_length", 
            description="Weak trend",
            direction="stable",
            strength=0.3,
            confidence=0.4,
            time_series_data=[1.0, 1.1, 1.0, 0.9, 1.0],
            significance_level=0.2,
            affected_sessions=["s1", "s2"],
            trend_period=timedelta(days=5),
            key_factors=[]
        )
        
        assert weak_trend.is_statistically_significant == False
        assert weak_trend.is_strong_trend == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])