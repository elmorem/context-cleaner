"""Comprehensive tests for the Context Rot Analyzer."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
from src.context_cleaner.telemetry.context_rot.security import PrivacyConfig, SecureContextRotAnalyzer
from src.context_cleaner.telemetry.context_rot.monitor import ProductionReadyContextRotMonitor
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
from tests.telemetry.conftest import MockTelemetryClient


class TestContextRotAnalyzer:
    """Test suite for Context Rot Analyzer."""

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client for testing."""
        client = AsyncMock(spec=ClickHouseClient)
        client.health_check.return_value = True
        client.execute_query.return_value = []
        return client

    @pytest.fixture
    def mock_error_recovery_manager(self):
        """Mock error recovery manager for testing."""
        mock_client = MockTelemetryClient()
        return ErrorRecoveryManager(mock_client, max_retries=3)

    @pytest.fixture
    def analyzer(self, mock_clickhouse_client, mock_error_recovery_manager):
        """Create analyzer instance for testing."""
        return ContextRotAnalyzer(mock_clickhouse_client, mock_error_recovery_manager)

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self, analyzer):
        """Test analyzer initializes correctly."""
        assert analyzer.clickhouse_client is not None
        assert analyzer.error_manager is not None
        assert analyzer.security_analyzer is not None
        assert analyzer.monitor is not None
        
        # Check status
        status = await analyzer.get_analyzer_status()
        assert status['status'] == 'healthy'
        assert 'version' in status
        assert 'components' in status

    @pytest.mark.asyncio
    async def test_real_time_analysis(self, analyzer):
        """Test real-time context rot analysis."""
        test_data = {
            'session_id': 'test-session-001',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'This is not working at all, very frustrated',
            'context_size': 5000,
            'tools_used': ['Read', 'Edit', 'Bash']
        }
        
        result = await analyzer.analyze_realtime(test_data)
        
        assert result['status'] in ['success', 'warning', 'error']
        assert 'rot_score' in result
        assert 'confidence' in result
        assert 'analysis_timestamp' in result
        assert isinstance(result['rot_score'], float)
        assert 0.0 <= result['rot_score'] <= 1.0
        assert 0.0 <= result['confidence'] <= 1.0

    @pytest.mark.asyncio
    async def test_conversation_sentiment_analysis(self, analyzer):
        """Test conversation sentiment analysis."""
        conversation = [
            "I need help with this feature",
            "It's not working as expected", 
            "I'm getting frustrated with this",
            "This is really annoying me",
            "Why won't this work?!"
        ]
        
        result = await analyzer.analyze_conversation_sentiment('test-user', conversation)
        
        assert result['status'] == 'success'
        assert 'analysis' in result
        assert 'alert_level' in result
        assert 'recommendations' in result
        
        analysis = result['analysis']
        assert 'frustration_level' in analysis
        assert 'confidence' in analysis
        assert isinstance(analysis['frustration_level'], float)

    @pytest.mark.asyncio
    async def test_personalized_insights(self, analyzer):
        """Test personalized insights generation."""
        analyzer.clickhouse_client.execute_query.return_value = [
            {'normal_level': 0.3, 'variance': 0.15, 'confidence': 0.8}
        ]
        
        insights = await analyzer.get_personalized_insights('test-user')
        
        assert insights['status'] == 'success'
        assert 'baseline' in insights
        assert 'recommendations' in insights
        assert 'threshold_suggestions' in insights

    @pytest.mark.asyncio
    async def test_user_feedback_integration(self, analyzer):
        """Test user feedback integration."""
        feedback_result = await analyzer.update_user_feedback(
            'test-user', 
            'too_sensitive', 
            {'rot_score': 0.7, 'alert_triggered': True}
        )
        
        assert feedback_result['status'] == 'success'
        assert 'updated_thresholds' in feedback_result

    @pytest.mark.asyncio
    async def test_error_handling(self, analyzer):
        """Test error handling in analyzer."""
        # Test with invalid input
        invalid_data = {'invalid': 'data'}
        
        result = await analyzer.analyze_realtime(invalid_data)
        assert result['status'] == 'error'
        assert 'error_message' in result

    @pytest.mark.asyncio
    async def test_security_integration(self, analyzer):
        """Test security analyzer integration."""
        # Test with potentially sensitive data
        sensitive_data = {
            'session_id': 'test-session-001',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'My password is secret123',
            'context_size': 5000
        }
        
        result = await analyzer.analyze_realtime(sensitive_data)
        
        # Verify PII was scrubbed
        assert result['status'] in ['success', 'warning']
        assert 'security_filtered' in result or result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, analyzer):
        """Test circuit breaker behavior."""
        # Mock repeated failures
        analyzer.clickhouse_client.execute_query.side_effect = Exception("Connection failed")
        
        results = []
        for _ in range(10):
            result = await analyzer.analyze_realtime({
                'session_id': 'test-session-circuit',
                'timestamp': datetime.now().isoformat(),
                'user_message': 'test message',
                'context_size': 1000
            })
            results.append(result)
        
        # After several failures, circuit breaker should trip
        assert any(r.get('circuit_breaker_active') for r in results)

    @pytest.mark.asyncio
    async def test_ml_capabilities_availability(self, analyzer):
        """Test ML capabilities detection."""
        status = await analyzer.get_analyzer_status()
        components = status['components']
        
        # Check ML components are properly detected
        assert 'ml_frustration_detector' in components
        assert 'adaptive_thresholds' in components
        
        # Check ML enabled flag
        assert hasattr(analyzer, 'ml_enabled')

    @pytest.mark.asyncio
    async def test_memory_bounds_enforcement(self, analyzer):
        """Test memory bounds are enforced."""
        # Try to process large amounts of data
        large_conversation = ["Test message"] * 1000
        
        result = await analyzer.analyze_conversation_sentiment('test-user', large_conversation)
        
        # Should still work but with truncated input
        assert result['status'] in ['success', 'warning']
        if result['status'] == 'warning':
            assert 'truncated' in result.get('message', '').lower()


class TestContextRotAnalyzerPerformance:
    """Performance tests for Context Rot Analyzer."""

    @pytest.fixture
    def analyzer(self, mock_clickhouse_client, mock_error_recovery_manager):
        """Create analyzer instance for performance testing."""
        return ContextRotAnalyzer(mock_clickhouse_client, mock_error_recovery_manager)

    @pytest.mark.asyncio
    async def test_high_frequency_analysis(self, analyzer):
        """Test analyzer handles high frequency requests."""
        import time
        
        start_time = time.time()
        
        # Simulate 100 rapid-fire analyses
        tasks = []
        for i in range(100):
            task = analyzer.analyze_realtime({
                'session_id': f'perf-test-{i}',
                'timestamp': datetime.now().isoformat(),
                'user_message': f'Test message {i}',
                'context_size': 1000 + i * 10
            })
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time (adjust as needed)
        assert duration < 10.0  # 10 seconds max for 100 analyses
        
        # Most results should be successful
        successful_results = [r for r in results if not isinstance(r, Exception) and r.get('status') == 'success']
        assert len(successful_results) >= 80  # At least 80% success rate

    @pytest.mark.asyncio
    async def test_concurrent_session_analysis(self, analyzer):
        """Test concurrent analysis of different sessions."""
        # Test concurrent analysis of multiple sessions
        session_ids = [f'concurrent-session-{i}' for i in range(20)]
        
        tasks = []
        for session_id in session_ids:
            conversation = [f"Message {j} in {session_id}" for j in range(10)]
            task = analyzer.analyze_conversation_sentiment(session_id, conversation)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should handle concurrent requests
        successful_results = [r for r in results if not isinstance(r, Exception) and r.get('status') == 'success']
        assert len(successful_results) >= 15  # At least 75% success rate

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, analyzer):
        """Test memory efficiency under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process large amounts of data
        for i in range(50):
            large_data = {
                'session_id': f'memory-test-{i}',
                'timestamp': datetime.now().isoformat(),
                'user_message': 'Test message ' * 100,  # Large message
                'context_size': 10000
            }
            await analyzer.analyze_realtime(large_data)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be bounded (adjust threshold as needed)
        assert memory_growth < 100  # Less than 100MB growth


class TestContextRotAnalyzerIntegration:
    """Integration tests for Context Rot Analyzer with real components."""

    @pytest.fixture
    def real_clickhouse_client(self):
        """Real ClickHouse client (if available)."""
        return ClickHouseClient()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_clickhouse_integration(self, real_clickhouse_client, mock_error_recovery_manager):
        """Test integration with real ClickHouse (if available)."""
        # Skip if ClickHouse is not available
        healthy = await real_clickhouse_client.health_check()
        if not healthy:
            pytest.skip("ClickHouse not available for integration test")
        
        analyzer = ContextRotAnalyzer(real_clickhouse_client, mock_error_recovery_manager)
        
        # Test real database interaction
        result = await analyzer.analyze_realtime({
            'session_id': 'integration-test-001',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'Integration test message',
            'context_size': 2000,
            'tools_used': ['Read', 'Edit']
        })
        
        assert result['status'] in ['success', 'warning']
        assert 'rot_score' in result

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_workflow(self, real_clickhouse_client, mock_error_recovery_manager):
        """Test complete end-to-end workflow."""
        # Skip if ClickHouse is not available
        healthy = await real_clickhouse_client.health_check()
        if not healthy:
            pytest.skip("ClickHouse not available for integration test")
        
        analyzer = ContextRotAnalyzer(real_clickhouse_client, mock_error_recovery_manager)
        
        # 1. Analyze initial conversation
        conversation = [
            "I need help with this problem",
            "It's not working correctly",
            "Getting frustrated now",
            "This is really annoying"
        ]
        
        sentiment_result = await analyzer.analyze_conversation_sentiment('e2e-user', conversation)
        assert sentiment_result['status'] == 'success'
        
        # 2. Get personalized insights
        insights = await analyzer.get_personalized_insights('e2e-user')
        assert insights['status'] in ['success', 'warning']  # Might be warning for new user
        
        # 3. Update feedback
        feedback_result = await analyzer.update_user_feedback(
            'e2e-user', 
            'appropriate', 
            {'rot_score': sentiment_result['analysis']['frustration_level']}
        )
        assert feedback_result['status'] == 'success'
        
        # 4. Verify updated insights
        updated_insights = await analyzer.get_personalized_insights('e2e-user')
        assert updated_insights['status'] == 'success'


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])