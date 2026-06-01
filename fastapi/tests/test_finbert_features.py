"""Tests for finbert_features.py.

Tests run with transformers mocked - do not require GPU or model download.
"""
from unittest.mock import patch

import pytest


def _mock_pipe(labels_scores: list[list[tuple[str, float]]]):
    """Returns a mock pipeline callable matching HuggingFace output format."""
    def _pipe(texts, **kwargs):
        out = []
        for i, _ in enumerate(texts):
            idx = min(i, len(labels_scores) - 1)
            out.append([{"label": lbl, "score": sc} for lbl, sc in labels_scores[idx]])
        return out
    return _pipe


_POSITIVE_OUTPUTS = [
    [("positive", 0.8), ("negative", 0.1), ("neutral", 0.1)],
]
_NEGATIVE_OUTPUTS = [
    [("positive", 0.1), ("negative", 0.7), ("neutral", 0.2)],
]
_NEUTRAL_OUTPUTS = [
    [("positive", 0.3), ("negative", 0.3), ("neutral", 0.4)],
]


@pytest.fixture
def mock_positive_pipeline():
    import finbert_features
    finbert_features._load_pipeline.cache_clear()
    pipe = _mock_pipe(_POSITIVE_OUTPUTS * 10)
    with patch.object(finbert_features, "_load_pipeline", return_value=pipe):
        yield
    finbert_features._load_pipeline.cache_clear()


@pytest.fixture
def mock_negative_pipeline():
    import finbert_features
    finbert_features._load_pipeline.cache_clear()
    pipe = _mock_pipe(_NEGATIVE_OUTPUTS * 10)
    with patch.object(finbert_features, "_load_pipeline", return_value=pipe):
        yield
    finbert_features._load_pipeline.cache_clear()


def test_batch_score_returns_correct_keys(mock_positive_pipeline):
    from finbert_features import batch_score_headlines
    scores = batch_score_headlines(["Fed raises rates"])
    assert len(scores) == 1
    assert set(scores[0].keys()) == {"positive", "negative", "neutral"}


def test_batch_score_positive_dominates(mock_positive_pipeline):
    from finbert_features import batch_score_headlines
    scores = batch_score_headlines(["Stocks rally on earnings beat"])
    assert scores[0]["positive"] > scores[0]["negative"]


def test_aggregate_returns_float_in_range(mock_positive_pipeline):
    from finbert_features import aggregate_daily_sentiment
    score = aggregate_daily_sentiment(["headline 1", "headline 2"])
    assert isinstance(score, float)
    assert -1.0 <= score <= 1.0


def test_aggregate_empty_headlines():
    from finbert_features import aggregate_daily_sentiment
    assert aggregate_daily_sentiment([]) == 0.0


def test_no_transformers_returns_fallback():
    import finbert_features
    finbert_features._load_pipeline.cache_clear()
    with patch.object(finbert_features, "_load_pipeline", return_value=None):
        from finbert_features import batch_score_headlines
        results = batch_score_headlines(["some headline"])
    assert results[0]["neutral"] == 1.0
    assert results[0]["positive"] == 0.0
    finbert_features._load_pipeline.cache_clear()


def test_batch_score_empty_input():
    from finbert_features import batch_score_headlines
    assert batch_score_headlines([]) == []


def test_aggregate_negative_sentiment(mock_negative_pipeline):
    from finbert_features import aggregate_daily_sentiment
    score = aggregate_daily_sentiment(["market crash", "stocks tank", "selloff"])
    assert score < 0
