#!/usr/bin/env python3
"""
Simplified Temporal Analyzer Tests

Tests that focus on core functionality without complex data model setup.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from src.context_cleaner.cache.temporal_analyzer import (
    TemporalContextAnalyzer, TopicTransition, SessionBoundary, TemporalInsights
)


class TestTemporalContextAnalyzerSimple:
    """Simplified test suite for TemporalContextAnalyzer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = TemporalContextAnalyzer()
    
    def test_analyzer_instantiation(self):
        """Test that analyzer can be instantiated."""
        assert self.analyzer is not None
        assert hasattr(self.analyzer, 'analyze_temporal_patterns')
    
    def test_analyze_temporal_patterns_empty(self):
        """Test temporal analysis with empty cache locations."""
        with patch.object(self.analyzer.discovery, 'discover_cache_locations') as mock_discovery:
            mock_discovery.return_value = []
            
            insights = self.analyzer.analyze_temporal_patterns()
            
            assert isinstance(insights, TemporalInsights)
            assert insights.average_session_length == 0.0
            assert insights.confidence_score == 0.0
    
    def test_topic_similarity_calculation(self):
        """Test topic similarity calculation method."""
        topics1 = {"python", "debugging"}
        topics2 = {"python", "scripting"}
        
        similarity = self.analyzer._calculate_topic_similarity(topics1, topics2)
        
        assert isinstance(similarity, float)
        assert 0 <= similarity <= 1
        assert similarity > 0  # Should have some overlap with "python"
    
    def test_classify_transition_type(self):
        """Test transition type classification."""
        # Test abrupt transition
        transition_type = self.analyzer._classify_transition_type(
            similarity=0.1, time_gap=30.0, context_change=True
        )
        assert transition_type in ["gradual", "abrupt", "return", "continuation"]
    
    def test_is_significant_time_gap(self):
        """Test significant time gap detection."""
        assert self.analyzer._is_significant_time_gap(30.0) == True
        assert self.analyzer._is_significant_time_gap(2.0) == False
    
    def test_calculate_boundary_confidence(self):
        """Test boundary confidence calculation."""
        confidence = self.analyzer._calculate_boundary_confidence(
            time_gap=30.0, topic_change=True, activity_change=True
        )
        
        assert isinstance(confidence, float)
        assert 0 <= confidence <= 1
    
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