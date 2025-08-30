#!/usr/bin/env python3
"""
Tests for the Context Analysis Engine

Comprehensive tests for the main ContextAnalyzer class including:
- Integration with all analysis components
- Performance and timeout handling
- Circuit breaker functionality
- Cache management
- Error handling and graceful degradation
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.context_cleaner.core.context_analyzer import (
    ContextAnalyzer, ContextAnalysisResult, analyze_context, analyze_context_sync
)
from src.context_cleaner.core.redundancy_detector import RedundancyReport
from src.context_cleaner.core.recency_analyzer import RecencyReport
from src.context_cleaner.core.focus_scorer import FocusMetrics
from src.context_cleaner.core.priority_analyzer import PriorityReport


class TestContextAnalyzer:
    """Test suite for ContextAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ContextAnalyzer()
        
        self.sample_context = {
            'session_id': 'test-session-123',
            'messages': [
                'Currently working on authentication bug fix',
                'Need to implement OAuth2 integration',
                'Fixed login issue - completed yesterday'
            ],
            'todos': [
                'HIGH PRIORITY: Fix critical auth bug',
                'Write unit tests for auth module', 
                'Update documentation - COMPLETED'
            ],
            'files': [
                '/project/auth.py',
                '/project/utils.py',
                '/project/auth.py'  # Duplicate
            ],
            'timestamp': datetime.now().isoformat()
        }
    
    @pytest.mark.asyncio
    async def test_analyze_context_success(self):
        """Test successful context analysis."""
        result = await self.analyzer.analyze_context(self.sample_context)
        
        assert result is not None
        assert isinstance(result, ContextAnalysisResult)
        assert result.health_score >= 0 and result.health_score <= 100
        assert result.total_tokens > 0
        assert result.total_chars > 0
        assert len(result.analysis_timestamp) > 0
        assert result.analysis_duration > 0
    
    @pytest.mark.asyncio
    async def test_analyze_context_with_cache(self):
        """Test context analysis with caching."""
        # First analysis
        result1 = await self.analyzer.analyze_context(self.sample_context, use_cache=True)
        assert result1 is not None
        
        # Second analysis should use cache
        result2 = await self.analyzer.analyze_context(self.sample_context, use_cache=True)
        assert result2 is not None
        assert result1.analysis_timestamp == result2.analysis_timestamp
    
    @pytest.mark.asyncio
    async def test_analyze_context_no_cache(self):
        """Test context analysis without caching."""
        # Disable caching
        result1 = await self.analyzer.analyze_context(self.sample_context, use_cache=False)
        assert result1 is not None
        
        result2 = await self.analyzer.analyze_context(self.sample_context, use_cache=False)
        assert result2 is not None
        # Should be different analysis instances
        assert result1.analysis_timestamp != result2.analysis_timestamp
    
    def test_analyze_context_sync(self):
        """Test synchronous wrapper for context analysis."""
        result = self.analyzer.analyze_context_sync(self.sample_context)
        
        assert result is not None
        assert isinstance(result, ContextAnalysisResult)
        assert result.health_score >= 0 and result.health_score <= 100
    
    def test_validate_context_data_valid(self):
        """Test context data validation with valid data."""
        is_valid, message = self.analyzer._validate_context_data(self.sample_context)
        assert is_valid is True
        assert message == "Valid"
    
    def test_validate_context_data_invalid_empty(self):
        """Test context data validation with empty data."""
        is_valid, message = self.analyzer._validate_context_data({})
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_validate_context_data_invalid_type(self):
        """Test context data validation with invalid type."""
        is_valid, message = self.analyzer._validate_context_data("not a dict")
        assert is_valid is False
        assert "dictionary" in message.lower()
    
    def test_validate_context_data_too_large(self):
        """Test context data validation with oversized data."""
        # Create large context that exceeds limit
        large_data = {"large_content": "x" * (self.analyzer.MAX_CONTEXT_SIZE + 1000)}
        is_valid, message = self.analyzer._validate_context_data(large_data)
        assert is_valid is False
        assert "exceeds limit" in message
    
    @pytest.mark.asyncio
    async def test_analyze_context_timeout(self):
        """Test context analysis timeout handling."""
        # Mock slow components to force timeout
        with patch.object(self.analyzer.redundancy_detector, 'analyze_redundancy') as mock_redundancy:
            mock_redundancy.return_value = AsyncMock(side_effect=asyncio.sleep(10))
            
            # Set very short timeout
            self.analyzer.MAX_ANALYSIS_TIME = 0.1
            
            result = await self.analyzer.analyze_context(self.sample_context)
            assert result is None  # Should return None on timeout
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker behavior."""
        # Initially should allow operations
        assert self.analyzer._check_circuit_breaker() is True
        
        # Record failures to trip circuit breaker
        for _ in range(self.analyzer.CIRCUIT_BREAKER_THRESHOLD):
            self.analyzer._record_failure()
        
        # Should now block operations
        assert self.analyzer._check_circuit_breaker() is False
        
        # Record success should reduce failure count
        self.analyzer._record_success()
        assert self.analyzer.circuit_breaker_failures == self.analyzer.CIRCUIT_BREAKER_THRESHOLD - 1
    
    def test_extract_context_categories(self):
        """Test context categorization extraction."""
        categories = self.analyzer._extract_context_categories(self.sample_context)
        
        assert isinstance(categories, dict)
        assert 'conversations' in categories
        assert 'files' in categories
        assert 'todos' in categories
        assert 'errors' in categories
        
        # Should have some content in relevant categories
        assert categories['todos'] > 0  # Has todo items
        assert categories['files'] > 0  # Has file items
    
    def test_calculate_optimization_potential(self):
        """Test optimization potential calculation."""
        # Mock analysis reports
        redundancy_report = Mock()
        redundancy_report.duplicate_content_percentage = 25.0
        redundancy_report.total_estimated_tokens = 10000
        
        recency_report = Mock()
        recency_report.stale_context_percentage = 15.0
        
        focus_metrics = Mock()
        focus_metrics.focus_score = 70
        
        potential, critical_ratio, cleanup_impact = self.analyzer._calculate_optimization_potential(
            redundancy_report, recency_report, focus_metrics
        )
        
        assert 0.0 <= potential <= 0.8  # Should be capped at 80%
        assert 0.2 <= critical_ratio <= 1.0  # Should be at least 20%
        assert cleanup_impact >= 0
        assert potential + critical_ratio == 1.0
    
    def test_calculate_overall_health_score(self):
        """Test overall health score calculation."""
        # Mock component reports with known values
        focus_metrics = Mock()
        focus_metrics.focus_score = 80
        
        redundancy_report = Mock()
        redundancy_report.duplicate_content_percentage = 20
        
        recency_report = Mock()
        recency_report.fresh_context_percentage = 30
        recency_report.recent_context_percentage = 40
        
        priority_report = Mock()
        priority_report.priority_alignment_score = 70
        
        health_score = self.analyzer._calculate_overall_health_score(
            focus_metrics, redundancy_report, recency_report, priority_report
        )
        
        assert 0 <= health_score <= 100
        assert isinstance(health_score, int)
    
    def test_generate_cache_key_consistency(self):
        """Test cache key generation consistency."""
        key1 = self.analyzer._generate_cache_key(self.sample_context)
        key2 = self.analyzer._generate_cache_key(self.sample_context)
        
        assert key1 == key2  # Same data should produce same key
        
        # Different data should produce different key
        modified_context = self.sample_context.copy()
        modified_context['new_field'] = 'different'
        key3 = self.analyzer._generate_cache_key(modified_context)
        
        assert key1 != key3
    
    def test_get_analysis_summary(self):
        """Test analysis summary generation."""
        # Create mock result
        result = Mock(spec=ContextAnalysisResult)
        result.get_health_status.return_value = "Excellent"
        result.get_size_category.return_value = "Medium"
        result.focus_metrics.focus_score = 85
        result.focus_metrics.priority_alignment_score = 75
        result.redundancy_report.duplicate_content_percentage = 15
        result.recency_report.stale_context_percentage = 10
        result.optimization_potential = 0.3
        result.cleanup_impact_estimate = 3000
        
        summary = self.analyzer.get_analysis_summary(result)
        
        assert isinstance(summary, dict)
        assert 'health_status' in summary
        assert 'size_category' in summary
        assert 'focus_summary' in summary
        assert 'redundancy_summary' in summary
        assert 'optimization_summary' in summary
        
        assert "Excellent" in summary['health_status']
        assert "85%" in summary['focus_summary']
    
    def test_get_analysis_summary_none_result(self):
        """Test analysis summary with None result."""
        summary = self.analyzer.get_analysis_summary(None)
        
        assert isinstance(summary, dict)
        assert summary['status'] == "Analysis unavailable"
        assert "failed" in summary['summary'].lower()
    
    @pytest.mark.asyncio
    async def test_parallel_component_execution(self):
        """Test that analysis components run in parallel for performance."""
        start_time = datetime.now()
        
        result = await self.analyzer.analyze_context(self.sample_context)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete reasonably quickly due to parallel execution
        assert duration < 2.0
        assert result is not None
    
    @pytest.mark.asyncio 
    async def test_error_handling_in_components(self):
        """Test graceful error handling when components fail."""
        # Mock component failure
        with patch.object(self.analyzer.redundancy_detector, 'analyze_redundancy') as mock:
            mock.side_effect = Exception("Component failure")
            
            result = await self.analyzer.analyze_context(self.sample_context)
            # Should handle the error gracefully and return None
            assert result is None


class TestContextAnalysisResult:
    """Test suite for ContextAnalysisResult dataclass."""
    
    def test_context_analysis_result_creation(self):
        """Test creating ContextAnalysisResult with all fields."""
        result = ContextAnalysisResult(
            health_score=85,
            focus_metrics=Mock(),
            redundancy_report=Mock(),
            recency_report=Mock(),
            priority_report=Mock(),
            total_tokens=15000,
            total_chars=60000,
            context_categories={'files': 1000, 'todos': 500},
            analysis_timestamp=datetime.now().isoformat(),
            analysis_duration=1.5,
            performance_metrics={'test': True},
            optimization_potential=0.3,
            critical_context_ratio=0.7,
            cleanup_impact_estimate=4500
        )
        
        assert result.health_score == 85
        assert result.total_tokens == 15000
        assert result.optimization_potential == 0.3
    
    def test_to_dict_conversion(self):
        """Test converting result to dictionary."""
        result = ContextAnalysisResult(
            health_score=85,
            focus_metrics=Mock(),
            redundancy_report=Mock(),
            recency_report=Mock(),
            priority_report=Mock(),
            total_tokens=15000,
            total_chars=60000,
            context_categories={'files': 1000},
            analysis_timestamp=datetime.now().isoformat(),
            analysis_duration=1.5,
            performance_metrics={},
            optimization_potential=0.3,
            critical_context_ratio=0.7,
            cleanup_impact_estimate=4500
        )
        
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict['health_score'] == 85
        assert result_dict['total_tokens'] == 15000
    
    def test_get_health_status_excellent(self):
        """Test health status classification - excellent."""
        result = ContextAnalysisResult(
            health_score=90,
            focus_metrics=Mock(), redundancy_report=Mock(), recency_report=Mock(),
            priority_report=Mock(), total_tokens=1000, total_chars=4000,
            context_categories={}, analysis_timestamp="", analysis_duration=1.0,
            performance_metrics={}, optimization_potential=0.2, critical_context_ratio=0.8,
            cleanup_impact_estimate=200
        )
        assert result.get_health_status() == "Excellent"
    
    def test_get_health_status_good(self):
        """Test health status classification - good."""
        result = ContextAnalysisResult(
            health_score=75,
            focus_metrics=Mock(), redundancy_report=Mock(), recency_report=Mock(),
            priority_report=Mock(), total_tokens=1000, total_chars=4000,
            context_categories={}, analysis_timestamp="", analysis_duration=1.0,
            performance_metrics={}, optimization_potential=0.2, critical_context_ratio=0.8,
            cleanup_impact_estimate=200
        )
        assert result.get_health_status() == "Good"
    
    def test_get_health_status_fair(self):
        """Test health status classification - fair."""
        result = ContextAnalysisResult(
            health_score=60,
            focus_metrics=Mock(), redundancy_report=Mock(), recency_report=Mock(),
            priority_report=Mock(), total_tokens=1000, total_chars=4000,
            context_categories={}, analysis_timestamp="", analysis_duration=1.0,
            performance_metrics={}, optimization_potential=0.2, critical_context_ratio=0.8,
            cleanup_impact_estimate=200
        )
        assert result.get_health_status() == "Fair"
    
    def test_get_health_status_needs_attention(self):
        """Test health status classification - needs attention."""
        result = ContextAnalysisResult(
            health_score=40,
            focus_metrics=Mock(), redundancy_report=Mock(), recency_report=Mock(),
            priority_report=Mock(), total_tokens=1000, total_chars=4000,
            context_categories={}, analysis_timestamp="", analysis_duration=1.0,
            performance_metrics={}, optimization_potential=0.2, critical_context_ratio=0.8,
            cleanup_impact_estimate=200
        )
        assert result.get_health_status() == "Needs Attention"
    
    def test_get_size_category_small(self):
        """Test size category classification - small."""
        result = ContextAnalysisResult(
            health_score=80, focus_metrics=Mock(), redundancy_report=Mock(),
            recency_report=Mock(), priority_report=Mock(),
            total_tokens=5000,  # Small
            total_chars=20000, context_categories={}, analysis_timestamp="",
            analysis_duration=1.0, performance_metrics={}, optimization_potential=0.2,
            critical_context_ratio=0.8, cleanup_impact_estimate=200
        )
        assert result.get_size_category() == "Small"
    
    def test_get_size_category_large(self):
        """Test size category classification - large."""
        result = ContextAnalysisResult(
            health_score=80, focus_metrics=Mock(), redundancy_report=Mock(),
            recency_report=Mock(), priority_report=Mock(),
            total_tokens=75000,  # Large
            total_chars=300000, context_categories={}, analysis_timestamp="",
            analysis_duration=1.0, performance_metrics={}, optimization_potential=0.2,
            critical_context_ratio=0.8, cleanup_impact_estimate=200
        )
        assert result.get_size_category() == "Large"


class TestConvenienceFunctions:
    """Test suite for convenience functions."""
    
    @pytest.mark.asyncio
    async def test_analyze_context_function(self):
        """Test convenience analyze_context function."""
        sample_data = {
            'test': 'data',
            'messages': ['Hello world'],
            'timestamp': datetime.now().isoformat()
        }
        
        result = await analyze_context(sample_data)
        assert result is not None
        assert isinstance(result, ContextAnalysisResult)
    
    def test_analyze_context_sync_function(self):
        """Test convenience analyze_context_sync function."""
        sample_data = {
            'test': 'data', 
            'messages': ['Hello world'],
            'timestamp': datetime.now().isoformat()
        }
        
        result = analyze_context_sync(sample_data)
        assert result is not None
        assert isinstance(result, ContextAnalysisResult)
    
    @pytest.mark.asyncio
    async def test_analyze_context_function_invalid_data(self):
        """Test convenience function with invalid data."""
        result = await analyze_context({})  # Empty data
        assert result is None
    
    def test_analyze_context_sync_function_invalid_data(self):
        """Test sync convenience function with invalid data."""
        result = analyze_context_sync({})  # Empty data
        assert result is None


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])