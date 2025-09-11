"""
Basic tests for Phase 4 - Advanced Analytics & Reporting components.

These tests verify that the Phase 4 analytics engines initialize properly
and can perform basic operations without errors.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.context_cleaner.analytics.predictive_intelligence import (
    PredictiveIntelligenceEngine,
    ProductivityForecastEngine,
    ContextHealthPredictor,
    ForecastHorizon,
    PredictionType
)
from src.context_cleaner.analytics.content_intelligence import (
    ContentIntelligenceEngine,
    SemanticAnalyzer,
    ConversationFlowAnalyzer,
    KnowledgeExtractor
)
from src.context_cleaner.analytics.business_intelligence import (
    BusinessIntelligenceEngine,
    ExecutiveDashboard,
    BenchmarkAnalyzer
)


class TestPredictiveIntelligenceEngine:
    """Test predictive intelligence engine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = PredictiveIntelligenceEngine()

    def test_engine_initialization(self):
        """Test that the predictive intelligence engine initializes properly."""
        assert self.engine is not None
        assert self.engine.productivity_engine is not None
        assert self.engine.health_predictor is not None
        assert self.engine.prediction_cache == {}
        assert self.engine.warning_cache == {}

    @pytest.mark.asyncio
    async def test_generate_predictions_basic(self):
        """Test basic prediction generation."""
        result = await self.engine.generate_predictions(
            prediction_type=PredictionType.PRODUCTIVITY,
            horizon=ForecastHorizon.DAY
        )
        
        assert result is not None
        assert isinstance(result, list)
        # Should return predictions even without training data

    @pytest.mark.asyncio
    async def test_early_warning_system_basic(self):
        """Test early warning system basic functionality."""
        warnings = await self.engine.check_early_warnings()
        
        assert warnings is not None
        assert isinstance(warnings, list)
        # Should return warnings list even with mock data


class TestContentIntelligenceEngine:
    """Test content intelligence engine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ContentIntelligenceEngine()

    def test_engine_initialization(self):
        """Test that the content intelligence engine initializes properly."""
        assert self.engine is not None
        assert self.engine.semantic_analyzer is not None
        assert self.engine.flow_analyzer is not None
        assert self.engine.knowledge_extractor is not None

    @pytest.mark.asyncio
    async def test_analyze_conversation_basic(self):
        """Test basic conversation analysis."""
        test_data = [
            {"content": "Hello, I need help with productivity", "role": "user"},
            {"content": "I can help you with that", "role": "assistant"}
        ]
        
        result = await self.engine.analyze_conversation(test_data)
        
        assert result is not None
        assert "semantic_insights" in result
        assert "conversation_flow" in result
        assert "knowledge_extraction" in result

    @pytest.mark.asyncio
    async def test_semantic_analysis_basic(self):
        """Test basic semantic analysis."""
        test_text = "Context cleaning improves productivity by optimizing conversation flow."
        
        analyzer = SemanticAnalyzer()
        result = await analyzer.analyze_content(test_text, "test_content")
        
        assert result is not None
        assert result.content_id == "test_content"
        assert result.sentiment_score is not None
        assert isinstance(result.key_topics, list)
        assert isinstance(result.entities, list)


class TestBusinessIntelligenceEngine:
    """Test business intelligence engine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = BusinessIntelligenceEngine()

    def test_engine_initialization(self):
        """Test that the business intelligence engine initializes properly."""
        assert self.engine is not None
        assert self.engine.executive_dashboard is not None
        assert self.engine.benchmark_analyzer is not None

    @pytest.mark.asyncio
    async def test_generate_comprehensive_report_basic(self):
        """Test basic comprehensive report generation."""
        result = await self.engine.generate_comprehensive_report()
        
        assert result is not None
        assert "comprehensive_bi_report" in result
        
        report = result["comprehensive_bi_report"]
        assert "report_metadata" in report
        assert "executive_dashboard" in report
        assert "benchmark_analysis" in report
        assert "action_items" in report

    @pytest.mark.asyncio
    async def test_executive_summary_basic(self):
        """Test basic executive summary generation."""
        dashboard = ExecutiveDashboard()
        result = await dashboard.generate_executive_summary()
        
        assert result is not None
        assert "executive_summary" in result
        
        summary = result["executive_summary"]
        assert "period" in summary
        assert "key_metrics" in summary
        assert "productivity" in summary["key_metrics"]
        assert "cost_optimization" in summary["key_metrics"]
        assert "efficiency" in summary["key_metrics"]

    @pytest.mark.asyncio
    async def test_benchmark_report_basic(self):
        """Test basic benchmark report generation."""
        analyzer = BenchmarkAnalyzer()
        result = await analyzer.generate_benchmark_report()
        
        assert result is not None
        assert "benchmark_report" in result
        
        report = result["benchmark_report"]
        assert "report_date" in report
        assert "metrics_comparison" in report
        assert "ranking" in report


class TestAnalyticsIntegration:
    """Test integration between analytics components."""

    @pytest.mark.asyncio
    async def test_all_engines_work_together(self):
        """Test that all analytics engines can work together."""
        # Initialize all engines
        predictive = PredictiveIntelligenceEngine()
        content = ContentIntelligenceEngine()
        business = BusinessIntelligenceEngine()
        
        # Generate outputs from each
        predictions = await predictive.generate_predictions(
            PredictionType.PRODUCTIVITY, 
            ForecastHorizon.DAY
        )
        
        content_analysis = await content.analyze_conversation([
            {"content": "Sample productivity analysis content", "role": "user"}
        ])
        
        bi_report = await business.generate_comprehensive_report()
        
        # Verify all components produced valid outputs
        assert predictions is not None
        assert content_analysis is not None
        assert bi_report is not None
        
        # Verify the outputs have expected structure
        assert isinstance(predictions, list)
        assert "semantic_insights" in content_analysis
        assert "comprehensive_bi_report" in bi_report


if __name__ == "__main__":
    pytest.main([__file__])