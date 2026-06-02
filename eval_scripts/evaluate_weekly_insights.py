#!/usr/bin/env python3
"""
Weekly Dashboard LLM Evaluation
================================
Collects quality metrics for AI-generated weekly market insights.

Metrics:
  Custom (no ground truth required):
    symbol_accuracy         % of mentioned tickers that exist in context data
    symbol_coverage         % of context tickers referenced in output
    numerical_faithfulness  % of stated % values within tolerance of actual data
    hedge_language_score    % of event_impacts using cautious language
    output_completeness     bullet counts within expected ranges
    temperature             LLM temperature setting (fixed 0.4)
    model                   LLM model used

  Ragas (requires OPENAI_API_KEY, adds API cost):
    faithfulness            factual grounding of claims in context
    answer_relevancy        relevance of output to the query/context

Usage:
  # From live API (backend must be running)
  python evaluate_weekly_insights.py --api-url http://localhost:8000

  # Save a snapshot and the report
  python evaluate_weekly_insights.py --api-url http://localhost:8000 --save-snapshot snapshot.json --output report.json

  # Evaluate from a previously saved snapshot (no API needed)
  python evaluate_weekly_insights.py --input snapshot.json

  # Custom metrics only (no Ragas / no extra OpenAI cost)
  python evaluate_weekly_insights.py --api-url http://localhost:8000 --skip-ragas

  # Adjust numerical tolerance (default ±1.5 percentage points)
  python evaluate_weekly_insights.py --api-url http://localhost:8000 --num-tolerance 2.0
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# Load .env from project root (one level up from eval_scripts/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Ragas import (optional)
# ---------------------------------------------------------------------------
RAGAS_AVAILABLE = False
try:
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness  # type: ignore

    RAGAS_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Common English words / abbreviations that look like tickers but are not
# ---------------------------------------------------------------------------
_NOT_TICKERS = {
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "AM", "AN", "AS", "AT", "BE", "BY", "IF", "IN", "IS", "IT",
    "OF", "ON", "OR", "SO", "TO", "UP", "US",
    "AND", "ARE", "BUT", "CAN", "FOR", "HAS", "HAD", "HIT", "ITS", "LED",
    "MAY", "NEW", "NOT", "THE", "WAS",
    "ALSO", "AMID", "BEEN", "BOTH", "FROM", "HAVE", "INTO", "RATE", "ROSE",
    "SAID", "THAN", "THAT", "THEM", "THEN", "THEY", "THIS", "WITH", "WERE",
    "WILL", "WEEK", "YEAR",
    # macro / market terms that are all-caps but not tickers
    "AI", "GDP", "IPO", "ETF", "FED", "SEC", "IMF", "ECB", "USD", "EUR",
    "OIL", "YOY", "QOQ", "YTD", "EPS", "CEO", "CFO", "CPI", "PPI",
}

_HEDGE_WORDS = [
    "could", "may", "might", "potentially", "likely", "possible", "possibly",
    "suggest", "suggests", "indicate", "indicates", "appear", "appears",
    "seem", "seems", "tend", "tends", "if", "should", "expected", "anticipate",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_tickers(text: str) -> set[str]:
    """Return set of plausible ticker symbols from free text."""
    candidates = re.findall(r"\b([A-Z]{1,5})\b", text)
    return {c for c in candidates if c not in _NOT_TICKERS}


def _extract_percentages(text: str) -> list[float]:
    """Return all numeric percentage values mentioned in text."""
    return [float(m) for m in re.findall(r"([+-]?\d+\.?\d*)\s*%", text)]


def _normalize_symbol(symbol: str) -> str:
    return symbol.upper().removesuffix(".US")


def _context_symbols(alerts: list[dict]) -> set[str]:
    return {_normalize_symbol(a["symbol"]) for a in alerts}


def _context_pct_changes(alerts: list[dict]) -> list[float]:
    return [a["pct_change"] for a in alerts]


# ---------------------------------------------------------------------------
# Custom metrics
# ---------------------------------------------------------------------------

def metric_symbol_accuracy(output_text: str, ctx_symbols: set[str]) -> dict:
    """% of mentioned tickers that actually exist in the context data."""
    found = _extract_tickers(output_text)
    if not found:
        return {"score": None, "note": "No ticker-like tokens found in output",
                "extracted": [], "matched": [], "unmatched": []}
    matched = found & ctx_symbols
    unmatched = found - ctx_symbols
    return {
        "score": round(len(matched) / len(found), 3),
        "extracted": sorted(found),
        "matched": sorted(matched),
        "unmatched": sorted(unmatched),
    }


def metric_symbol_coverage(output_text: str, ctx_symbols: set[str]) -> dict:
    """% of context tickers referenced anywhere in the output."""
    if not ctx_symbols:
        return {"score": None, "note": "No context symbols available"}
    mentioned = {s for s in ctx_symbols if s in output_text}
    return {
        "score": round(len(mentioned) / len(ctx_symbols), 3),
        "mentioned": sorted(mentioned),
        "not_mentioned": sorted(ctx_symbols - mentioned),
        "total_context_symbols": len(ctx_symbols),
    }


def metric_numerical_faithfulness(
    output_text: str,
    ctx_pcts: list[float],
    tolerance: float = 1.5,
) -> dict:
    """% of stated % values within ±tolerance of actual context data."""
    output_pcts = _extract_percentages(output_text)
    if not output_pcts:
        return {"score": None, "note": "No percentage values found in output"}
    ctx_abs = {round(abs(p), 2) for p in ctx_pcts}
    details = []
    matched_count = 0
    for pct in output_pcts:
        is_match = any(abs(abs(pct) - cp) <= tolerance for cp in ctx_abs)
        details.append({"stated_pct": pct, "matched_in_context": is_match})
        if is_match:
            matched_count += 1
    return {
        "score": round(matched_count / len(output_pcts), 3),
        "total_percentages_stated": len(output_pcts),
        "matched": matched_count,
        "tolerance_pct_points": tolerance,
        "details": details,
    }


def metric_hedge_language(event_impacts: list[str]) -> dict:
    """% of event_impacts bullets using cautious/hedge language."""
    if not event_impacts:
        return {"score": None, "note": "No event_impacts to evaluate"}
    hedged = [
        b for b in event_impacts
        if any(w in b.lower() for w in _HEDGE_WORDS)
    ]
    return {
        "score": round(len(hedged) / len(event_impacts), 3),
        "hedged_count": len(hedged),
        "total_count": len(event_impacts),
        "unhedged_bullets": [b for b in event_impacts if b not in hedged],
    }


def metric_output_completeness(
    market_insights: list[str],
    event_impacts: list[str],
) -> dict:
    """Check bullet counts against expected ranges (3-5 market, 0-5 events)."""
    market_ok = 3 <= len(market_insights) <= 5
    events_ok = 0 <= len(event_impacts) <= 5
    if market_ok and events_ok:
        score = 1.0
    elif market_ok or events_ok:
        score = 0.5
    else:
        score = 0.0
    return {
        "score": score,
        "market_insights_count": len(market_insights),
        "event_impacts_count": len(event_impacts),
        "market_in_range_3_5": market_ok,
        "events_in_range_0_5": events_ok,
    }


# ---------------------------------------------------------------------------
# Geo event grounding (sentence-transformers, optional)
# ---------------------------------------------------------------------------

def _sbert_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("sentence_transformers") is not None


@lru_cache(maxsize=1)
def _load_sbert():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def geo_event_grounding(
    insights: dict,
    source_headlines: list[str],
    threshold: float = 0.75,
) -> dict:
    """Fraction of event_impacts bullets grounded in at least one source headline (cosine >= threshold)."""
    event_impacts: list[str] = insights.get("event_impacts") or []
    if not event_impacts:
        return {"score": None, "note": "No event_impacts to evaluate"}
    clean_headlines = [h for h in source_headlines if h]
    if not clean_headlines:
        return {"score": None, "note": "No source headlines provided"}
    if not _sbert_available():
        return {"score": None, "note": "sentence-transformers not installed"}

    try:
        import numpy as np
        model = _load_sbert()
        impact_embs = model.encode(event_impacts, normalize_embeddings=True)
        headline_embs = model.encode(clean_headlines, normalize_embeddings=True)
        sims = np.dot(impact_embs, headline_embs.T)  # (n_impacts, n_headlines)

        details = []
        grounded_count = 0
        for i, bullet in enumerate(event_impacts):
            max_sim = float(sims[i].max())
            best_idx = int(sims[i].argmax())
            is_grounded = max_sim >= threshold
            if is_grounded:
                grounded_count += 1
            details.append({
                "bullet": bullet,
                "max_similarity": round(max_sim, 3),
                "best_match": clean_headlines[best_idx][:120],
                "grounded": is_grounded,
            })

        return {
            "score": round(grounded_count / len(event_impacts), 3),
            "grounded_count": grounded_count,
            "total_bullets": len(event_impacts),
            "threshold": threshold,
            "details": details,
        }
    except Exception as exc:  # noqa: BLE001
        return {"score": None, "note": f"sentence-transformers error: {exc}"}


# ---------------------------------------------------------------------------
# Ragas helpers
# ---------------------------------------------------------------------------

def _build_ragas_contexts(alerts: list[dict], events: list[dict]) -> list[str]:
    """Convert raw market data into Ragas-compatible context strings."""
    contexts: list[str] = []

    by_source: dict[str, list[dict]] = {}
    for a in alerts:
        by_source.setdefault(a.get("source", "other"), []).append(a)

    label_map = {"core": "Core stock weekly changes", "top": "Top weekly gainers",
                 "bottom": "Bottom weekly movers", "other": "Other stocks"}
    for source, label in label_map.items():
        items = by_source.get(source, [])
        if items:
            parts = ", ".join(
                f"{_normalize_symbol(i['symbol'])} {i['pct_change']:+.2f}%"
                for i in items
            )
            contexts.append(f"{label}: {parts}")

    if events:
        titles = "; ".join(e.get("title", "") for e in events if e.get("title"))
        if titles:
            contexts.append(f"Market events this week: {titles}")

    return contexts


def run_ragas(
    market_insights: list[str],
    event_impacts: list[str],
    date_range: str,
    alerts: list[dict],
    events: list[dict],
) -> dict:
    """Run Ragas faithfulness + answer_relevancy per bullet. Returns scores dict."""
    if not RAGAS_AVAILABLE:
        return {"error": "ragas not installed. Run: pip install 'ragas>=0.2'"}

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return {"error": "OPENAI_API_KEY not set — required for Ragas evaluation"}

    contexts = _build_ragas_contexts(alerts, events)
    user_input = (
        f"Generate concise market insights and event impacts for the week of {date_range}. "
        "Reference specific stock symbols and use cautious language for event impacts."
    )

    try:
        import openai as _openai  # type: ignore
        from ragas.llms import llm_factory  # type: ignore
        from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings  # type: ignore

        # ── Token usage tracker ──────────────────────────────
        # gpt-4o-mini pricing (per 1M tokens)
        GPT4O_MINI_INPUT_COST = 0.15 / 1e6
        GPT4O_MINI_OUTPUT_COST = 0.60 / 1e6
        # text-embedding-3-small pricing (per 1M tokens)
        EMBED_SMALL_COST = 0.02 / 1e6

        token_usage = {
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "embedding_tokens": 0,
        }

        class _TrackingAsyncOpenAI(_openai.AsyncOpenAI):
            """Thin wrapper that intercepts completions to accumulate token usage."""
            def __init__(self, tracker: dict, **kwargs):
                super().__init__(**kwargs)
                self._tracker = tracker
                # Wrap chat.completions.create
                _orig_create = self.chat.completions.create
                async def _tracked_create(*args, **kw):
                    resp = await _orig_create(*args, **kw)
                    if hasattr(resp, "usage") and resp.usage:
                        self._tracker["llm_input_tokens"] += resp.usage.prompt_tokens or 0
                        self._tracker["llm_output_tokens"] += resp.usage.completion_tokens or 0
                    return resp
                self.chat.completions.create = _tracked_create
                # Wrap embeddings.create
                _orig_embed = self.embeddings.create
                async def _tracked_embed(*args, **kw):
                    resp = await _orig_embed(*args, **kw)
                    if hasattr(resp, "usage") and resp.usage:
                        self._tracker["embedding_tokens"] += resp.usage.total_tokens or 0
                    return resp
                self.embeddings.create = _tracked_embed

        openai_client = _TrackingAsyncOpenAI(tracker=token_usage, api_key=openai_key)
        llm = llm_factory("gpt-4o-mini", client=openai_client, max_tokens=8192)
        embeddings = RagasOpenAIEmbeddings(model="text-embedding-3-small", client=openai_client)

        faith_metric = Faithfulness(llm=llm)
        rel_metric = AnswerRelevancy(llm=llm, embeddings=embeddings)

        def _score_bullet(bullet: str) -> dict:
            """Score a single bullet for faithfulness and answer relevancy."""
            f_result = faith_metric.score(
                user_input=user_input,
                response=bullet,
                retrieved_contexts=contexts,
            )
            r_result = rel_metric.score(
                user_input=user_input,
                response=bullet,
            )
            return {
                "text": bullet,
                "faithfulness": round(float(f_result.value), 3),
                "answer_relevancy": round(float(r_result.value), 3),
            }

        mi_scores = [_score_bullet(b) for b in market_insights]
        ei_scores = [_score_bullet(b) for b in event_impacts]

        def _avg(items: list[dict], key: str) -> Optional[float]:
            vals = [d[key] for d in items if d[key] is not None]
            return round(sum(vals) / len(vals), 3) if vals else None

        llm_cost = (token_usage["llm_input_tokens"] * GPT4O_MINI_INPUT_COST
                     + token_usage["llm_output_tokens"] * GPT4O_MINI_OUTPUT_COST)
        embed_cost = token_usage["embedding_tokens"] * EMBED_SMALL_COST
        total_cost = llm_cost + embed_cost

        return {
            "market_insights": {
                "bullets": mi_scores,
                "faithfulness": _avg(mi_scores, "faithfulness"),
                "answer_relevancy": _avg(mi_scores, "answer_relevancy"),
            },
            "event_impacts": {
                "bullets": ei_scores,
                "faithfulness": _avg(ei_scores, "faithfulness"),
                "answer_relevancy": _avg(ei_scores, "answer_relevancy"),
            },
            "overall": {
                "faithfulness": _avg(mi_scores + ei_scores, "faithfulness"),
                "answer_relevancy": _avg(mi_scores + ei_scores, "answer_relevancy"),
            },
            "cost": {
                "llm_input_tokens": token_usage["llm_input_tokens"],
                "llm_output_tokens": token_usage["llm_output_tokens"],
                "embedding_tokens": token_usage["embedding_tokens"],
                "llm_cost_usd": round(llm_cost, 6),
                "embedding_cost_usd": round(embed_cost, 6),
                "total_cost_usd": round(total_cost, 6),
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Ragas evaluation failed: {exc}"}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_from_api(base_url: str, end_date: str | None = None) -> dict:
    """Fetch insights and alert data from a running backend."""
    base_url = base_url.rstrip("/")
    params = {"end_date": end_date} if end_date else {}
    try:
        insights_resp = requests.get(
            f"{base_url}/api/weekly-insights", params=params, timeout=120,
        )
        insights_resp.raise_for_status()
        insights = insights_resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed to fetch weekly-insights: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        alerts_resp = requests.get(
            f"{base_url}/api/weekly-alerts", params=params, timeout=30,
        )
        alerts_resp.raise_for_status()
        alerts_data = alerts_resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed to fetch weekly-alerts: {exc}", file=sys.stderr)
        sys.exit(1)

    return {"insights": insights, "alerts": alerts_data}


def load_from_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _score_bar(score: Optional[float], width: int = 20) -> str:
    import math
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "N/A"
    filled = round(score * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score:.3f}"


def print_report(report: dict) -> None:
    print("\n" + "=" * 60)
    print("  Weekly Dashboard LLM Evaluation Report")
    print("=" * 60)
    meta = report["metadata"]
    print(f"  Date range : {meta['date_range']}")
    print(f"  Model      : {meta['model']}")
    print(f"  Temperature: {meta['temperature']}")
    print(f"  Evaluated  : {meta['evaluated_at']}")
    print()

    print("── Custom Metrics ──────────────────────────────────────")
    cm = report["custom_metrics"]

    print(f"  Symbol Accuracy         {_score_bar(cm['symbol_accuracy']['score'])}")
    acc = cm["symbol_accuracy"]
    if acc.get("unmatched"):
        print(f"    Unmatched tickers   : {', '.join(acc['unmatched'])}")

    print(f"  Symbol Coverage         {_score_bar(cm['symbol_coverage']['score'])}")

    print(f"  Numerical Faithfulness  {_score_bar(cm['numerical_faithfulness']['score'])}")
    nf = cm["numerical_faithfulness"]
    if "total_percentages_stated" in nf:
        print(f"    Stated %s matched   : {nf['matched']}/{nf['total_percentages_stated']} "
              f"(±{nf['tolerance_pct_points']} pp)")

    print(f"  Hedge Language Score    {_score_bar(cm['hedge_language']['score'])}")
    hl = cm["hedge_language"]
    if hl.get("unhedged_bullets"):
        print("    Unhedged bullets    :")
        for b in hl["unhedged_bullets"]:
            print(f"      • {b[:90]}")

    print(f"  Output Completeness     {_score_bar(cm['output_completeness']['score'])}")
    oc = cm["output_completeness"]
    print(f"    Market insights      : {oc['market_insights_count']} bullets "
          f"({'OK' if oc['market_in_range_3_5'] else 'OUT OF RANGE'})")
    print(f"    Event impacts        : {oc['event_impacts_count']} bullets "
          f"({'OK' if oc['events_in_range_0_5'] else 'OUT OF RANGE'})")

    geo = cm.get("geo_grounding")
    if geo is not None:
        print(f"  Geo Event Grounding     {_score_bar(geo.get('score'))}")
        if geo.get("note"):
            print(f"    Note                : {geo['note']}")
        elif geo.get("details"):
            ungrounded = [d for d in geo["details"] if not d.get("grounded")]
            if ungrounded:
                print("    Ungrounded bullets  :")
                for d in ungrounded:
                    print(f"      * {d['bullet'][:80]} (sim={d['max_similarity']:.3f})")

    ragas = report.get("ragas_metrics")
    if ragas:
        print()
        print("── Ragas Metrics ───────────────────────────────────────")
        if "error" in ragas:
            print(f"  {ragas['error']}")
        else:
            overall = ragas.get("overall", {})
            print(f"  Overall Faithfulness    {_score_bar(overall.get('faithfulness'))}")
            print(f"  Overall Relevancy       {_score_bar(overall.get('answer_relevancy'))}")

            for section, label in [("market_insights", "Market Insights"),
                                   ("event_impacts", "Event Impacts")]:
                data = ragas.get(section, {})
                if not data:
                    continue
                print(f"\n  {label} (avg faith={data.get('faithfulness', 'N/A')}, "
                      f"rel={data.get('answer_relevancy', 'N/A')}):")
                for b in data.get("bullets", []):
                    f_val = b.get("faithfulness", 0) or 0
                    r_val = b.get("answer_relevancy", 0) or 0
                    f_icon = "+" if f_val >= 0.5 else "-"
                    r_icon = "+" if r_val >= 0.5 else "-"
                    text = b["text"][:80] + ("..." if len(b["text"]) > 80 else "")
                    print(f"    [{f_icon}F {f_val:.2f}] [{r_icon}R {r_val:.2f}] {text}")

            cost = ragas.get("cost")
            if cost:
                print()
                print("── Ragas Cost ──────────────────────────────────────────")
                print(f"  LLM tokens     : {cost['llm_input_tokens']:,} in / {cost['llm_output_tokens']:,} out")
                print(f"  Embedding tokens: {cost['embedding_tokens']:,}")
                print(f"  LLM cost       : ${cost['llm_cost_usd']:.4f}")
                print(f"  Embedding cost : ${cost['embedding_cost_usd']:.4f}")
                print(f"  Total cost     : ${cost['total_cost_usd']:.4f}")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate weekly dashboard LLM output quality."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--api-url", metavar="URL",
        help="Base URL of running backend (e.g. http://localhost:8000)",
    )
    source.add_argument(
        "--input", metavar="FILE",
        help="Path to a previously saved snapshot JSON file",
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Write JSON report to this file",
    )
    parser.add_argument(
        "--save-snapshot", metavar="FILE",
        help="Save fetched API data as a snapshot JSON for later --input use",
    )
    parser.add_argument(
        "--skip-ragas", action="store_true",
        help="Skip Ragas metrics (no extra OpenAI cost)",
    )
    parser.add_argument(
        "--num-tolerance", type=float, default=1.5, metavar="PP",
        help="Tolerance in percentage points for numerical faithfulness (default 1.5)",
    )
    args = parser.parse_args()

    # ── Fetch data ──────────────────────────────────────────────────────────
    if args.api_url:
        print(f"Fetching data from {args.api_url} ...")
        data = fetch_from_api(args.api_url)
        if args.save_snapshot:
            with open(args.save_snapshot, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"Snapshot saved to {args.save_snapshot}")
    else:
        print(f"Loading snapshot from {args.input} ...")
        data = load_from_file(args.input)

    insights = data["insights"]
    alerts_data = data["alerts"]

    market_insights: list[str] = insights.get("market_insights") or []
    event_impacts: list[str] = insights.get("event_impacts") or []
    events: list[dict] = insights.get("events") or []
    alerts: list[dict] = alerts_data.get("alerts") or []

    if not market_insights:
        note = insights.get("note", "unknown")
        print(f"WARNING: No market_insights in response. Note: {note}", file=sys.stderr)

    output_text = " ".join(market_insights + event_impacts)
    ctx_symbols = _context_symbols(alerts)
    # Also include benchmark symbols (SPY, QQQ, DIA, IWM) so ETFs are recognised as valid
    for entry in alerts_data.get("benchmarks") or []:
        if isinstance(entry, dict) and entry.get("symbol"):
            ctx_symbols.add(_normalize_symbol(entry["symbol"]))
    ctx_pcts = _context_pct_changes(alerts)
    date_range = f"{insights.get('start', '?')} to {insights.get('end', '?')}"
    model = insights.get("model") or "unknown"

    # ── Custom metrics ───────────────────────────────────────────────────────
    source_headlines = [e.get("title", "") for e in events if e.get("title")]
    custom_metrics = {
        "symbol_accuracy": metric_symbol_accuracy(output_text, ctx_symbols),
        "symbol_coverage": metric_symbol_coverage(output_text, ctx_symbols),
        "numerical_faithfulness": metric_numerical_faithfulness(
            output_text, ctx_pcts, tolerance=args.num_tolerance
        ),
        "hedge_language": metric_hedge_language(event_impacts),
        "output_completeness": metric_output_completeness(market_insights, event_impacts),
        "geo_grounding": geo_event_grounding(insights, source_headlines),
    }

    # ── Ragas metrics ────────────────────────────────────────────────────────
    ragas_metrics: Optional[dict] = None
    if not args.skip_ragas:
        if not RAGAS_AVAILABLE:
            print("WARNING: ragas not installed. Run: pip install 'ragas>=0.2'")
            print("         Skipping Ragas metrics. Use --skip-ragas to suppress this warning.")
        else:
            print("Running Ragas evaluation (this calls OpenAI) ...")
            ragas_metrics = run_ragas(
                market_insights, event_impacts, date_range, alerts, events
            )

    # ── Build report ─────────────────────────────────────────────────────────
    report = {
        "metadata": {
            "date_range": date_range,
            "model": model,
            "temperature": 0.4,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
            "ragas_available": RAGAS_AVAILABLE,
        },
        "custom_metrics": custom_metrics,
        "ragas_metrics": ragas_metrics,
        "raw": {
            "market_insights": market_insights,
            "event_impacts": event_impacts,
            "events_count": len(events),
            "alerts_count": len(alerts),
        },
    }

    print_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
