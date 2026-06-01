from unittest.mock import MagicMock, patch

import pytest

from geo_features import (
    ACTOR_ENCODING,
    EVENT_TYPE_ENCODING,
    GEO_FEATURE_NAMES,
    SECTOR_ENCODING,
    ZERO_GEO_FEATURES,
    GeoFeatureExtractor,
    _CACHE,
)

MOCK_LLM_RESPONSE = {
    "actor": "us",
    "event_type": "tariff",
    "affected_sector": "semiconductors",
    "direction": -1,
    "magnitude": 0.72,
    "sentiment_score": -0.5,
}

EXPECTED_FEATURES = {
    "geo_sentiment_score": -0.5,
    "geo_event_magnitude": 0.72,
    "geo_actor_encoded": ACTOR_ENCODING["us"],
    "geo_event_type_encoded": EVENT_TYPE_ENCODING["tariff"],
    "geo_affected_sector_encoded": SECTOR_ENCODING["semiconductors"],
    "geo_direction": -1,
    "gpr_index": 0.0,
}


def _make_openai_response(content: str):
    import json
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return mock


def _make_newsapi_response(headlines: list[str]):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "articles": [{"title": h} for h in headlines]
    }
    return mock


@pytest.fixture(autouse=True)
def reset_cache():
    import geo_features
    with geo_features._CACHE_LOCK:
        geo_features._CACHE.update({
            "timestamp": 0.0,
            "date_key": None,
            "payload": None,
            "last_openai_attempt": 0.0,
            "cooldown_until": 0.0,
        })
    yield


def test_feature_names_complete():
    assert set(GEO_FEATURE_NAMES) == set(ZERO_GEO_FEATURES.keys())


def test_zero_features_correct_types():
    assert isinstance(ZERO_GEO_FEATURES["geo_sentiment_score"], float)
    assert isinstance(ZERO_GEO_FEATURES["geo_actor_encoded"], int)
    assert isinstance(ZERO_GEO_FEATURES["geo_direction"], int)


def test_parse_llm_result_correct_encoding(monkeypatch):
    extractor = GeoFeatureExtractor()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = extractor._parse_llm_result(MOCK_LLM_RESPONSE)
    assert result == EXPECTED_FEATURES


def test_get_geo_features_with_mocked_llm(monkeypatch):
    import json
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("NEWSAPI_KEY", "test-key")

    headlines = ["US imposes tariffs on Chinese semiconductors"]

    with patch("geo_features.requests.get") as mock_get, \
         patch("geo_features.requests.post") as mock_post:
        mock_get.return_value = _make_newsapi_response(headlines)
        mock_post.return_value = _make_openai_response(
            json.dumps(MOCK_LLM_RESPONSE)
        )

        extractor = GeoFeatureExtractor()
        features = extractor.get_geo_features("NVDA", "2025-01-15")

    assert features == EXPECTED_FEATURES


def test_get_geo_features_no_api_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    monkeypatch.delenv("NEWSAPI_API_KEY", raising=False)

    extractor = GeoFeatureExtractor()
    features = extractor.get_geo_features("AAPL", "2025-01-15")
    assert features == ZERO_GEO_FEATURES


def test_cache_is_reused(monkeypatch):
    import json
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("NEWSAPI_KEY", "test-key")

    headlines = ["US tariffs on China"]

    with patch("geo_features.requests.get") as mock_get, \
         patch("geo_features.requests.post") as mock_post:
        mock_get.return_value = _make_newsapi_response(headlines)
        mock_post.return_value = _make_openai_response(
            json.dumps(MOCK_LLM_RESPONSE)
        )

        extractor = GeoFeatureExtractor()
        extractor.get_geo_features("NVDA", "2025-01-15")
        extractor.get_geo_features("AAPL", "2025-01-15")

    # NewsAPI and OpenAI should each be called only once (cache hit on second call)
    assert mock_get.call_count == 1
    assert mock_post.call_count == 1


def test_clamps_out_of_range_values(monkeypatch):
    extractor = GeoFeatureExtractor()
    result = extractor._parse_llm_result({
        "actor": "us",
        "event_type": "tariff",
        "affected_sector": "none",
        "direction": 99,
        "magnitude": 5.0,
        "sentiment_score": -99.0,
    })
    assert result["geo_direction"] == 1
    assert result["geo_event_magnitude"] == 1.0
    assert result["geo_sentiment_score"] == -1.0


def test_unknown_actor_falls_back_to_other(monkeypatch):
    extractor = GeoFeatureExtractor()
    result = extractor._parse_llm_result({
        "actor": "mars",
        "event_type": "none",
        "affected_sector": "none",
        "direction": 0,
        "magnitude": 0.0,
        "sentiment_score": 0.0,
    })
    assert result["geo_actor_encoded"] == ACTOR_ENCODING["other"]
