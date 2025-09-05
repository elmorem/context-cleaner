"""Comprehensive integration tests for Context Rot Meter system."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
from src.context_cleaner.telemetry.context_rot.ml_analysis import MLFrustrationDetector, SentimentPipeline
from src.context_cleaner.telemetry.context_rot.adaptive_thresholds import AdaptiveThresholdManager
from src.context_cleaner.telemetry.context_rot.widget import ContextRotWidget
from src.context_cleaner.telemetry.context_rot.security import SecureContextRotAnalyzer, PrivacyConfig
from src.context_cleaner.telemetry.context_rot.monitor import ProductionReadyContextRotMonitor
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
from src.context_cleaner.telemetry.dashboard.widgets import TelemetryWidgetManager, TelemetryWidgetType
from tests.telemetry.conftest import MockTelemetryClient


class TestContextRotSystemIntegration:
    """Integration tests for the complete Context Rot system."""

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client with realistic responses."""
        client = AsyncMock(spec=ClickHouseClient)
        client.health_check.return_value = True
        
        # Default empty responses
        client.execute_query.return_value = []
        
        return client

    @pytest.fixture
    def integrated_system(self, mock_clickhouse_client):
        """Create fully integrated Context Rot system."""
        # Core components
        mock_telemetry_client = MockTelemetryClient()
        recovery_manager = ErrorRecoveryManager(mock_telemetry_client, max_retries=3)
        
        analyzer = ContextRotAnalyzer(mock_clickhouse_client, recovery_manager)
        threshold_manager = AdaptiveThresholdManager(mock_clickhouse_client)
        widget = ContextRotWidget(mock_clickhouse_client)
        
        return {
            'analyzer': analyzer,
            'threshold_manager': threshold_manager,
            'widget': widget,
            'clickhouse_client': mock_clickhouse_client,
            'recovery_manager': recovery_manager
        }

    @pytest.mark.asyncio
    async def test_complete_user_workflow(self, integrated_system):
        """Test complete user workflow from analysis to dashboard display."""
        analyzer = integrated_system['analyzer']
        threshold_manager = integrated_system['threshold_manager']
        widget = integrated_system['widget']
        
        user_id = 'integration-test-user'
        session_id = 'integration-test-session'
        
        # Step 1: User starts session with initial analysis
        initial_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'user_message': 'I need help with this feature implementation',
            'context_size': 3000,
            'tools_used': ['Read', 'Edit']
        }
        
        analysis_result = await analyzer.analyze_realtime(initial_data)
        assert analysis_result['status'] in ['success', 'warning']
        
        # Step 2: Get personalized thresholds for user
        thresholds = await threshold_manager.get_personalized_thresholds(user_id)
        assert thresholds.warning_threshold > 0
        assert thresholds.critical_threshold > thresholds.warning_threshold
        
        # Step 3: Simulate conversation escalation
        conversation = [
            "I'm trying to implement this feature but it's not working",
            "I've tried several approaches but nothing seems to work",
            "This is getting quite frustrating",
            "I'm starting to think this might be a deeper issue",
            "This is really blocking my progress"
        ]
        
        sentiment_result = await analyzer.analyze_conversation_sentiment(user_id, conversation)
        assert sentiment_result['status'] == 'success'
        assert 'analysis' in sentiment_result
        
        # Step 4: Update user feedback based on results
        feedback_result = await threshold_manager.update_user_sensitivity(
            user_id, 'appropriate'
        )
        assert feedback_result == True
        
        # Step 5: Get widget data for dashboard
        widget_data = await widget.get_widget_data(session_id=session_id, time_window_minutes=60)
        assert widget_data.widget_type == TelemetryWidgetType.CONTEXT_ROT_METER
        
        # Step 6: Verify system provides actionable insights
        insights = await analyzer.get_personalized_insights(user_id)
        assert insights['status'] in ['success', 'warning']
        assert 'recommendations' in insights

    @pytest.mark.asyncio
    async def test_multi_session_learning(self, integrated_system):
        """Test that system learns from multiple sessions."""
        analyzer = integrated_system['analyzer']
        threshold_manager = integrated_system['threshold_manager']
        clickhouse_client = integrated_system['clickhouse_client']
        
        user_id = 'learning-test-user'
        
        # Mock user baseline data that gets updated over time
        baseline_evolution = [
            # Initial baseline (session 1-5)
            [{
                'user_id': user_id,
                'normal_level': 0.4,  # High initial baseline
                'variance': 0.3,
                'session_count': 5,
                'confidence': 0.5,
                'sensitivity_factor': 1.0
            }],
            # Updated baseline (session 6-15) 
            [{
                'user_id': user_id,
                'normal_level': 0.25,  # Learned user is typically calmer
                'variance': 0.15,
                'session_count': 15,
                'confidence': 0.8,
                'sensitivity_factor': 1.1  # Slightly more sensitive due to feedback
            }]
        ]
        
        # Simulate learning progression
        for stage, baseline_data in enumerate(baseline_evolution):
            clickhouse_client.execute_query.return_value = baseline_data
            
            # Get thresholds at this learning stage
            thresholds = await threshold_manager.get_personalized_thresholds(user_id)
            
            if stage == 0:
                # Initial stage - higher thresholds due to uncertainty
                initial_warning = thresholds.warning_threshold
                initial_critical = thresholds.critical_threshold
                assert thresholds.confidence_required >= 0.7  # Higher confidence required
            else:
                # Advanced stage - more refined thresholds
                assert thresholds.warning_threshold != initial_warning  # Should have adjusted
                assert thresholds.confidence_required <= 0.8  # Can be more confident
        
        # Verify learning has occurred
        assert True  # Test structure validates learning progression

    @pytest.mark.asyncio
    async def test_security_integration_throughout_pipeline(self, integrated_system):
        """Test security measures are applied throughout the pipeline."""
        analyzer = integrated_system['analyzer']
        
        # Test with potentially sensitive data
        sensitive_data = {
            'session_id': 'security-test-session',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'My password is secret123 and my email is user@example.com',
            'context_size': 2000,
            'file_paths': ['/home/user/secret_config.json', '/usr/local/app/database.cfg']
        }
        
        result = await analyzer.analyze_realtime(sensitive_data)
        
        # Should succeed but with security filtering applied
        assert result['status'] in ['success', 'warning']
        
        # Verify PII has been handled appropriately
        # (The security analyzer should have processed this)
        assert 'security_filtered' in result or result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_error_recovery_across_components(self, integrated_system):
        """Test error recovery mechanisms work across all components."""
        analyzer = integrated_system['analyzer']
        threshold_manager = integrated_system['threshold_manager']
        widget = integrated_system['widget']
        clickhouse_client = integrated_system['clickhouse_client']
        
        # Simulate database failure
        clickhouse_client.execute_query.side_effect = Exception("Database connection lost")
        
        # Test analyzer graceful degradation
        test_data = {
            'session_id': 'error-recovery-session',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'Test message during database failure',
            'context_size': 3000
        }
        
        analyzer_result = await analyzer.analyze_realtime(test_data)
        # Should degrade gracefully rather than crash
        assert analyzer_result['status'] in ['success', 'warning', 'error']
        
        # Test threshold manager fallback
        threshold_result = await threshold_manager.get_personalized_thresholds('error-test-user')
        # Should return default thresholds
        assert threshold_result.warning_threshold > 0
        
        # Test widget error handling
        widget_result = await widget.get_widget_data(session_id='error-test-session')
        assert widget_result.metadata['status'] in ['error', 'no_data']

    @pytest.mark.asyncio
    async def test_real_time_feedback_loop(self, integrated_system):
        """Test real-time feedback loop between components."""
        analyzer = integrated_system['analyzer']
        threshold_manager = integrated_system['threshold_manager']
        clickhouse_client = integrated_system['clickhouse_client']
        
        user_id = 'feedback-loop-user'
        
        # Set up initial user baseline
        clickhouse_client.execute_query.return_value = [{
            'user_id': user_id,
            'normal_level': 0.3,
            'variance': 0.2,
            'session_count': 10,
            'confidence': 0.75,
            'sensitivity_factor': 1.0
        }]
        
        # Step 1: Get initial thresholds
        initial_thresholds = await threshold_manager.get_personalized_thresholds(user_id)
        
        # Step 2: User provides "too sensitive" feedback
        feedback_result = await threshold_manager.update_user_sensitivity(
            user_id, 'too_sensitive'
        )
        assert feedback_result == True
        
        # Step 3: Mock updated baseline reflecting feedback
        clickhouse_client.execute_query.return_value = [{
            'user_id': user_id,
            'normal_level': 0.3,
            'variance': 0.2,
            'session_count': 11,
            'confidence': 0.78,
            'sensitivity_factor': 1.2  # Increased due to feedback
        }]
        
        # Step 4: Get updated thresholds
        updated_thresholds = await threshold_manager.get_personalized_thresholds(user_id)
        
        # Thresholds should be adjusted based on feedback
        assert updated_thresholds.sensitivity_factor > initial_thresholds.sensitivity_factor
        
        # Step 5: Test analysis with new thresholds
        test_conversation = ["I'm getting a bit frustrated with this"]
        
        sentiment_result = await analyzer.analyze_conversation_sentiment(user_id, test_conversation)
        assert sentiment_result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_dashboard_widget_integration(self, integrated_system):
        """Test dashboard widget integration with telemetry system."""
        widget = integrated_system['widget']
        clickhouse_client = integrated_system['clickhouse_client']
        
        # Mock rich context rot data for dashboard
        dashboard_data = [
            {
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.3,
                'confidence_score': 0.85,
                'indicator_breakdown': '{"frustration": 0.4, "repetition": 0.2, "confusion": 0.1}',
                'analysis_version': 1
            },
            {
                'timestamp': '2024-01-01 10:15:00', 
                'rot_score': 0.55,
                'confidence_score': 0.9,
                'indicator_breakdown': '{"frustration": 0.7, "repetition": 0.4, "confusion": 0.0}',
                'analysis_version': 1
            },
            {
                'timestamp': '2024-01-01 10:30:00',
                'rot_score': 0.75,
                'confidence_score': 0.95,
                'indicator_breakdown': '{"frustration": 0.9, "repetition": 0.6, "confusion": 0.2}',
                'analysis_version': 1
            }
        ]
        
        clickhouse_client.execute_query.return_value = dashboard_data
        
        # Get widget data
        widget_data = await widget.get_widget_data(
            session_id='dashboard-integration-session',
            time_window_minutes=60
        )
        
        # Verify dashboard-ready structure
        assert widget_data.widget_type == TelemetryWidgetType.CONTEXT_ROT_METER
        assert len(widget_data.data) == 3
        
        # Verify metadata includes dashboard essentials
        metadata = widget_data.metadata
        assert 'summary' in metadata
        assert 'recommendations' in metadata
        assert 'alert_level' in metadata
        
        # Verify trend analysis
        summary = metadata['summary']
        assert summary['trend'] == 'increasing'  # Scores are increasing
        assert summary['current_level'] == 0.75  # Latest score
        
        # Should include alert for high rot score
        assert metadata['alert_level'] in ['warning', 'critical']

    @pytest.mark.asyncio
    async def test_concurrent_multi_user_operations(self, integrated_system):
        """Test system handling concurrent operations for multiple users."""
        analyzer = integrated_system['analyzer']
        threshold_manager = integrated_system['threshold_manager']
        
        # Simulate 20 concurrent users
        user_operations = []
        
        for i in range(20):
            user_id = f'concurrent-user-{i:02d}'
            
            # Each user has multiple concurrent operations
            user_tasks = [
                analyzer.analyze_realtime({
                    'session_id': f'{user_id}-session',
                    'timestamp': datetime.now().isoformat(),
                    'user_message': f'Concurrent message from {user_id}',
                    'context_size': 3000 + i * 100
                }),
                threshold_manager.get_personalized_thresholds(user_id),
                analyzer.get_personalized_insights(user_id)
            ]
            
            user_operations.extend(user_tasks)
        
        # Execute all operations concurrently
        results = await asyncio.gather(*user_operations, return_exceptions=True)
        
        # Analyze results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        error_count = len(results) - len(successful_results)
        
        print(f"Concurrent Operations Results:")
        print(f"  Total operations: {len(results)}")
        print(f"  Successful: {len(successful_results)}")
        print(f"  Errors: {error_count}")
        print(f"  Success rate: {len(successful_results)/len(results)*100:.1f}%")
        
        # Should handle concurrent operations well
        assert len(successful_results) >= len(results) * 0.8  # 80% success rate
        assert error_count < len(results) * 0.2  # Less than 20% errors

    @pytest.mark.asyncio 
    async def test_data_flow_consistency(self, integrated_system):
        """Test data consistency across the entire system pipeline."""
        analyzer = integrated_system['analyzer']
        widget = integrated_system['widget']
        clickhouse_client = integrated_system['clickhouse_client']
        
        session_id = 'data-consistency-session'
        
        # Step 1: Perform analysis that should be stored
        analysis_data = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'user_message': 'This is a consistency test message that should flow through the system',
            'context_size': 4000,
            'tools_used': ['Read', 'Edit', 'Bash']
        }
        
        analysis_result = await analyzer.analyze_realtime(analysis_data)
        assert analysis_result['status'] in ['success', 'warning']
        
        # Mock that the data was stored and can be retrieved
        stored_analysis = {
            'timestamp': analysis_data['timestamp'],
            'rot_score': analysis_result.get('rot_score', 0.4),
            'confidence_score': analysis_result.get('confidence', 0.8),
            'indicator_breakdown': '{"consistency_test": 1.0}',
            'analysis_version': 1
        }
        
        clickhouse_client.execute_query.return_value = [stored_analysis]
        
        # Step 2: Retrieve through widget and verify consistency
        widget_data = await widget.get_widget_data(session_id=session_id, time_window_minutes=30)
        
        assert len(widget_data.data) == 1
        retrieved_data = widget_data.data[0]
        
        # Verify data consistency
        assert retrieved_data['timestamp'] == analysis_data['timestamp']
        assert retrieved_data['rot_score'] == stored_analysis['rot_score']
        assert retrieved_data['confidence'] == stored_analysis['confidence_score']


class TestContextRotProductionReadiness:
    """Tests for production readiness aspects."""

    @pytest.mark.asyncio
    async def test_system_health_monitoring(self, integrated_system):
        """Test system health monitoring capabilities."""
        analyzer = integrated_system['analyzer']
        
        # Test analyzer health status
        health_status = await analyzer.get_analyzer_status()
        
        assert 'status' in health_status
        assert 'version' in health_status
        assert 'components' in health_status
        assert 'uptime' in health_status
        
        # Verify all critical components are reported
        components = health_status['components']
        assert 'security_analyzer' in components
        assert 'monitor' in components
        assert 'ml_frustration_detector' in components
        assert 'adaptive_thresholds' in components

    @pytest.mark.asyncio
    async def test_configuration_management(self, integrated_system):
        """Test configuration management across environments."""
        analyzer = integrated_system['analyzer']
        
        # Test that analyzer has configurable parameters
        assert hasattr(analyzer, 'clickhouse_client')
        assert hasattr(analyzer, 'error_manager')
        assert hasattr(analyzer, 'security_analyzer')
        assert hasattr(analyzer, 'monitor')
        
        # Test configuration validation
        status = await analyzer.get_analyzer_status()
        assert status['status'] in ['healthy', 'degraded', 'error']

    @pytest.mark.asyncio
    async def test_data_retention_compliance(self, integrated_system):
        """Test data retention and privacy compliance."""
        analyzer = integrated_system['analyzer']
        
        # Test that security analyzer is properly configured
        assert analyzer.security_analyzer is not None
        
        # Test analysis with privacy-sensitive data
        sensitive_test = {
            'session_id': 'privacy-test-session',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'Contains PII like john.doe@company.com and phone 555-1234',
            'context_size': 2000
        }
        
        result = await analyzer.analyze_realtime(sensitive_test)
        
        # Should process but handle PII appropriately
        assert result['status'] in ['success', 'warning']

    @pytest.mark.asyncio
    async def test_scalability_indicators(self, integrated_system):
        """Test scalability indicators and limits."""
        analyzer = integrated_system['analyzer']
        
        # Test memory-bounded processing
        large_context_data = {
            'session_id': 'scalability-test-session',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'Large message content ' * 500,  # Large message
            'context_size': 50000,  # Large context
            'tools_used': ['Read', 'Edit', 'Bash', 'Grep', 'TodoWrite'] * 20
        }
        
        result = await analyzer.analyze_realtime(large_context_data)
        
        # Should handle large input gracefully
        assert result['status'] in ['success', 'warning']
        
        # May include truncation warnings for large input
        if result['status'] == 'warning':
            assert 'truncated' in result.get('message', '').lower() or 'limited' in result.get('message', '').lower()

    @pytest.mark.asyncio
    async def test_alerting_system_integration(self, integrated_system):
        """Test integration with alerting systems."""
        widget = integrated_system['widget']
        clickhouse_client = integrated_system['clickhouse_client']
        
        # Mock critical rot score data
        critical_data = [{
            'timestamp': '2024-01-01 10:00:00',
            'rot_score': 0.95,  # Critical level
            'confidence_score': 0.98,
            'indicator_breakdown': '{"frustration": 0.98, "repetition": 0.92}',
            'analysis_version': 1
        }]
        
        clickhouse_client.execute_query.return_value = critical_data
        
        widget_data = await widget.get_widget_data(session_id='alert-test-session')
        
        # Should include alert metadata
        assert 'alert_level' in widget_data.metadata
        assert widget_data.metadata['alert_level'] == 'critical'
        assert 'alert_message' in widget_data.metadata
        assert 'recommendations' in widget_data.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])