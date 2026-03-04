import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import requests
from functools import lru_cache



# -------------------------
# (1) Momentum Window Features (Primary drivers)
# -------------------------

def rolling_return(df, window):
    return df.pct_change(window)

def momentum_12_1(df):
    return df.pct_change(252) - df.pct_change(21)

def moving_average_distance(df, window):
    ma = df.rolling(window).mean()
    return (df - ma) / ma



# -------------------------
# (2) Volatility Window Features
# -------------------------
def realized_volatility(df, window):
    return df.pct_change().rolling(window).std()

def downside_vol(df, window):
    returns = df.pct_change()
    negative_returns = returns.copy()
    negative_returns = returns.clip(upper=0)
    return negative_returns.rolling(window).std()

def atr(high, low, close, window=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window).mean()

def hl_range(high, low, close, window):
    """High-Low range over window, normalized by close"""
    return (high.rolling(window).max() - low.rolling(window).min()) / close

# -------------------------
# (3) Volume / Liquidity Window Features
# -------------------------
def volume_zscore(volume, window=20):
    return (volume - volume.rolling(window).mean()) / volume.rolling(window).std()


def volume_trend_slope(volume, window=60):
    """Linear regression slope of volume over window, normalized by mean volume"""

    def calculate_slope(series):
        if len(series) < 2:
            return np.nan
        x = np.arange(len(series))
        try:
            slope = np.polyfit(x, series.values, 1)[0]
            # Key fix: Normalize by mean volume
            mean_vol = np.mean(series.values)
            if mean_vol > 0:
                return slope / mean_vol  # Returns: change rate as % of avg volume
            else:
                return np.nan
        except:
            return np.nan

    return volume.rolling(window).apply(calculate_slope, raw=False)
def dollar_volume(close, volume, window=20):
    """Average dollar volume (Price * Volume) by stocks own baseline"""
    raw_dv = (close * volume).rolling(window).mean()
    dv_ma = raw_dv.rolling(60).mean()
    return raw_dv / dv_ma.replace(0, 1)

def volume_spike_ratio(volume, window=20):
    """Today's volume / x-day average volume"""
    vol_ma = volume.rolling(window).mean()
    return volume / vol_ma

# -------------------------
# (4) Relative Strength (Cross-Sectional Modeling)
# -------------------------

def stock_spy_return_diff(stock_returns, spy_returns, window=20):
    """Stock return - SPY return (relative performance)"""
    stock_returns = stock_returns.fillna(0)
    spy_returns = spy_returns.fillna(0)

    # Reindex spy_returns to match stock_returns index
    spy_returns = spy_returns.reindex(stock_returns.index, method='ffill')

    # Calculate rolling sum
    stock_ret_20d = stock_returns.rolling(window).sum()
    spy_ret_20d = spy_returns.rolling(window).sum()

    return stock_ret_20d - spy_ret_20d

def beta_to_spy(stock_returns, spy_returns, window=60):
    cov = stock_returns.rolling(window).cov(spy_returns)
    var = spy_returns.rolling(window).var()
    return cov / var

def alpha_vs_spy(stock_returns, spy_returns, window=60):
    """Jensen's alpha vs SPY (simplified)"""
    beta = beta_to_spy(stock_returns, spy_returns, window)
    excess_stock = stock_returns
    excess_spy = spy_returns
    alpha = excess_stock - (beta * excess_spy)
    return alpha.rolling(window).mean()


# -------------------------
# 2️⃣ Macro Features (FRED API)
# -------------------------
FRED_API_KEY = "0c6916b4eec52ef37d4514807e36600c"
fred_series = {
    "DGS10": "TY10Y",
    "DGS2": "TY2Y",
    "CPIAUCSL": "CPI",
    "UNRATE": "UnemploymentRate",
    "FEDFUNDS": "FedFunds",
    "INDPRO": "IndustrialProduction",
    "WRMFNS": "RetailMoneyMarketFunds",
}

@lru_cache(maxsize=32)
def fetch_fred_data(series_id, name):
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
        response = requests.get(url, timeout=10)
        r = response.json()

        if 'error_code' in r:
            print(f"FRED Error for {series_id}: {r.get('error_message', 'Unknown error')}")
            return None

        data = pd.DataFrame(r["observations"])
        data["Date"] = pd.to_datetime(data["date"], format="%Y-%m-%d")
        data[name] = pd.to_numeric(data["value"], errors='coerce')
        data.set_index("Date", inplace=True)
        data.drop(columns=["realtime_start", "realtime_end", "date", "value"], inplace=True)

    except Exception as e:
        print(f"Failed to fetch FRED data for {series_id}: {e}")
        return None

    # Pad data for missing dates
    full_date_range = pd.date_range(start=data.index.min(), end=data.index.max(),freq='D')
    data = data.reindex(full_date_range, columns=[name], method='ffill')
    data = data.fillna(method="ffill")

    return data[name]

# -------------------------
# 3️⃣ Market Breadth Indicators (computed across market)
# -------------------------

def pct_above_ma(df, ma_window):
    return (df > df.rolling(ma_window).mean()).sum(axis=1) / df.shape[1]

def advance_decline_ratio(df):
    daily_ret = df.pct_change()
    adv = (daily_ret > 0).sum(axis=1)
    dec = (daily_ret < 0).sum(axis=1)
    return adv / dec.replace(0, 1)

def new_52w_high_low(df):
    highs = df.rolling(252).max()
    lows = df.rolling(252).min()
    new_highs = (df == highs).sum(axis=1)
    new_lows = (df == lows).sum(axis=1)
    return (new_highs - new_lows) / df.shape[1]

def calculate_equal_vs_cap_weight_spread(rsp_close, spy_close, window=20):
    """Calculate spread between equal-weight and cap-weight SPY."""
    rsp_returns = rsp_close.pct_change()
    spy_returns = spy_close.pct_change()
    spread = rsp_returns - spy_returns
    rolling_spread = spread.rolling(window).mean()
    return rolling_spread

# -------------------------
# (4) VIX & Volatility Structure
# # NOTE: VIX index is a real-time benchmark measuring the market's expectation of near-term vcolatility in the S&P500 over the next 30 days
# ------------------------

def vix_realized_vol_ratio(vix, realized_vol, window=20):
    """VIX implied vol / Realized vol ratio"""
    vix_annual = vix / 100
    ratio = vix_annual / realized_vol
    return ratio.rolling(window).mean()


def calculate_vix_term_structure(vix_series, window=20):
    """
    Calculate VIX momentum as proxy for term structure.
    Positive = VIX above average (fear increasing)
    Negative = VIX below average (fear decreasing)
    """
    vix_ma = vix_series.rolling(window).mean()
    vix_term = (vix_series - vix_ma) / vix_ma * 100  # As percentage
    return vix_term


def calculate_vix_realized_vol_ratio(vix_series, realized_vol_series, window=20):
    """
    Calculate VIX / Realized Volatility ratio.
    > 1.0: VIX too high (overpriced volatility)
    < 1.0: VIX too low (underpriced volatility)
    """
    # Annualize realized volatility
    realized_vol_annual = realized_vol_series * np.sqrt(252)

    # Convert VIX from percentage to decimal
    vix_decimal = vix_series / 100

    # Calculate rolling ratio
    ratio = (vix_decimal / realized_vol_annual).rolling(window).mean()
    return ratio
# -------------------------
# (3) Options Market Proxies (Public Approximation)
# -------------------------
def put_call_ratio_proxy(ticker):
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return np.nan

        opt = t.option_chain(expirations[0])
        if opt.puts.empty or opt.calls.empty:
            return np.nan

        put_vol = opt.puts['volume'].sum()
        call_vol = opt.calls['volume'].sum()

        if call_vol == 0:
            return np.nan
        return put_vol / call_vol
    except:
        return np.nan


# -------------------------
# (6) Earnings & Analyst Proxies
# -------------------------
def earnings_days_until(ticker):
    try:
        t = yf.Ticker(ticker)
        if not hasattr(t, 'calendar') or t.calendar is None:
            return np.nan
        calendar = t.calendar
        if calendar.empty:
            return np.nan
        next_earnings = pd.to_datetime(calendar.iloc[0, 0])
        days = (next_earnings - pd.Timestamp.today()).days
        return max(0, days)
    except:
        return np.nan

def analyst_rating_mean(ticker):
    """Mean analyst rating"""
    try:
        t = yf.Ticker(ticker)
        rec = t.recommendations
        if rec is None or rec.empty:
            return np.nan

        rating_map = {'Buy': 1, 'Overweight': 1.5, 'Hold': 2.5, 'Underweight': 3.5, 'Sell': 4}
        latest_rec = rec.iloc[0]
        if 'To Grade' in latest_rec and latest_rec['To Grade'] in rating_map:
            return rating_map[latest_rec['To Grade']]
        return np.nan
    except:
        return np.nan

def analyst_rating_change(ticker, days=30):
    try:
        t = yf.Ticker(ticker)
        rec = t.recommendations
        if rec is None or rec.empty:
            return np.nan

        rec_30d = rec[rec.index >= (pd.Timestamp.today() - timedelta(days=30))]
        if rec_30d.empty:
            return np.nan

        buy_count = (rec_30d['To Grade'] == 'Buy').sum()
        sell_count = (rec_30d['To Grade'] == 'Sell').sum()
        return buy_count - sell_count
    except:
        return np.nan


def rating_change_30d(ticker):
    """Change in analyst rating over 30 days"""
    try:
        t = yf.Ticker(ticker)
        rec = t.recommendations
        if rec is None or rec.empty:
            return np.nan

        rec_30d = rec[rec.index >= (pd.Timestamp.today() - timedelta(days=30))]
        if rec_30d.empty:
            return np.nan

        buy_count = (rec_30d['To Grade'] == 'Buy').sum()
        sell_count = (rec_30d['To Grade'] == 'Sell').sum()
        return buy_count - sell_count
    except:
        return np.nan

# -------------------------
# (7) Time Embeddings
# -------------------------
def time_embeddings(start_date, end_date):
    # Convert to datetime if needed
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date)
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date)

    # Create business days only
    dates = pd.bdate_range(start=start_date, end=end_date)
    embeddings = pd.DataFrame(index=dates)

    # 1. WEEKDAY (5 trading days: Mon-Fri)
    weekday = dates.weekday.values
    weekday_radians = (weekday / 5) * 2 * np.pi
    embeddings['sin_weekday'] = np.sin(weekday_radians)
    embeddings['cos_weekday'] = np.cos(weekday_radians)

    # 2. MONTH (21 trading days per month)
    month_day_list = []
    current_month = None
    day_count = 0

    for date in dates:
        date_month = (date.year, date.month)
        if date_month != current_month:
            current_month = date_month
            day_count = 0
        month_day_list.append(day_count)
        day_count += 1

    month_day = np.array(month_day_list)
    month_radians = (month_day / 21) * 2 * np.pi
    embeddings['sin_month'] = np.sin(month_radians)
    embeddings['cos_month'] = np.cos(month_radians)

    # 3. YEAR (252 trading days per year)
    year_day_list = []
    current_year = None
    day_count = 0

    for date in dates:
        if date.year != current_year:
            current_year = date.year
            day_count = 0
        year_day_list.append(day_count)
        day_count += 1

    year_day = np.array(year_day_list)
    year_radians = (year_day / 252) * 2 * np.pi
    embeddings['sin_year'] = np.sin(year_radians)
    embeddings['cos_year'] = np.cos(year_radians)

    return embeddings



# -------------------------
# 5️⃣ Full Feature Builder
# -------------------------
def build_full_features(tickers, start_date=date(2021, 1, 1), end_date=date(2024, 1, 1)):

    before_start_date = start_date - timedelta(days=400)
    after_end_date = end_date + timedelta(days=30)
    # Download multi-ticker price data
    data = yf.download(tickers, start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=after_end_date, group_by='ticker', auto_adjust=True)
    spy = yf.download("SPY", start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=end_date)['Close']['SPY']
    vix = yf.download("^VIX", start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=end_date)['Close']
    rsp = yf.download("RSP", start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=end_date)['Close']['RSP']

    feature_list = []

    for ticker in tickers:
        df = data[ticker].copy()
        feat = pd.DataFrame(index=df.index)

        # ---- Technical / Momentum ----
        for w in [5, 10, 20, 60, 120, 252]:
            feat[f"ret_{w}d"] = rolling_return(df['Close'], w)
        feat["momentum_12_1"] = momentum_12_1(df['Close'])
        for w in [20, 60, 200]:
            feat[f"ma_dist_{w}d"] = moving_average_distance(df['Close'], w)


        # ---- Volatility ----
        for w in [20, 60, 120]:
            feat[f"realized_vol_{w}d"] = realized_volatility(df['Close'], w)
        feat["downside_vol_60d"] = downside_vol(df['Close'], 60)
        feat["atr_14d"] = atr(df['High'], df['Low'], df['Close'])
        feat["hl_range_10d"] = (df['High'].rolling(10).max() - df['Low'].rolling(10).min()) / df['Close']

        # ---- Volume ----
        feat["volume_zscore_20d"] = volume_zscore(df['Volume'])
        feat["volume_trend_slope_60d"] = volume_trend_slope(df['Volume'], 60)
        feat["dollar_vol_20d"] = dollar_volume(df['Close'], df['Volume'],20)
        feat["volume_spike_ratio_20d"] = volume_spike_ratio(df['Volume'], 20)


        # ---- Relative Strength ----
        stock_ret = df['Close'].pct_change()
        spy_ret = spy.pct_change()
        #feat["spy_return_20d"] = stock_spy_return_diff(stock_ret, spy_ret, 20)
        feat["beta_spy_60d"] = beta_to_spy(stock_ret, spy.pct_change())
        #feat["alpha_spy_60d"] = alpha_vs_spy(stock_ret, spy_ret, 60)

        # ---- Options Market Proxies (Public Approximation)
        feat["put_call_ratio"] = put_call_ratio_proxy(ticker)

        #YFinance returns NaN for most tickers (not all stocks have recommendations)
        feat['put_call_ratio'] = feat['put_call_ratio'].fillna(-1)

        feat['ticker'] = ticker
        feat.reset_index(inplace=True)
        feat.rename(columns={'index': 'Date'}, inplace=True)
        feature_list.append(feat)

    # Concatenate all tickers
    features = pd.concat(feature_list, axis=0, ignore_index=True)

    # ---- Market Breadth ----
    # Combine close prices across tickers
    close_df = pd.concat([data[t]['Close'] for t in tickers], axis=1)
    close_df.columns = tickers
    close_df.index.name = 'Date'
    breadth = pd.DataFrame({
        'pct_above_200d': pct_above_ma(close_df, 200),
        'pct_above_50d': pct_above_ma(close_df, 50),
        'adv_decl_ratio': advance_decline_ratio(close_df),
        'new_52w_high_low': new_52w_high_low(close_df),
        'equal_weight_vs_cap_weight_spy_spread_20d': calculate_equal_vs_cap_weight_spread(rsp, spy, window=20),
    }).reset_index()

    features = features.merge(breadth, on='Date', how='left')

    # ---- VIX ----
    features = features.merge(vix, on='Date', how='left')
    features.sort_values(['ticker', 'Date'], inplace=True)

    features['VIX_5d_chg'] = features.groupby('ticker')['^VIX'].pct_change(5)
    features['VIX_20d_chg'] = features.groupby('ticker')['^VIX'].pct_change(20)
    features['VIX_term_structure'] = features.groupby('ticker')['^VIX'].apply(lambda x: calculate_vix_term_structure(x, window=20)).reset_index(level=0, drop=True)
    features['VIX_realized_vol_ratio_20d'] = calculate_vix_realized_vol_ratio(features['^VIX'], features['realized_vol_60d'], window=20)
    features.drop(columns=['^VIX'], axis=1, inplace=True)

    # ---- Macro Features ----
    for sid, name in fred_series.items():
        macro_df = fetch_fred_data(sid, name)
        if macro_df is not None:
            features = features.merge(macro_df, left_on="Date", right_index=True, how="left")

    # Normalize macro features to 0-1 range
    for sid, name in fred_series.items():
        if name in features.columns:
            min_val = features[name].min()
            max_val = features[name].max()
            if max_val > min_val:
                features[name] = (features[name] - min_val) / (max_val - min_val)


    # ---- Time Embedding ----
    time_embedding_df = time_embeddings(start_date, end_date)
    features = features.merge(time_embedding_df, left_on="Date", right_index=True, how="left")


    features['Date'] = pd.to_datetime(features['Date'])
    start_date_datetime = datetime.combine(start_date, datetime.min.time())
    end_date_datetime = datetime.combine(end_date, datetime.min.time())

    features = features[features['Date'] >= start_date_datetime]

    # ---- Forward Return Target (10d) ----
    fut_10d_ret = features.groupby('ticker')['ret_5d'].shift(-2)

    features = features[features['Date'] <= end_date_datetime]
    return features, fut_10d_ret[:len(features)]


# -------------------------
# Example Usage
# -------------------------
if __name__ == "__main__":
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    features, labels = build_full_features(tickers, start_date=date(2018, 1, 1), end_date=date(2024, 1, 1))
    # Check NaN distribution
    print("\n=== NaN Counts ===")
    nan_stats = features.isna().sum().sort_values(ascending=False)
    print(nan_stats[nan_stats > 0])
    print(f"\n=== {len(features)} Columns ===")
    print(features.columns)
    print("\n=== Dimensions ===")
    print(features.shape)
    print("\n=== Head ===")
    print(features.head())

    print(labels)
    features.to_csv("test_dataset.csv", index=False)