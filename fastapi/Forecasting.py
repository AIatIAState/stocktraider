from darts import TimeSeries
import pandas as pd
from darts.dataprocessing.transformers import Scaler, MissingValuesFiller
from darts.models import ARIMA, \
    ExponentialSmoothing, RandomForestModel, NaiveMovingAverage, NaiveSeasonal, NaiveDrift, \
    NaiveMean, Theta, FourTheta, AutoARIMA, LightGBMModel, LinearRegressionModel
from darts.utils.utils import SeasonalityMode
from matplotlib import pyplot as plt

from Connector import get_connection
import warnings
from sklearn.exceptions import DataConversionWarning
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

def get_forecast(symbol, timeframe, forecast_length=7):
    where = ["symbol = ?", "timeframe = ?"]
    sql = f"""
        SELECT symbol, per, date, time, open, high, low, close, volume, openint, timeframe
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date {"ASC"}, time {"DESC"}
    """
    params: list[object] = [symbol, timeframe]
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    rows = [{'date': dict(row)['date'], 'open': dict(row)['open']} for row in rows]

    df = pd.DataFrame(rows)
    df['open'] = df['open'].ffill()
    df['date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
    ts = TimeSeries.from_dataframe(df, time_col='date', value_cols='open', fill_missing_dates=True, freq='D')

    # Resample to different frequency
    ts_weekly = ts.resample('W')


    scaler = Scaler()
    ts = scaler.fit_transform(ts)

    # Fill missing values with dart
    filler = MissingValuesFiller(fill='auto')
    ts = filler.transform(ts)

    forecasters = [
        {
            "name": "Light GBM",
            "model": LightGBMModel(lags=forecast_length, output_chunk_length=forecast_length, verbose=0),
            "summary": "Gradient boosting framework that builds an ensemble of decision trees sequentially, where each tree corrects errors from previous trees using lagged features. Uses histogram-based learning and leaf-wise growth for efficient training on time series data."
        },
        {
            "name": "Random Forest",
            "model": RandomForestModel(lags=forecast_length, output_chunk_length=forecast_length),
            "summary": "Ensemble of decision trees that uses lagged time series values as features to predict future values through bootstrap aggregation. Each tree learns non-linear patterns, and predictions are averaged across all trees to reduce variance."
        },
        {
            "name": "Auto Arima",
            "model": AutoARIMA(),
            "summary": "Automatically selects optimal ARIMA parameters (p, d, q) and seasonal parameters through systematic search using information criteria like AIC/BIC. Uses the same ARIMA framework but removes the need for manual parameter tuning."
        },
        {
            "name": "FourTheta",
            "model": FourTheta(seasonality_period=forecast_length, season_mode=SeasonalityMode.ADDITIVE),
            "summary": "Extension of Theta method that decomposes the series into four components using different theta coefficients to capture multiple patterns. Combines forecasts from multiple theta lines with optimized weights to improve accuracy over standard Theta."
        },
        {
            "name": "Exponential Smoothing",
            "model": ExponentialSmoothing(seasonal_periods=forecast_length),
            "summary": "Applies exponentially decreasing weights to past observations, with more recent data having greater influence on forecasts. Can capture level, trend, and seasonal components through state space formulations (Holt-Winters method)."
        },
        {
            "name": "Theta",
            "model": Theta(seasonality_period=forecast_length, season_mode=SeasonalityMode.ADDITIVE),
            "summary": "Decomposes the time series into long-term trend and short-term fluctuations using theta lines, then forecasts each component separately before combining. The trend is typically modeled with simple exponential smoothing while the seasonal component uses a drift method."
        },
        {
            "name": "Arima",
            "model": ARIMA(),
            "summary": "AutoRegressive Integrated Moving Average combines differencing to achieve stationarity with AR (autoregressive) and MA (moving average) components to model temporal dependencies. The model uses past values and past forecast errors to predict future values through linear combinations."
        },
        {
            "name": "Linear Regression",
            "model": LinearRegressionModel(lags=forecast_length, output_chunk_length=forecast_length),
            "summary": "Fits a linear model to the time series using ordinary least squares, treating time or lagged values as features. Minimizes the sum of squared residuals to find optimal coefficients that best explain the linear relationship in the data."
        },
        {
            "name": "Naive Seasonal",
            "model": NaiveSeasonal(K=forecast_length),
            "summary": "Predicts future values by repeating observations from exactly K periods ago, assuming perfect seasonal repetition. Uses the most recent complete seasonal cycle as the forecast without any statistical modeling."
        },
        {
            "name": "Simple Moving Average",
            "model": NaiveMovingAverage(input_chunk_length=forecast_length),
            "summary": "Calculates the arithmetic mean of the most recent observations within a sliding window. Forecasts by simply using this average as the prediction for future time steps, giving equal weight to all observations in the window."
        },
        {
            "name": "Naive Drift",
            "model": NaiveDrift(),
            "summary": "Extends the last observation by adding a linear drift component calculated from the slope between first and last observations. Essentially fits a straight line through the historical data and extrapolates it forward."
        },
        {
            "name": "Naive Mean",
            "model": NaiveMean(),
            "summary": "Uses the arithmetic mean of all historical observations as the forecast for all future time steps. Assumes the time series is stationary with no trend or seasonality, treating all past values equally."
        }
    ]

    results = []
    for forecaster in forecasters:
        model_name = forecaster['name']
        model_summary = forecaster['summary']
        model = forecaster['model']
        model.fit(ts)
        model_result = model.predict(n=forecast_length)
        inversed_model_result = scaler.inverse_transform(model_result)
        result_dict = [
            {"date": str(timestamp).replace('-', '').replace(':', '').replace(' ', ''), "open": float(value)}
            for timestamp, value in zip(
                inversed_model_result.time_index,
                inversed_model_result.values().flatten()
            )
        ]
        results.append({"name": model_name, "summary": model_summary, "forecast": result_dict})

    return {'results': results}

if __name__ == "__main__":
    print(get_forecast("AAPL.US", "daily"))