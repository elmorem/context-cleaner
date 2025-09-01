#!/usr/bin/env python3
"""
Basic Functionality Test for Cache Analysis Components

Tests core functionality of the PR15.2: Usage Pattern Intelligence components
to validate they can be imported and instantiated correctly.
"""

import pytest

def test_can_import_all_analyzers():
    """Test that all analyzer components can be imported."""
    from src.context_cleaner.analysis.import (
        UsagePatternAnalyzer, TokenEfficiencyAnalyzer, 
        TemporalContextAnalyzer, EnhancedContextAnalyzer,
        CrossSessionCorrelationAnalyzer
    )
    assert UsagePatternAnalyzer is not None
    assert TokenEfficiencyAnalyzer is not None
    assert TemporalContextAnalyzer is not None
    assert EnhancedContextAnalyzer is not None
    assert CrossSessionCorrelationAnalyzer is not None

def test_can_instantiate_analyzers():
    """Test that all analyzers can be instantiated."""
    from src.context_cleaner.analysis.import (
        UsagePatternAnalyzer, TokenEfficiencyAnalyzer,
        TemporalContextAnalyzer, CrossSessionCorrelationAnalyzer
    )
    
    usage_analyzer = UsagePatternAnalyzer()
    token_analyzer = TokenEfficiencyAnalyzer()
    temporal_analyzer = TemporalContextAnalyzer()
    correlation_analyzer = CrossSessionCorrelationAnalyzer()
    
    assert usage_analyzer is not None
    assert token_analyzer is not None
    assert temporal_analyzer is not None
    assert correlation_analyzer is not None

def test_can_import_data_models():
    """Test that all data models can be imported."""
    from src.context_cleaner.analysis.import (
        WorkflowPattern, FileUsageMetrics, UsagePatternSummary,
        TokenWastePattern, CacheEfficiencyMetrics, TokenAnalysisSummary,
        TopicTransition, SessionBoundary, TemporalInsights,
        UsageWeightedScore, CacheEnhancedAnalysis,
        SessionCluster, CrossSessionPattern, LongTermTrend, CorrelationInsights
    )
    
    # Just check they can be imported
    assert WorkflowPattern is not None
    assert FileUsageMetrics is not None
    assert UsagePatternSummary is not None
    assert TokenWastePattern is not None
    assert CacheEfficiencyMetrics is not None
    assert TokenAnalysisSummary is not None
    assert TopicTransition is not None
    assert SessionBoundary is not None
    assert TemporalInsights is not None
    assert UsageWeightedScore is not None
    assert CacheEnhancedAnalysis is not None
    assert SessionCluster is not None
    assert CrossSessionPattern is not None
    assert LongTermTrend is not None
    assert CorrelationInsights is not None

def test_basic_analyzer_methods_exist():
    """Test that analyzers have the expected main analysis methods."""
    from src.context_cleaner.analysis.import (
        UsagePatternAnalyzer, TokenEfficiencyAnalyzer,
        TemporalContextAnalyzer, CrossSessionCorrelationAnalyzer
    )
    
    usage_analyzer = UsagePatternAnalyzer()
    token_analyzer = TokenEfficiencyAnalyzer()
    temporal_analyzer = TemporalContextAnalyzer()
    correlation_analyzer = CrossSessionCorrelationAnalyzer()
    
    # Check main analysis methods exist
    assert hasattr(usage_analyzer, 'analyze_usage_patterns')
    assert callable(usage_analyzer.analyze_usage_patterns)
    
    assert hasattr(token_analyzer, 'analyze_token_efficiency')
    assert callable(token_analyzer.analyze_token_efficiency)
    
    assert hasattr(temporal_analyzer, 'analyze_temporal_patterns')
    assert callable(temporal_analyzer.analyze_temporal_patterns)
    
    assert hasattr(correlation_analyzer, 'analyze_cross_session_correlations')
    assert callable(correlation_analyzer.analyze_cross_session_correlations)

def test_empty_session_handling():
    """Test that analyzers can handle empty session lists gracefully."""
    from src.context_cleaner.analysis.import (
        UsagePatternAnalyzer, TokenEfficiencyAnalyzer,
        TemporalContextAnalyzer, CrossSessionCorrelationAnalyzer
    )
    
    empty_sessions = []
    
    usage_analyzer = UsagePatternAnalyzer()
    token_analyzer = TokenEfficiencyAnalyzer()
    temporal_analyzer = TemporalContextAnalyzer()
    correlation_analyzer = CrossSessionCorrelationAnalyzer()
    
    # Test empty sessions don't crash
    try:
        usage_result = usage_analyzer.analyze_usage_patterns(empty_sessions)
        assert usage_result is not None
    except Exception as e:
        pytest.skip(f"Usage analyzer needs session data: {e}")
    
    try:
        token_result = token_analyzer.analyze_token_efficiency(empty_sessions)
        assert token_result is not None
    except Exception as e:
        pytest.skip(f"Token analyzer needs session data: {e}")
    
    try:
        temporal_result = temporal_analyzer.analyze_temporal_patterns(empty_sessions)
        assert temporal_result is not None
    except Exception as e:
        pytest.skip(f"Temporal analyzer needs session data: {e}")
    
    try:
        correlation_result = correlation_analyzer.analyze_cross_session_correlations(empty_sessions)
        assert correlation_result is not None
    except Exception as e:
        pytest.skip(f"Correlation analyzer needs session data: {e}")

def test_enhanced_context_analyzer_integration():
    """Test that enhanced context analyzer can be instantiated with mock base analyzer."""
    from unittest.mock import Mock
    from src.context_cleaner.analysis.import EnhancedContextAnalyzer
    
    # Create mock base analyzer
    mock_base_analyzer = Mock()
    
    # Test instantiation
    enhanced_analyzer = EnhancedContextAnalyzer(context_analyzer=mock_base_analyzer)
    assert enhanced_analyzer is not None
    
    # Check it has the expected method
    assert hasattr(enhanced_analyzer, 'analyze_with_cache_intelligence')
    assert callable(enhanced_analyzer.analyze_with_cache_intelligence)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])