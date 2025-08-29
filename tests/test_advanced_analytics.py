"""
Tests for Advanced Analytics Components (Phase 2 features).
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from context_cleaner.analytics.advanced_patterns import AdvancedPatterns
from context_cleaner.analytics.anomaly_detector import AnomalyDetector  
from context_cleaner.analytics.correlation_analyzer import CorrelationAnalyzer
from context_cleaner.analytics.predictive_models import PredictiveModels
from context_cleaner.analytics.seasonal_patterns import SeasonalPatterns


@pytest.fixture
def sample_session_data():
    """Generate sample session data for testing."""
    base_time = datetime.now() - timedelta(days=30)
    sessions = []
    
    for i in range(100):
        # Create realistic productivity patterns
        hour = (base_time + timedelta(hours=i*2)).hour
        productivity_base = 70 + (10 * np.sin(i * 0.1))  # Seasonal pattern
        
        if 9 <= hour <= 17:  # Work hours boost
            productivity_base += 15
        
        sessions.append({
            "timestamp": (base_time + timedelta(hours=i*2)).isoformat(),
            "productivity_score": max(0, min(100, productivity_base + np.random.normal(0, 5))),
            "context_size": 1000 + int(200 * np.random.random()),
            "optimization_events": np.random.poisson(2),
            "session_duration": 60 + int(120 * np.random.random()),
            "tools_used": np.random.randint(3, 10),
            "hour": hour,
            "weekday": ((base_time + timedelta(hours=i*2)).weekday())
        })
    
    return sessions


@pytest.fixture
def sample_metrics_data():
    """Generate sample metrics data for testing."""
    return {
        "response_times": np.random.normal(100, 20, 1000).tolist(),
        "memory_usage": np.random.normal(45, 10, 1000).tolist(),  
        "cpu_usage": np.random.normal(12, 3, 1000).tolist(),
        "productivity_scores": np.random.normal(75, 15, 1000).tolist(),
        "context_sizes": np.random.normal(5000, 1000, 1000).tolist()
    }


class TestAdvancedPatterns:
    """Test suite for AdvancedPatterns class."""

    @pytest.fixture
    def advanced_patterns(self, test_config):
        return AdvancedPatterns(test_config)

    def test_detect_temporal_patterns(self, advanced_patterns, sample_session_data):
        """Test temporal pattern detection."""
        patterns = advanced_patterns.detect_temporal_patterns(sample_session_data)
        
        assert "hourly_patterns" in patterns
        assert "daily_patterns" in patterns
        assert "weekly_patterns" in patterns
        
        # Should identify work hour patterns
        hourly = patterns["hourly_patterns"]
        work_hours = [h for h in hourly if 9 <= h["hour"] <= 17]
        non_work_hours = [h for h in hourly if h["hour"] < 9 or h["hour"] > 17]
        
        if work_hours and non_work_hours:
            avg_work_productivity = np.mean([h["avg_productivity"] for h in work_hours])
            avg_nonwork_productivity = np.mean([h["avg_productivity"] for h in non_work_hours])
            assert avg_work_productivity > avg_nonwork_productivity

    def test_detect_behavioral_patterns(self, advanced_patterns, sample_session_data):
        """Test behavioral pattern detection."""
        patterns = advanced_patterns.detect_behavioral_patterns(sample_session_data)
        
        assert "productivity_clusters" in patterns
        assert "optimization_patterns" in patterns
        assert "session_duration_patterns" in patterns
        
        # Verify clustering results
        clusters = patterns["productivity_clusters"]
        assert len(clusters) > 0
        assert all("cluster_center" in cluster for cluster in clusters)

    def test_detect_contextual_patterns(self, advanced_patterns, sample_session_data):
        """Test contextual pattern detection."""
        patterns = advanced_patterns.detect_contextual_patterns(sample_session_data)
        
        assert "context_size_correlation" in patterns
        assert "tools_usage_patterns" in patterns
        assert "optimization_impact_patterns" in patterns
        
        # Context size should have some correlation with productivity
        correlation = patterns["context_size_correlation"]
        assert -1 <= correlation <= 1

    def test_detect_performance_patterns(self, advanced_patterns, sample_session_data):
        """Test performance pattern detection."""
        # Add performance data to sessions
        for session in sample_session_data:
            session["response_time"] = np.random.normal(100, 20)
            session["memory_usage"] = np.random.normal(45, 10)
        
        patterns = advanced_patterns.detect_performance_patterns(sample_session_data)
        
        assert "response_time_patterns" in patterns
        assert "memory_usage_patterns" in patterns
        assert "performance_degradation_events" in patterns

    def test_comprehensive_pattern_analysis(self, advanced_patterns, sample_session_data):
        """Test comprehensive pattern analysis."""
        analysis = advanced_patterns.analyze_patterns(sample_session_data)
        
        # Verify complete analysis structure
        required_sections = [
            "temporal_patterns",
            "behavioral_patterns", 
            "contextual_patterns",
            "performance_patterns",
            "pattern_summary",
            "insights"
        ]
        
        for section in required_sections:
            assert section in analysis
        
        # Verify insights are generated
        assert len(analysis["insights"]) > 0
        assert all(isinstance(insight, str) for insight in analysis["insights"])


class TestAnomalyDetector:
    """Test suite for AnomalyDetector class."""

    @pytest.fixture  
    def anomaly_detector(self, test_config):
        return AnomalyDetector(test_config)

    def test_detect_statistical_anomalies(self, anomaly_detector, sample_metrics_data):
        """Test statistical anomaly detection methods."""
        # Test with response times
        response_times = sample_metrics_data["response_times"]
        anomalies = anomaly_detector.detect_statistical_anomalies(response_times)
        
        assert "z_score_anomalies" in anomalies
        assert "modified_z_score_anomalies" in anomalies
        assert "iqr_anomalies" in anomalies
        assert "ensemble_anomalies" in anomalies
        
        # Verify anomaly structure
        for method in anomalies:
            assert "anomaly_indices" in anomalies[method]
            assert "anomaly_scores" in anomalies[method]
            assert "threshold" in anomalies[method]

    def test_detect_productivity_anomalies(self, anomaly_detector, sample_session_data):
        """Test productivity-specific anomaly detection."""
        anomalies = anomaly_detector.detect_productivity_anomalies(sample_session_data)
        
        assert "productivity_score_anomalies" in anomalies
        assert "session_duration_anomalies" in anomalies
        assert "optimization_anomalies" in anomalies
        
        # Verify temporal context
        for anomaly_type in anomalies:
            if anomalies[anomaly_type]["anomaly_indices"]:
                assert "temporal_context" in anomalies[anomaly_type]

    def test_detect_performance_anomalies(self, anomaly_detector, sample_metrics_data):
        """Test performance anomaly detection."""
        # Create performance data with known anomalies
        performance_data = {
            "response_times": sample_metrics_data["response_times"] + [500, 600, 700],  # Add outliers
            "memory_usage": sample_metrics_data["memory_usage"],
            "cpu_usage": sample_metrics_data["cpu_usage"]
        }
        
        anomalies = anomaly_detector.detect_performance_anomalies(performance_data)
        
        assert "response_time_anomalies" in anomalies
        assert "memory_anomalies" in anomalies
        assert "cpu_anomalies" in anomalies
        
        # Should detect the added outliers
        response_anomalies = anomalies["response_time_anomalies"]
        assert len(response_anomalies["anomaly_indices"]) >= 1

    def test_anomaly_severity_assessment(self, anomaly_detector):
        """Test anomaly severity assessment."""
        # Create data with various anomaly levels
        normal_data = [50] * 100
        mild_anomalies = [75, 80]  # 1.5-2 std devs
        severe_anomalies = [120, 130]  # >3 std devs
        
        data = normal_data + mild_anomalies + severe_anomalies
        
        severity = anomaly_detector.assess_anomaly_severity(data, [100, 101, 102, 103])
        
        assert "severity_scores" in severity
        assert "severity_categories" in severity
        assert len(severity["severity_scores"]) == 4
        assert len(severity["severity_categories"]) == 4


class TestCorrelationAnalyzer:
    """Test suite for CorrelationAnalyzer class."""

    @pytest.fixture
    def correlation_analyzer(self, test_config):
        return CorrelationAnalyzer(test_config)

    def test_analyze_correlations_basic(self, correlation_analyzer, sample_session_data):
        """Test basic correlation analysis."""
        # Extract numeric features
        features = {
            "productivity_score": [s["productivity_score"] for s in sample_session_data],
            "context_size": [s["context_size"] for s in sample_session_data],
            "session_duration": [s["session_duration"] for s in sample_session_data],
            "optimization_events": [s["optimization_events"] for s in sample_session_data],
            "tools_used": [s["tools_used"] for s in sample_session_data]
        }
        
        correlations = correlation_analyzer.analyze_correlations(features)
        
        assert "pearson_correlations" in correlations
        assert "spearman_correlations" in correlations
        assert "kendall_correlations" in correlations
        assert "correlation_matrix" in correlations
        
        # Verify matrix dimensions
        n_features = len(features)
        assert correlations["correlation_matrix"].shape == (n_features, n_features)

    def test_causal_inference(self, correlation_analyzer, sample_session_data):
        """Test causal inference capabilities."""
        # Create features with known causal relationship
        features = {
            "optimization_events": [s["optimization_events"] for s in sample_session_data],
            "productivity_score": [s["productivity_score"] for s in sample_session_data]
        }
        
        causal_analysis = correlation_analyzer.infer_causal_relationships(features)
        
        assert "causal_relationships" in causal_analysis
        assert "causal_strength" in causal_analysis
        assert "confidence_intervals" in causal_analysis

    def test_partial_correlations(self, correlation_analyzer, sample_session_data):
        """Test partial correlation analysis."""
        features = {
            "productivity_score": [s["productivity_score"] for s in sample_session_data],
            "context_size": [s["context_size"] for s in sample_session_data],
            "session_duration": [s["session_duration"] for s in sample_session_data]
        }
        
        partial_corr = correlation_analyzer.calculate_partial_correlations(features)
        
        assert "partial_correlations" in partial_corr
        assert "controlled_variables" in partial_corr
        
        # Should have correlations between all variable pairs
        assert len(partial_corr["partial_correlations"]) > 0

    def test_time_lagged_correlations(self, correlation_analyzer, sample_session_data):
        """Test time-lagged correlation analysis."""
        # Create time series data
        productivity_scores = [s["productivity_score"] for s in sample_session_data]
        optimization_events = [s["optimization_events"] for s in sample_session_data]
        
        lagged_corr = correlation_analyzer.analyze_lagged_correlations(
            productivity_scores, 
            optimization_events,
            max_lag=5
        )
        
        assert "lag_correlations" in lagged_corr
        assert "optimal_lag" in lagged_corr
        assert "significance_test" in lagged_corr


class TestPredictiveModels:
    """Test suite for PredictiveModels class."""

    @pytest.fixture
    def predictive_models(self, test_config):
        return PredictiveModels(test_config)

    def test_linear_regression_prediction(self, predictive_models, sample_session_data):
        """Test linear regression prediction."""
        # Prepare features and target
        features = np.array([[s["context_size"], s["session_duration"], s["tools_used"]] 
                           for s in sample_session_data])
        target = np.array([s["productivity_score"] for s in sample_session_data])
        
        prediction = predictive_models.linear_regression_predict(features, target)
        
        assert "predictions" in prediction
        assert "model_performance" in prediction
        assert "feature_importance" in prediction
        
        # Verify prediction quality
        assert prediction["model_performance"]["r2_score"] is not None
        assert len(prediction["predictions"]) > 0

    def test_polynomial_regression(self, predictive_models, sample_session_data):
        """Test polynomial regression prediction."""
        # Use context size to predict productivity (non-linear relationship expected)
        context_sizes = np.array([[s["context_size"]] for s in sample_session_data])
        productivity = np.array([s["productivity_score"] for s in sample_session_data])
        
        prediction = predictive_models.polynomial_regression_predict(
            context_sizes, productivity, degree=2
        )
        
        assert "predictions" in prediction
        assert "model_performance" in prediction
        assert "polynomial_degree" in prediction

    def test_time_series_forecasting(self, predictive_models, sample_session_data):
        """Test time series forecasting."""
        # Create time series from productivity scores
        time_series = [s["productivity_score"] for s in sample_session_data]
        
        forecast = predictive_models.forecast_time_series(time_series, forecast_periods=10)
        
        assert "forecast" in forecast
        assert "confidence_intervals" in forecast
        assert "model_performance" in forecast
        assert len(forecast["forecast"]) == 10

    def test_ensemble_forecasting(self, predictive_models, sample_session_data):
        """Test ensemble forecasting methods."""
        time_series = [s["productivity_score"] for s in sample_session_data]
        
        ensemble_forecast = predictive_models.ensemble_forecast(
            time_series, 
            forecast_periods=5,
            methods=["linear", "exponential", "moving_average"]
        )
        
        assert "ensemble_forecast" in ensemble_forecast
        assert "individual_forecasts" in ensemble_forecast
        assert "model_weights" in ensemble_forecast
        assert "confidence_score" in ensemble_forecast


class TestSeasonalPatterns:
    """Test suite for SeasonalPatterns class."""

    @pytest.fixture
    def seasonal_patterns(self, test_config):
        return SeasonalPatterns(test_config)

    def test_detect_hourly_patterns(self, seasonal_patterns, sample_session_data):
        """Test hourly pattern detection."""
        patterns = seasonal_patterns.detect_hourly_patterns(sample_session_data)
        
        assert "hourly_productivity" in patterns
        assert "peak_hours" in patterns
        assert "low_hours" in patterns
        assert "statistical_significance" in patterns
        
        # Should have 24 hourly entries
        assert len(patterns["hourly_productivity"]) <= 24

    def test_detect_daily_patterns(self, seasonal_patterns, sample_session_data):
        """Test daily pattern detection."""
        patterns = seasonal_patterns.detect_daily_patterns(sample_session_data)
        
        assert "daily_productivity" in patterns
        assert "weekday_patterns" in patterns
        assert "weekend_patterns" in patterns
        
        # Should identify weekday vs weekend differences
        if patterns["weekday_patterns"] and patterns["weekend_patterns"]:
            weekday_avg = patterns["weekday_patterns"]["average_productivity"]
            weekend_avg = patterns["weekend_patterns"]["average_productivity"]
            assert weekday_avg != weekend_avg  # Should be different

    def test_detect_seasonal_cycles(self, seasonal_patterns):
        """Test seasonal cycle detection with longer time series."""
        # Generate longer time series with seasonal pattern
        base_date = datetime.now() - timedelta(days=365)
        seasonal_data = []
        
        for i in range(365):
            date = base_date + timedelta(days=i)
            # Add seasonal pattern (higher productivity in certain months)
            seasonal_boost = 10 * np.sin(2 * np.pi * i / 365)
            productivity = 75 + seasonal_boost + np.random.normal(0, 5)
            
            seasonal_data.append({
                "timestamp": date.isoformat(),
                "productivity_score": max(0, min(100, productivity)),
                "month": date.month,
                "quarter": (date.month - 1) // 3 + 1
            })
        
        patterns = seasonal_patterns.detect_seasonal_cycles(seasonal_data)
        
        assert "monthly_patterns" in patterns
        assert "quarterly_patterns" in patterns
        assert "seasonal_strength" in patterns

    def test_statistical_significance_testing(self, seasonal_patterns, sample_session_data):
        """Test statistical significance of detected patterns."""
        # Test with work hours vs non-work hours
        work_hour_data = [s for s in sample_session_data if 9 <= s["hour"] <= 17]
        non_work_hour_data = [s for s in sample_session_data if s["hour"] < 9 or s["hour"] > 17]
        
        significance = seasonal_patterns.test_pattern_significance(
            [s["productivity_score"] for s in work_hour_data],
            [s["productivity_score"] for s in non_work_hour_data]
        )
        
        assert "p_value" in significance
        assert "statistical_test" in significance
        assert "confidence_level" in significance
        assert 0 <= significance["p_value"] <= 1


@pytest.mark.integration
class TestAdvancedAnalyticsIntegration:
    """Integration tests for advanced analytics components."""

    def test_complete_analytics_pipeline(self, sample_session_data, sample_metrics_data, test_config):
        """Test complete advanced analytics pipeline."""
        # Initialize all components
        patterns = AdvancedPatterns(test_config)
        anomaly_detector = AnomalyDetector(test_config)
        correlation_analyzer = CorrelationAnalyzer(test_config)
        predictive_models = PredictiveModels(test_config)
        seasonal_patterns = SeasonalPatterns(test_config)
        
        # Run complete analysis pipeline
        results = {}
        
        # Pattern analysis
        results["patterns"] = patterns.analyze_patterns(sample_session_data)
        
        # Anomaly detection
        results["anomalies"] = anomaly_detector.detect_productivity_anomalies(sample_session_data)
        
        # Correlation analysis
        features = {
            "productivity_score": [s["productivity_score"] for s in sample_session_data],
            "context_size": [s["context_size"] for s in sample_session_data],
            "optimization_events": [s["optimization_events"] for s in sample_session_data]
        }
        results["correlations"] = correlation_analyzer.analyze_correlations(features)
        
        # Predictive modeling
        feature_matrix = np.array([[s["context_size"], s["optimization_events"]] 
                                  for s in sample_session_data])
        target = np.array([s["productivity_score"] for s in sample_session_data])
        results["predictions"] = predictive_models.linear_regression_predict(feature_matrix, target)
        
        # Seasonal analysis
        results["seasonal"] = seasonal_patterns.detect_hourly_patterns(sample_session_data)
        
        # Verify comprehensive results
        assert all(key in results for key in 
                  ["patterns", "anomalies", "correlations", "predictions", "seasonal"])
        
        # Verify each component produced meaningful results
        assert len(results["patterns"]["insights"]) > 0
        assert "ensemble_anomalies" in results["anomalies"]["productivity_score_anomalies"]
        assert results["correlations"]["correlation_matrix"] is not None
        assert results["predictions"]["model_performance"]["r2_score"] is not None
        assert "peak_hours" in results["seasonal"]

    def test_analytics_performance_benchmarks(self, sample_session_data, test_config):
        """Test performance benchmarks for analytics components."""
        import time
        
        # Test pattern analysis performance
        patterns = AdvancedPatterns(test_config)
        start_time = time.perf_counter()
        pattern_results = patterns.analyze_patterns(sample_session_data)
        pattern_time = time.perf_counter() - start_time
        
        # Should complete pattern analysis in reasonable time
        assert pattern_time < 5.0  # Less than 5 seconds for 100 sessions
        assert len(pattern_results["insights"]) > 0
        
        # Test anomaly detection performance
        anomaly_detector = AnomalyDetector(test_config)
        start_time = time.perf_counter()
        anomaly_results = anomaly_detector.detect_productivity_anomalies(sample_session_data)
        anomaly_time = time.perf_counter() - start_time
        
        # Should complete anomaly detection quickly
        assert anomaly_time < 2.0  # Less than 2 seconds
        
        print(f"Pattern analysis: {pattern_time:.2f}s, Anomaly detection: {anomaly_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__])