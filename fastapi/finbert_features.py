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

import importlib
import logging
from functools import lru_cache

LOGGER = logging.getLogger(__name__)


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

    Returns a float in [-1, 1]. Returns 0.0 if no headlines.
    """
    if not headlines:
        return 0.0

    scores = batch_score_headlines(headlines)
    if not scores:
        return 0.0

    daily = sum(s["positive"] - s["negative"] for s in scores) / len(scores)
    return max(-1.0, min(1.0, daily))
