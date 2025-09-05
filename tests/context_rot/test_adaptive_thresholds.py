"""Comprehensive tests for Adaptive Thresholds components."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.context_cleaner.telemetry.context_rot.adaptive_thresholds import (
    AdaptiveThresholdManager, UserBaselineTracker, ThresholdOptimizer,
    UserBaseline, ThresholdConfig, SensitivityFeedback
)
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class TestUserBaselineTracker:
    """Test suite for User Baseline Tracker."""

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client for testing."""
        client = AsyncMock(spec=ClickHouseClient)
        client.health_check.return_value = True
        client.execute_query.return_value = []
        return client

    @pytest.fixture
    def baseline_tracker(self, mock_clickhouse_client):
        """Create baseline tracker for testing."""
        return UserBaselineTracker(mock_clickhouse_client)

    @pytest.mark.asyncio
    async def test_get_user_baseline_existing_user(self, baseline_tracker, mock_clickhouse_client):
        """Test getting baseline for existing user."""
        # Mock existing user data
        mock_clickhouse_client.execute_query.return_value = [
            {
                'user_id': 'test_user',
                'normal_level': 0.25,
                'variance': 0.15,
                'session_count': 10,
                'last_updated': '2024-01-01 10:00:00',
                'confidence': 0.8,
                'avg_session_length': 45.5,
                'avg_messages_per_session': 12.3,
                'typical_conversation_flow': 0.75,
                'sensitivity_factor': 1.0
            }
        ]
        
        baseline = await baseline_tracker.get_user_baseline('test_user')
        
        assert isinstance(baseline, UserBaseline)
        assert baseline.user_id == 'test_user'
        assert baseline.normal_level == 0.25
        assert baseline.variance == 0.15
        assert baseline.session_count == 10
        assert baseline.confidence == 0.8
        assert baseline.avg_session_length == 45.5
        assert baseline.sensitivity_factor == 1.0

    @pytest.mark.asyncio
    async def test_get_user_baseline_new_user(self, baseline_tracker, mock_clickhouse_client):
        """Test getting baseline for new user (no data)."""
        # Mock no existing data
        mock_clickhouse_client.execute_query.return_value = []
        
        baseline = await baseline_tracker.get_user_baseline('new_user')
        
        assert isinstance(baseline, UserBaseline)
        assert baseline.user_id == 'new_user'
        assert baseline.normal_level == 0.4  # Default
        assert baseline.variance == 0.2  # Default
        assert baseline.session_count == 0
        assert baseline.confidence == 0.3  # Low confidence for new user
        assert baseline.sensitivity_factor == 1.0  # Default

    @pytest.mark.asyncio
    async def test_update_user_baseline(self, baseline_tracker, mock_clickhouse_client):
        """Test updating user baseline."""
        baseline = UserBaseline(
            user_id='test_user',
            normal_level=0.3,
            variance=0.18,
            session_count=15,
            confidence=0.85,
            avg_session_length=50.0,
            avg_messages_per_session=14.0,
            typical_conversation_flow=0.8,
            sensitivity_factor=1.1
        )
        
        success = await baseline_tracker.update_user_baseline(baseline)
        
        assert success == True
        mock_clickhouse_client.execute_query.assert_called()

    @pytest.mark.asyncio
    async def test_calculate_baseline_from_sessions(self, baseline_tracker):
        """Test baseline calculation from session data."""
        session_data = [
            {'frustration_level': 0.2, 'session_length': 40, 'message_count': 10, 'flow_quality': 0.8},
            {'frustration_level': 0.3, 'session_length': 45, 'message_count': 12, 'flow_quality': 0.7},
            {'frustration_level': 0.25, 'session_length': 50, 'message_count': 15, 'flow_quality': 0.75},
            {'frustration_level': 0.35, 'session_length': 42, 'message_count': 11, 'flow_quality': 0.65},
            {'frustration_level': 0.28, 'session_length': 48, 'message_count': 13, 'flow_quality': 0.78}
        ]
        
        baseline = baseline_tracker.calculate_baseline_from_sessions('test_user', session_data)
        
        assert isinstance(baseline, UserBaseline)
        assert baseline.user_id == 'test_user'
        assert 0.2 <= baseline.normal_level <= 0.35  # Within observed range
        assert baseline.variance > 0  # Should have some variance
        assert baseline.session_count == len(session_data)
        assert baseline.confidence > 0.5  # Should have reasonable confidence with 5 sessions
        assert 40 <= baseline.avg_session_length <= 50
        assert 10 <= baseline.avg_messages_per_session <= 15

    @pytest.mark.asyncio
    async def test_calculate_baseline_insufficient_data(self, baseline_tracker):
        """Test baseline calculation with insufficient data."""
        insufficient_data = [
            {'frustration_level': 0.3, 'session_length': 45, 'message_count': 12, 'flow_quality': 0.7}
        ]
        
        baseline = baseline_tracker.calculate_baseline_from_sessions('test_user', insufficient_data)
        
        assert isinstance(baseline, UserBaseline)
        assert baseline.confidence <= 0.4  # Low confidence with insufficient data
        assert baseline.session_count == 1

    @pytest.mark.asyncio
    async def test_get_baseline_statistics(self, baseline_tracker, mock_clickhouse_client):
        """Test getting overall baseline statistics."""
        mock_clickhouse_client.execute_query.return_value = [
            {
                'total_users': 100,
                'avg_normal_level': 0.35,
                'avg_confidence': 0.75,
                'reliable_baselines': 80
            }
        ]
        
        stats = await baseline_tracker.get_baseline_statistics()
        
        assert stats['total_users'] == 100
        assert stats['avg_normal_level'] == 0.35
        assert stats['avg_confidence'] == 0.75
        assert stats['reliable_baselines'] == 80


class TestThresholdOptimizer:
    """Test suite for Threshold Optimizer."""

    @pytest.fixture
    def threshold_optimizer(self):
        """Create threshold optimizer for testing."""
        return ThresholdOptimizer()

    @pytest.mark.asyncio
    async def test_optimize_thresholds_balanced(self, threshold_optimizer):
        """Test threshold optimization for balanced user."""
        baseline = UserBaseline(
            user_id='test_user',
            normal_level=0.3,
            variance=0.15,
            session_count=20,
            confidence=0.85,
            sensitivity_factor=1.0
        )
        
        config = await threshold_optimizer.optimize_thresholds(baseline)
        
        assert isinstance(config, ThresholdConfig)
        assert config.warning_threshold > baseline.normal_level
        assert config.critical_threshold > config.warning_threshold
        assert 0.0 <= config.confidence_required <= 1.0
        assert config.sensitivity_factor == 1.0

    @pytest.mark.asyncio
    async def test_optimize_thresholds_high_variance(self, threshold_optimizer):
        """Test threshold optimization for high variance user."""
        baseline = UserBaseline(
            user_id='test_user',
            normal_level=0.3,
            variance=0.35,  # High variance
            session_count=15,
            confidence=0.7,
            sensitivity_factor=1.0
        )
        
        config = await threshold_optimizer.optimize_thresholds(baseline)
        
        assert isinstance(config, ThresholdConfig)
        # Should have higher thresholds due to high variance
        assert config.warning_threshold >= baseline.normal_level + baseline.variance
        assert config.critical_threshold >= config.warning_threshold + 0.2

    @pytest.mark.asyncio
    async def test_optimize_thresholds_low_confidence(self, threshold_optimizer):
        """Test threshold optimization for low confidence baseline."""
        baseline = UserBaseline(
            user_id='test_user',
            normal_level=0.3,
            variance=0.15,
            session_count=3,  # Low session count
            confidence=0.4,   # Low confidence
            sensitivity_factor=1.0
        )
        
        config = await threshold_optimizer.optimize_thresholds(baseline)
        
        assert isinstance(config, ThresholdConfig)
        # Should require higher confidence for alerts due to low baseline confidence
        assert config.confidence_required >= 0.7

    @pytest.mark.asyncio
    async def test_apply_sensitivity_feedback(self, threshold_optimizer):
        """Test applying sensitivity feedback to thresholds."""
        original_config = ThresholdConfig(
            warning_threshold=0.5,
            critical_threshold=0.7,
            confidence_required=0.8,
            sensitivity_factor=1.0
        )
        
        # Test "too sensitive" feedback
        adjusted_config = threshold_optimizer.apply_sensitivity_feedback(
            original_config, SensitivityFeedback.TOO_SENSITIVE
        )
        
        assert adjusted_config.warning_threshold > original_config.warning_threshold
        assert adjusted_config.critical_threshold > original_config.critical_threshold
        assert adjusted_config.sensitivity_factor > 1.0

    @pytest.mark.asyncio
    async def test_apply_not_sensitive_feedback(self, threshold_optimizer):
        """Test applying 'not sensitive enough' feedback."""
        original_config = ThresholdConfig(
            warning_threshold=0.6,
            critical_threshold=0.8,
            confidence_required=0.8,
            sensitivity_factor=1.0
        )
        
        # Test "not sensitive enough" feedback
        adjusted_config = threshold_optimizer.apply_sensitivity_feedback(
            original_config, SensitivityFeedback.NOT_SENSITIVE_ENOUGH
        )
        
        assert adjusted_config.warning_threshold < original_config.warning_threshold
        assert adjusted_config.critical_threshold < original_config.critical_threshold
        assert adjusted_config.sensitivity_factor < 1.0

    @pytest.mark.asyncio
    async def test_calculate_effectiveness_score(self, threshold_optimizer):
        """Test effectiveness score calculation."""
        feedback_history = [
            {'feedback': SensitivityFeedback.APPROPRIATE, 'timestamp': datetime.now()},
            {'feedback': SensitivityFeedback.APPROPRIATE, 'timestamp': datetime.now()},
            {'feedback': SensitivityFeedback.TOO_SENSITIVE, 'timestamp': datetime.now()},
            {'feedback': SensitivityFeedback.APPROPRIATE, 'timestamp': datetime.now()},
        ]
        
        score = threshold_optimizer.calculate_effectiveness_score(feedback_history)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.7  # Should be high with mostly appropriate feedback


class TestAdaptiveThresholdManager:
    """Test suite for Adaptive Threshold Manager."""

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client for testing."""
        client = AsyncMock(spec=ClickHouseClient)
        client.health_check.return_value = True
        client.execute_query.return_value = []
        return client

    @pytest.fixture
    def threshold_manager(self, mock_clickhouse_client):
        """Create adaptive threshold manager for testing."""
        return AdaptiveThresholdManager(mock_clickhouse_client)

    @pytest.mark.asyncio
    async def test_get_personalized_thresholds_existing_user(self, threshold_manager, mock_clickhouse_client):
        """Test getting personalized thresholds for existing user."""
        # Mock existing baseline data
        mock_clickhouse_client.execute_query.return_value = [
            {
                'user_id': 'test_user',
                'normal_level': 0.25,
                'variance': 0.15,
                'session_count': 15,
                'last_updated': '2024-01-01 10:00:00',
                'confidence': 0.8,
                'avg_session_length': 45.5,
                'avg_messages_per_session': 12.3,
                'typical_conversation_flow': 0.75,
                'sensitivity_factor': 1.0
            }
        ]
        
        config = await threshold_manager.get_personalized_thresholds('test_user')
        
        assert isinstance(config, ThresholdConfig)
        assert config.warning_threshold > 0.25  # Should be above normal level
        assert config.critical_threshold > config.warning_threshold
        assert config.sensitivity_factor == 1.0

    @pytest.mark.asyncio
    async def test_get_personalized_thresholds_new_user(self, threshold_manager, mock_clickhouse_client):
        """Test getting personalized thresholds for new user."""
        # Mock no existing data (empty result)
        mock_clickhouse_client.execute_query.return_value = []
        
        config = await threshold_manager.get_personalized_thresholds('new_user')
        
        assert isinstance(config, ThresholdConfig)
        # Should use default values for new user
        assert config.warning_threshold == 0.6  # Default warning threshold
        assert config.critical_threshold == 0.8  # Default critical threshold
        assert config.confidence_required >= 0.7  # Higher confidence required for new users

    @pytest.mark.asyncio
    async def test_update_user_sensitivity_appropriate(self, threshold_manager):
        """Test updating user sensitivity with 'appropriate' feedback."""
        result = await threshold_manager.update_user_sensitivity(
            'test_user', 
            SensitivityFeedback.APPROPRIATE.value
        )
        
        assert result == True

    @pytest.mark.asyncio
    async def test_update_user_sensitivity_too_sensitive(self, threshold_manager):
        """Test updating user sensitivity with 'too_sensitive' feedback."""
        result = await threshold_manager.update_user_sensitivity(
            'test_user',
            SensitivityFeedback.TOO_SENSITIVE.value
        )
        
        assert result == True

    @pytest.mark.asyncio
    async def test_update_user_sensitivity_invalid_feedback(self, threshold_manager):
        """Test handling invalid sensitivity feedback."""
        result = await threshold_manager.update_user_sensitivity(
            'test_user',
            'invalid_feedback'
        )
        
        assert result == False

    @pytest.mark.asyncio
    async def test_recalibrate_user_thresholds(self, threshold_manager, mock_clickhouse_client):
        """Test threshold recalibration based on recent sessions."""
        # Mock recent session data
        recent_sessions = [
            {
                'frustration_level': 0.2,
                'session_length': 40,
                'message_count': 10,
                'flow_quality': 0.8,
                'timestamp': '2024-01-01 10:00:00'
            },
            {
                'frustration_level': 0.3,
                'session_length': 45,
                'message_count': 12,
                'flow_quality': 0.7,
                'timestamp': '2024-01-01 11:00:00'
            }
        ]
        
        mock_clickhouse_client.execute_query.return_value = recent_sessions
        
        result = await threshold_manager.recalibrate_user_thresholds('test_user')
        
        assert result == True

    @pytest.mark.asyncio
    async def test_get_threshold_effectiveness(self, threshold_manager, mock_clickhouse_client):
        """Test getting threshold effectiveness metrics."""
        # Mock feedback history
        mock_clickhouse_client.execute_query.return_value = [
            {
                'feedback': 'appropriate',
                'timestamp': '2024-01-01 10:00:00',
                'rot_score': 0.7
            },
            {
                'feedback': 'too_sensitive',
                'timestamp': '2024-01-01 11:00:00',
                'rot_score': 0.5
            }
        ]
        
        effectiveness = await threshold_manager.get_threshold_effectiveness('test_user')
        
        assert isinstance(effectiveness, dict)
        assert 'effectiveness_score' in effectiveness
        assert 'total_feedback' in effectiveness
        assert 'appropriate_ratio' in effectiveness

    @pytest.mark.asyncio
    async def test_bulk_threshold_optimization(self, threshold_manager, mock_clickhouse_client):
        """Test bulk threshold optimization for multiple users."""
        # Mock user list
        mock_clickhouse_client.execute_query.return_value = [
            {'user_id': 'user1'}, 
            {'user_id': 'user2'}, 
            {'user_id': 'user3'}
        ]
        
        results = await threshold_manager.bulk_threshold_optimization()
        
        assert isinstance(results, dict)
        assert 'optimized_users' in results
        assert 'failed_users' in results
        assert 'total_processed' in results

    @pytest.mark.asyncio
    async def test_threshold_configuration_validation(self, threshold_manager):
        """Test validation of threshold configurations."""
        # Test valid configuration
        valid_config = ThresholdConfig(
            warning_threshold=0.5,
            critical_threshold=0.7,
            confidence_required=0.8,
            sensitivity_factor=1.0
        )
        
        is_valid = threshold_manager.validate_threshold_config(valid_config)
        assert is_valid == True
        
        # Test invalid configuration (critical < warning)
        invalid_config = ThresholdConfig(
            warning_threshold=0.7,
            critical_threshold=0.5,  # Less than warning
            confidence_required=0.8,
            sensitivity_factor=1.0
        )
        
        is_valid = threshold_manager.validate_threshold_config(invalid_config)
        assert is_valid == False

    @pytest.mark.asyncio
    async def test_error_handling_database_failure(self, threshold_manager, mock_clickhouse_client):
        """Test error handling when database is unavailable."""
        # Mock database failure
        mock_clickhouse_client.execute_query.side_effect = Exception("Database connection failed")
        
        config = await threshold_manager.get_personalized_thresholds('test_user')
        
        # Should return default configuration on error
        assert isinstance(config, ThresholdConfig)
        assert config.warning_threshold == 0.6  # Default values
        assert config.critical_threshold == 0.8


class TestAdaptiveThresholdsIntegration:
    """Integration tests for Adaptive Thresholds system."""

    @pytest.mark.asyncio
    async def test_complete_threshold_lifecycle(self):
        """Test complete threshold adaptation lifecycle."""
        # Create mock client
        mock_clickhouse = AsyncMock(spec=ClickHouseClient)
        mock_clickhouse.health_check.return_value = True
        mock_clickhouse.execute_query.return_value = []  # New user initially
        
        manager = AdaptiveThresholdManager(mock_clickhouse)
        
        # 1. Get initial thresholds (new user)
        initial_config = await manager.get_personalized_thresholds('lifecycle_user')
        assert isinstance(initial_config, ThresholdConfig)
        
        # 2. Simulate user feedback (too sensitive)
        feedback_result = await manager.update_user_sensitivity(
            'lifecycle_user', 
            SensitivityFeedback.TOO_SENSITIVE.value
        )
        assert feedback_result == True
        
        # 3. Mock updated baseline after feedback
        mock_clickhouse.execute_query.return_value = [
            {
                'user_id': 'lifecycle_user',
                'normal_level': 0.3,
                'variance': 0.15,
                'session_count': 5,
                'confidence': 0.6,
                'sensitivity_factor': 1.2  # Increased due to feedback
            }
        ]
        
        # 4. Get updated thresholds
        updated_config = await manager.get_personalized_thresholds('lifecycle_user')
        
        # Thresholds should be adjusted based on feedback
        assert updated_config.sensitivity_factor >= initial_config.sensitivity_factor

    @pytest.mark.asyncio
    async def test_concurrent_threshold_updates(self):
        """Test concurrent threshold updates for multiple users."""
        mock_clickhouse = AsyncMock(spec=ClickHouseClient)
        mock_clickhouse.health_check.return_value = True
        mock_clickhouse.execute_query.return_value = []
        
        manager = AdaptiveThresholdManager(mock_clickhouse)
        
        # Test concurrent operations
        user_ids = [f'concurrent_user_{i}' for i in range(10)]
        
        tasks = []
        for user_id in user_ids:
            task = manager.get_personalized_thresholds(user_id)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should handle concurrent requests successfully
        successful_results = [r for r in results if isinstance(r, ThresholdConfig)]
        assert len(successful_results) == len(user_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])