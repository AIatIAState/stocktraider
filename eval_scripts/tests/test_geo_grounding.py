"""Tests for geo_event_grounding in evaluate_weekly_insights."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluate_weekly_insights import geo_event_grounding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_model(impact_vecs, headline_vecs):
    """Create a mock SentenceTransformer returning controlled embeddings."""
    mock = MagicMock()
    call_count = {"n": 0}

    def fake_encode(texts, normalize_embeddings=True):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return np.array(impact_vecs, dtype=float)
        return np.array(headline_vecs, dtype=float)

    mock.encode.side_effect = fake_encode
    return mock


def _sbert_ctx(mock):
    """Context manager: sbert available + _load_sbert returns mock."""
    return (
        patch("evaluate_weekly_insights._sbert_available", return_value=True),
        patch("evaluate_weekly_insights._load_sbert", return_value=mock),
    )


# ---------------------------------------------------------------------------
# Edge cases (no model needed)
# ---------------------------------------------------------------------------

def test_empty_event_impacts():
    result = geo_event_grounding({"event_impacts": []}, ["some headline"])
    assert result["score"] is None
    assert "No event_impacts" in result["note"]


def test_missing_event_impacts_key():
    result = geo_event_grounding({}, ["some headline"])
    assert result["score"] is None


def test_empty_source_headlines():
    result = geo_event_grounding({"event_impacts": ["bullet"]}, [])
    assert result["score"] is None
    assert "No source headlines" in result["note"]


def test_blank_source_headlines_filtered():
    result = geo_event_grounding({"event_impacts": ["bullet"]}, ["", "  ", ""])
    assert result["score"] is None
    assert "No source headlines" in result["note"]


def test_sbert_unavailable(monkeypatch):
    monkeypatch.setattr("evaluate_weekly_insights._sbert_available", lambda: False)
    result = geo_event_grounding({"event_impacts": ["bullet"]}, ["headline"])
    assert result["score"] is None
    assert "sentence-transformers" in result["note"]


# ---------------------------------------------------------------------------
# Grounding logic
# ---------------------------------------------------------------------------

def test_fully_grounded():
    """Identical vectors -> cosine sim 1.0 -> all bullets grounded."""
    mock = _mock_model([[1.0, 0.0]], [[1.0, 0.0]])
    with _sbert_ctx(mock)[0], _sbert_ctx(mock)[1]:
        result = geo_event_grounding({"event_impacts": ["rate hike impact"]}, ["Fed raises rates"])
    assert result["score"] == 1.0
    assert result["grounded_count"] == 1
    assert result["details"][0]["grounded"] is True


def test_not_grounded():
    """Orthogonal vectors -> cosine sim 0.0 -> no bullets grounded."""
    mock = _mock_model([[1.0, 0.0]], [[0.0, 1.0]])
    with _sbert_ctx(mock)[0], _sbert_ctx(mock)[1]:
        result = geo_event_grounding({"event_impacts": ["unrelated"]}, ["different headline"])
    assert result["score"] == 0.0
    assert result["grounded_count"] == 0
    assert result["details"][0]["grounded"] is False


def test_partial_grounding():
    """First bullet grounded (sim=1.0), second not (sim=0.0)."""
    mock = _mock_model([[1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0]])
    with _sbert_ctx(mock)[0], _sbert_ctx(mock)[1]:
        result = geo_event_grounding(
            {"event_impacts": ["grounded", "ungrounded"]},
            ["matching headline"],
        )
    assert result["score"] == 0.5
    assert result["grounded_count"] == 1
    assert result["total_bullets"] == 2


def test_threshold_boundary():
    """Sim=0.8 passes threshold=0.75 but fails threshold=0.85."""
    # impact=[1,0], headline=[0.8, 0.6] -> dot product = 0.8
    def make_mock():
        m = MagicMock()
        calls = {"n": 0}

        def enc(texts, normalize_embeddings=True):
            calls["n"] += 1
            return np.array([[1.0, 0.0]] * len(texts) if calls["n"] == 1 else [[0.8, 0.6]] * len(texts))

        m.encode.side_effect = enc
        return m

    mock_pass = make_mock()
    with _sbert_ctx(mock_pass)[0], _sbert_ctx(mock_pass)[1]:
        result_pass = geo_event_grounding(
            {"event_impacts": ["bullet"]}, ["headline"], threshold=0.75
        )

    mock_fail = make_mock()
    with _sbert_ctx(mock_fail)[0], _sbert_ctx(mock_fail)[1]:
        result_fail = geo_event_grounding(
            {"event_impacts": ["bullet"]}, ["headline"], threshold=0.85
        )

    assert result_pass["details"][0]["grounded"] is True
    assert result_fail["details"][0]["grounded"] is False


def test_details_fields():
    """Each detail entry has expected keys."""
    mock = _mock_model([[1.0, 0.0]], [[1.0, 0.0]])
    with _sbert_ctx(mock)[0], _sbert_ctx(mock)[1]:
        result = geo_event_grounding({"event_impacts": ["bullet"]}, ["headline"])
    assert "details" in result
    d = result["details"][0]
    assert "bullet" in d
    assert "max_similarity" in d
    assert "best_match" in d
    assert "grounded" in d
    assert result["threshold"] == 0.75


def test_best_match_truncated():
    """best_match is capped at 120 chars."""
    long_headline = "x" * 200
    mock = _mock_model([[1.0, 0.0]], [[1.0, 0.0]])
    with _sbert_ctx(mock)[0], _sbert_ctx(mock)[1]:
        result = geo_event_grounding({"event_impacts": ["bullet"]}, [long_headline])
    assert len(result["details"][0]["best_match"]) <= 120
