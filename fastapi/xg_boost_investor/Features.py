import os

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import requests
from functools import lru_cache

def rolling_return(df, window):
    return df.pct_change(window)

def momentum_12_1(df):
    return df.pct_change(252) - df.pct_change(21)

def moving_average_distance(df, window):
    ma = df.rolling(window).mean()
    return (df - ma) / ma

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
    return (high.rolling(window).max() - low.rolling(window).min()) / close

def volume_zscore(volume, window=20):
    return (volume - volume.rolling(window).mean()) / volume.rolling(window).std()

def volume_trend_slope(volume, window=60):

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

def fetch_fred_data(series_id, name, save_load=True):
    if os.path.exists(f'{name}_fred.csv') and save_load:
        cached_fred_data = pd.read_csv(f'{name}_fred.csv')
        cached_fred_data["Date"] = pd.to_datetime(cached_fred_data["Date"], format="%Y-%m-%d")
        cached_fred_data = cached_fred_data[["Date", name]]

        cached_fred_data.set_index("Date", inplace=True)
        cached_fred_data.sort_index(inplace=True)
        return cached_fred_data[name]
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
        response = requests.get(url, timeout=30)
        r = response.json()

        if 'error_code' in r:
            print(f"FRED Error for {series_id}: {r.get('error_message', 'Unknown error')}")
            return None

        data = pd.DataFrame(r["observations"])

        data["Date"] = pd.to_datetime(data["date"], format="%Y-%m-%d")
        data[name] = pd.to_numeric(data["value"], errors='coerce')

        data = data[["Date", name]]

        data.set_index("Date", inplace=True)
        data.sort_index(inplace=True)

        date_range_start = data.index.min()
        date_range_end = date.today()

        # Pad data for missing dates
        full_date_range = pd.date_range(start=date_range_start, end=date_range_end, freq='D')
        data = data.reindex(full_date_range)
        data[name] = data[name].ffill()

        data.index.name = "Date"

        data[name].to_csv(f'{name}_fred.csv')

    except Exception as e:
        print(f"Failed to fetch FRED data for {series_id}: {e}")
        return None


    return data[name]

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



def build_full_features(tickers, start_date=date(2021, 1, 1), end_date=date(2024, 1, 1), explainable=False, alias_tag=None, save_fred=True):

    before_start_date = start_date - timedelta(days=400)
    after_end_date = end_date + timedelta(days=10)
    # Download multi-ticker price data
    data = yf.download(tickers, start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=after_end_date, group_by='ticker', auto_adjust=True)
    spy = yf.download("SPY", start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=after_end_date)['Close']['SPY']
    vix = yf.download("^VIX", start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=after_end_date)['Close']
    rsp = yf.download("RSP", start=before_start_date.strftime("%Y-%m-%d"), interval="1d", end=after_end_date)['Close']['RSP']

    feature_list = []

    for ticker in tickers:
        df = data[ticker].copy()
        feat = pd.DataFrame(index=df.index)

        # ---- Technical / Momentum ----
        for w in [1, 5, 10, 20, 60, 120, 252]:
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

        tag = '_' + str(start_date.year)
        if alias_tag is not None:
            tag = '_' + str(alias_tag)
        feat['ticker'] = ticker + tag
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
        macro_df = fetch_fred_data(sid, name, save_fred)
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

    # ---- Forward Return Target (1d) ----
    future_1d_return = features.groupby('ticker')['ret_1d'].shift(-1)

    features = features[features['Date'] <= end_date_datetime]

    return features, future_1d_return[:len(features)]

def get_feature_explanations():
    return [
        # ---- Momentum / Returns ----
        {
            "identifier": "ret_1d",
            "name": "1-Day Returns",
            "description": "Percentage change in close price over the past 1 trading day"
        },
        {
            "identifier": "ret_5d",
            "name": "5-Day Returns",
            "description": "Percentage change in close price over the past 5 trading days"
        },
        {
            "identifier": "ret_10d",
            "name": "10-Day Returns",
            "description": "Percentage change in close price over the past 10 trading days"
        },
        {
            "identifier": "ret_20d",
            "name": "20-Day Returns",
            "description": "Percentage change in close price over the past 20 trading days (1 month)"
        },
        {
            "identifier": "ret_60d",
            "name": "60-Day Returns",
            "description": "Percentage change in close price over the past 60 trading days (3 months)"
        },
        {
            "identifier": "ret_120d",
            "name": "120-Day Returns",
            "description": "Percentage change in close price over the past 120 trading days (6 months)"
        },
        {
            "identifier": "ret_252d",
            "name": "252-Day Returns",
            "description": "Percentage change in close price over the past 252 trading days (1 year)"
        },
        {
            "identifier": "momentum_12_1",
            "name": "12-Month 1-Month Momentum",
            "description": "Momentum indicator: 1-year return minus 1-month return, capturing intermediate-term price momentum"
        },

        # ---- Moving Average Distance ----
        {
            "identifier": "ma_dist_20d",
            "name": "20-Day MA Distance",
            "description": "Normalized distance from 20-day moving average: (Price - MA) / MA"
        },
        {
            "identifier": "ma_dist_60d",
            "name": "60-Day MA Distance",
            "description": "Normalized distance from 60-day moving average: (Price - MA) / MA"
        },
        {
            "identifier": "ma_dist_200d",
            "name": "200-Day MA Distance",
            "description": "Normalized distance from 200-day moving average: (Price - MA) / MA"
        },

        # ---- Volatility ----
        {
            "identifier": "realized_vol_20d",
            "name": "20-Day Realized Volatility",
            "description": "Standard deviation of daily returns over the past 20 trading days"
        },
        {
            "identifier": "realized_vol_60d",
            "name": "60-Day Realized Volatility",
            "description": "Standard deviation of daily returns over the past 60 trading days"
        },
        {
            "identifier": "realized_vol_120d",
            "name": "120-Day Realized Volatility",
            "description": "Standard deviation of daily returns over the past 120 trading days"
        },
        {
            "identifier": "downside_vol_60d",
            "name": "60-Day Downside Volatility",
            "description": "Standard deviation of negative daily returns only over the past 60 trading days"
        },
        {
            "identifier": "atr_14d",
            "name": "14-Day Average True Range",
            "description": "Average True Range: 14-day moving average of the daily trading range (high-low), adjusted for gaps"
        },
        {
            "identifier": "hl_range_10d",
            "name": "10-Day High-Low Range",
            "description": "Normalized 10-day high-low range: (10d High - 10d Low) / Close"
        },

        # ---- Volume ----
        {
            "identifier": "volume_zscore_20d",
            "name": "20-Day Volume Z-Score",
            "description": "Z-score of current volume relative to 20-day moving average: (Volume - MA) / StdDev"
        },
        {
            "identifier": "volume_trend_slope_60d",
            "name": "60-Day Volume Trend Slope",
            "description": "Linear regression slope of volume over 60 days, normalized by mean volume"
        },
        {
            "identifier": "dollar_vol_20d",
            "name": "20-Day Dollar Volume Ratio",
            "description": "Average dollar volume (Price * Volume) normalized by 60-day baseline"
        },
        {
            "identifier": "volume_spike_ratio_20d",
            "name": "20-Day Volume Spike Ratio",
            "description": "Current volume divided by 20-day average volume"
        },

        # ---- Relative Strength ----
        {
            "identifier": "beta_spy_60d",
            "name": "60-Day Beta vs SPY",
            "description": "Covariance of stock returns with SPY divided by SPY variance over 60 days"
        },

        # ---- Options Market ----
        {
            "identifier": "put_call_ratio",
            "name": "Put/Call Ratio",
            "description": "Options market sentiment: ratio of put volume to call volume on nearest expiration"
        },

        # ---- Identifiers ----
        {
            "identifier": "ticker",
            "name": "Ticker Symbol",
            "description": "Stock ticker symbol with year identifier (e.g., AAPL_2026)"
        },

        # ---- Market Breadth ----
        {
            "identifier": "pct_above_200d",
            "name": "Percentage Above 200-Day MA",
            "description": "Proportion of stocks in the market basket trading above their 200-day moving average"
        },
        {
            "identifier": "pct_above_50d",
            "name": "Percentage Above 50-Day MA",
            "description": "Proportion of stocks in the market basket trading above their 50-day moving average"
        },
        {
            "identifier": "adv_decl_ratio",
            "name": "Advance/Decline Ratio",
            "description": "Market breadth indicator: number of advancing stocks divided by declining stocks"
        },
        {
            "identifier": "new_52w_high_low",
            "name": "New 52-Week High/Low Ratio",
            "description": "Proportion of stocks at new 52-week highs minus new lows, normalized by basket size"
        },
        {
            "identifier": "equal_weight_vs_cap_weight_spy_spread_20d",
            "name": "Equal-Weight vs Cap-Weight Spread",
            "description": "20-day average spread between RSP (equal-weight) and SPY (cap-weight) returns"
        },

        # ---- VIX ----
        {
            "identifier": "VIX_5d_chg",
            "name": "5-Day VIX Change",
            "description": "Percentage change in VIX volatility index over the past 5 trading days"
        },
        {
            "identifier": "VIX_20d_chg",
            "name": "20-Day VIX Change",
            "description": "Percentage change in VIX volatility index over the past 20 trading days"
        },
        {
            "identifier": "VIX_term_structure",
            "name": "VIX Term Structure",
            "description": "VIX momentum proxy: (VIX - 20d MA) / 20d MA * 100, indicating fear level relative to average"
        },
        {
            "identifier": "VIX_realized_vol_ratio_20d",
            "name": "VIX/Realized Vol Ratio",
            "description": "Ratio of implied volatility (VIX) to realized volatility over 20 days; >1 suggests overpriced vol"
        },

        # ---- Macroeconomic ----
        {
            "identifier": "TY10Y",
            "name": "10-Year Treasury Yield",
            "description": "10-year US Treasury yield (DGS10), normalized to 0-1 range"
        },
        {
            "identifier": "TY2Y",
            "name": "2-Year Treasury Yield",
            "description": "2-year US Treasury yield (DGS2), normalized to 0-1 range"
        },
        {
            "identifier": "CPI",
            "name": "Consumer Price Index",
            "description": "CPI inflation measure, normalized to 0-1 range"
        },
        {
            "identifier": "UnemploymentRate",
            "name": "Unemployment Rate",
            "description": "US unemployment rate, normalized to 0-1 range"
        },
        {
            "identifier": "FedFunds",
            "name": "Federal Funds Rate",
            "description": "Federal Reserve target interest rate, normalized to 0-1 range"
        },
        {
            "identifier": "IndustrialProduction",
            "name": "Industrial Production Index",
            "description": "US industrial production growth index, normalized to 0-1 range"
        },
        {
            "identifier": "RetailMoneyMarketFunds",
            "name": "Retail Money Market Funds",
            "description": "Retail money market fund holdings, normalized to 0-1 range"
        },

        # ---- Time Embeddings ----
        {
            "identifier": "sin_weekday",
            "name": "Weekday Sine Component",
            "description": "Sine of weekday position (0-4, Mon-Fri) encoded as radians, captures day-of-week seasonality"
        },
        {
            "identifier": "cos_weekday",
            "name": "Weekday Cosine Component",
            "description": "Cosine of weekday position encoded as radians, captures day-of-week seasonality"
        },
        {
            "identifier": "sin_month",
            "name": "Month Sine Component",
            "description": "Sine of day-in-month position (0-21 trading days) encoded as radians, captures intra-month seasonality"
        },
        {
            "identifier": "cos_month",
            "name": "Month Cosine Component",
            "description": "Cosine of day-in-month position encoded as radians, captures intra-month seasonality"
        },
        {
            "identifier": "sin_year",
            "name": "Year Sine Component",
            "description": "Sine of day-in-year position (0-252 trading days) encoded as radians, captures intra-year seasonality"
        },
        {
            "identifier": "cos_year",
            "name": "Year Cosine Component",
            "description": "Cosine of day-in-year position encoded as radians, captures intra-year seasonality"
        }
    ]
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
    #features.to_csv("test_dataset.csv", index=False)
