# System Architecture

Overview of the AI Stock Trading Platform showing how the frontend, backend, database, and external services connect.

```mermaid
flowchart TD
    subgraph Client["Browser (Port 8080)"]
        HOME["Home Page"]
        DATA["Data Search"]
        DASH["Dashboard"]
        ADMIN["Admin Panel"]
    end

    subgraph Web["Web Container — Nginx"]
        NGINX["Nginx Reverse Proxy\n:8080"]
    end

    subgraph API["FastAPI Container — Uvicorn :5000"]
        MAIN["FastAPI App"]
        WEEKLY["Weekly Dashboard\nInsights, Alerts, Recommendations"]
        FORECAST["Forecasting Engine\nDarts Time Series"]
        PATTERN["Pattern Recognition\nDTW Matching"]
        XGBOOST["XGBoost Investor\nML Signals & Features"]
        FETCH["Price Fetcher"]
        MOVERS["Weekly Movers"]
        SCHEDULER["APScheduler\nBackground Jobs"]
    end

    subgraph DB["Storage"]
        SQLITE[("SQLite WAL\nstocks.db ~17GB")]
    end

    subgraph External["External Services"]
        OPENAI["OpenAI API\nChat Completions"]
        NEWSAPI["NewsAPI\nMarket News"]
        YAHOO["Yahoo Finance\nPrice Data"]
        FRED["FRED API\nEconomic Indicators"]
    end

    HOME & DATA & DASH & ADMIN -->|HTTP| NGINX
    NGINX -->|"/api/*"| MAIN
    NGINX -->|"Static assets"| NGINX

    MAIN --> WEEKLY
    MAIN --> FORECAST
    MAIN --> PATTERN
    MAIN --> XGBOOST
    MAIN --> FETCH
    MAIN --> MOVERS

    SCHEDULER -->|"Scheduled refresh"| FETCH

    WEEKLY -->|"Generate insights"| OPENAI
    WEEKLY -->|"Fetch headlines"| NEWSAPI
    FETCH -->|"Download OHLCV"| YAHOO
    XGBOOST -->|"Economic data"| FRED

    MAIN -->|"Read/Write"| SQLITE
    WEEKLY -->|"Read movers"| SQLITE
    FETCH -->|"Write bars"| SQLITE
    XGBOOST -->|"Read features"| SQLITE

    classDef frontend fill:#4285F4,stroke:#333,color:#fff
    classDef backend fill:#34A853,stroke:#333,color:#fff
    classDef database fill:#FA7B17,stroke:#333,color:#fff
    classDef external fill:#EA4335,stroke:#333,color:#fff
    classDef proxy fill:#9C27B0,stroke:#333,color:#fff

    class HOME,DATA,DASH,ADMIN frontend
    class MAIN,WEEKLY,FORECAST,PATTERN,XGBOOST,FETCH,MOVERS,SCHEDULER backend
    class SQLITE database
    class OPENAI,NEWSAPI,YAHOO,FRED external
    class NGINX proxy
```

## Key Components

- **Nginx Reverse Proxy**: Serves the React SPA and forwards `/api/*` requests to FastAPI
- **FastAPI App**: Central API layer with 20+ endpoints for price data, forecasts, patterns, and insights
- **Weekly Dashboard**: Generates LLM-powered market summaries, alerts, and purchase recommendations via OpenAI
- **Forecasting Engine**: Darts-based time series forecasting for stock price prediction
- **Pattern Recognition**: Dynamic Time Warping (DTW) to find similar historical chart patterns
- **XGBoost Investor**: ML model using technical indicators + FRED economic data for trade signals
- **APScheduler**: Runs background jobs (weekly Yahoo Finance refresh)
- **SQLite**: Single WAL-mode database (~17GB) storing all OHLCV price data

---
*Generated on 2026-03-26*
