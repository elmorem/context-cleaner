#!/usr/bin/env python3
"""
Tests for Temporal Context Analyzer

Tests for session boundary detection, topic drift analysis, and temporal pattern recognition
in Claude Code conversation analysis.
"""

import pytest
from datetime import datetime, timedelta

from src.context_cleaner.cache.temporal_analyzer import (
    TemporalContextAnalyzer, TopicTransition, SessionBoundary, TemporalInsights
)
from src.context_cleaner.cache.models import SessionMessage, ToolUsage, SessionAnalysis, MessageType, MessageRole


class TestTemporalContextAnalyzer:
    """Test suite for TemporalContextAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = TemporalContextAnalyzer()
        
        # Create sample session data
        now = datetime.now()
        
        # Sample messages with different timestamps and topics
        self.sample_messages = [
            SessionMessage(
                uuid="msg_1",
                parent_uuid=None,
                message_type=MessageType.USER,
                role=MessageRole.USER,
                content="Help me debug this Python script",
                timestamp=now - timedelta(hours=2),
                tool_usage=[]
            ),
            SessionMessage(
                uuid="msg_2",
                parent_uuid="msg_1",
                message_type=MessageType.ASSISTANT,
                role=MessageRole.ASSISTANT,
                content="I'll help you debug the script. Let me read the file first.",
                timestamp=now - timedelta(hours=2, minutes=5),
                tool_usage=[ToolUsage(
                    tool_name="Read", tool_id="read_1",
                    parameters={"file_path": "script.py"}, 
                    timestamp=now - timedelta(hours=2, minutes=5)
                )]
            ),
            SessionMessage(
                uuid="msg_3",
                parent_uuid="msg_2",
                message_type=MessageType.USER,
                role=MessageRole.USER,
                content="Actually, let's work on the React frontend instead",
                timestamp=now - timedelta(hours=1, minutes=45),  # 20 minute gap
                tool_usage=[]
            ),
            SessionMessage(
                uuid="msg_4",
                parent_uuid="msg_3",
                message_type=MessageType.ASSISTANT,
                role=MessageRole.ASSISTANT,
                content="Sure! Let me look at your React components.",
                timestamp=now - timedelta(hours=1, minutes=40),
                tool_usage=[ToolUsage(
                    tool_name="Read", tool_id="read_2",
                    parameters={"file_path": "App.js"}, 
                    timestamp=now - timedelta(hours=1, minutes=40)
                )]
            ),
            SessionMessage(
                uuid="msg_5",
                parent_uuid="msg_4",
                message_type=MessageType.USER,
                role=MessageRole.USER,
                content="Let's go back to the Python debugging issue",
                timestamp=now - timedelta(minutes=30),  # 70 minute gap
                tool_usage=[]
            )
        ]
        
        # Sample session for analysis
        self.sample_session = SessionAnalysis(
            session_id="test_session_1",
            start_time=now - timedelta(hours=2),
            end_time=now,
            messages=self.sample_messages,
            tool_usage_summary={},
            file_paths=["/test/script.py", "/test/App.js"],
            total_tokens=5000,
            cache_hits=10,
            cache_misses=5,
            topics=["python", "debugging", "react", "frontend"]
        )
        
        self.sample_sessions = [self.sample_session]
    
    def test_analyze_temporal_patterns(self):
        """Test full temporal pattern analysis."""
        insights = self.analyzer.analyze_temporal_patterns(self.sample_sessions)
        
        assert isinstance(insights, TemporalInsights)
        assert isinstance(insights.session_boundaries, list)
        assert isinstance(insights.topic_transitions, list)
        assert isinstance(insights.evolution_patterns, list)
        assert insights.average_session_length > 0
        assert insights.typical_break_duration >= 0
        assert isinstance(insights.peak_activity_periods, list)
        assert 0 <= insights.context_stability_score <= 1
        assert insights.topic_drift_frequency >= 0
        assert 0 <= insights.return_to_topic_rate <= 1
        assert 0 <= insights.multitasking_intensity <= 1
        assert insights.optimal_session_length > 0
        assert insights.recommended_break_frequency > 0
        assert isinstance(insights.productivity_time_patterns, dict)
        assert 0 <= insights.context_switching_cost <= 1
        assert isinstance(insights.analysis_period, tuple)
        assert 0 <= insights.confidence_score <= 1
    
    def test_detect_session_boundaries(self):
        """Test session boundary detection."""
        boundaries = self.analyzer._detect_session_boundaries(self.sample_sessions)
        
        assert isinstance(boundaries, list)
        assert all(isinstance(boundary, SessionBoundary) for boundary in boundaries)
        
        for boundary in boundaries:
            assert boundary.boundary_type in ["natural_break", "topic_shift", "extended_pause", "explicit_end"]
            assert 0 <= boundary.confidence_score <= 1
            assert boundary.time_gap_minutes >= 0
    
    def test_detect_topic_transitions(self):
        """Test topic transition detection."""
        transitions = self.analyzer._detect_topic_transitions(self.sample_sessions)
        
        assert isinstance(transitions, list)
        assert all(isinstance(transition, TopicTransition) for transition in transitions)
        
        for transition in transitions:
            assert transition.transition_type in ["gradual", "abrupt", "return", "continuation"]
            assert 0 <= transition.confidence_score <= 1
            assert 0 <= transition.context_similarity <= 1
            assert transition.time_gap_minutes >= 0
    
    def test_analyze_topic_evolution(self):
        """Test topic evolution pattern analysis."""
        patterns = self.analyzer._analyze_topic_evolution(self.sample_sessions)
        
        assert isinstance(patterns, list)
        assert all(isinstance(pattern, str) for pattern in patterns)
    
    def test_calculate_session_metrics(self):
        """Test session metric calculations."""
        avg_length, typical_break = self.analyzer._calculate_session_metrics(self.sample_sessions)
        
        assert isinstance(avg_length, float)
        assert isinstance(typical_break, float)
        assert avg_length > 0
        assert typical_break >= 0
    
    def test_identify_peak_activity_periods(self):
        """Test peak activity period identification."""
        periods = self.analyzer._identify_peak_activity_periods(self.sample_sessions)
        
        assert isinstance(periods, list)
        assert all(isinstance(period, str) for period in periods)
    
    def test_calculate_context_stability_score(self):
        """Test context stability score calculation."""
        stability = self.analyzer._calculate_context_stability_score(self.sample_sessions)
        
        assert isinstance(stability, float)
        assert 0 <= stability <= 1
    
    def test_calculate_topic_drift_frequency(self):
        """Test topic drift frequency calculation."""
        drift_freq = self.analyzer._calculate_topic_drift_frequency(self.sample_sessions)
        
        assert isinstance(drift_freq, float)
        assert drift_freq >= 0
    
    def test_calculate_return_to_topic_rate(self):
        """Test return to topic rate calculation."""
        return_rate = self.analyzer._calculate_return_to_topic_rate(self.sample_sessions)
        
        assert isinstance(return_rate, float)
        assert 0 <= return_rate <= 1
    
    def test_calculate_multitasking_intensity(self):
        """Test multitasking intensity calculation."""
        intensity = self.analyzer._calculate_multitasking_intensity(self.sample_sessions)
        
        assert isinstance(intensity, float)
        assert 0 <= intensity <= 1
    
    def test_calculate_optimal_session_length(self):
        """Test optimal session length calculation."""
        optimal = self.analyzer._calculate_optimal_session_length(self.sample_sessions)
        
        assert isinstance(optimal, float)
        assert optimal > 0
    
    def test_calculate_recommended_break_frequency(self):
        """Test recommended break frequency calculation."""
        break_freq = self.analyzer._calculate_recommended_break_frequency(self.sample_sessions)
        
        assert isinstance(break_freq, float)
        assert break_freq > 0
    
    def test_analyze_productivity_patterns(self):
        """Test productivity time pattern analysis."""
        patterns = self.analyzer._analyze_productivity_patterns(self.sample_sessions)
        
        assert isinstance(patterns, dict)
        assert all(isinstance(k, str) for k in patterns.keys())
        assert all(isinstance(v, float) and 0 <= v <= 1 for v in patterns.values())
    
    def test_calculate_context_switching_cost(self):
        """Test context switching cost calculation."""
        cost = self.analyzer._calculate_context_switching_cost(self.sample_sessions)
        
        assert isinstance(cost, float)
        assert 0 <= cost <= 1
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        confidence = self.analyzer._calculate_confidence_score(
            len(self.sample_sessions), datetime.now() - datetime.now() + timedelta(days=30)
        )
        
        assert isinstance(confidence, float)
        assert 0 <= confidence <= 1
    
    def test_extract_message_topics(self):
        """Test topic extraction from messages."""
        topics = self.analyzer._extract_message_topics(self.sample_messages[0])
        
        assert isinstance(topics, set)
        assert len(topics) > 0
    
    def test_calculate_topic_similarity(self):
        """Test topic similarity calculation."""
        topics1 = {"python", "debugging"}
        topics2 = {"python", "scripting"}
        
        similarity = self.analyzer._calculate_topic_similarity(topics1, topics2)
        
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
        assert similarity > 0  # Should have some overlap
    
    def test_classify_transition_type(self):
        """Test transition type classification."""
        # Test abrupt transition
        transition_type = self.analyzer._classify_transition_type(
            similarity=0.1, time_gap=30.0, context_change=True
        )
        assert transition_type in ["gradual", "abrupt", "return", "continuation"]
        
        # Test gradual transition
        transition_type = self.analyzer._classify_transition_type(
            similarity=0.7, time_gap=5.0, context_change=False
        )
        assert transition_type in ["gradual", "abrupt", "return", "continuation"]
    
    def test_is_significant_time_gap(self):
        """Test significant time gap detection."""
        # Test significant gap
        assert self.analyzer._is_significant_time_gap(30.0) == True
        
        # Test insignificant gap
        assert self.analyzer._is_significant_time_gap(2.0) == False
    
    def test_calculate_boundary_confidence(self):
        """Test boundary confidence calculation."""
        confidence = self.analyzer._calculate_boundary_confidence(
            time_gap=30.0, topic_change=True, activity_change=True
        )
        
        assert isinstance(confidence, float)
        assert 0 <= confidence <= 1
    
    def test_empty_sessions(self):
        """Test handling of empty session list."""
        insights = self.analyzer.analyze_temporal_patterns([])
        
        assert isinstance(insights, TemporalInsights)
        assert insights.average_session_length == 0.0
        assert insights.confidence_score == 0.0
    
    def test_single_message_session(self):
        """Test handling of session with single message."""
        single_message_session = SessionAnalysis(
            session_id="single_msg",
            start_time=datetime.now() - timedelta(minutes=1),
            end_time=datetime.now(),
            messages=[self.sample_messages[0]],
            tool_usage_summary={},
            file_paths=[],
            total_tokens=100,
            cache_hits=1,
            cache_misses=0,
            topics=["python"]
        )
        
        insights = self.analyzer.analyze_temporal_patterns([single_message_session])
        
        assert isinstance(insights, TemporalInsights)
        assert insights.average_session_length >= 0
    
    def test_topic_transition_properties(self):
        """Test TopicTransition property methods."""
        transition = TopicTransition(
            from_topic="python",
            to_topic="react", 
            transition_time=datetime.now(),
            session_id="test",
            confidence_score=0.8,
            transition_type="abrupt",
            context_similarity=0.2,
            time_gap_minutes=30.0
        )
        
        assert transition.is_abrupt_change == True
        
        # Test non-abrupt change
        gradual_transition = TopicTransition(
            from_topic="python",
            to_topic="scripting",
            transition_time=datetime.now(),
            session_id="test",
            confidence_score=0.8,
            transition_type="gradual",
            context_similarity=0.7,
            time_gap_minutes=5.0
        )
        
        assert gradual_transition.is_abrupt_change == False
    
    def test_session_boundary_properties(self):
        """Test SessionBoundary property methods."""
        boundary = SessionBoundary(
            boundary_time=datetime.now(),
            boundary_type="extended_pause",
            confidence_score=0.9,
            time_gap_minutes=45.0,
            context_change_indicators=["topic_shift", "tool_change"],
            session_before="session1",
            session_after="session2"
        )
        
        assert boundary.is_natural_break == True
        
        # Test non-natural break
        forced_boundary = SessionBoundary(
            boundary_time=datetime.now(),
            boundary_type="explicit_end",
            confidence_score=0.6,
            time_gap_minutes=5.0,
            context_change_indicators=[],
            session_before="session1",
            session_after="session2"
        )
        
        assert forced_boundary.is_natural_break == False
    
    def test_temporal_insights_properties(self):
        """Test TemporalInsights calculated properties."""
        now = datetime.now()
        insights = TemporalInsights(
            session_boundaries=[],
            topic_transitions=[],
            evolution_patterns=[],
            average_session_length=2.5,
            typical_break_duration=20.0,
            peak_activity_periods=["9-11", "14-16"],
            context_stability_score=0.7,
            topic_drift_frequency=3.0,
            return_to_topic_rate=0.4,
            multitasking_intensity=0.6,
            optimal_session_length=3.0,
            recommended_break_frequency=45.0,
            productivity_time_patterns={"9": 0.9, "10": 0.8, "14": 0.7},
            context_switching_cost=0.3,
            analysis_period=(now - timedelta(days=30), now),
            confidence_score=0.8
        )
        
        # Test productivity score
        productivity = insights.overall_productivity_score
        assert isinstance(productivity, float)
        assert 0 <= productivity <= 1
        
        # Test focus quality
        focus_quality = insights.focus_quality_score  
        assert isinstance(focus_quality, float)
        assert 0 <= focus_quality <= 1
        
        # Test session health
        session_health = insights.session_health_score
        assert isinstance(session_health, float)
        assert 0 <= session_health <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])