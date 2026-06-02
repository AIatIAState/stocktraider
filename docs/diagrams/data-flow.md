# Data Flow

Overview of how data flows through the AI Stock Trading Platform, covering user-initiated requests (React -> Nginx -> FastAPI -> SQLite/External APIs) and the background scheduled refresh pipeline.

```mermaid
sequenceDiagram
    participant React as React Frontend
    participant Nginx as Nginx (:8080)
    participant API as FastAPI (:5000)
    participant Cache as In-Memory Cache
    participant DB as SQLite (stocks.db)
    participant YF as Yahoo Finance
    participant News as NewsAPI
    participant OpenAI as OpenAI API
    participant XGB as XGBoost Model
    participant Sched as APScheduler

    Note over React,OpenAI: === Price Data & Bars Retrieval ===
    React->>Nginx: GET /api/bars?symbol=AAPL
    Nginx->>API: proxy /api/*
    API->>Cache: check BARS_CACHE (24h TTL)
    alt cache miss
        API->>DB: SELECT FROM bars WHERE symbol, timeframe, date range
        DB-->>API: OHLCV rows
        API->>Cache: store result
    end
    API-->>React: {results: Bar[]}

    Note over React,OpenAI: === Weekly Insights (NewsAPI + OpenAI) ===
    React->>Nginx: GET /api/weekly-insights
    Nginx->>API: proxy
    API->>Cache: check INSIGHTS_CACHE (24h TTL)
    alt cache miss
        API->>DB: weekly range + core/benchmark symbol changes + top/bottom movers
        API->>News: GET /v2/everything (market news, last 7 days)
        News-->>API: articles[]
        API->>OpenAI: POST /v1/chat/completions (market data + news prompt)
        OpenAI-->>API: {market_insights[], event_impacts[]}
        API->>Cache: store payload
    end
    API-->>React: insights, events, event_impacts

    Note over React,OpenAI: === Weekly Recommendation (LLM Pick) ===
    React->>Nginx: GET /api/weekly-recommendation?risk=mid
    Nginx->>API: proxy
    API->>DB: movers + core changes + benchmarks
    API->>XGB: build_full_features() for candidates
    API->>News: fetch market events
    API->>OpenAI: prompt with features + risk preference
    OpenAI-->>API: {symbol, action, reasoning, confidence}
    API-->>React: recommendation payload

    Note over React,OpenAI: === Ticker Signal (BUY/SELL) ===
    React->>Nginx: GET /api/ticker-signal?symbol=NVDA
    Nginx->>API: proxy
    API->>XGB: build_full_features() + predict()
    API->>DB: get_forecast() via Darts time-series
    API->>DB: get_dtw_patterns() pattern recognition
    API->>News: symbol-specific + market news
    API->>OpenAI: prompt with features, forecast, patterns, news
    OpenAI-->>API: {signal: BUY/SELL, reasoning, key_factors}
    API-->>React: ticker signal response

    Note over React,OpenAI: === Forecasts & Patterns ===
    React->>Nginx: GET /api/getForecasts?symbol=AAPL
    Nginx->>API: proxy
    API->>DB: historical bars for Darts forecasting
    API-->>React: {results: forecast series[]}

    React->>Nginx: GET /api/getPatterns?symbol=AAPL
    Nginx->>API: proxy
    API->>DB: historical bars for DTW pattern matching
    API-->>React: {results: similar patterns[]}

    Note over Sched,DB: === Background Scheduled Refresh (Sundays 03:00) ===
    Sched->>API: run_scheduled_update() via CronTrigger
    API->>DB: load all symbols from symbols table
    API->>YF: yf.download() in chunks of 50
    YF-->>API: OHLCV DataFrame (last 7 days)
    API->>DB: INSERT INTO bars (deduplicated upsert)
```

## Key Flows

- **Price Data (Bars)**: Frontend calls `/api/bars`, FastAPI checks a 24-hour in-memory cache keyed by `symbol:timeframe:start:end:order:limit`, then queries the `bars` table in SQLite on cache miss. Used by `StockHistoryService` and `fetchBars()`.

- **Weekly Insights**: `/api/weekly-insights` gathers core symbol changes (NVDA, AAPL, MSFT, etc.), benchmark changes (SPY, QQQ, DIA, IWM), top/bottom weekly movers from SQLite, fetches news articles from NewsAPI `/v2/everything`, then sends all data as a structured JSON prompt to OpenAI `gpt-4o-mini` for market insight bullets and event impact analysis. Results are cached for 24 hours with rate-limit cooldown logic.

- **Weekly Recommendation**: `/api/weekly-recommendation` extends the insights pipeline by also calling `build_full_features()` from the XGBoost module to gather quantitative feature snapshots (momentum, volatility, beta, alpha) for candidate stocks, then asks OpenAI to pick ONE stock given a risk preference (low/mid/high).

- **Ticker Signal (BUY/SELL)**: `/api/ticker-signal` is the most data-intensive endpoint -- it aggregates XGBoost features + predictions, Darts time-series forecasts, DTW pattern matches, market news, and symbol-specific news from NewsAPI, then sends everything to OpenAI for a BUY/SELL decision with reasoning and key factors.

- **Forecasts**: `/api/getForecasts` calls `forecasting.get_forecast()` which uses the Darts library to produce time-series forecasts from historical bar data in SQLite.

- **Pattern Matching**: `/api/getPatterns` calls `pattern_recognition.get_dtw_patterns()` which uses Dynamic Time Warping on historical bars to find similar price patterns.

- **Ticker Conditions**: `/api/getCurrentTickerConditions` builds full XGBoost features for a symbol and runs the trained model to produce a prediction, cached for 24 hours.

- **Background Refresh**: APScheduler runs `run_scheduled_update()` every Sunday at 03:00 (configurable timezone). It loads all symbols from the `symbols` table, downloads the last 7 days of data from Yahoo Finance via `yf.download()` in chunks of 50 tickers, and inserts new rows into `bars` with deduplication. Scheduler state is persisted in the `app_settings` table.

---
*Generated on 2026-03-26*
