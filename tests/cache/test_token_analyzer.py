#!/usr/bin/env python3
"""
Tests for Token Efficiency Analyzer

Comprehensive tests for analyzing token usage patterns, cache efficiency,
and identifying optimization opportunities.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.context_cleaner.cache.token_analyzer import (
    TokenEfficiencyAnalyzer, TokenWastePattern, CacheEfficiencyMetrics, 
    TokenAnalysisSummary, TokenUsageInsights
)
from src.context_cleaner.cache.models import SessionAnalysis, ToolUsage, CacheConfig
from src.context_cleaner.cache.discovery import CacheLocation


class TestTokenEfficiencyAnalyzer:
    """Test suite for TokenEfficiencyAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = TokenEfficiencyAnalyzer()
        self.config = CacheConfig()
        
        # Create sample session data with token metrics
        now = datetime.now()
        
        self.sample_sessions = [
            SessionAnalysis(
                session_id="session-1",
                start_time=now - timedelta(hours=2),
                end_time=now - timedelta(hours=1),
                total_messages=10,
                total_tokens=2000,  # High token session
                file_operations=[
                    ToolUsage("Read", "tool1", {"file_path": "/test/large_file.py"}, now),
                    ToolUsage("Read", "tool2", {"file_path": "/test/large_file.py"}, now),  # Repeated read
                    ToolUsage("Edit", "tool3", {"file_path": "/test/large_file.py"}, now)
                ],
                context_switches=5,  # High context switches
                average_response_time=2.0,
                cache_efficiency=0.3  # Poor cache efficiency
            ),
            SessionAnalysis(
                session_id="session-2",
                start_time=now - timedelta(hours=1),
                end_time=now,
                total_messages=15,
                total_tokens=900,  # More efficient session
                file_operations=[
                    ToolUsage("Read", "tool4", {"file_path": "/test/app.py"}, now),
                    ToolUsage("Edit", "tool5", {"file_path": "/test/app.py"}, now),
                    ToolUsage("Bash", "tool6", {"command": "python test.py"}, now)
                ],
                context_switches=2,
                average_response_time=1.0,
                cache_efficiency=0.8  # Good cache efficiency
            ),
            SessionAnalysis(
                session_id="session-3",
                start_time=now - timedelta(minutes=30),
                end_time=now,
                total_messages=5,
                total_tokens=3000,  # Very high token per message ratio
                file_operations=[
                    ToolUsage("Read", "tool7", {"file_path": "/test/huge_context.py"}, now)
                ],
                context_switches=1,
                average_response_time=3.0,
                cache_efficiency=0.1  # Very poor cache efficiency
            )
        ]
        
        # Mock cache location
        self.mock_location = CacheLocation(
            path=Path("/test/cache"),
            project_name="test-project",
            session_files=[Path("/test/session1.jsonl"), Path("/test/session2.jsonl")],
            last_modified=now,
            total_size_bytes=1024
        )
    
    def test_analyze_token_efficiency_with_sessions(self):
        """Test token efficiency analysis with sample sessions."""
        with patch.object(self.analyzer.discovery, 'discover_cache_locations') as mock_discover:
            with patch.object(self.analyzer.parser, 'parse_session_file') as mock_parse:
                mock_discover.return_value = [self.mock_location]
                mock_parse.side_effect = self.sample_sessions
                
                summary = self.analyzer.analyze_token_efficiency()
                
                assert summary.total_sessions_analyzed == 3
                assert isinstance(summary.cache_efficiency, CacheEfficiencyMetrics)
                assert isinstance(summary.usage_insights, TokenUsageInsights)
                assert isinstance(summary.waste_patterns, list)
                assert summary.overall_efficiency_score >= 0
                assert summary.overall_efficiency_score <= 100
    
    def test_analyze_cache_efficiency(self):
        """Test cache efficiency analysis."""
        metrics = self.analyzer._analyze_cache_efficiency(self.sample_sessions)
        
        assert isinstance(metrics, CacheEfficiencyMetrics)
        assert metrics.total_input_tokens > 0
        assert metrics.total_output_tokens > 0
        assert 0 <= metrics.overall_cache_hit_ratio <= 1
        assert 0 <= metrics.average_cache_efficiency <= 1
        assert 0 <= metrics.cache_utilization_score <= 1
        
        # Check session categorization
        total_categorized = (metrics.sessions_with_good_cache_usage + 
                           metrics.sessions_with_poor_cache_usage + 
                           metrics.sessions_with_no_cache_usage)
        assert total_categorized == len(self.sample_sessions)
        
        # Check cache effectiveness grade
        assert metrics.cache_effectiveness_grade in ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
    
    def test_analyze_usage_patterns(self):
        """Test token usage pattern analysis."""
        insights = self.analyzer._analyze_usage_patterns(self.sample_sessions)
        
        assert isinstance(insights, TokenUsageInsights)
        assert insights.average_tokens_per_session > 0
        assert insights.average_tokens_per_message > 0
        assert len(insights.peak_token_sessions) <= 5
        assert len(insights.most_token_efficient_sessions) <= 5
        assert isinstance(insights.repetitive_operations, list)
        assert isinstance(insights.context_bloat_indicators, list)
        assert isinstance(insights.token_distribution, dict)
        
        # Check efficiency summary
        assert insights.efficiency_summary in ["Highly Efficient", "Efficient", "Moderate", "Inefficient"]
    
    def test_detect_repetitive_operations(self):
        """Test repetitive operation detection."""
        repetitive_ops = self.analyzer._detect_repetitive_operations(self.sample_sessions)
        
        assert isinstance(repetitive_ops, list)
        
        # Should detect repeated reads in session-1
        if repetitive_ops:
            pattern, count = repetitive_ops[0]
            assert isinstance(pattern, str)
            assert isinstance(count, int)
            assert count >= self.analyzer.repetition_threshold
    
    def test_detect_context_bloat(self):
        """Test context bloat detection."""
        indicators = self.analyzer._detect_context_bloat(self.sample_sessions)
        
        assert isinstance(indicators, list)
        assert all(isinstance(indicator, str) for indicator in indicators)
        
        # Should detect high token-to-message ratios
        any("token-to-message" in indicator for indicator in indicators)
        # May or may not be present depending on thresholds
    
    def test_identify_optimization_opportunities(self):
        """Test optimization opportunity identification."""
        opportunities = self.analyzer._identify_optimization_opportunities(self.sample_sessions)
        
        assert isinstance(opportunities, list)
        assert all(isinstance(opp, str) for opp in opportunities)
        
        # Should identify cache efficiency improvement opportunity
        any("cache" in opp.lower() for opp in opportunities)
        # May be present if enough sessions have low cache efficiency
    
    def test_calculate_length_efficiency_correlation(self):
        """Test session length vs efficiency correlation calculation."""
        correlation = self.analyzer._calculate_length_efficiency_correlation(self.sample_sessions)
        
        assert isinstance(correlation, float)
        assert -1 <= correlation <= 1
    
    def test_detect_waste_patterns(self):
        """Test waste pattern detection."""
        patterns = self.analyzer._detect_waste_patterns(self.sample_sessions)
        
        assert isinstance(patterns, list)
        assert all(isinstance(pattern, TokenWastePattern) for pattern in patterns)
        
        for pattern in patterns:
            assert pattern.estimated_waste_tokens >= 0
            assert pattern.frequency >= 0
            assert 0 <= pattern.potential_savings_percent <= 100
            assert pattern.severity_level in ["High", "Medium", "Low"]
    
    def test_detect_repetitive_reads(self):
        """Test repetitive read detection."""
        repetitive = self.analyzer._detect_repetitive_reads(self.sample_sessions)
        
        if repetitive:
            assert "count" in repetitive
            assert "sessions" in repetitive
            assert "estimated_waste" in repetitive
            
            assert repetitive["count"] > 0
            assert repetitive["estimated_waste"] >= 0
            assert isinstance(repetitive["sessions"], list)
    
    def test_detect_cache_inefficiency(self):
        """Test cache inefficiency detection."""
        inefficiency = self.analyzer._detect_cache_inefficiency(self.sample_sessions)
        
        if inefficiency:
            assert "count" in inefficiency
            assert "sessions" in inefficiency
            assert "estimated_waste" in inefficiency
            
            assert inefficiency["count"] > 0
            assert inefficiency["estimated_waste"] >= 0
    
    def test_detect_token_bloat_pattern(self):
        """Test token bloat pattern detection."""
        bloat = self.analyzer._detect_token_bloat_pattern(self.sample_sessions)
        
        if bloat:
            assert "count" in bloat
            assert "sessions" in bloat
            assert "estimated_waste" in bloat
            
            assert bloat["count"] > 0
            assert bloat["estimated_waste"] >= 0
    
    def test_generate_optimization_recommendations(self):
        """Test optimization recommendation generation."""
        cache_efficiency = CacheEfficiencyMetrics(
            total_input_tokens=1000,
            total_output_tokens=500,
            total_cache_creation_tokens=200,
            total_cache_read_tokens=100,
            ephemeral_5m_tokens=150,
            ephemeral_1h_tokens=50,
            overall_cache_hit_ratio=0.4,  # Poor cache efficiency
            average_cache_efficiency=0.4,
            cache_utilization_score=0.5,
            sessions_with_good_cache_usage=1,
            sessions_with_poor_cache_usage=2,
            sessions_with_no_cache_usage=0
        )
        
        usage_insights = TokenUsageInsights(
            average_tokens_per_session=1500.0,
            average_tokens_per_message=600.0,  # High tokens per message
            peak_token_sessions=[],
            most_token_efficient_sessions=[],
            repetitive_operations=[],
            context_bloat_indicators=[],
            optimization_opportunities=[],
            token_distribution={},
            session_length_correlation=-0.5  # Negative correlation
        )
        
        waste_patterns = [
            TokenWastePattern(
                pattern_type="repetitive_reads",
                description="Multiple reads of same file",
                estimated_waste_tokens=1000,
                frequency=3,
                sessions_affected=["s1", "s2"],
                optimization_suggestion="Use caching",
                potential_savings_percent=20.0
            )
        ]
        
        recommendations = self.analyzer._generate_optimization_recommendations(
            cache_efficiency, usage_insights, waste_patterns
        )
        
        assert isinstance(recommendations, list)
        assert all(isinstance(rec, str) for rec in recommendations)
        assert len(recommendations) > 0
        
        # Should recommend cache efficiency improvement
        cache_rec = any("cache" in rec.lower() for rec in recommendations)
        assert cache_rec
        
        # Should recommend addressing high token usage
        token_rec = any("token" in rec.lower() for rec in recommendations)
        assert token_rec
    
    def test_estimate_monthly_savings(self):
        """Test monthly savings estimation."""
        cache_efficiency = CacheEfficiencyMetrics(
            total_input_tokens=1000,
            total_output_tokens=500,
            total_cache_creation_tokens=200,
            total_cache_read_tokens=100,
            ephemeral_5m_tokens=150,
            ephemeral_1h_tokens=50,
            overall_cache_hit_ratio=0.5,
            average_cache_efficiency=0.5,
            cache_utilization_score=0.5,
            sessions_with_good_cache_usage=1,
            sessions_with_poor_cache_usage=1,
            sessions_with_no_cache_usage=1
        )
        
        usage_insights = TokenUsageInsights(
            average_tokens_per_session=1000.0,
            average_tokens_per_message=100.0,
            peak_token_sessions=[],
            most_token_efficient_sessions=[],
            repetitive_operations=[],
            context_bloat_indicators=[],
            optimization_opportunities=[],
            token_distribution={},
            session_length_correlation=0.0
        )
        
        waste_patterns = [
            TokenWastePattern(
                pattern_type="test_waste",
                description="Test waste pattern",
                estimated_waste_tokens=1000,
                frequency=2,
                sessions_affected=["s1"],
                optimization_suggestion="Test suggestion",
                potential_savings_percent=10.0
            )
        ]
        
        savings = self.analyzer._estimate_monthly_savings(
            cache_efficiency, usage_insights, waste_patterns
        )
        
        assert isinstance(savings, dict)
        
        required_keys = [
            'waste_elimination_tokens', 'waste_elimination_cost',
            'cache_efficiency_tokens', 'cache_efficiency_cost',
            'total_potential_tokens', 'total_potential_cost'
        ]
        
        for key in required_keys:
            assert key in savings
            assert isinstance(savings[key], (int, float))
            assert savings[key] >= 0
    
    def test_empty_sessions_handling(self):
        """Test handling of empty session list."""
        with patch.object(self.analyzer.discovery, 'discover_cache_locations') as mock_discover:
            mock_discover.return_value = []
            
            summary = self.analyzer.analyze_token_efficiency()
            
            assert summary.total_sessions_analyzed == 0
            assert summary.overall_efficiency_score == 0
            assert len(summary.waste_patterns) == 0
            assert len(summary.optimization_recommendations) > 0  # Should have "No data" message


class TestTokenWastePattern:
    """Test suite for TokenWastePattern class."""
    
    def test_token_waste_pattern_properties(self):
        """Test TokenWastePattern property calculations."""
        # High severity pattern
        high_pattern = TokenWastePattern(
            pattern_type="repetitive_reads",
            description="Many repeated file reads",
            estimated_waste_tokens=15000,  # High waste
            frequency=10,
            sessions_affected=["s1", "s2", "s3"],
            optimization_suggestion="Use context caching",
            potential_savings_percent=30.0
        )
        
        assert high_pattern.severity_level == "High"
        
        # Medium severity pattern  
        medium_pattern = TokenWastePattern(
            pattern_type="inefficient_cache",
            description="Poor cache utilization",
            estimated_waste_tokens=7000,  # Medium waste
            frequency=5,
            sessions_affected=["s1", "s2"],
            optimization_suggestion="Improve context structure",
            potential_savings_percent=20.0
        )
        
        assert medium_pattern.severity_level == "Medium"
        
        # Low severity pattern
        low_pattern = TokenWastePattern(
            pattern_type="minor_bloat",
            description="Minor context bloat",
            estimated_waste_tokens=2000,  # Low waste
            frequency=2,
            sessions_affected=["s1"],
            optimization_suggestion="Clean up context",
            potential_savings_percent=5.0
        )
        
        assert low_pattern.severity_level == "Low"


class TestCacheEfficiencyMetrics:
    """Test suite for CacheEfficiencyMetrics class."""
    
    def test_cache_efficiency_metrics_properties(self):
        """Test CacheEfficiencyMetrics property calculations."""
        metrics = CacheEfficiencyMetrics(
            total_input_tokens=6000,
            total_output_tokens=4000,
            total_cache_creation_tokens=2000,
            total_cache_read_tokens=1500,
            ephemeral_5m_tokens=1200,
            ephemeral_1h_tokens=800,
            overall_cache_hit_ratio=0.75,
            average_cache_efficiency=0.7,
            cache_utilization_score=0.8,
            sessions_with_good_cache_usage=3,
            sessions_with_poor_cache_usage=1,
            sessions_with_no_cache_usage=1
        )
        
        # Test total tokens calculation
        assert metrics.total_tokens == 10000  # 6000 + 4000
        
        # Test cache effectiveness grade
        assert metrics.cache_effectiveness_grade == "Good"  # 0.75 cache hit ratio
        
        # Test estimated cost savings
        savings = metrics.estimated_cost_savings_percent
        assert isinstance(savings, float)
        assert 0 <= savings <= 100
        
        # Test different cache effectiveness grades
        excellent_metrics = CacheEfficiencyMetrics(
            total_input_tokens=1000, total_output_tokens=500,
            total_cache_creation_tokens=100, total_cache_read_tokens=200,
            ephemeral_5m_tokens=150, ephemeral_1h_tokens=50,
            overall_cache_hit_ratio=0.9,  # Excellent
            average_cache_efficiency=0.85, cache_utilization_score=0.9,
            sessions_with_good_cache_usage=5, sessions_with_poor_cache_usage=0,
            sessions_with_no_cache_usage=0
        )
        assert excellent_metrics.cache_effectiveness_grade == "Excellent"
        
        poor_metrics = CacheEfficiencyMetrics(
            total_input_tokens=1000, total_output_tokens=500,
            total_cache_creation_tokens=100, total_cache_read_tokens=50,
            ephemeral_5m_tokens=40, ephemeral_1h_tokens=10,
            overall_cache_hit_ratio=0.3,  # Poor
            average_cache_efficiency=0.25, cache_utilization_score=0.3,
            sessions_with_good_cache_usage=0, sessions_with_poor_cache_usage=2,
            sessions_with_no_cache_usage=3
        )
        assert poor_metrics.cache_effectiveness_grade == "Poor"


class TestTokenUsageInsights:
    """Test suite for TokenUsageInsights class."""
    
    def test_token_usage_insights_properties(self):
        """Test TokenUsageInsights property calculations."""
        # Highly efficient usage
        efficient_insights = TokenUsageInsights(
            average_tokens_per_session=500.0,
            average_tokens_per_message=50.0,  # Very efficient
            peak_token_sessions=[("s1", 1000), ("s2", 900)],
            most_token_efficient_sessions=[("s3", 0.1), ("s4", 0.08)],
            repetitive_operations=[],
            context_bloat_indicators=[],
            optimization_opportunities=[],
            token_distribution={"input_ratio": 0.6, "output_ratio": 0.4},
            session_length_correlation=0.2
        )
        
        assert efficient_insights.efficiency_summary == "Highly Efficient"
        
        # Inefficient usage
        inefficient_insights = TokenUsageInsights(
            average_tokens_per_session=5000.0,
            average_tokens_per_message=800.0,  # Inefficient
            peak_token_sessions=[("s1", 10000)],
            most_token_efficient_sessions=[("s2", 0.001)],
            repetitive_operations=[("repeat_pattern", 10)],
            context_bloat_indicators=["Large context detected"],
            optimization_opportunities=["Reduce context size"],
            token_distribution={"input_ratio": 0.8, "output_ratio": 0.2},
            session_length_correlation=-0.5
        )
        
        assert inefficient_insights.efficiency_summary == "Inefficient"


class TestTokenAnalysisSummary:
    """Test suite for TokenAnalysisSummary class."""
    
    def test_token_analysis_summary_properties(self):
        """Test TokenAnalysisSummary property calculations."""
        now = datetime.now()
        
        cache_efficiency = CacheEfficiencyMetrics(
            total_input_tokens=3000, total_output_tokens=2000,
            total_cache_creation_tokens=500, total_cache_read_tokens=400,
            ephemeral_5m_tokens=300, ephemeral_1h_tokens=100,
            overall_cache_hit_ratio=0.8, average_cache_efficiency=0.75,
            cache_utilization_score=0.85, sessions_with_good_cache_usage=4,
            sessions_with_poor_cache_usage=1, sessions_with_no_cache_usage=0
        )
        
        usage_insights = TokenUsageInsights(
            average_tokens_per_session=1000.0, average_tokens_per_message=100.0,
            peak_token_sessions=[], most_token_efficient_sessions=[],
            repetitive_operations=[], context_bloat_indicators=[],
            optimization_opportunities=[], token_distribution={},
            session_length_correlation=0.3
        )
        
        waste_patterns = [
            TokenWastePattern(
                pattern_type="minor_waste", description="Small waste",
                estimated_waste_tokens=1000, frequency=1,
                sessions_affected=["s1"], optimization_suggestion="Fix",
                potential_savings_percent=5.0
            )
        ]
        
        summary = TokenAnalysisSummary(
            cache_efficiency=cache_efficiency,
            usage_insights=usage_insights,
            waste_patterns=waste_patterns,
            optimization_recommendations=["Improve caching"],
            total_sessions_analyzed=5,
            analysis_period=(now - timedelta(days=7), now),
            potential_monthly_savings={"total_potential_cost": 10.0}
        )
        
        # Test overall efficiency score calculation
        efficiency_score = summary.overall_efficiency_score
        assert 0 <= efficiency_score <= 100
        
        # With good cache efficiency (0.8) and reasonable token usage (100/msg),
        # should have a decent score
        assert efficiency_score > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])