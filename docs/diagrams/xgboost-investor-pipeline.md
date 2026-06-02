# XGBoost Investor Pipeline

End-to-end pipeline for the XGBoost-based stock return prediction system. Covers feature engineering from Yahoo Finance, FRED, and VIX data, model training with BaggingRegressor + XGBRegressor, isotonic calibration, and integration with the FastAPI endpoints for real-time ticker signals and conditions.

```mermaid
flowchart TD
    A[S&P 500 Membership\nsymbol_collector.py\nWikipedia scrape + change log] --> B[Download Price Data\nyfinance: tickers, SPY, VIX, RSP]

    B --> C[Technical Features\nret 1/5/10/20/60/120/252d\nmomentum_12_1\nMA distance 20/60/200d]
    B --> D[Volatility Features\nrealized_vol 20/60/120d\ndownside_vol_60d\nATR 14d, HL range 10d]
    B --> E[Volume Features\nvolume_zscore_20d\nvolume_trend_slope_60d\ndollar_vol, spike_ratio]
    B --> F[Relative Strength\nbeta_spy_60d\nput_call_ratio proxy]

    C --> G[Merge All Features\nper-ticker DataFrame]
    D --> G
    E --> G
    F --> G

    G --> H[Market Breadth\npct_above 50/200d MA\nadv/decline ratio\n52w high/low, RSP vs SPY]
    G --> I[VIX Indicators\nVIX_5d/20d change\nterm structure\nVIX/realized vol ratio]
    G --> J[FRED Macro Data\n10Y/2Y yields, CPI\nUnemployment, FedFunds\nIndustrial Prod, Money Mkt]
    G --> K[Time Embeddings\nsin/cos weekday\nsin/cos month\nsin/cos year]

    H --> L[Full Feature Matrix\n~45 features per ticker-day]
    I --> L
    J --> L
    K --> L

    L --> M[Quarterly Data Chunks\n8 quarters look-back\nretrain_model]
    M --> N[prepare_training\nRobustScaler fit_transform\nDrop constant cols + NaN rows]
    N --> O[BaggingRegressor\n100 estimators, 80% samples\nXGBRegressor base\nlr=0.05, depth=6]
    O --> P[Isotonic Calibration\nLast 20% of training data]
    P --> Q[Save Model\n5 pickle files:\nmodel, x_scaler, y_scaler\nconstant_cols, calibrator]

    L --> R[prepare_predictions\nRobustScaler transform\nTarget: next-day return]
    Q --> R
    R --> S[Predict\nBagging predict\nIsotonic calibrate\nInverse scale]

    S --> T["/api/getCurrentTickerConditions"\nFeatures + prediction\nfor single ticker]
    S --> U["/api/ticker-signal"\nXGBoost pred + forecasts\n+ patterns + news\nto OpenAI for BUY/SELL]
    S --> V[Simulator.py\nBacktest yearly\nTop-20 daily picks\nPortfolio tracking]
    V --> W[Metrics.py\nSharpe, Sortino, Calmar\nDrawdown, Win Rate\nVisualizations + Excel]

    classDef frontend fill:#4285F4,stroke:#333,color:#fff
    classDef backend fill:#34A853,stroke:#333,color:#fff
    classDef database fill:#FA7B17,stroke:#333,color:#fff
    classDef external fill:#EA4335,stroke:#333,color:#fff

    class T,U frontend
    class C,D,E,F,G,H,I,K,L,M,N,O,P,Q,R,S,V,W backend
    class A,B,J external
```

## Key Components

- **Symbol Collection** (`symbol_collector.py`): Reconstructs historical S&P 500 membership at any date by scraping Wikipedia's current list and unwinding the change log backward
- **Feature Engineering** (`Features.py`): Builds ~45 features per ticker-day across 6 categories -- momentum/returns (7 windows), volatility (6 indicators), volume (4 metrics), relative strength (beta, put/call), market breadth (5 cross-sectional), VIX (4 derivatives), FRED macroeconomic (7 series normalized 0-1), and cyclical time embeddings (6 sin/cos)
- **FRED Integration**: Fetches 7 economic indicators via FRED API (10Y/2Y Treasury yields, CPI, unemployment, Fed Funds rate, industrial production, retail money market funds), caches to CSV, forward-fills missing dates
- **Model Architecture** (`XGBoostInvestor.py`): `BaggingRegressor` wrapping 100 `XGBRegressor` estimators (learning_rate=0.05, max_depth=6, subsample=0.8), with `RobustScaler` for features and targets, plus `IsotonicRegression` calibration on the last 20% of training data
- **Training Pipeline**: Collects 8 quarterly chunks of historical data, each with its own S&P 500 membership; prepares data by removing constant columns and non-finite rows; persists 5 pickle files (model, x_scaler, y_scaler, constant_cols, calibrator)
- **Prediction Target**: Next-day forward return (`ret_1d` shifted by -1), predicting the percentage return one trading day ahead
- **API Integration**: Two endpoints consume predictions -- `/api/getCurrentTickerConditions` returns raw features + XGBoost prediction, `/api/ticker-signal` feeds the prediction along with forecasts, pattern matches, and news into OpenAI for a BUY/SELL signal
- **Backtesting** (`Simulator.py`): Runs year-by-year simulation selecting top-20 predicted stocks daily, tracks portfolio value; `Metrics.py` computes Sharpe, Sortino, Calmar ratios, drawdown, win rate, and exports to Excel + PNG charts

---
*Generated on 2026-03-26*
