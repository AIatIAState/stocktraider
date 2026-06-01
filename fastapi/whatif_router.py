import logging
import os
import time

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from geo_features import GeoFeatureExtractor, ZERO_GEO_FEATURES

LOGGER = logging.getLogger("uvicorn.error")

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
WHATIF_DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "NVDA", "XOM", "LMT", "TSM"]

_RATE_LOCK = __import__("threading").Lock()
_LAST_OPENAI_CALL = 0.0
OPENAI_MIN_INTERVAL_SECONDS = int(os.getenv("OPENAI_MIN_INTERVAL_SECONDS", "60"))

router = APIRouter()


class WhatIfRequest(BaseModel):
    scenario: str = Field(..., description="Free-text hypothetical geopolitical event")
    tickers: list[str] | None = Field(None, description="Tickers to evaluate; defaults to watchlist")
    horizon_days: int = Field(5, ge=1, le=30)


class TickerPrediction(BaseModel):
    ticker: str
    baseline_return: float
    adjusted_return: float
    delta: float
    confidence: float
    narrative: str


class WhatIfResponse(BaseModel):
    scenario_summary: str
    extracted_features: dict
    predictions: list[TickerPrediction]
    disclaimer: str


def _call_openai_raw(prompt: str, max_tokens: int = 300) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    global _LAST_OPENAI_CALL
    now = time.time()
    with _RATE_LOCK:
        wait = OPENAI_MIN_INTERVAL_SECONDS - (now - _LAST_OPENAI_CALL)
        if wait > 0:
            time.sleep(wait)
        _LAST_OPENAI_CALL = time.time()

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise financial market analyst. Provide informational analysis only, no investment advice.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    try:
        resp = requests.post(
            OPENAI_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        LOGGER.warning("whatif: OpenAI call failed: %s", exc)
        return None


def _extract_scenario_features(scenario: str) -> dict:
    """Use GeoFeatureExtractor to parse scenario into numeric features."""
    extractor = GeoFeatureExtractor()
    if not extractor._openai_key:
        return dict(ZERO_GEO_FEATURES)

    prompt = (
        f'Scenario: "{scenario}"\n\n'
        "Extract structured features and return JSON with:\n"
        '- actor: ["none","us","china","russia","other"]\n'
        '- event_type: ["none","tariff","sanctions","conflict","election","policy"]\n'
        '- affected_sector: ["none","energy","materials","industrials","utilities","healthcare",'
        '"financials","consumer_discretionary","consumer_staples","information_technology",'
        '"communication_services","real_estate","defense","semiconductors"]\n'
        "- direction: -1, 0, or 1 (market impact)\n"
        "- magnitude: 0.0-1.0 (impact size)\n"
        "- sentiment_score: -1.0-1.0\n"
        "Return only valid JSON."
    )
    raw = extractor._call_openai([scenario])
    if raw:
        return extractor._parse_llm_result(raw)
    return dict(ZERO_GEO_FEATURES)


def _compute_adjusted_return(baseline: float, geo_features: dict) -> tuple[float, float]:
    """Apply geo feature adjustment to baseline prediction.

    Uses a linear heuristic: direction * magnitude scales the baseline.
    Confidence reflects the LLM's certainty (magnitude proxy).
    Returns (adjusted_return, confidence).
    """
    direction = geo_features.get("geo_direction", 0)
    magnitude = geo_features.get("geo_event_magnitude", 0.0)
    sensitivity = 0.015

    adjustment = direction * magnitude * sensitivity
    adjusted = baseline + adjustment
    confidence = max(0.3, min(0.9, 0.5 + magnitude * 0.4))
    return adjusted, confidence


def _get_baseline_predictions(tickers: list[str]) -> dict[str, float]:
    """Call XGBoostInvestor to get baseline predictions for each ticker."""
    try:
        import pandas as pd
        from xg_boost_investor import XGBoostInvestor
        from xg_boost_investor.Features import build_full_features

        results: dict[str, float] = {}
        for ticker in tickers:
            try:
                market_conditions, _ = build_full_features([ticker], today=True)
                xgb = XGBoostInvestor.XGBoostInvestor()
                xgb.load("xg_boost_investor/model_save/model/xgboost_investor")
                df = pd.DataFrame(market_conditions).reset_index(drop=True)
                X, _, _, _ = xgb.prepare_predictions(df, pd.DataFrame({"ret_1d": [0]}))
                pred = xgb.predict(X)
                results[ticker] = float(pred[-1]) if len(pred) > 0 else 0.0
            except Exception as exc:
                LOGGER.warning("whatif: baseline prediction failed for %s: %s", ticker, exc)
                results[ticker] = 0.0
        return results
    except ImportError as exc:
        LOGGER.warning("whatif: XGBoostInvestor not available: %s", exc)
        return {t: 0.0 for t in tickers}


def _generate_narrative(ticker: str, scenario: str, features: dict, delta: float) -> str:
    direction_word = "positive" if delta > 0 else ("negative" if delta < 0 else "neutral")
    prompt = (
        f'Given this hypothetical scenario: "{scenario}"\n'
        f"Extracted event type: {features.get('geo_event_type_encoded')}, "
        f"actor: {features.get('geo_actor_encoded')}, "
        f"sector impact: {features.get('geo_affected_sector_encoded')}\n"
        f"Expected {direction_word} market impact for {ticker}.\n\n"
        f"In 1-2 sentences, explain why {ticker} would be affected. "
        "Focus on supply chain, sector exposure, or macro sensitivity. No investment advice."
    )
    narrative = _call_openai_raw(prompt, max_tokens=80)
    if not narrative:
        return f"Scenario may have a {direction_word} effect on {ticker} based on sector and geopolitical exposure."
    return narrative


@router.post("/api/whatif", response_model=WhatIfResponse)
def what_if(request: WhatIfRequest) -> WhatIfResponse:
    tickers = [t.upper() for t in (request.tickers or WHATIF_DEFAULT_TICKERS)]
    if len(tickers) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 tickers per request")

    geo_features = _extract_scenario_features(request.scenario)

    scenario_summary_raw = _call_openai_raw(
        f'Summarize this scenario in one sentence: "{request.scenario}"',
        max_tokens=60,
    )
    scenario_summary = scenario_summary_raw or request.scenario

    extracted = {
        "actor": geo_features.get("geo_actor_encoded"),
        "event_type": geo_features.get("geo_event_type_encoded"),
        "affected_sector": geo_features.get("geo_affected_sector_encoded"),
        "direction": geo_features.get("geo_direction"),
        "magnitude": geo_features.get("geo_event_magnitude"),
    }

    baselines = _get_baseline_predictions(tickers)

    predictions: list[TickerPrediction] = []
    for ticker in tickers:
        baseline = baselines.get(ticker, 0.0)
        adjusted, confidence = _compute_adjusted_return(baseline, geo_features)
        delta = adjusted - baseline

        narrative = _generate_narrative(ticker, request.scenario, geo_features, delta)

        predictions.append(
            TickerPrediction(
                ticker=ticker,
                baseline_return=round(baseline, 6),
                adjusted_return=round(adjusted, 6),
                delta=round(delta, 6),
                confidence=round(confidence, 4),
                narrative=narrative,
            )
        )

    predictions.sort(key=lambda p: p.delta)

    return WhatIfResponse(
        scenario_summary=scenario_summary,
        extracted_features=extracted,
        predictions=predictions,
        disclaimer="Hypothetical scenario. Not financial advice.",
    )
