"""Focused tests for AdaptiveThresholdManager aligned with current implementation."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.context_cleaner.telemetry.context_rot.adaptive_thresholds import (
    AdaptiveThresholdManager,
    UserBaseline,
    ThresholdConfig,
    ThresholdOptimizationResult,
)
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class StubBaselineTracker:
    """Lightweight baseline tracker stub for AdaptiveThresholdManager tests."""

    def __init__(self, baseline=None):
        self._baseline = baseline
        self.stored_baseline = None

    async def get_user_baseline(self, user_id: str):
        return self._baseline

    async def _store_user_baseline(self, baseline: UserBaseline):
        self.stored_baseline = baseline


class StubOptimizer:
    """Simple threshold optimizer stub that returns deterministic results."""

    def __init__(self):
        self.calls = 0

    async def optimize_thresholds(self, baseline: UserBaseline, historical_performance):
        self.calls += 1
        optimized = ThresholdConfig(
            user_id=baseline.user_id,
            warning_threshold=round(baseline.normal_level + 0.1, 2),
            critical_threshold=round(baseline.normal_level + 0.2, 2),
            confidence_required=0.75,
            last_optimized=datetime.now(),
        )
        return ThresholdOptimizationResult(
            optimized_thresholds=optimized,
            improvement_score=0.8,
            false_positive_reduction=0.2,
            false_negative_reduction=0.1,
            confidence=baseline.confidence,
            evidence=[],
        )


@pytest.fixture
def threshold_manager():
    fake_client = MagicMock(spec=ClickHouseClient)
    manager = AdaptiveThresholdManager(clickhouse_client=fake_client)
    return manager


@pytest.mark.asyncio
async def test_get_personalized_thresholds_returns_default_when_insufficient_data(threshold_manager):
    threshold_manager.user_baseline_tracker = StubBaselineTracker(baseline=None)

    config = await threshold_manager.get_personalized_thresholds("user-123")

    assert config.user_id == "default"
    assert config.warning_threshold == threshold_manager.default_thresholds.warning_threshold
    assert config.critical_threshold == threshold_manager.default_thresholds.critical_threshold


@pytest.mark.asyncio
async def test_get_personalized_thresholds_uses_optimizer_and_caches(threshold_manager):
    baseline = UserBaseline(
        user_id="user-123",
        normal_level=0.35,
        variance=0.08,
        session_count=12,
        last_updated=datetime.now(),
        confidence=0.85,
        avg_session_length=45.0,
        avg_messages_per_session=30.0,
        typical_conversation_flow=0.7,
        sensitivity_factor=1.0,
    )

    tracker = StubBaselineTracker(baseline=baseline)
    optimizer = StubOptimizer()
    threshold_manager.user_baseline_tracker = tracker
    threshold_manager.threshold_optimizer = optimizer

    config_first = await threshold_manager.get_personalized_thresholds("user-123")

    assert config_first.user_id == "user-123"
    assert config_first.warning_threshold == pytest.approx(0.45, rel=1e-3)
    assert config_first.critical_threshold == pytest.approx(0.55, rel=1e-3)
    assert optimizer.calls == 1

    # Subsequent call should use cache (no additional optimizer invocation)
    optimizer.calls = 0
    config_second = await threshold_manager.get_personalized_thresholds("user-123")
    assert optimizer.calls == 0
    assert config_second.warning_threshold == config_first.warning_threshold


@pytest.mark.asyncio
async def test_update_user_sensitivity_adjusts_factor_and_clears_cache(threshold_manager):
    baseline = UserBaseline(
        user_id="user-xyz",
        normal_level=0.4,
        variance=0.05,
        session_count=8,
        last_updated=datetime.now(),
        confidence=0.6,
        avg_session_length=30.0,
        avg_messages_per_session=25.0,
        typical_conversation_flow=0.6,
        sensitivity_factor=1.0,
    )

    tracker = StubBaselineTracker(baseline=baseline)
    threshold_manager.user_baseline_tracker = tracker

    cache_key = "thresholds_user-xyz"
    threshold_manager.threshold_cache[cache_key] = (threshold_manager.default_thresholds, datetime.now())

    updated = await threshold_manager.update_user_sensitivity("user-xyz", "too_sensitive")

    assert updated is True
    assert tracker.stored_baseline is not None
    assert tracker.stored_baseline.sensitivity_factor == pytest.approx(0.9)
    assert cache_key not in threshold_manager.threshold_cache


@pytest.mark.asyncio
async def test_update_user_sensitivity_handles_missing_baseline(threshold_manager):
    threshold_manager.user_baseline_tracker = StubBaselineTracker(baseline=None)

    result = await threshold_manager.update_user_sensitivity("ghost-user", "too_sensitive")

    assert result is False
