"""Tests for session analytics and comparison."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
import statistics

from src.context_cleaner.telemetry.analytics.session_analysis import (
    SessionAnalyticsEngine,
    SessionComparison,
    TrendAnalysis,
    SessionInsights,
    ProductivityTrend,
    TrendDirection,
    MetricType,
)


class TestSessionAnalyticsEngine:
    """Test suite for SessionAnalyticsEngine."""
    
    @pytest.fixture
    def analytics_engine(self, mock_telemetry_client):
        """Create analytics engine with mocked dependencies."""
        return SessionAnalyticsEngine(mock_telemetry_client)
    
    @pytest.fixture
    def sample_session_a(self):
        """Create sample session A for comparison."""
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        return SessionMetrics(
            session_id="session-a",
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now() - timedelta(hours=1),
            api_calls=15,
            total_cost=2.0,
            total_input_tokens=6000,
            total_output_tokens=1200,
            error_count=1,
            tools_used=["Read", "Edit", "Bash", "TodoWrite"]
        )
    
    @pytest.fixture
    def sample_session_b(self):
        """Create sample session B for comparison."""
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        return SessionMetrics(
            session_id="session-b",
            start_time=datetime.now() - timedelta(hours=3),
            end_time=datetime.now() - timedelta(hours=1, minutes=30),
            api_calls=20,
            total_cost=1.5,
            total_input_tokens=8000,
            total_output_tokens=1000,
            error_count=0,
            tools_used=["Read", "Grep", "Edit", "TodoWrite"]
        )
    
    @pytest.mark.asyncio
    async def test_compare_sessions(self, analytics_engine, mock_telemetry_client, 
                                  sample_session_a, sample_session_b):
        """Test session comparison functionality."""
        # Mock session retrieval
        def get_session_side_effect(session_id):
            if session_id == "session-a":
                return sample_session_a
            elif session_id == "session-b":
                return sample_session_b
            return None
        
        mock_telemetry_client.get_session_metrics = AsyncMock(side_effect=get_session_side_effect)
        
        comparison = await analytics_engine.compare_sessions("session-a", "session-b")
        
        assert isinstance(comparison, SessionComparison)
        assert comparison.session_a == "session-a"
        assert comparison.session_b == "session-b"
        assert comparison.cost_difference == -0.5  # Session B is $0.50 cheaper
        assert comparison.efficiency_difference != 0  # Different cost per token
        assert comparison.duration_difference != 0  # Different durations
        assert 0 <= comparison.tool_usage_similarity <= 1.0
        assert len(comparison.insights) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_session_trends(self, analytics_engine, mock_telemetry_client):
        """Test session trend analysis."""
        # Mock multiple sessions with improving productivity
        sessions = []
        for i in range(10):
            from src.context_cleaner.telemetry.clients.base import SessionMetrics
            session = SessionMetrics(
                session_id=f"session-{i}",
                start_time=datetime.now() - timedelta(days=i),
                end_time=datetime.now() - timedelta(days=i, hours=-1),
                api_calls=10 + i,  # Increasing API calls
                total_cost=2.0 - (i * 0.1),  # Decreasing cost (improving)
                total_input_tokens=5000,
                total_output_tokens=1000,
                error_count=max(0, 2 - i),  # Decreasing errors
                tools_used=["Read", "Edit"]
            )
            sessions.append(session)
        
        # Mock the _get_recent_sessions method
        analytics_engine._get_recent_sessions = AsyncMock(return_value=sessions)
        
        trend = await analytics_engine.analyze_session_trends(days=30, metric_type=MetricType.COST)
        
        assert isinstance(trend, TrendAnalysis)
        assert trend.metric_type == MetricType.COST
        assert trend.direction in [TrendDirection.IMPROVING, TrendDirection.DECLINING, TrendDirection.STABLE]
        assert len(trend.data_points) == len(sessions)
        assert trend.confidence > 0
        assert len(trend.insights) > 0
    
    @pytest.mark.asyncio
    async def test_get_session_insights(self, analytics_engine, mock_telemetry_client, sample_session_a):
        """Test comprehensive session insights generation."""
        mock_telemetry_client.get_session_metrics = AsyncMock(return_value=sample_session_a)
        
        insights = await analytics_engine.get_session_insights("session-a")
        
        assert isinstance(insights, SessionInsights)
        assert insights.session_id == "session-a"
        assert 0 <= insights.productivity_score <= 1.0
        assert 0 <= insights.cost_efficiency <= 1.0
        assert 0 <= insights.tool_effectiveness <= 1.0
        assert 0 <= insights.error_resilience <= 1.0
        assert 0 <= insights.time_management <= 1.0
        
        # Should have some insights
        total_insights = len(insights.strengths) + len(insights.improvement_areas)
        assert total_insights > 0
        assert len(insights.recommendations) >= len(insights.improvement_areas)
    
    @pytest.mark.asyncio
    async def test_get_productivity_trends(self, analytics_engine, mock_telemetry_client):
        """Test productivity trend analysis."""
        # Mock sessions with varying productivity
        sessions = []
        productivity_scores = [0.8, 0.7, 0.9, 0.6, 0.8, 0.85, 0.75]
        
        for i, score in enumerate(productivity_scores):
            from src.context_cleaner.telemetry.clients.base import SessionMetrics
            
            # Create session at different hours to test peak hour detection
            hour = 9 + (i % 8)  # Spread across work hours
            start_time = datetime.now().replace(hour=hour, minute=0) - timedelta(days=i)
            
            session = SessionMetrics(
                session_id=f"session-{i}",
                start_time=start_time,
                end_time=start_time + timedelta(hours=1),
                api_calls=int(score * 20),  # Scale API calls with productivity
                total_cost=2.0 - score,  # Higher productivity = lower cost
                total_input_tokens=5000,
                total_output_tokens=1000,
                error_count=int((1 - score) * 3),  # Higher productivity = fewer errors
                tools_used=["Read", "Edit", "Bash"]
            )
            sessions.append(session)
        
        analytics_engine._get_recent_sessions = AsyncMock(return_value=sessions)
        
        # Mock productivity score calculation to return our predetermined scores
        original_calc = analytics_engine._calculate_productivity_score
        analytics_engine._calculate_productivity_score = AsyncMock(
            side_effect=lambda s: productivity_scores[sessions.index(s)]
        )
        
        trend = await analytics_engine.get_productivity_trends(period="weekly")
        
        # Restore original method
        analytics_engine._calculate_productivity_score = original_calc
        
        assert isinstance(trend, ProductivityTrend)
        assert trend.period == "weekly"
        assert 0 <= trend.average_score <= 1.0
        assert trend.best_session in [s.session_id for s in sessions]
        assert trend.worst_session in [s.session_id for s in sessions]
        assert 0 <= trend.consistency_score <= 1.0
        assert isinstance(trend.peak_hours, list)
        assert isinstance(trend.factors, dict)
    
    def test_calculate_productivity_score(self, analytics_engine, sample_session_a):
        """Test productivity score calculation."""
        import asyncio
        
        # Test with different session characteristics
        score = asyncio.run(analytics_engine._calculate_productivity_score(sample_session_a))
        
        assert 0 <= score <= 1.0
        
        # Test with perfect session (no errors, good cost efficiency)
        perfect_session = sample_session_a
        perfect_session.error_count = 0
        perfect_session.total_cost = 0.5  # Very efficient
        perfect_session.api_calls = 20
        
        perfect_score = asyncio.run(analytics_engine._calculate_productivity_score(perfect_session))
        assert perfect_score >= score  # Perfect session should score higher
    
    def test_calculate_cost_efficiency(self, analytics_engine, sample_session_a):
        """Test cost efficiency calculation."""
        efficiency = analytics_engine._calculate_cost_efficiency(sample_session_a)
        
        assert 0 <= efficiency <= 1.0
        
        # Test with very efficient session
        efficient_session = sample_session_a
        efficient_session.total_cost = 0.1
        efficient_session.total_input_tokens = 10000
        
        efficient_score = analytics_engine._calculate_cost_efficiency(efficient_session)
        assert efficient_score > efficiency
    
    def test_calculate_tool_effectiveness(self, analytics_engine, sample_session_a):
        """Test tool usage effectiveness calculation."""
        effectiveness = analytics_engine._calculate_tool_effectiveness(sample_session_a)
        
        assert 0 <= effectiveness <= 1.0
        
        # Test with efficient tool pattern
        efficient_session = sample_session_a
        efficient_session.tools_used = ["Read", "Edit", "Read", "Edit", "Bash"]
        
        efficient_score = analytics_engine._calculate_tool_effectiveness(efficient_session)
        # Should get bonus for Read->Edit pattern
        assert efficient_score >= effectiveness
    
    def test_calculate_tool_similarity(self, analytics_engine):
        """Test tool usage similarity calculation."""
        tools_a = ["Read", "Edit", "Bash", "TodoWrite"]
        tools_b = ["Read", "Grep", "Edit", "TodoWrite"]
        tools_c = ["Write", "Delete", "Copy"]
        
        # Similar tool sets
        similarity_ab = analytics_engine._calculate_tool_similarity(tools_a, tools_b)
        assert 0 < similarity_ab < 1.0
        
        # Very different tool sets
        similarity_ac = analytics_engine._calculate_tool_similarity(tools_a, tools_c)
        assert similarity_ac < similarity_ab
        
        # Identical tool sets
        similarity_aa = analytics_engine._calculate_tool_similarity(tools_a, tools_a)
        assert similarity_aa == 1.0
        
        # Empty tool sets
        similarity_empty = analytics_engine._calculate_tool_similarity([], [])
        assert similarity_empty == 0.0
    
    def test_determine_trend_direction(self, analytics_engine):
        """Test trend direction determination."""
        # Improving trend
        improving_values = [1.0, 1.2, 1.4, 1.6, 1.8]
        improving_trend = analytics_engine._determine_trend_direction(improving_values)
        assert improving_trend == TrendDirection.IMPROVING
        
        # Declining trend
        declining_values = [2.0, 1.8, 1.6, 1.4, 1.2]
        declining_trend = analytics_engine._determine_trend_direction(declining_values)
        assert declining_trend == TrendDirection.DECLINING
        
        # Stable trend
        stable_values = [1.5, 1.5, 1.5, 1.5, 1.5]
        stable_trend = analytics_engine._determine_trend_direction(stable_values)
        assert stable_trend == TrendDirection.STABLE
        
        # Volatile trend
        volatile_values = [1.0, 2.0, 0.5, 3.0, 1.0]
        volatile_trend = analytics_engine._determine_trend_direction(volatile_values)
        assert volatile_trend == TrendDirection.VOLATILE
    
    def test_calculate_change_percentage(self, analytics_engine):
        """Test percentage change calculation."""
        # 50% increase
        values = [2.0, 3.0]
        change = analytics_engine._calculate_change_percentage(values)
        assert abs(change - 50.0) < 0.1
        
        # 25% decrease
        values = [4.0, 3.0]
        change = analytics_engine._calculate_change_percentage(values)
        assert abs(change - (-25.0)) < 0.1
        
        # No change
        values = [1.0, 1.0]
        change = analytics_engine._calculate_change_percentage(values)
        assert abs(change) < 0.1
    
    def test_calculate_trend_confidence(self, analytics_engine):
        """Test trend confidence calculation."""
        # Consistent data should have high confidence
        consistent_values = [1.0, 1.0, 1.0, 1.0, 1.0]
        high_confidence = analytics_engine._calculate_trend_confidence(consistent_values)
        
        # Inconsistent data should have low confidence
        inconsistent_values = [1.0, 5.0, 0.5, 10.0, 2.0]
        low_confidence = analytics_engine._calculate_trend_confidence(inconsistent_values)
        
        assert high_confidence > low_confidence
        assert 0 <= high_confidence <= 1.0
        assert 0 <= low_confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_extract_metric_value(self, analytics_engine, sample_session_a):
        """Test metric value extraction from sessions."""
        # Test different metric types
        cost_value = await analytics_engine._extract_metric_value(sample_session_a, MetricType.COST)
        assert cost_value == sample_session_a.total_cost
        
        efficiency_value = await analytics_engine._extract_metric_value(sample_session_a, MetricType.EFFICIENCY)
        assert 0 <= efficiency_value <= 1.0
        
        error_rate = await analytics_engine._extract_metric_value(sample_session_a, MetricType.ERROR_RATE)
        assert error_rate == sample_session_a.error_count / sample_session_a.api_calls
        
        duration = await analytics_engine._extract_metric_value(sample_session_a, MetricType.DURATION)
        assert duration > 0  # Should be positive
        
        productivity = await analytics_engine._extract_metric_value(sample_session_a, MetricType.PRODUCTIVITY)
        assert 0 <= productivity <= 1.0
        
        tool_usage = await analytics_engine._extract_metric_value(sample_session_a, MetricType.TOOL_USAGE)
        assert tool_usage == len(set(sample_session_a.tools_used))
    
    def test_get_session_duration(self, analytics_engine, sample_session_a):
        """Test session duration calculation."""
        # Test completed session
        duration = analytics_engine._get_session_duration(sample_session_a)
        assert duration > 0
        
        # Test ongoing session (no end time)
        ongoing_session = sample_session_a
        ongoing_session.end_time = None
        ongoing_duration = analytics_engine._get_session_duration(ongoing_session)
        assert ongoing_duration > 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, analytics_engine, mock_telemetry_client):
        """Test error handling in analytics operations."""
        # Mock client to raise exceptions
        mock_telemetry_client.get_session_metrics = AsyncMock(
            side_effect=Exception("Database error")
        )
        
        # Should raise exception instead of returning invalid data
        with pytest.raises(Exception):
            await analytics_engine.compare_sessions("session-a", "session-b")
        
        with pytest.raises(Exception):
            await analytics_engine.get_session_insights("failing-session")
    
    @pytest.mark.asyncio
    async def test_insufficient_data_handling(self, analytics_engine):
        """Test handling of insufficient data scenarios."""
        # Mock empty session list
        analytics_engine._get_recent_sessions = AsyncMock(return_value=[])
        
        with pytest.raises(ValueError, match="No sessions found"):
            await analytics_engine.get_productivity_trends()
        
        # Mock insufficient sessions for trend analysis
        from src.context_cleaner.telemetry.clients.base import SessionMetrics
        few_sessions = [
            SessionMetrics(
                session_id="session-1",
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                api_calls=10,
                total_cost=1.0,
                total_input_tokens=1000,
                total_output_tokens=200,
                error_count=0,
                tools_used=["Read"]
            )
        ]
        
        analytics_engine._get_recent_sessions = AsyncMock(return_value=few_sessions)
        
        with pytest.raises(ValueError, match="Need at least"):
            await analytics_engine.analyze_session_trends()
    
    def test_dataclass_structures(self):
        """Test all dataclass structures."""
        # Test SessionComparison
        comparison = SessionComparison(
            session_a="a",
            session_b="b",
            cost_difference=1.0,
            efficiency_difference=0.1,
            duration_difference=0.5,
            tool_usage_similarity=0.8,
            productivity_score_diff=0.2,
            insights=["Test insight"]
        )
        assert comparison.cost_difference == 1.0
        
        # Test TrendAnalysis
        trend = TrendAnalysis(
            metric_type=MetricType.COST,
            direction=TrendDirection.IMPROVING,
            change_percentage=15.0,
            confidence=0.8,
            time_period="30 days",
            data_points=[(datetime.now(), 1.0)],
            insights=["Improving trend"]
        )
        assert trend.metric_type == MetricType.COST
        
        # Test ProductivityTrend
        prod_trend = ProductivityTrend(
            period="weekly",
            average_score=0.75,
            trend_direction=TrendDirection.STABLE,
            best_session="best",
            worst_session="worst",
            consistency_score=0.8,
            peak_hours=[9, 10, 11],
            factors={"morning": 0.2}
        )
        assert prod_trend.period == "weekly"