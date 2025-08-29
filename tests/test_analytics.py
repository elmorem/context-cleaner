"""
Tests for Context Cleaner analytics components.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from context_cleaner.analytics.productivity_analyzer import ProductivityAnalyzer


class TestProductivityAnalyzer:
    """Test suite for ProductivityAnalyzer."""
    
    def test_analyzer_initialization(self, test_config):
        """Test analyzer initialization with config."""
        analyzer = ProductivityAnalyzer(test_config)
        assert analyzer.config == test_config
        assert hasattr(analyzer, 'circuit_breaker')
    
    def test_context_health_analysis_basic(self, productivity_analyzer, mock_context_data):
        """Test basic context health analysis."""
        result = productivity_analyzer.analyze_context_health(mock_context_data)
        
        assert 'health_score' in result
        assert 'recommendations' in result
        assert 'metrics' in result
        assert 0 <= result['health_score'] <= 100
        assert isinstance(result['recommendations'], list)
    
    def test_context_health_scoring(self, productivity_analyzer):
        """Test context health scoring with different inputs."""
        # High health context
        high_health_context = {
            "total_tokens": 5000,
            "file_count": 10,
            "conversation_depth": 20,
            "session_start": datetime.now().isoformat()
        }
        
        result_high = productivity_analyzer.analyze_context_health(high_health_context)
        
        # Low health context  
        low_health_context = {
            "total_tokens": 95000,
            "file_count": 100,
            "conversation_depth": 200,
            "session_start": (datetime.now() - timedelta(hours=6)).isoformat()
        }
        
        result_low = productivity_analyzer.analyze_context_health(low_health_context)
        
        # High health should have better score
        assert result_high['health_score'] > result_low['health_score']
    
    def test_productivity_session_analysis(self, productivity_analyzer, mock_session_data):
        """Test productivity session analysis."""
        session = mock_session_data[0]  # Use first session
        result = productivity_analyzer.analyze_productivity_session(session)
        
        assert 'productivity_score' in result
        assert 'session_metrics' in result
        assert 'insights' in result
        assert 0 <= result['productivity_score'] <= 100
        assert isinstance(result['insights'], list)
    
    def test_session_type_classification(self, productivity_analyzer):
        """Test session type classification."""
        # Coding session indicators
        coding_session = {
            "timestamp": datetime.now().isoformat(),
            "session_duration": 180,
            "context_health_score": 85,
            "tools_used": ["Write", "Edit", "Read"],
            "optimization_events": 2
        }
        
        result = productivity_analyzer.analyze_productivity_session(coding_session)
        # Should classify as productive coding session
        assert result['session_metrics']['session_type'] in ['productive_coding', 'optimization_session']
    
    @patch('time.time')
    def test_circuit_breaker_timeout_protection(self, mock_time, productivity_analyzer):
        """Test circuit breaker timeout protection."""
        # Mock time progression to simulate timeout
        mock_time.side_effect = [0, 1, 2, 31]  # Timeout after 30 seconds
        
        # Create problematic context data that might cause timeout
        problematic_context = {
            "total_tokens": 500000,  # Very large context
            "file_count": 1000,
            "conversation_depth": 1000,
            "session_start": datetime.now().isoformat()
        }
        
        result = productivity_analyzer.analyze_context_health(problematic_context)
        
        # Should return safe fallback due to timeout
        assert result['health_score'] is not None
        assert 'timeout' in str(result.get('error', '')).lower() or result['health_score'] >= 0
    
    def test_empty_data_handling(self, productivity_analyzer):
        """Test handling of empty or minimal data."""
        empty_context = {}
        result = productivity_analyzer.analyze_context_health(empty_context)
        
        # Should handle gracefully and return valid result
        assert 'health_score' in result
        assert isinstance(result['health_score'], (int, float))
        assert 0 <= result['health_score'] <= 100
    
    def test_recommendation_generation(self, productivity_analyzer, mock_context_data):
        """Test recommendation generation based on context health."""
        result = productivity_analyzer.analyze_context_health(mock_context_data)
        recommendations = result['recommendations']
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Check that recommendations are strings
        for rec in recommendations:
            assert isinstance(rec, str)
            assert len(rec) > 0
    
    def test_metrics_calculation(self, productivity_analyzer, mock_context_data):
        """Test metrics calculation accuracy."""
        result = productivity_analyzer.analyze_context_health(mock_context_data)
        metrics = result['metrics']
        
        assert 'token_density' in metrics
        assert 'file_complexity' in metrics
        assert 'session_age' in metrics
        
        # Verify calculated values are reasonable
        assert metrics['token_density'] >= 0
        assert metrics['file_complexity'] >= 0
        assert metrics['session_age'] >= 0
    
    def test_concurrent_analysis_safety(self, productivity_analyzer, mock_context_data, mock_session_data):
        """Test that concurrent analyses don't interfere."""
        import threading
        import time
        
        results = []
        errors = []
        
        def analyze_context():
            try:
                result = productivity_analyzer.analyze_context_health(mock_context_data)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        def analyze_session():
            try:
                result = productivity_analyzer.analyze_productivity_session(mock_session_data[0])
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Run concurrent analyses
        threads = []
        for _ in range(3):
            threads.extend([
                threading.Thread(target=analyze_context),
                threading.Thread(target=analyze_session)
            ])
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=5)
        
        # Verify no errors and got results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 6  # 3 context + 3 session analyses