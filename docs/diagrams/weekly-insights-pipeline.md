# Weekly Insights Pipeline

End-to-end flow for generating weekly market insights, alerts, and purchase recommendations. The pipeline gathers movers data from SQLite, fetches news headlines from NewsAPI, builds structured prompts, calls OpenAI with retry/rate-limit logic, and caches results behind thread locks with a 24-hour TTL.

```mermaid
flowchart TD
    A["/api/weekly-insights\n/api/weekly-alerts\n/api/weekly-recommendation"] --> B{Cache Hit?\nTTL 86400s}
    B -->|Yes| C[Return Cached Payload]
    B -->|No| D{Cooldown Active?\nMin 60s between calls}
    D -->|Yes| E[Return Stale Cache\n+ Cooldown Note]
    D -->|No| F[Get Weekly Date Range\nMAX date from bars table]

    F --> G[Fetch Core Symbol Changes\nNVDA, AAPL, MSFT, AMZN,\nGOOGL, META, TSLA, etc.]
    F --> H[Fetch Benchmark Changes\nSPY, QQQ, DIA, IWM]
    F --> I[Fetch Top/Bottom Movers\nSQL pct_change with\nvolume filter]
    F --> J[Load Events\nNewsAPI / ENV / URL]

    G --> K[Build JSON Prompt]
    H --> K
    I --> K
    J --> K

    I --> L[Build Alerts\nCore + Top + Bottom\nDeduplicated, max 20]
    L --> M[Fetch Featured Series\nSpark-line data for top 9]
    M --> N[Cache Alerts Payload\nALERTS_CACHE_LOCK]

    K --> O[Record last_openai_attempt\nINSIGHTS_CACHE_LOCK]
    O --> P[Call OpenAI API\ngpt-4o-mini, temp 0.4]
    P --> Q{Rate Limited?\nHTTP 429}
    Q -->|Yes| R[Exponential Backoff\nRetry up to 2x]
    R --> P
    Q -->|No| S[Parse JSON Response\nmarket_insights + event_impacts]

    S --> T{Recommendation\nEndpoint?}
    T -->|Yes| U[Parse Single Stock Pick\nsymbol, action, reasoning,\nconfidence, predicted_move]
    T -->|No| V[Split Markdown Sections\nMarket vs Event bullets]

    U --> W[Cache Result\nRECOMMENDATION_CACHE_LOCK\nKeyed by end_int:risk]
    V --> X[Cache Result\nINSIGHTS_CACHE_LOCK\nKeyed by end_int + events_sig]

    W --> Y[Return JSON Payload]
    X --> Y

    classDef frontend fill:#4285F4,stroke:#333,color:#fff
    classDef backend fill:#34A853,stroke:#333,color:#fff
    classDef database fill:#FA7B17,stroke:#333,color:#fff
    classDef external fill:#EA4335,stroke:#333,color:#fff

    class A frontend
    class B,D,T backend
    class C,E,N,W,X,Y backend
    class F,G,H,I,L,M database
    class J,P,Q,R external
    class K,O,S,U,V backend
```

## Key Components

- **Three Endpoints**: `/api/weekly-insights` (market bullets), `/api/weekly-alerts` (price alerts with spark-lines), `/api/weekly-recommendation` (single stock pick with risk preference: low/mid/high)
- **Movers Calculation** (`WeeklyMovers.py`): SQL query computes `pct_change` between start/end trading day close prices, with optional average volume filter (`DEFAULT_MIN_VOLUME = 2,000,000`), cached per `(direction, min_volume)` key
- **Events Loading** (`_load_events`): Tries three sources in order: `MARKET_EVENTS_JSON` env var, NewsAPI (`/v2/everything` with market query, up to 12 articles), or `MARKET_EVENTS_URL` fallback
- **OpenAI Call** (`_call_openai`): Uses `gpt-4o-mini` by default, temperature 0.4, max 500 tokens, system prompt as "concise market analyst", retries up to 2x with exponential backoff (1-8s), handles 429 with Retry-After header
- **Caching/Locking**: Three independent caches with `threading.Lock` -- `INSIGHTS_CACHE` (single dict, keyed by `end_int` + events signature), `ALERTS_CACHE` (keyed by `end_int:min_volume`), `RECOMMENDATION_CACHE` (keyed by `end_int:risk_strategy`), all with 24-hour TTL
- **Cooldown Mechanism**: 60s minimum between OpenAI calls (`OPENAI_MIN_INTERVAL_SECONDS`), 300s cooldown after rate-limit, 60s cooldown after other errors
- **Recommendation Extras**: Gathers XGBoost feature snapshots (`_get_feature_summaries`) for candidate stocks, includes risk preference description in prompt, returns structured JSON with symbol/action/reasoning/confidence

---
*Generated on 2026-03-26*
