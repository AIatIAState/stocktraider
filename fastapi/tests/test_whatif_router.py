from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("whatif_router._get_baseline_predictions") as mock_baselines, \
         patch("whatif_router._call_openai_raw") as mock_openai, \
         patch("whatif_router._extract_scenario_features") as mock_features:

        mock_baselines.return_value = {
            "SPY": 0.001,
            "NVDA": 0.003,
        }
        mock_openai.return_value = "Scenario summary sentence."
        mock_features.return_value = {
            "geo_sentiment_score": -0.5,
            "geo_event_magnitude": 0.7,
            "geo_actor_encoded": 1,
            "geo_event_type_encoded": 1,
            "geo_affected_sector_encoded": 13,
            "geo_direction": -1,
            "gpr_index": 0.0,
        }

        from fastapi import FastAPI
        from whatif_router import router

        app = FastAPI()
        app.include_router(router)
        yield TestClient(app)


def test_whatif_returns_200(client):
    resp = client.post(
        "/api/whatif",
        json={"scenario": "US imposes tariffs on Chinese semiconductors", "tickers": ["SPY", "NVDA"]},
    )
    assert resp.status_code == 200


def test_whatif_response_schema(client):
    resp = client.post(
        "/api/whatif",
        json={"scenario": "Russia invades Ukraine escalation", "tickers": ["SPY", "NVDA"]},
    )
    data = resp.json()
    assert "scenario_summary" in data
    assert "predictions" in data
    assert "disclaimer" in data
    assert len(data["predictions"]) == 2


def test_whatif_predictions_have_delta(client):
    resp = client.post(
        "/api/whatif",
        json={"scenario": "US sanctions on oil exports", "tickers": ["SPY", "NVDA"]},
    )
    data = resp.json()
    for pred in data["predictions"]:
        assert "ticker" in pred
        assert "baseline_return" in pred
        assert "adjusted_return" in pred
        assert "delta" in pred
        assert abs(pred["delta"] - (pred["adjusted_return"] - pred["baseline_return"])) < 1e-5


def test_whatif_too_many_tickers(client):
    tickers = [f"TICK{i}" for i in range(11)]
    resp = client.post(
        "/api/whatif",
        json={"scenario": "some event", "tickers": tickers},
    )
    assert resp.status_code == 400


def test_whatif_disclaimer_present(client):
    resp = client.post(
        "/api/whatif",
        json={"scenario": "nuclear conflict"},
    )
    data = resp.json()
    assert "Not financial advice" in data["disclaimer"]
