import argparse
import os
from datetime import date, timedelta
import pandas as pd
import numpy as np
from datetime import date, timedelta
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
import numpy as np

from Features import build_full_features
from symbol_collector import get_sp500_at_date
from XGBoostInvestor import XGBoostInvestor
from Metrics import analyze_portfolio, create_visualizations, export_metrics


def simulate_year(year, look_back, precompute=True, data_dir='./', model_dir='./',
                  pred_dir='./'):

    yearly_features = None
    yearly_targets = None
    model_path = f'{model_dir}xgboost_investor_{year}'

    print(f"\n{'=' * 60}")
    print(f"{year} - COLLECTING DATA")

    for i in reversed(range(look_back)):
        feature_file_save = f"{data_dir}feature_dataset_{year - 1 - i}.csv"
        target_file_save = f"{data_dir}target_series_{year - 1 - i}.csv"

        if not (precompute and os.path.isfile(feature_file_save) and os.path.isfile(target_file_save)):
            tickers = get_sp500_at_date(date(year - 1 - i, 1, 1))
            features, target = build_full_features(
                tickers,
                start_date=date(year - 1 - i, 1, 1),
                end_date=date(year - i, 1, 1),
                save_fred=False,
                threads=False
            )
            target.to_csv(target_file_save, index=False)
            features.to_csv(feature_file_save, index=False)

        features = pd.read_csv(feature_file_save)
        target = pd.read_csv(target_file_save)

        if yearly_features is None:
            yearly_features = features
            yearly_targets = target
        else:
            yearly_features = pd.concat([yearly_features, features], ignore_index=True)
            yearly_targets = pd.concat([yearly_targets, target], ignore_index=True)


    model = XGBoostInvestor()

    # Load existing model or train new one
    if os.path.isfile(model_path + "_model.pkl"):
        print(f"Loading existing model from {model_path}")
        model.load(model_path)
    else:
        print(f"{year} - PREPROCESSING DATA")
        X_train, y_train = model.prepare_training(yearly_features, yearly_targets)
        print(f"{year} - TRAINING MODEL")
        print(f"\t{len(X_train)} Training Samples")
        model.train(X_train, y_train)

        # Calibrate on last 20% of training data
        split_idx = int(len(X_train) * .8)
        model.calibrate(X_train[split_idx:], y_train[split_idx:])

        model.save(f'{model_dir}xgboost_investor_{year}')


    feature_file_save = f"{data_dir}feature_dataset_{year}.csv"
    target_file_save = f"{data_dir}target_series_{year}.csv"

    if not (precompute and os.path.isfile(feature_file_save) and os.path.isfile(target_file_save)):
        print(f"{year} - COLLECTING PREDICTION DATA")
        tickers = get_sp500_at_date(date(year, 1, 1))
        features, target = build_full_features(
            tickers,
            start_date=date(year, 1, 1),
            end_date=date(year + 1, 1, 1),
            save_fred=False,
            threads=False
        )
        target.to_csv(target_file_save, index=False)
        features.to_csv(feature_file_save, index=False)

    features = pd.read_csv(feature_file_save)
    target = pd.read_csv(target_file_save)

    X_test, y_test, dates, ticker_list = model.prepare_predictions(features, target)
    print(f"{year} - PREDICTING")
    print(f"\t{len(X_test)} Testing Samples")
    y_preds = model.predict(X_test)
    y_test = y_test.flatten()

    output = pd.DataFrame({
        "y_true": y_test,
        "y_pred": y_preds,
        "dates": dates,
        "tickers": ticker_list
    })
    output.to_csv(f"{pred_dir}predictions_{year}.csv")

    err = y_test - y_preds
    metrics_dict = {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "R2": float(1 - np.sum(err ** 2) / np.sum((y_test - y_test.mean()) ** 2)),
        "Directional_Accuracy": float(np.mean(np.sign(y_test) == np.sign(y_preds))),
        "Corr": float(np.corrcoef(y_test, y_preds)[0, 1]),
    }
    print("\nPrediction Metrics:")
    for k, v in metrics_dict.items():
        print(f"  {k}: {v:.4f}")

def trade(year, save_dir="./"):

    predictions = pd.read_csv(f"{save_dir}predictions_{year}.csv")
    predictions = predictions.sort_values(by="dates")

    starting_portfolio_value = 100000
    starting_date = date(year, 1, 1)
    ending_date = date(year + 1, 1, 1)

    portfolio1 = [(starting_date, starting_portfolio_value)]
    portfolio2 = [(starting_date, starting_portfolio_value)]
    portfolio3 = [(starting_date, starting_portfolio_value)]
    portfolio4 = [(starting_date, starting_portfolio_value)]
    portfolio5 = [(starting_date, starting_portfolio_value)]
    portfolio6 = [(starting_date, starting_portfolio_value)]
    portfolio7 = [(starting_date, starting_portfolio_value)]
    portfolio8 = [(starting_date, starting_portfolio_value)]
    portfolio9 = [(starting_date, starting_portfolio_value)]
    portfolio10 = [(starting_date, starting_portfolio_value)]
    portfolio11 = [(starting_date, starting_portfolio_value)]
    portfolio12 = [(starting_date, starting_portfolio_value)]
    portfolio13 = [(starting_date, starting_portfolio_value)]
    portfolio14 = [(starting_date, starting_portfolio_value)]




    current_day = starting_date

    while current_day < ending_date:
        todays_predictions = predictions[predictions['dates'] == str(current_day)]

        if todays_predictions.empty:
            current_day += timedelta(days=1)
            continue

        #Strategy 1 - top 20 predictions
        top_n = todays_predictions.nlargest(20, 'y_pred')
        true_returns = np.array(top_n['y_true'].values) + 1
        new_value = (true_returns * (portfolio1[-1][1] / len(true_returns) * .9998)).sum()
        portfolio1.append((current_day, new_value))

        #Strategy  2- top 15 positions
        top_n = todays_predictions.nlargest(15, 'y_pred')
        true_returns = np.array(top_n['y_true'].values) + 1
        new_value = (true_returns * (portfolio2[-1][1] / len(true_returns) * .9998)).sum()
        portfolio2.append((current_day, new_value))

        #Strategy 3 - top 10 positions
        top_n = todays_predictions.nlargest(10, 'y_pred')
        true_returns = np.array(top_n['y_true'].values) + 1
        new_value = (true_returns * (portfolio3[-1][1] / len(true_returns) * .9998)).sum()
        portfolio3.append((current_day, new_value))

        #Strategy 4 - top 5 positions
        top_n = todays_predictions.nlargest(5, 'y_pred')
        true_returns = np.array(top_n['y_true'].values) + 1
        new_value = (true_returns * (portfolio4[-1][1] / len(true_returns) * .9998)).sum()
        portfolio4.append((current_day, new_value))

        #Strategy 5 - invest in everything positive (zero threshold)
        positive_preds = todays_predictions[todays_predictions['y_pred'] > 0]
        if len(positive_preds) == 0:
            portfolio5.append((current_day, portfolio5[-1][1]))
        else:
            true_returns = np.array(positive_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio5[-1][1] / len(true_returns) * .9998)).sum()
            portfolio5.append((current_day, new_value))

        #Strategy 6 - invest in everything threshold=-.01
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > -.01]
        if len(threshold_preds) == 0:
            portfolio6.append((current_day, portfolio6[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio6[-1][1] / len(true_returns) * .9998)).sum()
            portfolio6.append((current_day, new_value))

        #Strategy 7 - invest in everything threshold=-.001
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > -.001]
        if len(threshold_preds) == 0:
            portfolio7.append((current_day, portfolio7[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio7[-1][1] / len(true_returns) * .9998)).sum()
            portfolio7.append((current_day, new_value))

        # Strategy 8 - invest in everything threshold=.001
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > .001]
        if len(threshold_preds) == 0:
            portfolio8.append((current_day, portfolio8[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio8[-1][1] / len(true_returns) * .9998)).sum()
            portfolio8.append((current_day, new_value))

        # Strategy 9 - invest in everything threshold=.01
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > .01]
        if len(threshold_preds) == 0:
            portfolio9.append((current_day, portfolio9[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio9[-1][1] / len(true_returns) * .9998)).sum()
            portfolio9.append((current_day, new_value))

        # Strategy 10 - invest in everything threshold=.02
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > .02]
        if len(threshold_preds) == 0:
            portfolio10.append((current_day, portfolio10[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio10[-1][1] / len(true_returns) * .9998)).sum()
            portfolio10.append((current_day, new_value))

        # Strategy 11 - invest in everything threshold=.03
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > .03]
        if len(threshold_preds) == 0:
            portfolio11.append((current_day, portfolio11[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio11[-1][1] / len(true_returns) * .9998)).sum()
            portfolio11.append((current_day, new_value))

        # Strategy 12 - always take top 10% of signals
        threshold = todays_predictions['y_pred'].quantile(0.9)
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > threshold]
        if len(threshold_preds) == 0:
            portfolio12.append((current_day, portfolio12[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio12[-1][1] / len(true_returns) * .9998)).sum()
            portfolio12.append((current_day, new_value))

        # Strategy 13 - volatility adjusted threshold
        vol = todays_predictions['y_pred'].std()
        threshold = 0.5 * vol
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > threshold]
        if len(threshold_preds) == 0:
            portfolio13.append((current_day, portfolio13[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio13[-1][1] / len(true_returns) * .9998)).sum()
            portfolio13.append((current_day, new_value))

        # Strategy 14 - volatility + quantile threshold approach
        threshold = max(0.01, todays_predictions['y_pred'].quantile(0.9))
        threshold_preds = todays_predictions[todays_predictions['y_pred'] > threshold]
        if len(threshold_preds) == 0:
            portfolio14.append((current_day, portfolio14[-1][1]))
        else:
            true_returns = np.array(threshold_preds['y_true'].values) + 1
            new_value = (true_returns * (portfolio14[-1][1] / len(true_returns)* .9998)).sum()
            portfolio14.append((current_day, new_value))


        current_day += timedelta(days=1)



    return [portfolio1, portfolio2, portfolio3, portfolio4, portfolio5, portfolio6, portfolio7, portfolio8, portfolio9, portfolio10, portfolio11, portfolio12, portfolio13, portfolio14]


def metrics(year, portfolio, save_dir="./", strategy=None):
    if strategy is not None:
        label = f"_strategy_{strategy}"
    else:
        label = ""

    df, metrics_data = analyze_portfolio(portfolio)
    create_visualizations(df, year, save_dir, label)
    export_metrics(metrics_data, year, save_dir,label)


def trade_portfolio15(year, save_dir="./"):

    predictions = pd.read_csv(f"{save_dir}predictions_{year}.csv")
    predictions = predictions.sort_values(by="dates")

    starting_portfolio_value = 100000
    starting_date = date(year, 1, 1)
    ending_date = date(year + 1, 1, 1)
    trades_made = []

    portfolio_15 = [(starting_date, starting_portfolio_value)]

    # Decision matrix: market regime + vol regime -> strategies to use
    strategy_rules = {
        ('bull_strong', 'low'): 6,
        ('bull_strong', 'normal'): 6,
        ('bull_strong', 'high'): 9,
        ('bull', 'low'): 6,
        ('bull', 'normal'): 6,
        ('bull', 'high'): 9,
        ('bull_weak', 'low'): 1,
        ('bull_weak', 'normal'): 1,
        ('bull_weak', 'high'): 4,
        ('bear_mild', 'low'): 1,
        ('bear_mild', 'normal'): 4,
        ('bear_mild', 'high'): 4,
        ('bear_severe', 'low'): 1,
        ('bear_severe', 'normal'): 4,
        ('bear_severe', 'high'): 4,
    }

    portfolio_history = [starting_portfolio_value]
    portfolio_peaks = [starting_portfolio_value]
    current_day = starting_date
    days_traded = 0

    while current_day < ending_date:
        todays_predictions = predictions[predictions['dates'] == str(current_day)]
        if todays_predictions.empty:
            current_day += timedelta(days=1)
            continue

        # Detect market regime every trading month
        if days_traded % 20 == 0 and days_traded > 0:
            current_value = portfolio_15[-1][1]
            portfolio_history.append(current_value)

            # Return (YTD or rolling)
            recent_return_pct = (
                (portfolio_history[-1] - portfolio_history[-20]) / portfolio_history[-20] * 100
                if len(portfolio_history) >= 20
                else (current_value - starting_portfolio_value) / starting_portfolio_value * 100
            )

            # Volatility (20-day rolling)
            if len(portfolio_history) > 20:
                returns_20 = np.diff(portfolio_history[-21:]) / np.array(portfolio_history[-21:-1])
                volatility_pct = np.std(returns_20) * np.sqrt(252) * 100
            else:
                volatility_pct = 5.0

            # Drawdown
            peak = max(portfolio_peaks)
            drawdown_pct = (current_value - peak) / peak * 100 if peak > 0 else 0

            # Classify regimes
            if recent_return_pct > 20:
                market_regime = 'bull_strong'
            elif recent_return_pct > 10:
                market_regime = 'bull'
            elif recent_return_pct > 0:
                market_regime = 'bull_weak'
            elif recent_return_pct > -5:
                market_regime = 'bear_mild'
            else:
                market_regime = 'bear_severe'

            if volatility_pct < 5:
                vol_regime = 'low'
            elif volatility_pct < 10:
                vol_regime = 'normal'
            else:
                vol_regime = 'high'

            # Risk adjustment
            if drawdown_pct < -15:
                primary_strategy = 6
            else:
                regime_key = (market_regime, vol_regime)
                primary_strategy = strategy_rules.get(regime_key, 6)
        else:
            # Use last determined strategy or default
            primary_strategy = 6 if 'primary_strategy' not in locals() else primary_strategy

        # Execute selected strategy (use first in list)
        selected_strategy = primary_strategy
        current_value = portfolio_15[-1][1]

        # Simple strategy execution
        if selected_strategy == 1:
            top_n = todays_predictions.nlargest(20, 'y_pred')
        elif selected_strategy == 2:
            top_n = todays_predictions.nlargest(15, 'y_pred')
        elif selected_strategy == 3:
            top_n = todays_predictions.nlargest(10, 'y_pred')
        elif selected_strategy == 4:
            top_n = todays_predictions.nlargest(5, 'y_pred')
        elif selected_strategy == 5:
            top_n = todays_predictions[todays_predictions['y_pred'] > 0]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 6:
            top_n = todays_predictions[todays_predictions['y_pred'] > -0.01]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 7:
            top_n = todays_predictions[todays_predictions['y_pred'] > -0.001]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 8:
            top_n = todays_predictions[todays_predictions['y_pred'] > 0.001]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 9:
            top_n = todays_predictions[todays_predictions['y_pred'] > 0.01]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 10:
            top_n = todays_predictions[todays_predictions['y_pred'] > 0.02]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 11:
            top_n = todays_predictions[todays_predictions['y_pred'] > 0.03]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 12:
            threshold = todays_predictions['y_pred'].quantile(0.9)
            top_n = todays_predictions[todays_predictions['y_pred'] > threshold]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        elif selected_strategy == 13:
            vol = todays_predictions['y_pred'].std()
            threshold = 0.5 * vol
            top_n = todays_predictions[todays_predictions['y_pred'] > threshold]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue
        else:  # Strategy 14
            threshold = max(0.01, todays_predictions['y_pred'].quantile(0.9))
            top_n = todays_predictions[todays_predictions['y_pred'] > threshold]
            if len(top_n) == 0:
                portfolio_15.append((current_day, current_value))
                current_day += timedelta(days=1)
                days_traded += 1
                continue

        # Calculate new portfolio value
        if len(top_n) > 0:
            true_returns = np.array(top_n['y_true'].values) + 1
            new_value = (true_returns * (current_value / len(true_returns) * .9998)).sum()
            trades_made.append({'date': current_day, 'ticker': top_n['tickers'].values, 'pred': top_n['y_pred'].values, 'true': true_returns})
        else:
            new_value = current_value

        portfolio_15.append((current_day, new_value))
        portfolio_peaks.append(max(portfolio_peaks[-1], new_value))

        current_day += timedelta(days=1)
        days_traded += 1

    pd.DataFrame(trades_made).to_csv(f'{save_dir}portfolio_15_trades_{year}.csv', index=False)
    return portfolio_15

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=10)
    parser.add_argument("--use-precomputed-df", type=bool, default=True)
    parser.add_argument("--save-directory", type=str, default="./backtest-enhanced/")
    args = parser.parse_args()

    # Create save directories
    if not os.path.exists(args.save_directory):
        os.makedirs(args.save_directory)

    prediction_dir = f"{args.save_directory}/preds/"
    if not os.path.exists(prediction_dir):
        os.makedirs(prediction_dir)

    data_dir = f"{args.save_directory}/data/"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    results_dir = f"{args.save_directory}/results/"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    models_dir = f"{args.save_directory}/models/"
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    years = [2019,2020, 2021, 2022, 2023, 2024, 2025, 2026]
    for year in years:

        # Train/predict
        simulate_year(
            year,
            look_back=args.lookback,
            precompute=args.use_precomputed_df,
            data_dir=data_dir,
            model_dir=models_dir,
            pred_dir=prediction_dir
        )

        # Load model
        model_path = f'{models_dir}xgboost_investor_{year}'
        investor = XGBoostInvestor()
        investor.load(model_path)

        # Trade with both strategies
        print(f"\nExecuting trading strategies for {year}...")
        portfolios = trade(year, save_dir=prediction_dir)

        print(f"  Portfolio15: Dynamic Adaptive Strategy...")
        portfolios.append(trade_portfolio15(year, save_dir=prediction_dir))

        for i, portfolio in enumerate(portfolios):
            # Calculate metrics
            metrics(year, portfolio, results_dir, strategy=i+1)