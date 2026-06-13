"""FinBERT sentiment scorer for financial headlines.

Uses ProsusAI/finbert from HuggingFace to score each headline as
positive/negative/neutral, then aggregates to a single daily sentiment
float: (positive_prob - negative_prob).

This is Baseline B2b in the ablation study (eval_scripts/baseline_ablation.py),
used for head-to-head comparison against B2 (GPT sentiment) and B3 (structured
geo features).

Usage:
    scorer = FinBERTScorer()
    score = scorer.score_headlines(["Fed raises rates by 75bps", "Earnings beat"])
    # score is a float in [-1, 1]
"""

import hashlib
import importlib
import json
import logging
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger(__name__)

_DEFAULT_CACHE_PATH = (
    Path(__file__).resolve().parents[1] / "results" / "finbert_cache.jsonl"
)
FINBERT_CACHE_PATH = Path(os.getenv("FINBERT_CACHE_PATH", str(_DEFAULT_CACHE_PATH)))

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, float] = {}
_DISK_LOAD_DONE = False


def _headline_key(headlines: list[str]) -> str:
    """Stable hash of the sorted, normalized headline list."""
    joined = "\n".join(sorted(h.strip() for h in headlines if h and h.strip()))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _load_disk_cache() -> None:
    global _DISK_LOAD_DONE
    if _DISK_LOAD_DONE:
        return
    _DISK_LOAD_DONE = True
    if not FINBERT_CACHE_PATH.exists():
        return
    try:
        with FINBERT_CACHE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    key = row.get("key")
                    score = row.get("score")
                    if key and isinstance(score, (int, float)):
                        _CACHE[key] = float(score)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        LOGGER.info("finbert_features: loaded %d cached entries from %s", len(_CACHE), FINBERT_CACHE_PATH)
    except OSError as exc:
        LOGGER.warning("finbert_features: could not read disk cache %s: %s", FINBERT_CACHE_PATH, exc)


def _persist_to_disk(key: str, score: float) -> None:
    try:
        FINBERT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FINBERT_CACHE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "score": score, "ts": time.time()}) + "\n")
    except OSError as exc:
        LOGGER.warning("finbert_features: could not write disk cache: %s", exc)


def _check_transformers_available() -> bool:
    return importlib.util.find_spec("transformers") is not None


@lru_cache(maxsize=1)
def _load_pipeline():
    if not _check_transformers_available():
        return None
    try:
        from transformers import pipeline as hf_pipeline
        return hf_pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            top_k=None,
            device=-1,
        )
    except Exception as exc:
        LOGGER.warning("finbert_features: failed to load ProsusAI/finbert: %s", exc)
        return None


def batch_score_headlines(headlines: list[str]) -> list[dict]:
    """Score each headline with FinBERT.

    Returns a list of dicts with keys 'positive', 'negative', 'neutral'
    (probabilities summing to 1.0). Returns fallback zeros if model is
    unavailable or headline is empty.

    Parameters
    ----------
    headlines:
        List of news headline strings.

    Returns
    -------
    list[dict]
        One dict per headline with keys 'positive', 'negative', 'neutral'.
    """
    fallback = {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
    if not headlines:
        return []

    pipe = _load_pipeline()
    if pipe is None:
        return [dict(fallback) for _ in headlines]

    cleaned = [h.strip()[:512] or "no text" for h in headlines]

    results = []
    try:
        raw = pipe(cleaned, batch_size=8, truncation=True)
        for item in raw:
            scores = {entry["label"].lower(): entry["score"] for entry in item}
            results.append({
                "positive": scores.get("positive", 0.0),
                "negative": scores.get("negative", 0.0),
                "neutral": scores.get("neutral", 1.0),
            })
    except Exception as exc:
        LOGGER.warning("finbert_features: inference failed: %s", exc)
        return [dict(fallback) for _ in headlines]

    return results


def aggregate_daily_sentiment(headlines: list[str]) -> float:
    """Return daily FinBERT sentiment score for a list of headlines.

    Aggregates per-headline scores by averaging
    (positive_prob - negative_prob) across all headlines.

    Result is cached to JSONL on disk keyed by SHA1 of the sorted headline
    list, so backtests survive process restarts without re-running FinBERT.

    Returns a float in [-1, 1]. Returns 0.0 if no headlines.
    """
    if not headlines:
        return 0.0

    key = _headline_key(headlines)
    with _CACHE_LOCK:
        _load_disk_cache()
        cached = _CACHE.get(key)
    if cached is not None:
        return cached

    scores = batch_score_headlines(headlines)
    if not scores:
        return 0.0

    daily = sum(s["positive"] - s["negative"] for s in scores) / len(scores)
    daily = max(-1.0, min(1.0, daily))

    with _CACHE_LOCK:
        _CACHE[key] = daily
    _persist_to_disk(key, daily)

    return daily
