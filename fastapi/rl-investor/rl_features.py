from datetime import date, timedelta
import pandas as pd
import pandas_ta as ta
import yfinance


def preprocess_data(start_date, end_date, tickers):
    df_prices = yfinance.download(tickers, start=(start_date - timedelta(days=60)).strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by='ticker', interval="1d", progress=False, threads=True, auto_adjust=True)
    df_close = (
        df_prices.xs("Close", axis=1, level="Price")
        .stack(level=0)
        .reset_index()
    )
    df_close.columns = ['date', 'ticker', 'close']
    df_close['date'] = pd.to_datetime(df_close['date']).dt.date
    df_high = (
        df_prices.xs("High", axis=1, level="Price")
        .stack(level=0)
        .reset_index()
    )
    df_high.columns = ['date', 'ticker', 'high']
    df_high['date'] = pd.to_datetime(df_high['date']).dt.date
    df_low = (
        df_prices.xs("Low", axis=1, level="Price")
        .stack(level=0)
        .reset_index()
    )
    df_low.columns = ['date', 'ticker', 'low']
    df_low['date'] = pd.to_datetime(df_low['date']).dt.date
    df_volume = (
        df_prices.xs("Volume", axis=1, level="Price")
        .stack(level=0)
        .reset_index()
    )
    df_volume.columns = ['date', 'ticker', 'volume']
    df_volume['date'] = pd.to_datetime(df_volume['date']).dt.date

    df_close  = df_close.pivot(index="date", columns="ticker", values="close")
    df_high   = df_high.pivot(index="date", columns="ticker", values="high")
    df_low    = df_low.pivot(index="date", columns="ticker", values="low")
    df_volume = df_volume.pivot(index="date", columns="ticker", values="volume")

    indicators = compute_indicators(df_close, df_high, df_low, df_volume)

    found_tickers = []
    for ticker in indicators:
        df = indicators[ticker]
        if df.empty:
            del indicators[ticker]
        else:
            indicators[ticker] = df[(df.index >= start_date) & (df.index <= end_date)]
            found_tickers.append(ticker)

    return indicators, found_tickers

def get_opens(start_date, end_date, tickers):
    df_prices = yfinance.download(tickers, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"),
                                  group_by='ticker', interval="1d", progress=False, threads=True, auto_adjust=True)

    df_open = df_prices.xs("Open", axis=1, level="Price")

    valid_tickers = df_open.columns[df_open.notna().any()].tolist()
    df_open = df_open[valid_tickers]

    df = (
        df_open
        .stack(level=0)
        .reset_index()
    )
    df.columns = ["date", "ticker", "open"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[["ticker", "date", "open"]]

    return df, valid_tickers

def get_index(index, start_date, end_date):
    if index == "dow":
        index_ticker = "DJI"
    else:
        index_ticker = "SPY"
    df = yfinance.download(f"^{index_ticker}", start=start_date.strftime("%Y-%m-%d"),
                           end=end_date.strftime("%Y-%m-%d"), progress=False)
    return df["Open"].values, df["Close"].values

def compute_indicators(df_close, df_high, df_low, df_volume):
    """
    Paper uses: BOLL, CCI, RSI, TR, DMI, MACD, MFI
    """
    features = {}
    for ticker in df_close.columns:
        c = df_close[ticker]
        h = df_high[ticker]
        l = df_low[ticker]
        v = df_volume[ticker]


        features[ticker] = pd.DataFrame({
            'close': c,
            'boll_upper': ta.bbands(c, length=20)['BBU_20_2.0_2.0'],
            'boll_lower': ta.bbands(c, length=20)['BBL_20_2.0_2.0'],
            'cci': ta.cci(h, l, c, length=20),
            'rsi': ta.rsi(c, length=14),
            'tr': ta.true_range(h, l, c),
            'dmi': ta.adx(h, l, c, length=14)['ADX_14'],
            'macd': ta.macd(c)['MACD_12_26_9'],
            'mfi': ta.mfi(h, l, c, v, length=14),
        })
    return features
if __name__ == "__main__":
    preprocess_data(date(2020,1,1), date(2020,12,31), ["AAPL", "MSFT"])