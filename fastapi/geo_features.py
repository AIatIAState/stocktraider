import json
import logging
import os
import threading
import time

import requests

LOGGER = logging.getLogger("uvicorn.error")

GEO_CACHE_TTL_SECONDS = int(os.getenv("GEO_FEATURES_CACHE_SECONDS", "86400"))
OPENAI_MIN_INTERVAL_SECONDS = int(os.getenv("OPENAI_MIN_INTERVAL_SECONDS", "60"))

NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

ACTOR_ENCODING = {"none": 0, "us": 1, "china": 2, "russia": 3, "other": 4}
EVENT_TYPE_ENCODING = {
    "none": 0, "tariff": 1, "sanctions": 2,
    "conflict": 3, "election": 4, "policy": 5,
}
SECTOR_ENCODING = {
    "none": 0, "energy": 1, "materials": 2, "industrials": 3,
    "utilities": 4, "healthcare": 5, "financials": 6,
    "consumer_discretionary": 7, "consumer_staples": 8,
    "information_technology": 9, "communication_services": 10,
    "real_estate": 11, "defense": 12, "semiconductors": 13,
}

ZERO_GEO_FEATURES: dict = {
    "geo_sentiment_score": 0.0,
    "geo_event_magnitude": 0.0,
    "geo_actor_encoded": 0,
    "geo_event_type_encoded": 0,
    "geo_affected_sector_encoded": 0,
    "geo_direction": 0,
    "gpr_index": 0.0,
}

GEO_FEATURE_NAMES = list(ZERO_GEO_FEATURES.keys())

_CACHE_LOCK = threading.Lock()
_CACHE: dict = {
    "timestamp": 0.0,
    "date_key": None,
    "payload": None,
    "last_openai_attempt": 0.0,
    "cooldown_until": 0.0,
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _parse_json_blob(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


class GeoFeatureExtractor:
    """Converts geopolitical news headlines into numeric ML features.

    Fetches top-5 headlines via NewsAPI, calls GPT-4o-mini for structured
    JSON extraction, and caches the result for 24 hours (matching the
    INSIGHTS_CACHE_TTL_SECONDS pattern in weekly_dashboard.py).
    """

    def __init__(self) -> None:
        self._openai_key = os.getenv("OPENAI_API_KEY")
        self._newsapi_key = os.getenv("NEWSAPI_KEY") or os.getenv("NEWSAPI_API_KEY")

    def get_geo_features(self, ticker: str, date_str: str) -> dict:
        """Return geo feature dict for (ticker, date_str).

        Features are global-macro (not ticker-specific) so the cache is
        keyed only by date. ticker is used to refine headline queries.
        Falls back to ZERO_GEO_FEATURES on any error.
        """
        now = time.time()
        with _CACHE_LOCK:
            ts = float(_CACHE["timestamp"])
            key = _CACHE["date_key"]
            payload = _CACHE["payload"]

        if key == date_str and payload is not None and now - ts < GEO_CACHE_TTL_SECONDS:
            return dict(payload)

        features = self._extract(ticker, date_str)

        with _CACHE_LOCK:
            _CACHE["timestamp"] = time.time()
            _CACHE["date_key"] = date_str
            _CACHE["payload"] = features

        return dict(features)

    def _extract(self, ticker: str, date_str: str) -> dict:
        headlines = self._fetch_headlines(ticker, date_str)
        if not headlines:
            return dict(ZERO_GEO_FEATURES)

        llm_result = self._call_openai(headlines)
        if not llm_result:
            return dict(ZERO_GEO_FEATURES)

        return self._parse_llm_result(llm_result)

    def _fetch_headlines(self, ticker: str, date_str: str) -> list[str]:
        if not self._newsapi_key:
            return []
        query = (
            "geopolitical OR tariff OR sanctions OR conflict OR election OR policy "
            "stock market"
        )
        try:
            resp = requests.get(
                NEWSAPI_ENDPOINT,
                params={
                    "q": query,
                    "from": date_str,
                    "to": date_str,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 5,
                },
                headers={"X-Api-Key": self._newsapi_key},
                timeout=10,
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return [a.get("title", "") for a in articles if a.get("title")]
        except Exception as exc:
            LOGGER.warning("geo_features: NewsAPI fetch failed: %s", exc)
            return []

    def _call_openai(self, headlines: list[str]) -> dict | None:
        if not self._openai_key:
            return None

        now = time.time()
        with _CACHE_LOCK:
            cooldown = float(_CACHE.get("cooldown_until") or 0.0)
            last = float(_CACHE.get("last_openai_attempt") or 0.0)

        if now < cooldown or now - last < OPENAI_MIN_INTERVAL_SECONDS:
            return None

        with _CACHE_LOCK:
            _CACHE["last_openai_attempt"] = now

        headline_text = "\n".join(f"- {h}" for h in headlines[:5])
        prompt = (
            "Analyze these financial news headlines and return a JSON object with:\n"
            '- actor: one of ["none","us","china","russia","other"]\n'
            '- event_type: one of ["none","tariff","sanctions","conflict","election","policy"]\n'
            '- affected_sector: one of ["none","energy","materials","industrials","utilities",'
            '"healthcare","financials","consumer_discretionary","consumer_staples",'
            '"information_technology","communication_services","real_estate","defense","semiconductors"]\n'
            "- direction: -1 (negative), 0 (neutral), or 1 (positive market impact)\n"
            "- magnitude: float 0.0-1.0 (estimated market impact size)\n"
            "- sentiment_score: float -1.0-1.0\n\n"
            f"Headlines:\n{headline_text}\n\nReturn only valid JSON."
        )

        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "temperature": 0.1,
            "max_tokens": 200,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a financial analyst extracting structured geopolitical "
                        "features. Return only valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            resp = requests.post(
                OPENAI_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            if resp.status_code == 429:
                with _CACHE_LOCK:
                    _CACHE["cooldown_until"] = now + 300
                return None
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_json_blob(content)
        except Exception as exc:
            LOGGER.warning("geo_features: OpenAI call failed: %s", exc)
            return None

    def _parse_llm_result(self, result: dict) -> dict:
        def _safe_float(val, lo: float, hi: float, default: float = 0.0) -> float:
            try:
                return _clamp(float(val), lo, hi)
            except (TypeError, ValueError):
                return default

        def _safe_int(val, lo: int, hi: int, default: int = 0) -> int:
            try:
                return max(lo, min(hi, int(val)))
            except (TypeError, ValueError):
                return default

        actor = str(result.get("actor", "none")).lower()
        event = str(result.get("event_type", "none")).lower()
        sector = str(result.get("affected_sector", "none")).lower()

        return {
            "geo_sentiment_score": _safe_float(result.get("sentiment_score"), -1.0, 1.0),
            "geo_event_magnitude": _safe_float(result.get("magnitude"), 0.0, 1.0),
            "geo_actor_encoded": ACTOR_ENCODING.get(actor, ACTOR_ENCODING["other"]),
            "geo_event_type_encoded": EVENT_TYPE_ENCODING.get(event, EVENT_TYPE_ENCODING["none"]),
            "geo_affected_sector_encoded": SECTOR_ENCODING.get(sector, SECTOR_ENCODING["none"]),
            "geo_direction": _safe_int(result.get("direction"), -1, 1),
            "gpr_index": 0.0,
        }
