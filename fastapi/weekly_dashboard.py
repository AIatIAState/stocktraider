import datetime as _dt
import json
import logging
import os
import threading
import time
from datetime import timedelta

import requests
from fastapi import HTTPException

from connector import get_connection
from WeeklyMovers import (
    date_int_to_date,
    date_to_int,
    fetch_weekly_movers,
    fetch_weekly_series,
)

LOGGER = logging.getLogger("uvicorn.error")

INSIGHTS_CACHE_TTL_SECONDS = int(os.getenv("WEEKLY_INSIGHTS_CACHE_SECONDS", "86400"))
OPENAI_MIN_INTERVAL_SECONDS = int(os.getenv("OPENAI_MIN_INTERVAL_SECONDS", "60"))
OPENAI_RATE_LIMIT_COOLDOWN_SECONDS = int(
    os.getenv("OPENAI_RATE_LIMIT_COOLDOWN_SECONDS", "300")
)
OPENAI_ERROR_COOLDOWN_SECONDS = int(os.getenv("OPENAI_ERROR_COOLDOWN_SECONDS", "60"))
INSIGHTS_CACHE_LOCK = threading.Lock()
INSIGHTS_CACHE: dict[str, object] = {
    "timestamp": 0.0,
    "end_int": None,
    "events_sig": None,
    "payload": None,
    "last_openai_attempt": 0.0,
    "cooldown_until": 0.0,
}

CORE_SYMBOLS_DEFAULT = "NVDA,AAPL,MSFT,AMZN,GOOGL,META,TSLA,AMD,NFLX,JPM"
BENCHMARK_SYMBOLS_DEFAULT = "SPY,QQQ,DIA,IWM"
NEWSDATA_ENDPOINT = "https://newsdata.io/api/1/latest"
NEWSDATA_DEFAULT_QUERY = (
    "stock market OR stocks OR equities OR earnings OR inflation OR "
    "\"Federal Reserve\" OR rates OR oil OR geopolitics"
)
NEWSDATA_MAX_PAGE_SIZE = 10


def _ensure_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _parse_json_from_text(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


def _split_markdown_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"market": [], "event": []}
    current = "market"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if "event impacts" in lower:
            current = "event"
            continue
        if "market insights" in lower:
            current = "market"
            continue
        if line.startswith(("-", "•")):
            bullet = line.lstrip("-• ").strip()
            if bullet:
                sections[current].append(bullet)
    return sections


def _get_weekly_range(conn, end_date_override: str | None = None):
    if end_date_override:
        from datetime import date as _date
        end_date = _date.fromisoformat(end_date_override)
        end_int = date_to_int(end_date)
    else:
        row = conn.execute(
            "SELECT MAX(date) AS max_date FROM bars WHERE timeframe = 'daily'"
        ).fetchone()
        if not row or row["max_date"] is None:
            raise HTTPException(status_code=404, detail="No daily bars available")
        end_int = row["max_date"]
        end_date = date_int_to_date(end_int)
    range_start = end_date - timedelta(days=6)
    range_start_int = date_to_int(range_start)
    row = conn.execute(
        """
        SELECT MIN(date) AS min_date
        FROM bars
        WHERE timeframe = 'daily'
          AND date BETWEEN ? AND ?
        """,
        (range_start_int, end_int),
    ).fetchone()
    start_int = row["min_date"] or range_start_int
    start_date = date_int_to_date(start_int)
    return start_int, end_int, start_date, end_date


def _get_core_symbols() -> list[str]:
    raw = os.getenv("WEEKLY_CORE_SYMBOLS", CORE_SYMBOLS_DEFAULT)
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


def _get_benchmark_symbols() -> list[str]:
    raw = os.getenv("WEEKLY_BENCHMARK_SYMBOLS", BENCHMARK_SYMBOLS_DEFAULT)
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


def _fetch_closes(conn, date_int: int, symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    expanded: list[str] = []
    for symbol in symbols:
        if not symbol:
            continue
        expanded.append(symbol)
        if not symbol.upper().endswith(".US"):
            expanded.append(f"{symbol}.US")
    unique_symbols = list(dict.fromkeys(expanded))
    placeholders = ",".join("?" for _ in unique_symbols)
    sql = f"""
        SELECT symbol, close
        FROM bars
        WHERE timeframe = 'daily'
          AND date = ?
          AND close IS NOT NULL
          AND symbol IN ({placeholders})
    """
    rows = conn.execute(sql, (date_int, *unique_symbols)).fetchall()
    return {row["symbol"]: row["close"] for row in rows}


def _fetch_symbol_changes(conn, symbols: list[str], start_int: int, end_int: int) -> list[dict]:
    start_closes = _fetch_closes(conn, start_int, symbols)
    end_closes = _fetch_closes(conn, end_int, symbols)
    changes: list[dict] = []
    for symbol in symbols:
        first_close = start_closes.get(symbol)
        last_close = end_closes.get(symbol)
        actual_symbol = symbol
        if first_close is None or last_close is None:
            alt_symbol = f"{symbol}.US" if not symbol.upper().endswith(".US") else symbol[:-3]
            alt_first = start_closes.get(alt_symbol)
            alt_last = end_closes.get(alt_symbol)
            if alt_first is not None and alt_last is not None:
                first_close = alt_first
                last_close = alt_last
                actual_symbol = alt_symbol
        if first_close is None or last_close is None or first_close <= 0:
            continue
        pct_change = ((last_close - first_close) / first_close) * 100.0
        changes.append(
            {
                "symbol": _normalize_symbol(actual_symbol),
                "first_close": first_close,
                "last_close": last_close,
                "pct_change": pct_change,
            }
        )
    return changes


def _normalize_symbol(symbol: str) -> str:
    if not symbol:
        return symbol
    if symbol.upper().endswith(".US"):
        return symbol[:-3]
    return symbol


def _pick_unique(items: list[dict], count: int, used: set[str]) -> list[dict]:
    picked: list[dict] = []
    for item in items:
        symbol = item.get("symbol")
        key = _normalize_symbol(symbol)
        if not symbol or key in used:
            continue
        picked.append(item)
        used.add(key)
        if len(picked) >= count:
            break
    return picked


def _extend_alerts(
    alerts: list[dict],
    used: set[str],
    items: list[dict],
    source: str,
    limit: int,
) -> None:
    for item in items:
        if len(alerts) >= limit:
            return
        symbol = item.get("symbol")
        key = _normalize_symbol(symbol)
        if not symbol or key in used:
            continue
        alerts.append({**item, "source": source})
        used.add(key)


def _normalize_event(event: dict) -> dict:
    return {
        "title": str(event.get("title") or event.get("headline") or "").strip(),
        "date": event.get("date"),
        "source": event.get("source"),
        "url": event.get("url"),
    }


def _fetch_newsdata(query: str, page_size: int) -> tuple[list[dict], str | None]:
    api_key = os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_KEY")
    if not api_key:
        return [], "NEWSDATA_API_KEY is not configured."

    params = {
        "apikey": api_key,
        "q": query,
        "language": "en",
        "size": max(1, min(page_size, NEWSDATA_MAX_PAGE_SIZE)),
    }
    try:
        response = requests.get(NEWSDATA_ENDPOINT, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        body = ""
        try:
            body = exc.response.json().get("results", {}).get("message") or exc.response.text[:120]
        except Exception:
            pass
        LOGGER.error("NewsData.io HTTP %s: %s", status, body)
        return [], f"NewsData.io returned HTTP {status}: {body}"
    except requests.RequestException as exc:
        LOGGER.error("NewsData.io request failed: %s", exc)
        return [], f"Failed to load NewsData.io events: {exc}"
    except json.JSONDecodeError:
        return [], "NewsData.io did not return JSON."

    results = data.get("results", []) if isinstance(data, dict) else []
    events: list[dict] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        source = item.get("source_id") or item.get("source_name")
        events.append(
            {
                "title": title,
                "date": item.get("pubDate"),
                "source": source,
                "url": item.get("link"),
                "image_url": item.get("image_url"),
            }
        )
    return events, None


def _load_events(start_date, end_date) -> tuple[list[dict], str | None, list[str]]:
    raw_json = os.getenv("MARKET_EVENTS_JSON")
    if raw_json:
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict) and "events" in data:
                data = data["events"]
            if isinstance(data, list):
                events = [
                    _normalize_event(item)
                    for item in data
                    if isinstance(item, dict)
                ]
                events = [event for event in events if event["title"]]
                return events, None, ["manual"]
            return (
                [],
                "MARKET_EVENTS_JSON must be a JSON array or an object with an events array.",
                [],
            )
        except json.JSONDecodeError:
            return [], "MARKET_EVENTS_JSON is not valid JSON.", []

    if os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_KEY"):
        query = os.getenv("NEWSDATA_QUERY", NEWSDATA_DEFAULT_QUERY)
        try:
            page_size = int(os.getenv("NEWSDATA_PAGE_SIZE", "10"))
        except ValueError:
            page_size = 10
        events, error = _fetch_newsdata(query, page_size)
        return events, error, ["newsdata.io"]

    url = os.getenv("MARKET_EVENTS_URL")
    if not url:
        return [], "No events feed configured.", []

    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return [], "Failed to load events feed.", []
    except json.JSONDecodeError:
        return [], "Events feed did not return JSON.", []

    if isinstance(data, dict) and "events" in data:
        data = data["events"]
    if not isinstance(data, list):
        return [], "Events feed must be a JSON array or an object with an events array.", []
    events = [_normalize_event(item) for item in data if isinstance(item, dict)]
    events = [event for event in events if event["title"]]
    return events, None, ["external-feed"]


def _parse_retry_after(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _call_openai(
    prompt: str,
) -> tuple[list[str], list[str], str | None, str | None, bool, int | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [], [], "OPENAI_API_KEY is not configured.", None, False, None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
    backoff_base = float(os.getenv("OPENAI_BACKOFF_BASE_SECONDS", "1"))
    backoff_max = float(os.getenv("OPENAI_BACKOFF_MAX_SECONDS", "8"))
    payload = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 500,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise market analyst. Provide informational summaries only, "
                    "no investment advice."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            if attempt >= max_retries:
                return [], [], f"OpenAI request failed: {exc}", model, False, None
            sleep_seconds = min(backoff_base * (2**attempt), backoff_max)
            time.sleep(sleep_seconds)
            continue

        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            if attempt >= max_retries:
                return (
                    [],
                    [],
                    "OpenAI rate limit hit. Try again later.",
                    model,
                    True,
                    retry_after,
                )
            sleep_seconds = retry_after or min(backoff_base * (2**attempt), backoff_max)
            time.sleep(sleep_seconds)
            continue

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            if attempt >= max_retries:
                return [], [], f"OpenAI request failed: {exc}", model, False, None
            sleep_seconds = min(backoff_base * (2**attempt), backoff_max)
            time.sleep(sleep_seconds)
            continue

        try:
            data = response.json()
        except ValueError:
            return [], [], "OpenAI response was not valid JSON.", model, False, None

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        parsed = _parse_json_from_text(content)
        market_insights = _ensure_list(parsed.get("market_insights"))
        event_impacts = _ensure_list(parsed.get("event_impacts"))

    if not market_insights and content:
        market_insights = _ensure_list(content)

    if (
        not event_impacts
        and len(market_insights) == 1
        and "event impacts" in market_insights[0].lower()
    ):
        sections = _split_markdown_sections(market_insights[0])
        market_insights = sections.get("market") or market_insights
        event_impacts = sections.get("event") or event_impacts
    return market_insights, event_impacts, None, model, False, None
    return [], [], "OpenAI request failed after retries.", model, False, None


ALERTS_CACHE_TTL_SECONDS = 86400  # 24 hours
ALERTS_CACHE_LOCK = threading.Lock()
# Keyed by "end_int:min_volume"
ALERTS_CACHE: dict[str, dict] = {}


def _alerts_cache_key(end_int: int, min_volume: int | None) -> str:
    return f"{end_int}:{min_volume or 0}"


def build_weekly_alerts(end_date: str | None = None, min_volume: int | None = None) -> dict:
    historical = end_date is not None
    limit = int(os.getenv("WEEKLY_ALERTS_LIMIT", "20"))
    core_target = int(os.getenv("WEEKLY_ALERTS_CORE_TARGET", "10"))
    top_target = int(os.getenv("WEEKLY_ALERTS_TOP_TARGET", "5"))
    bottom_target = int(os.getenv("WEEKLY_ALERTS_BOTTOM_TARGET", "5"))
    conn = get_connection(readonly=True)
    try:
        start_int, end_int, start_date, end_date = _get_weekly_range(conn, end_date)

        # --- cache check ---
        if not historical:
            cache_key = _alerts_cache_key(end_int, min_volume)
            with ALERTS_CACHE_LOCK:
                cached = ALERTS_CACHE.get(cache_key)
                if cached:
                    now = time.time()
                    if (now - cached["timestamp"]) < ALERTS_CACHE_TTL_SECONDS:
                        return cached["payload"]
        core_symbols = _get_core_symbols()
        core_changes = _fetch_symbol_changes(conn, core_symbols, start_int, end_int)

        core_target = min(core_target, limit)
        remaining = limit - core_target
        top_target = min(top_target, remaining)
        remaining -= top_target
        bottom_target = min(bottom_target, remaining)

        movers_limit = max(limit, core_target + top_target + bottom_target, 25)
        top_movers = fetch_weekly_movers(conn, start_int, end_int, "DESC", movers_limit, min_volume)
        bottom_movers = fetch_weekly_movers(conn, start_int, end_int, "ASC", movers_limit, min_volume)

        used: set[str] = set()
        alerts: list[dict] = []

        core_pick = _pick_unique(core_changes, core_target, used)
        for item in core_pick:
            alerts.append({**item, "source": "core"})

        top_pick = _pick_unique(top_movers, top_target, used)
        for item in top_pick:
            alerts.append({**item, "source": "top"})

        bottom_pick = _pick_unique(bottom_movers, bottom_target, used)
        for item in bottom_pick:
            alerts.append({**item, "source": "bottom"})

        if len(alerts) < limit:
            _extend_alerts(alerts, used, core_changes, "core", limit)
            _extend_alerts(alerts, used, top_movers, "top", limit)
            _extend_alerts(alerts, used, bottom_movers, "bottom", limit)

        featured_used: set[str] = set()
        featured: list[dict] = []
        for item in _pick_unique(core_changes, 3, featured_used):
            featured.append({**item, "source": "core"})
        for item in _pick_unique(top_movers, 3, featured_used):
            featured.append({**item, "source": "top"})
        for item in _pick_unique(bottom_movers, 3, featured_used):
            featured.append({**item, "source": "bottom"})

        if len(featured) < 9:
            _extend_alerts(featured, featured_used, core_changes, "core", 9)
            _extend_alerts(featured, featured_used, top_movers, "top", 9)
            _extend_alerts(featured, featured_used, bottom_movers, "bottom", 9)

        featured_symbols = [item["symbol"] for item in featured]
        series_map = fetch_weekly_series(conn, featured_symbols, start_int, end_int)
        for item in featured:
            symbol = item["symbol"]
            item["series"] = series_map.get(symbol, [])

        benchmark_symbols = _get_benchmark_symbols()
        benchmark_changes = _fetch_symbol_changes(conn, benchmark_symbols, start_int, end_int)

        payload = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "alerts": alerts[:limit],
            "featured": featured,
            "benchmarks": benchmark_changes,
        }

        if not historical:
            cache_key = _alerts_cache_key(end_int, min_volume)
            with ALERTS_CACHE_LOCK:
                ALERTS_CACHE[cache_key] = {
                    "timestamp": time.time(),
                    "payload": payload,
                }

        return payload
    finally:
        conn.close()


def build_weekly_insights(force_refresh: bool = False, end_date: str | None = None) -> dict:
    historical = end_date is not None
    conn = get_connection(readonly=True)
    try:
        start_int, end_int, start_date, end_date = _get_weekly_range(conn, end_date)
        events, events_note, sources = _load_events(start_date, end_date)
        events_sig = json.dumps(events, sort_keys=True)

        # Skip cache and cooldown logic for historical (eval) requests
        if not historical:
            now = time.time()
            with INSIGHTS_CACHE_LOCK:
                cached = INSIGHTS_CACHE
                cooldown_until = float(cached.get("cooldown_until") or 0.0)
                if not force_refresh:
                    if (
                        cached["end_int"] == end_int
                        and cached["events_sig"] == events_sig
                        and (now - cached["timestamp"]) < INSIGHTS_CACHE_TTL_SECONDS
                    ):
                        payload = cached["payload"]
                        if isinstance(payload, dict):
                            note = payload.get("note")
                            if note:
                                if now < cooldown_until:
                                    return payload
                            else:
                                return payload

                if now < cooldown_until:
                    payload = cached.get("payload")
                    if isinstance(payload, dict):
                        return payload

                last_attempt = float(cached.get("last_openai_attempt") or 0.0)
                if (now - last_attempt) < OPENAI_MIN_INTERVAL_SECONDS:
                    remaining = int(OPENAI_MIN_INTERVAL_SECONDS - (now - last_attempt))
                    return {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                        "market_insights": [],
                        "event_impacts": [],
                        "events": events,
                        "note": f"OpenAI cooldown active. Try again in {remaining}s.",
                        "events_note": events_note,
                        "model": None,
                        "sources": sources,
                    }

        core_symbols = _get_core_symbols()
        benchmark_symbols = _get_benchmark_symbols()
        core_changes = _fetch_symbol_changes(conn, core_symbols, start_int, end_int)
        benchmark_changes = _fetch_symbol_changes(
            conn, benchmark_symbols, start_int, end_int
        )
        top_movers = fetch_weekly_movers(conn, start_int, end_int, "DESC", 5)
        bottom_movers = fetch_weekly_movers(conn, start_int, end_int, "ASC", 5)

        prompt = json.dumps(
            {
                "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "benchmarks": benchmark_changes,
                "core_changes": core_changes,
                "top_movers": top_movers,
                "bottom_movers": bottom_movers,
                "events": events,
                "instructions": {
                    # PROMPTS HEEEERRRRRREEEEEEEEEEEEEEEE
                    "market_insights": (
                        "3-5 bullets about weekly market conditions. Each bullet must mention "
                        "at least one specific symbol from core_changes or the top/bottom movers. "
                        "Prefer referencing the top three gainers/losers when possible."
                    ),
                    "event_impacts": (
                        "2-5 bullets connecting listed events to specific stock symbols and an "
                        "expected direction (potential gain or loss). Each bullet should reference "
                        "the event and a symbol (prefer core or top/bottom movers). "
                        "Use cautious language (e.g., could, may) and avoid financial advice. "
                        "If no events, return []."
                    ),
                },
            },
            ensure_ascii=True,
        )

        if not historical:
            with INSIGHTS_CACHE_LOCK:
                INSIGHTS_CACHE["last_openai_attempt"] = time.time()

        market_insights, event_impacts, note, model, rate_limited, retry_after = _call_openai(prompt)
        payload = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "market_insights": market_insights,
            "event_impacts": event_impacts,
            "events": events,
            "note": note,
            "events_note": events_note,
            "model": model,
            "sources": sources,
        }

        if not historical:
            with INSIGHTS_CACHE_LOCK:
                if note:
                    cooldown_seconds = (
                        OPENAI_RATE_LIMIT_COOLDOWN_SECONDS
                        if rate_limited
                        else OPENAI_ERROR_COOLDOWN_SECONDS
                    )
                    if retry_after:
                        cooldown_seconds = max(cooldown_seconds, retry_after)
                    INSIGHTS_CACHE["cooldown_until"] = time.time() + cooldown_seconds
                INSIGHTS_CACHE.update(
                    {
                        "timestamp": time.time(),
                        "end_int": end_int,
                        "events_sig": events_sig,
                        "payload": payload,
                    }
                )

        return payload
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Feature 1 — Weekly LLM Stock Recommendation
# ---------------------------------------------------------------------------

RISK_STRATEGIES = {
    "low": (
        "Prioritize stability — pick from large-cap, low-volatility stocks with "
        "strong fundamentals. Avoid stocks with recent extreme moves. Acceptable "
        "to pick a modest outperformer."
    ),
    "mid": (
        "Balance risk and reward — pick a stock with solid momentum and reasonable "
        "volatility. May include mid-cap names with positive catalysts."
    ),
    "high": (
        "Maximize upside potential — pick a stock with strong recent momentum even "
        "if volatile. Small/mid-cap names with breakout patterns are acceptable."
    ),
}

RECOMMENDATION_CACHE_LOCK = threading.Lock()
# Keyed by "end_int:risk_strategy"
RECOMMENDATION_CACHE: dict[str, dict] = {}


def _recommendation_cache_key(end_int: int, risk_strategy: str) -> str:
    return f"{end_int}:{risk_strategy}"


def build_weekly_recommendation(
    risk_strategy: str = "mid",
    force_refresh: bool = False,
    end_date: str | None = None,
) -> dict:
    if risk_strategy not in RISK_STRATEGIES:
        raise HTTPException(status_code=400, detail="risk must be low, mid, or high")

    historical = end_date is not None
    conn = get_connection(readonly=True)
    try:
        start_int, end_int, start_date_val, end_date_val = _get_weekly_range(conn, end_date)

        # --- cache check ---
        if not historical and not force_refresh:
            cache_key = _recommendation_cache_key(end_int, risk_strategy)
            with RECOMMENDATION_CACHE_LOCK:
                cached = RECOMMENDATION_CACHE.get(cache_key)
                if cached:
                    now = time.time()
                    if (now - cached.get("timestamp", 0)) < INSIGHTS_CACHE_TTL_SECONDS:
                        return cached["payload"]

        # --- gather data ---
        core_symbols = _get_core_symbols()
        benchmark_symbols = _get_benchmark_symbols()
        core_changes = _fetch_symbol_changes(conn, core_symbols, start_int, end_int)
        benchmark_changes = _fetch_symbol_changes(conn, benchmark_symbols, start_int, end_int)
        top_movers = fetch_weekly_movers(conn, start_int, end_int, "DESC", 10)
        bottom_movers = fetch_weekly_movers(conn, start_int, end_int, "ASC", 5)
        events, events_note, sources = _load_events(start_date_val, end_date_val)

        # Gather feature snapshots for candidate stocks (top movers + core)
        candidate_symbols = list({
            _normalize_symbol(m["symbol"])
            for m in (top_movers + core_changes)
            if m.get("symbol")
        })
        feature_summaries = _get_feature_summaries(candidate_symbols)

        prompt = json.dumps(
            {
                "range": {
                    "start": start_date_val.isoformat(),
                    "end": end_date_val.isoformat(),
                },
                "benchmarks": benchmark_changes,
                "core_watchlist": core_changes,
                "top_movers": top_movers,
                "bottom_movers": bottom_movers,
                "events": events,
                "feature_snapshots": feature_summaries,
                "risk_preference": {
                    "level": risk_strategy,
                    "description": RISK_STRATEGIES[risk_strategy],
                },
                "instructions": (
                    "You are a quantitative stock analyst. Select ONE stock from the "
                    "candidates (core_watchlist + top_movers) that is most likely to "
                    f"outperform SPY next week given the '{risk_strategy}' risk preference. "
                    "Return ONLY valid JSON with these fields: "
                    '"symbol" (ticker), '
                    '"action" ("BUY"), '
                    '"reasoning" (2-3 sentences), '
                    '"predicted_move" (e.g. "+2-4%"), '
                    '"confidence" ("low", "medium", or "high"), '
                    '"risk_strategy" (echo back the preference used).'
                ),
            },
            ensure_ascii=True,
        )

        market_insights, event_impacts, note, model, rate_limited, retry_after = (
            _call_openai(prompt)
        )

        # Parse the structured recommendation from the first insight
        recommendation = {}
        if market_insights:
            raw_text = market_insights[0] if len(market_insights) == 1 else " ".join(market_insights)
            recommendation = _parse_json_from_text(raw_text)

        payload = {
            "start": start_date_val.isoformat(),
            "end": end_date_val.isoformat(),
            "symbol": recommendation.get("symbol"),
            "action": recommendation.get("action", "BUY"),
            "reasoning": recommendation.get("reasoning"),
            "predicted_move": recommendation.get("predicted_move"),
            "confidence": recommendation.get("confidence"),
            "risk_strategy": risk_strategy,
            "model": model,
            "note": note,
            "events_note": events_note,
            "sources": sources,
        }

        # --- cache store ---
        if not historical:
            cache_key = _recommendation_cache_key(end_int, risk_strategy)
            with RECOMMENDATION_CACHE_LOCK:
                RECOMMENDATION_CACHE[cache_key] = {
                    "timestamp": time.time(),
                    "payload": payload,
                }

        return payload
    finally:
        conn.close()


def _get_feature_summaries(symbols: list[str]) -> list[dict]:
    """Build lightweight feature summaries for candidate stocks.

    Calls build_full_features for each symbol and extracts key metrics.
    Falls back gracefully if features cannot be built.
    """
    summaries: list[dict] = []
    try:
        from xg_boost_investor.Features import build_full_features
    except ImportError:
        return []

    today = _dt.date.today()
    for symbol in symbols[:15]:  # cap to avoid excessive API calls
        try:
            features_df, _ = build_full_features([symbol], today=True)
            if features_df.empty:
                continue
            row = features_df.iloc[-1]
            key_features = {}
            for col in [
                "ret_1d", "ret_5d", "ret_20d", "momentum_12_1",
                "realized_vol_20d", "volume_zscore_20d", "beta_spy_60d",
                "alpha_spy_60d", "stock_spy_diff_20d",
            ]:
                if col in row.index:
                    val = row[col]
                    if val is not None and str(val) != "nan":
                        key_features[col] = round(float(val), 4)
            if key_features:
                summaries.append({"symbol": symbol, "features": key_features})
        except Exception as exc:
            LOGGER.debug("Feature build failed for %s: %s", symbol, exc)
            continue
    return summaries


# ---------------------------------------------------------------------------
# Feature 2 — BUY/SELL Ticker Signal
# ---------------------------------------------------------------------------

SIGNAL_CACHE_LOCK = threading.Lock()
SIGNAL_CACHE: dict[str, dict] = {}  # keyed by symbol


def build_ticker_signal(symbol: str) -> dict:
    symbol = symbol.strip().upper().replace(".US", "")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    # --- cache check ---
    now = time.time()
    with SIGNAL_CACHE_LOCK:
        cached = SIGNAL_CACHE.get(symbol)
        if cached and (now - cached.get("timestamp", 0)) < INSIGHTS_CACHE_TTL_SECONDS:
            return cached["payload"]

    # --- gather all available data ---
    features_df = None

    # 1. Current feature conditions
    feature_snapshot = {}
    try:
        from xg_boost_investor.Features import build_full_features
        today = _dt.date.today()
        features_df, _ = build_full_features([symbol], today=True)
        if not features_df.empty:
            row = features_df.iloc[-1]
            feature_snapshot = {
                k: round(float(v), 4)
                for k, v in row.to_dict().items()
                if v is not None and str(v) != "nan"
            }
    except Exception as exc:
        LOGGER.warning("Feature build failed for %s: %s", symbol, exc)

    # 2. XGBoost model prediction
    xgboost_prediction = None
    try:
        import pandas as pd
        from xg_boost_investor import XGBoostInvestor as XGI
        xgboost = XGI.XGBoostInvestor()
        xgboost.load("xg_boost_investor/model_save/model/xgboost_investor")
        if features_df is not None and not features_df.empty:
            features_df_copy = pd.DataFrame(features_df).reset_index(drop=True)
            X_test, _, _, _ = xgboost.prepare_predictions(
                features_df_copy, pd.DataFrame([{"ret_1d": 0}])
            )
            pred = xgboost.predict(X_test)
            xgboost_prediction = round(float(pred[0]), 4)
    except Exception as exc:
        LOGGER.warning("XGBoost prediction failed for %s: %s", symbol, exc)

    # 3. Forecast data
    forecast_summary = {}
    try:
        from forecasting import get_forecast
        forecast_result = get_forecast(f"{symbol}.US", "daily", 7)
        if isinstance(forecast_result, dict) and "results" in forecast_result:
            for entry in forecast_result["results"]:
                name = entry.get("name", "")
                values = entry.get("forecast", [])
                if values:
                    forecast_summary[name] = round(float(values[-1]["open"]), 2)
    except Exception as exc:
        LOGGER.warning("Forecast failed for %s: %s", symbol, exc)

    # 4. Pattern match data
    pattern_summary = {}
    try:
        from pattern_recognition import get_dtw_patterns
        pattern_result = get_dtw_patterns(f"{symbol}.US", "daily", 7, 90)
        if isinstance(pattern_result, dict) and "results" in pattern_result:
            patterns = pattern_result["results"]
            if patterns:
                avg_similarity = sum(
                    p.get("similarity_score", 0) for p in patterns
                ) / len(patterns)
                pattern_summary = {
                    "num_matches": len(patterns),
                    "avg_similarity_score": round(avg_similarity, 2),
                }
    except Exception as exc:
        LOGGER.warning("Pattern matching failed for %s: %s", symbol, exc)

    # 5. News context — general market events + symbol-specific news
    today = _dt.date.today()
    week_ago = today - timedelta(days=7)
    market_news: list[dict] = []
    symbol_news: list[dict] = []
    try:
        market_news, _, _ = _load_events(week_ago, today)
    except Exception as exc:
        LOGGER.warning("Market news load failed: %s", exc)

    if os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_KEY"):
        try:
            articles, fetch_error = _fetch_newsdata(f"{symbol} stock", 5)
            if fetch_error:
                LOGGER.warning("Symbol news fetch failed for %s: %s", symbol, fetch_error)
            for article in articles:
                symbol_news.append({
                    "title": article["title"],
                    "date": article.get("date"),
                    "source": article.get("source"),
                })
        except Exception as exc:
            LOGGER.warning("Symbol news fetch failed for %s: %s", symbol, exc)

    # --- build GPT prompt ---
    prompt = json.dumps(
        {
            "symbol": symbol,
            "feature_conditions": feature_snapshot,
            "xgboost_prediction": xgboost_prediction,
            "forecast_endpoints": forecast_summary,
            "pattern_analysis": pattern_summary,
            "market_news": [{"title": e["title"]} for e in market_news[:8]],
            "symbol_news": symbol_news,
            "instructions": (
                "You are an investment research assistant. Based on the curated data, "
                "forecasts, and news provided, decide whether this stock is a BUY or SELL "
                "for investors considering a variety of investment horizons (short, medium, "
                "and long term). "
                "Begin your reasoning with 'Our insights suggest...' and write 2-3 sentences "
                "in plain, conversational language. Focus on: "
                "1) The company's reputation and track record as an investment. "
                "2) How recent news and market events may impact this stock. "
                "3) Whether the predicted returns support a bullish or bearish outlook. "
                "Do NOT use technical jargon like forecast endpoints, similarity scores, "
                "model clustering, pattern matches, or feature conditions. "
                "Do not mention missing data or incomplete information. Be decisive. "
                "Return ONLY valid JSON with these fields: "
                '"signal" ("BUY" or "SELL"), '
                '"reasoning" (2-3 sentences starting with "Our insights suggest..."), '
                '"confidence" ("low", "medium", or "high"), '
                '"key_factors" (list of 3-5 factors as short, non-technical strings).'
            ),
        },
        ensure_ascii=True,
    )

    market_insights, _, note, model, rate_limited, retry_after = _call_openai(prompt)

    signal_data = {}
    if market_insights:
        raw_text = market_insights[0] if len(market_insights) == 1 else " ".join(market_insights)
        signal_data = _parse_json_from_text(raw_text)

    payload = {
        "symbol": symbol,
        "signal": signal_data.get("signal", "SELL"),
        "reasoning": signal_data.get("reasoning"),
        "confidence": signal_data.get("confidence"),
        "key_factors": signal_data.get("key_factors", []),
        "as_of": _dt.date.today().isoformat(),
        "model": model,
        "note": note,
    }

    # --- cache store ---
    with SIGNAL_CACHE_LOCK:
        SIGNAL_CACHE[symbol] = {
            "timestamp": time.time(),
            "payload": payload,
        }

    return payload
