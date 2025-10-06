"""Smoke tests for the lightweight SentimentPipeline heuristics."""

import pytest

from src.context_cleaner.telemetry.context_rot.ml_analysis import SentimentPipeline, SentimentScore


@pytest.mark.asyncio
async def test_sentiment_pipeline_detects_positive_language():
    pipeline = SentimentPipeline()

    result = await pipeline.analyze("This dashboard works great and has been very helpful today!")

    assert result.score == SentimentScore.POSITIVE
    assert result.confidence >= pipeline.confidence_threshold
    assert "positive" in " ".join(result.evidence).lower()


@pytest.mark.asyncio
async def test_sentiment_pipeline_detects_frustration():
    pipeline = SentimentPipeline()

    result = await pipeline.analyze("This feature is not working, it's completely broken and useless right now.")

    assert result.score in {SentimentScore.FRUSTRATED, SentimentScore.NEGATIVE}
    assert result.confidence >= pipeline.confidence_threshold
    assert any("frustration" in entry.lower() for entry in result.evidence)


@pytest.mark.asyncio
async def test_sentiment_pipeline_rejects_oversized_input():
    pipeline = SentimentPipeline()
    oversized = "a" * (pipeline.max_input_length + 50)

    result = await pipeline.analyze(oversized)

    assert result.score == SentimentScore.NEUTRAL
    assert result.confidence == 0.0
    assert any("invalid" in entry.lower() for entry in result.evidence)
