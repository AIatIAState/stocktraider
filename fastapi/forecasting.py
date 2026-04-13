from darts import TimeSeries
import pandas as pd
from darts.dataprocessing.transformers import Scaler, MissingValuesFiller
from darts.models import ARIMA, \
    ExponentialSmoothing, RandomForestModel, NaiveDrift, \
    Theta, FourTheta, AutoARIMA, LightGBMModel, LinearRegressionModel
from darts.utils.utils import SeasonalityMode
from matplotlib import pyplot as plt

from connector import get_connection
import threading
import time as _time
import warnings
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
import numpy as np

warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

FORECAST_CACHE_TTL_SECONDS = 86400  # 24 hours
FORECAST_CACHE_LOCK = threading.Lock()
FORECAST_CACHE: dict[str, dict] = {}


def get_forecast(symbol, timeframe, forecast_length=5):
    cache_key = f"{symbol}:{timeframe}:{forecast_length}"
    with FORECAST_CACHE_LOCK:
        cached = FORECAST_CACHE.get(cache_key)
        if cached and (_time.time() - cached["timestamp"]) < FORECAST_CACHE_TTL_SECONDS:
            return cached["payload"]

    where = ["symbol = ?", "timeframe = ?"]
    sql = f"""
        SELECT date, close
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date {"ASC"}, time {"DESC"}
    """
    params: list[object] = [symbol, timeframe]
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    rows = [{'date': dict(row)['date'], 'close': dict(row)['close']} for row in rows]
    df = pd.DataFrame(rows)
    df['close'] = df['close'].ffill()
    df['date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
    df = df.sort_values('date').reset_index(drop=True)
    df['log_ret'] = np.log(df['close']).diff()
    df['return'] = df['log_ret'].shift(-1)
    df = df.dropna().reset_index(drop=True)

    if len(df) < 100:
        print(f"Warning: {symbol} has insufficient data ({len(df)} rows)")
        return None

    # Prepare time series
    ts = TimeSeries.from_dataframe(df, time_col='date', value_cols='return', fill_missing_dates=True, freq='B')

    filler = MissingValuesFiller()
    ts = filler.transform(ts)


    scaler = Scaler()
    ts = scaler.fit_transform(ts)

    forecasters = [
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
            "name": "Theta",
            "model": Theta(seasonality_period=forecast_length, season_mode=SeasonalityMode.ADDITIVE),
            "summary": "Decomposes the time series into long-term trend and short-term fluctuations using theta lines, then forecasts each component separately before combining. The trend is typically modeled with simple exponential smoothing while the seasonal component uses a drift method."
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

        pred_log_returns = inversed_model_result.values().flatten()

        # Get last known close
        last_close = df['close'].iloc[-1]

        # Reconstruct price path
        prices = []
        current_price = last_close

        for r in pred_log_returns:
            current_price = current_price * np.exp(r)
            prices.append(current_price)

        result_dict = [
            {"date": str(timestamp).replace('-', '').replace(':', '').replace(' ', ''), "close": float(value)}
            for timestamp, value in zip(
                inversed_model_result.time_index,
                prices
            )
        ]
        results.append({"name": model_name, "summary": model_summary, "forecast": result_dict})

    result = {'results': results}
    with FORECAST_CACHE_LOCK:
        FORECAST_CACHE[cache_key] = {"timestamp": _time.time(), "payload": result}
    return result


def evaluate_models_backtest(symbol, timeframe, forecast_lengths=[5, 10, 15, 20]):
    """
    Perform walk-forward validation on all models for different forecast lengths.
    Returns evaluation metrics for each model and forecast length.
    """

    # Fetch data
    where = ["symbol = ?", "timeframe = ?", "date < ?"]
    sql = f"""
        SELECT symbol, date, close
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date ASC
    """
    params = [symbol, timeframe, "20260101"]
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    rows = [{'date': dict(row)['date'], 'close': dict(row)['close']} for row in rows]
    df = pd.DataFrame(rows)
    df['close'] = df['close'].ffill()
    df['date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
    df = df.sort_values('date').reset_index(drop=True)
    df['log_ret'] = np.log(df['close']).diff()
    df['return'] = df['log_ret'].shift(-1)
    df = df.dropna().reset_index(drop=True)


    if len(df) < 100:
        print(f"Warning: {symbol} has insufficient data ({len(df)} rows)")
        return None

    # Prepare time series
    ts = TimeSeries.from_dataframe(df, time_col='date', value_cols='return', fill_missing_dates=True, freq='B')

    filler = MissingValuesFiller()
    ts = filler.transform(ts)

    # Define models with baseline
    forecasters = [
        {
            "name": "Light GBM",
            "model": LightGBMModel(lags=20, output_chunk_length=20, verbose=0),
        },
        {
            "name": "Random Forest",
            "model": RandomForestModel(lags=20, output_chunk_length=20),
        },
        {
            "name": "Auto Arima",
            "model": AutoARIMA(),
        },
        {
            "name": "FourTheta",
            "model": FourTheta(seasonality_period=20, season_mode=SeasonalityMode.ADDITIVE),
        },
        {
            "name": "Exponential Smoothing",
            "model": ExponentialSmoothing(seasonal_periods=20),
        },
        {
            "name": "Theta",
            "model": Theta(seasonality_period=20, season_mode=SeasonalityMode.ADDITIVE),
        },
        {
            "name": "Arima",
            "model": ARIMA(),
        },
        {
            "name": "Linear Regression",
            "model": LinearRegressionModel(lags=100, output_chunk_length=20),
        },
        {
            "name": "Naive Drift (Baseline)",
            "model": NaiveDrift(),
        },
    ]

    # Walk-forward validation
    results_by_length = {fl: {m['name']: {'mae': [], 'rmse': [], 'mape': [], 'directional_acc': []} for m in forecasters}
                         for fl in forecast_lengths}

    # Use last 252 days for testing with rolling window
    test_start_idx = len(ts) - 252

    for forecast_length in forecast_lengths:
        print(f"  Testing forecast length: {forecast_length}")

        # Walk-forward: move the window forward by forecast_length steps
        for test_idx in range(test_start_idx, len(ts) - forecast_length, max(1, forecast_length // 2)):
            if test_idx + forecast_length > len(ts):
                break

            # Train on everything before test_idx, test on next forecast_length points
            ts_train = ts[:test_idx]
            ts_test = ts[test_idx:test_idx + forecast_length]

            # Scaler
            scaler = Scaler()
            ts_train_scaled = scaler.fit_transform(ts_train)
            ts_test_scaled = scaler.transform(ts_test)

            # Actual test values
            y_test = ts_test.values().flatten()

            for forecaster in forecasters:
                model_name = forecaster['name']
                try:
                    # Create a fresh model instance to avoid state issues
                    if model_name == "Auto Arima":
                        model = AutoARIMA()
                    elif model_name == "FourTheta":
                        model = FourTheta(seasonality_period=forecast_length, season_mode=SeasonalityMode.ADDITIVE)
                    elif model_name == "Exponential Smoothing":
                        model = ExponentialSmoothing(seasonal_periods=forecast_length)
                    elif model_name == "Theta":
                        model = Theta(seasonality_period=forecast_length, season_mode=SeasonalityMode.ADDITIVE)
                    elif model_name == "Arima":
                        model = ARIMA()
                    elif model_name == "Linear Regression":
                        model = LinearRegressionModel(lags=100, output_chunk_length=forecast_length)
                    elif model_name == "Naive Drift (Baseline)":
                        model = NaiveDrift()
                    elif model_name == "Light GBM":
                        model = LightGBMModel(lags=forecast_length, output_chunk_length=forecast_length, verbose=0)
                    elif model_name == "Random Forest":
                        model = RandomForestModel(lags=forecast_length, output_chunk_length=forecast_length)

                    if model_name == "Light GBM" or model_name == "Random Forest":
                        # For tree-based models, we need to fit on the original (unscaled) data
                        model.fit(ts_train)
                    else:
                        model.fit(ts_train_scaled)

                    forecast = model.predict(n=forecast_length)
                    if model_name == "Light GBM" or model_name == "Random Forest":
                        y_pred = forecast.values().flatten()
                    else:
                        y_pred = scaler.inverse_transform(forecast).values().flatten()

                    # Calculate metrics
                    mae = mean_absolute_error(y_test, y_pred)
                    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
                    mape = mean_absolute_percentage_error(y_test, y_pred)
                    directional_acc =  np.mean(np.sign(y_test) == np.sign(y_pred))

                    results_by_length[forecast_length][model_name]['mae'].append(mae)
                    results_by_length[forecast_length][model_name]['rmse'].append(rmse)
                    results_by_length[forecast_length][model_name]['mape'].append(mape)
                    results_by_length[forecast_length][model_name]['directional_acc'].append(directional_acc)

                except Exception as e:
                    print(f"    Error with {model_name}: {str(e)}")
                    continue

    # Aggregate results
    aggregated_results = {}
    for fl in forecast_lengths:
        aggregated_results[fl] = {}
        for model_name in results_by_length[fl]:
            mae_vals = results_by_length[fl][model_name]['mae']
            rmse_vals = results_by_length[fl][model_name]['rmse']
            mape_vals = results_by_length[fl][model_name]['mape']
            directional_acc_vals = results_by_length[fl][model_name]['directional_acc']

            aggregated_results[fl][model_name] = {
                'mae_mean': np.mean(mae_vals) if mae_vals else np.nan,
                'mae_std': np.std(mae_vals) if mae_vals else np.nan,
                'rmse_mean': np.mean(rmse_vals) if rmse_vals else np.nan,
                'rmse_std': np.std(rmse_vals) if rmse_vals else np.nan,
                'mape_mean': np.mean(mape_vals) if mape_vals else np.nan,
                'mape_std': np.std(mape_vals) if mape_vals else np.nan,
                'directional_acc_std': np.std(directional_acc_vals) if directional_acc_vals else np.nan,
                'directional_acc_mean': np.mean(directional_acc_vals) if directional_acc_vals else np.nan
            }

    return aggregated_results


def create_evaluation_report(tickers, forecast_lengths):
    """
    Create comprehensive evaluation report with tables and visualizations.
    """
    import numpy as np
    try:
        from tabulate import tabulate
    except ImportError:
        print("Installing tabulate for better table formatting...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'tabulate', '--break-system-packages'])
        from tabulate import tabulate

    all_results = {}

    print("\n" + "=" * 80)
    print("FORECASTING MODEL EVALUATION - WALK-FORWARD VALIDATION")
    print("=" * 80 + "\n")

    for ticker in tickers:
        print(f"\nEvaluating {ticker}...")
        results = evaluate_models_backtest(ticker, "daily", forecast_lengths)

        if results is None:
            continue

        all_results[ticker] = results

        # Create detailed tables for each forecast length
        for forecast_length in forecast_lengths:
            print(f"\n{'-' * 80}")
            print(f"{ticker} - Forecast Length: {forecast_length} days")
            print(f"{'-' * 80}")

            data = []
            for model_name in sorted(results[forecast_length].keys()):
                metrics = results[forecast_length][model_name]
                is_baseline = "Baseline" in model_name

                data.append([
                    model_name,
                    f"{metrics['mae_mean']:.4f} ± {metrics['mae_std']:.4f}",
                    f"{metrics['rmse_mean']:.4f} ± {metrics['rmse_std']:.4f}",
                    f"{metrics['mape_mean']:.4f} ± {metrics['mape_std']:.4f}",
                    f"{metrics['directional_acc_mean']:.4f} ± {metrics['directional_acc_std']:.4f}",

                    "✓ BASELINE" if is_baseline else ""
                ])

            headers = ["Model", "MAE (Mean ± Std)", "RMSE (Mean ± Std)", "MAPE (Mean ± Std)", "DirAcc (Mean ± Std)", "Note"]
            print(tabulate(data, headers=headers, tablefmt="grid"))

    # Create comparison visualizations
    create_visualizations(all_results, tickers, forecast_lengths)

    print("\n" + "=" * 80)
    print("Visualizations saved as PNG files in the working directory")
    print("=" * 80 + "\n")


def create_visualizations(all_results, tickers, forecast_lengths):
    """
    Create comprehensive visualizations comparing model performance.
    """
    import numpy as np

    for ticker in tickers:
        if ticker not in all_results:
            continue

        results = all_results[ticker]

        # 1. MAE, RMSE, MAPE Comparison across forecast lengths
        fig, axes = plt.subplots(1, 4, figsize=(25, 5))
        fig.suptitle(f'{ticker} - Model Performance Across Forecast Lengths', fontsize=14, fontweight='bold')

        metrics = ['mae_mean', 'rmse_mean', 'mape_mean', 'directional_acc_mean']
        metric_labels = ['MAE (Lower is Better)', 'RMSE (Lower is Better)', 'MAPE % (Lower is Better)', 'Directional Accuracy (Higher is Better)']

        for idx, (metric, label) in enumerate(zip(metrics, metric_labels)):
            ax = axes[idx]

            model_names = sorted(results[forecast_lengths[0]].keys())
            x = np.arange(len(forecast_lengths))
            width = 0.08

            for i, model_name in enumerate(model_names):
                values = [results[fl][model_name][metric] for fl in forecast_lengths]
                offset = width * (i - len(model_names) / 2)

                is_baseline = "Baseline" in model_name
                color = 'red' if is_baseline else None
                linewidth = 2 if is_baseline else 1

                ax.bar(x + offset, values, width, label=model_name, color=color, linewidth=linewidth)

            ax.set_xlabel('Forecast Length (days)')
            ax.set_ylabel(label)
            ax.set_title(label)
            ax.set_xticks(x)
            ax.set_xticklabels(forecast_lengths)
            ax.legend(fontsize=8, loc='upper left')
            ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        filename = f"evaluation_{ticker}_metrics_returns_no_dates_filled.png"
        plt.savefig(filename, dpi=100, bbox_inches='tight')
        print(f"Saved: {filename}")
        plt.close()

        # 2. Heat map for each metric
        for metric, metric_name in [('mae_mean', 'MAE'), ('rmse_mean', 'RMSE'), ('mape_mean', 'MAPE'), ('directional_acc_mean', 'Directional Accuracy')]:
            fig, ax = plt.subplots(figsize=(12, 8))

            model_names = sorted(results[forecast_lengths[0]].keys())
            data_matrix = []

            for model_name in model_names:
                row = [results[fl][model_name][metric] for fl in forecast_lengths]
                data_matrix.append(row)

            data_matrix = np.array(data_matrix)

            # Normalize for heatmap
            data_normalized = (data_matrix - data_matrix.min(axis=1, keepdims=True)) / \
                              (data_matrix.max(axis=1, keepdims=True) - data_matrix.min(axis=1, keepdims=True) + 1e-10)

            im = ax.imshow(data_normalized, cmap='RdYlGn_r', aspect='auto')

            ax.set_xticks(np.arange(len(forecast_lengths)))
            ax.set_yticks(np.arange(len(model_names)))
            ax.set_xticklabels(forecast_lengths)
            ax.set_yticklabels(model_names)

            # Rotate the tick labels
            plt.setp(ax.get_xticklabels(), rotation=0)

            # Add text annotations
            for i in range(len(model_names)):
                for j in range(len(forecast_lengths)):
                    text = ax.text(j, i, f'{data_matrix[i, j]:.2f}',
                                   ha="center", va="center", color="black", fontsize=9)

            ax.set_xlabel('Forecast Length (days)')
            ax.set_ylabel('Model')
            ax.set_title(f'{ticker} - {metric_name} Heatmap (Normalized by Row)\nDarker Red = Worse, Green = Better')

            fig.colorbar(im, ax=ax, label='Normalized Performance')
            plt.tight_layout()

            filename = f"evaluation_{ticker}_heatmap_{metric_name.lower()}_returns_no_dates_filled.png"
            plt.savefig(filename, dpi=100, bbox_inches='tight')
            print(f"Saved: {filename}")
            plt.close()

        # 3. Baseline comparison (% difference from baseline)
        fig, axes = plt.subplots(1, 4, figsize=(25, 5))
        fig.suptitle(f'{ticker} - Performance vs Baseline (Naive Drift)', fontsize=14, fontweight='bold')

        for idx, (metric, label) in enumerate(zip(metrics, metric_labels)):
            print(axes)
            ax = axes[idx]

            model_names = [m for m in sorted(results[forecast_lengths[0]].keys())
                           if "Baseline" not in m]

            baseline_values = [results[fl][next(m for m in results[fl].keys() if "Baseline" in m)][metric]
                               for fl in forecast_lengths]

            x = np.arange(len(forecast_lengths))
            width = 0.08

            for i, model_name in enumerate(model_names):
                values = [results[fl][model_name][metric] for fl in forecast_lengths]
                pct_diff = [(v - b) / b * 100 for v, b in zip(values, baseline_values)]
                offset = width * (i - len(model_names) / 2)

                colors = ['green' if p < 0 else 'orange' for p in pct_diff]
                ax.bar(x + offset, pct_diff, width, label=model_name, color=colors)

            ax.axhline(y=0, color='red', linestyle='--', linewidth=2, label='Baseline')
            ax.set_xlabel('Forecast Length (days)')
            ax.set_ylabel('% Difference from Baseline')
            ax.set_title(f'{label} vs Baseline\n(Negative = Better than Baseline)')
            ax.set_xticks(x)
            ax.set_xticklabels(forecast_lengths)
            ax.legend(fontsize=8, loc='upper left')
            ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        filename = f"evaluation_{ticker}_vs_baseline_returns_no_dates_filled.png"
        plt.savefig(filename, dpi=100, bbox_inches='tight')
        print(f"Saved: {filename}")
        plt.close()


if __name__ == "__main__":
    tickers = ["AAPL.US", "MSFT.US", "GOOGL.US", "AMZN.US"]
    forecast_lengths = [5, 10, 15, 20]
    create_evaluation_report(tickers, forecast_lengths)