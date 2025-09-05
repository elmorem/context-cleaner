"""Comprehensive tests for ML Analysis components."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.context_cleaner.telemetry.context_rot.ml_analysis import (
    MLFrustrationDetector, SentimentPipeline, ConversationFlowAnalyzer,
    SentimentScore, SentimentCategory, FrustrationAnalysis, ConversationFlowResult
)


class TestSentimentPipeline:
    """Test suite for Sentiment Pipeline."""

    @pytest.fixture
    def sentiment_pipeline(self):
        """Create sentiment pipeline for testing."""
        return SentimentPipeline(confidence_threshold=0.6)

    @pytest.mark.asyncio
    async def test_sentiment_analysis_positive(self, sentiment_pipeline):
        """Test positive sentiment analysis."""
        positive_messages = [
            "This is working great! Thanks for your help.",
            "Perfect! Everything is working now.",
            "Excellent, that solved the problem."
        ]
        
        for message in positive_messages:
            result = await sentiment_pipeline.analyze(message)
            
            assert isinstance(result, SentimentScore)
            assert result.score in [SentimentCategory.JOY, SentimentCategory.NEUTRAL]
            assert 0.0 <= result.confidence <= 1.0
            assert result.raw_scores is not None

    @pytest.mark.asyncio
    async def test_sentiment_analysis_negative(self, sentiment_pipeline):
        """Test negative sentiment analysis."""
        negative_messages = [
            "I'm getting frustrated, this doesn't work at all.",
            "This is broken and useless, I give up!",
            "Why won't this work?! This is terrible."
        ]
        
        for message in negative_messages:
            result = await sentiment_pipeline.analyze(message)
            
            assert isinstance(result, SentimentScore)
            assert result.score in [SentimentCategory.ANGER, SentimentCategory.FRUSTRATION, SentimentCategory.SADNESS]
            assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_sentiment_analysis_confusion(self, sentiment_pipeline):
        """Test confusion detection."""
        confused_messages = [
            "I'm confused, what does this mean?",
            "I don't understand what's happening here.",
            "How am I supposed to do this?"
        ]
        
        for message in confused_messages:
            result = await sentiment_pipeline.analyze(message)
            
            assert isinstance(result, SentimentScore)
            # Should detect confusion or neutral
            assert result.score in [SentimentCategory.CONFUSION, SentimentCategory.NEUTRAL]

    @pytest.mark.asyncio
    async def test_batch_sentiment_analysis(self, sentiment_pipeline):
        """Test batch sentiment analysis."""
        messages = [
            "This is great!",
            "I'm confused about this",
            "This doesn't work",
            "Perfect solution"
        ]
        
        results = await sentiment_pipeline.analyze_batch(messages)
        
        assert len(results) == len(messages)
        assert all(isinstance(r, SentimentScore) for r in results)
        assert all(0.0 <= r.confidence <= 1.0 for r in results)

    @pytest.mark.asyncio
    async def test_confidence_threshold_filtering(self, sentiment_pipeline):
        """Test confidence threshold filtering."""
        # Test with high confidence threshold
        high_confidence_pipeline = SentimentPipeline(confidence_threshold=0.9)
        
        ambiguous_message = "This is okay I guess"
        result = await high_confidence_pipeline.analyze(ambiguous_message)
        
        # Should either have high confidence or fallback to neutral
        assert result.confidence >= 0.6 or result.score == SentimentCategory.NEUTRAL

    @pytest.mark.asyncio
    async def test_empty_message_handling(self, sentiment_pipeline):
        """Test handling of empty messages."""
        empty_messages = ["", "   ", "\n\t"]
        
        for message in empty_messages:
            result = await sentiment_pipeline.analyze(message)
            
            assert result.score == SentimentCategory.NEUTRAL
            assert result.confidence >= 0.8  # High confidence in neutral for empty

    @pytest.mark.asyncio
    async def test_long_message_handling(self, sentiment_pipeline):
        """Test handling of very long messages."""
        long_message = "This is a very long message. " * 100
        
        result = await sentiment_pipeline.analyze(long_message)
        
        # Should still work but may be truncated
        assert isinstance(result, SentimentScore)
        assert 0.0 <= result.confidence <= 1.0


class TestMLFrustrationDetector:
    """Test suite for ML Frustration Detector."""

    @pytest.fixture
    def frustration_detector(self):
        """Create ML frustration detector for testing."""
        return MLFrustrationDetector(confidence_threshold=0.7)

    @pytest.mark.asyncio
    async def test_conversation_frustration_analysis(self, frustration_detector):
        """Test conversation-level frustration analysis."""
        conversation = [
            "I need help with this feature",
            "It's not working as expected",
            "I've tried everything, still broken", 
            "This is really frustrating me",
            "Why won't this just work?!"
        ]
        
        result = await frustration_detector.analyze_user_sentiment(conversation)
        
        assert isinstance(result, FrustrationAnalysis)
        assert 0.0 <= result.frustration_level <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.evidence) > 0
        assert result.escalation_detected is not None
        
        # Should detect escalation in this conversation
        assert result.escalation_detected == True

    @pytest.mark.asyncio
    async def test_positive_conversation_analysis(self, frustration_detector):
        """Test positive conversation analysis."""
        positive_conversation = [
            "I need help with authentication",
            "Here's what I'm trying to do",
            "That makes sense, let me try",
            "Great, it's working now!",
            "Thanks for the help!"
        ]
        
        result = await frustration_detector.analyze_user_sentiment(positive_conversation)
        
        assert isinstance(result, FrustrationAnalysis)
        assert result.frustration_level < 0.5  # Low frustration
        assert result.escalation_detected == False

    @pytest.mark.asyncio
    async def test_mixed_conversation_analysis(self, frustration_detector):
        """Test mixed sentiment conversation."""
        mixed_conversation = [
            "This is working well",
            "Wait, now there's an issue",
            "I'm a bit confused",
            "Oh I see, that helps",
            "Perfect, all good now"
        ]
        
        result = await frustration_detector.analyze_user_sentiment(mixed_conversation)
        
        assert isinstance(result, FrustrationAnalysis)
        assert 0.2 <= result.frustration_level <= 0.6  # Moderate frustration
        
    @pytest.mark.asyncio
    async def test_temporal_weighting(self, frustration_detector):
        """Test temporal weighting of messages."""
        # Recent messages should have more weight
        temporal_conversation = [
            "This was working fine earlier",  # Old, positive
            "Now there are some issues",      # Recent, negative 
            "This is really broken now",      # Most recent, very negative
        ]
        
        result = await frustration_detector.analyze_user_sentiment(temporal_conversation)
        
        # Should weight recent negative messages more heavily
        assert result.frustration_level > 0.6

    @pytest.mark.asyncio
    async def test_single_message_analysis(self, frustration_detector):
        """Test analysis of single message."""
        single_message = ["I'm extremely frustrated with this!"]
        
        result = await frustration_detector.analyze_user_sentiment(single_message)
        
        assert isinstance(result, FrustrationAnalysis)
        assert result.frustration_level > 0.7
        assert len(result.evidence) >= 1

    @pytest.mark.asyncio
    async def test_empty_conversation_handling(self, frustration_detector):
        """Test handling of empty conversation."""
        empty_conversations = [[], [""], ["   "]]
        
        for conversation in empty_conversations:
            result = await frustration_detector.analyze_user_sentiment(conversation)
            
            assert result.frustration_level == 0.0
            assert result.confidence == 1.0  # High confidence in no frustration for empty
            assert result.escalation_detected == False


class TestConversationFlowAnalyzer:
    """Test suite for Conversation Flow Analyzer."""

    @pytest.fixture
    def flow_analyzer(self):
        """Create conversation flow analyzer for testing."""
        return ConversationFlowAnalyzer()

    @pytest.mark.asyncio
    async def test_good_flow_analysis(self, flow_analyzer):
        """Test analysis of good conversation flow."""
        good_flow = [
            "I need help with authentication",
            "Here's what I'm trying to do",
            "That makes sense, let me try",
            "Great, it's working now!"
        ]
        
        result = await flow_analyzer.analyze_flow(good_flow)
        
        assert isinstance(result, ConversationFlowResult)
        assert result.flow_quality_score >= 0.7
        assert result.question_ratio <= 0.5  # Not too many questions
        assert result.repetition_ratio <= 0.3  # Low repetition
        assert result.escalation_detected == False

    @pytest.mark.asyncio
    async def test_poor_repetitive_flow(self, flow_analyzer):
        """Test analysis of repetitive conversation."""
        repetitive_flow = [
            "This doesn't work",
            "Still doesn't work",
            "Nothing works",
            "This is not working",
            "Why doesn't this work?"
        ]
        
        result = await flow_analyzer.analyze_flow(repetitive_flow)
        
        assert isinstance(result, ConversationFlowResult)
        assert result.flow_quality_score <= 0.5  # Poor quality
        assert result.repetition_ratio >= 0.4  # High repetition
        assert len(result.pattern_evidence) > 0

    @pytest.mark.asyncio
    async def test_confused_flow_analysis(self, flow_analyzer):
        """Test analysis of confused conversation flow."""
        confused_flow = [
            "What does this do?",
            "How do I use this?",
            "I don't understand?", 
            "What am I supposed to do?",
            "Can you explain this?"
        ]
        
        result = await flow_analyzer.analyze_flow(confused_flow)
        
        assert isinstance(result, ConversationFlowResult)
        assert result.question_ratio >= 0.7  # High question ratio
        assert result.flow_quality_score <= 0.6  # Moderate quality
        assert "confusion" in str(result.pattern_evidence).lower() if result.pattern_evidence else True

    @pytest.mark.asyncio
    async def test_escalation_detection(self, flow_analyzer):
        """Test escalation detection in conversation flow."""
        escalating_flow = [
            "There's an issue with this",
            "The problem is getting worse", 
            "This is really frustrating",
            "I'm getting angry about this",
            "This is completely broken!"
        ]
        
        result = await flow_analyzer.analyze_flow(escalating_flow)
        
        assert isinstance(result, ConversationFlowResult)
        assert result.escalation_detected == True
        assert result.flow_quality_score <= 0.5

    @pytest.mark.asyncio
    async def test_resolution_flow_analysis(self, flow_analyzer):
        """Test analysis of conversation that reaches resolution."""
        resolution_flow = [
            "I'm having trouble with this",
            "Let me try that suggestion",
            "That's helping some",
            "Getting closer to working",
            "Perfect! That fixed it."
        ]
        
        result = await flow_analyzer.analyze_flow(resolution_flow)
        
        assert isinstance(result, ConversationFlowResult)
        assert result.flow_quality_score >= 0.6  # Good resolution
        assert result.escalation_detected == False

    @pytest.mark.asyncio
    async def test_short_conversation_handling(self, flow_analyzer):
        """Test handling of very short conversations."""
        short_flows = [
            ["Help me"],
            ["This doesn't work", "Thanks"],
            ["Perfect!"]
        ]
        
        for flow in short_flows:
            result = await flow_analyzer.analyze_flow(flow)
            
            assert isinstance(result, ConversationFlowResult)
            # Should handle gracefully with appropriate confidence
            assert 0.0 <= result.flow_quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_very_long_conversation_handling(self, flow_analyzer):
        """Test handling of very long conversations."""
        long_flow = [f"Message number {i} about various topics" for i in range(100)]
        
        result = await flow_analyzer.analyze_flow(long_flow)
        
        assert isinstance(result, ConversationFlowResult)
        # Should handle efficiently (may truncate internally)
        assert 0.0 <= result.flow_quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_pattern_evidence_extraction(self, flow_analyzer):
        """Test pattern evidence extraction."""
        problematic_flow = [
            "I tried method A",
            "Method A doesn't work",
            "Let me try method B", 
            "Method B also fails",
            "Nothing seems to work"
        ]
        
        result = await flow_analyzer.analyze_flow(problematic_flow)
        
        assert isinstance(result, ConversationFlowResult)
        assert len(result.pattern_evidence) > 0
        # Should identify patterns in the conversation


class TestMLAnalysisIntegration:
    """Integration tests for ML Analysis components."""

    @pytest.mark.asyncio
    async def test_pipeline_integration(self):
        """Test integration between ML components."""
        # Create instances
        sentiment_pipeline = SentimentPipeline(confidence_threshold=0.6)
        frustration_detector = MLFrustrationDetector(confidence_threshold=0.7)
        flow_analyzer = ConversationFlowAnalyzer()
        
        # Test conversation
        test_conversation = [
            "I need help with this problem",
            "It's not working correctly",
            "Getting frustrated now", 
            "This is really annoying",
            "Maybe I should try a different approach"
        ]
        
        # Run all analyses
        sentiment_results = await sentiment_pipeline.analyze_batch(test_conversation)
        frustration_result = await frustration_detector.analyze_user_sentiment(test_conversation)
        flow_result = await flow_analyzer.analyze_flow(test_conversation)
        
        # Verify consistency between analyses
        assert len(sentiment_results) == len(test_conversation)
        
        # Frustration should correlate with negative sentiment
        negative_sentiments = sum(1 for r in sentiment_results 
                                if r.score in [SentimentCategory.ANGER, SentimentCategory.FRUSTRATION])
        if negative_sentiments >= 2:
            assert frustration_result.frustration_level >= 0.4

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test ML analysis performance under load."""
        import time
        
        sentiment_pipeline = SentimentPipeline(confidence_threshold=0.6)
        
        # Generate test data
        test_messages = [f"Test message number {i} with various content" for i in range(50)]
        
        start_time = time.time()
        
        # Run batch analysis
        results = await sentiment_pipeline.analyze_batch(test_messages)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time
        assert duration < 5.0  # 5 seconds for 50 messages
        assert len(results) == len(test_messages)
        assert all(isinstance(r, SentimentScore) for r in results)

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery in ML components."""
        sentiment_pipeline = SentimentPipeline(confidence_threshold=0.6)
        
        # Test with potentially problematic input
        problematic_inputs = [
            "",  # Empty
            "   ",  # Whitespace only
            "🤖🚀💥" * 100,  # Many emojis
            "a" * 1000,  # Very long
            None,  # None (should be handled)
        ]
        
        for inp in problematic_inputs[:-1]:  # Skip None for now
            try:
                result = await sentiment_pipeline.analyze(inp)
                assert isinstance(result, SentimentScore)
            except Exception as e:
                pytest.fail(f"Failed to handle input '{inp[:20]}...': {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])