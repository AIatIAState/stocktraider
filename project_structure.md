# Project: AI Stock Trading Platform

AI-powered stock and crypto trading platform that uses LLMs for trading suggestions, market summaries, and weekly insights. Built as a COMS 599 creative component.

## Architecture

- **Frontend**: React 19 + TypeScript, Vite, MUI v7, served by Nginx on port 8080
- **Backend**: FastAPI (Python), Uvicorn, runs on port 5000 internally
- **Database**: SQLite with WAL mode at `/data/stocks.db` (~17GB), accessed via `fastapi/connector.py` (`get_connection(readonly=bool)`)
- **Deployment**: Docker Compose with two services (`web`, `fastapi`), Nginx reverse proxies `/api/*` to FastAPI
- **CI/CD**: GitLab CI at `.gitlab-ci.yml`

## Backend Modules (`fastapi/`)

| Module | Role |
|---|---|
| `main.py` | FastAPI app, all REST endpoints |
| `weekly_dashboard.py` | OpenAI-powered weekly insights, NewsAPI integration, alerts, recommendations |
| `forecasting.py` | Darts time series forecasting |
| `pattern_recognition.py` | DTW pattern matching |
| `fetch_prices.py` | Yahoo Finance price data updates |
| `WeeklyMovers.py` | Weekly market movers calculation |
| `scheduled_updates.py` | APScheduler background tasks |
| `admin_jobs.py` | Admin job management |
| `connector.py` | SQLite connection helper |
| `symbol_collector.py` | Stock symbol management |
| `xg_boost_investor/` | XGBoost ML model — `XGBoostInvestor.py`, `Features.py`, `Metrics.py`, `Simulator.py`, `PortfolioManager.py` |

## API Endpoints (`fastapi/main.py`)

- `/api/bars` — OHLCV price data
- `/api/symbols` — Available stock symbols
- `/api/weekly-movers` — Top weekly movers
- `/api/weekly-insights` — LLM-generated market insights
- `/api/weekly-alerts` — Price alerts
- `/api/weekly-recommendation` — LLM purchase recommendations
- `/api/ticker-signal` — Individual ticker analysis
- `/api/getPatterns` — DTW pattern recognition
- `/api/getForecasts` — Time series forecasts
- `/api/getCurrentTickerConditions` — Current technical conditions
- `/api/admin/*` — Admin endpoints (scheduler, jobs, DB info, updates)
- `/api/health`, `/api/ready` — Health checks

## Frontend (`stockai-web/`)

**Routes** (`App.tsx`): `/` (Home), `/data` (DataSearch), `/dashboard`, `/admin`

**Key directories**:
- `src/components/charts/` — StockCharts, ForecastCharts, StockConditions, SimilarCharts, etc.
- `src/services/` — `api.ts` (base client), `StockForecastService.ts`, `StockPatternService.ts`, `StockMarketConditionsService.ts`, `StockHistoryService.tsx`
- `src/pages/` — HomePage, Dashboard, DataSearchPage, AdminPage

## External Services

- **OpenAI API** — Weekly insights text generation (`weekly_dashboard.py`)
- **NewsAPI** — Market news for context
- **Yahoo Finance** (`yfinance`) — Stock price data
- **FRED API** — Economic indicators (referenced in commits)

## Conventions

- Backend caching uses thread locks + in-memory dicts with TTL (`CACHE_TTL_SECONDS = 86400`)
- DB access: `get_connection(readonly=True)` for reads, `get_connection()` for writes
- Environment variables via `.env` and `docker-compose.yml` (`OPENAI_API_KEY`, `NEWSAPI_KEY`, `DB_PATH`, etc.)
- Frontend uses MUI theming with light/dark/system modes
