import argparse
import os
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
                save_fred=True
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
        split_idx = int(len(X_train) * 0.8)
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
            save_fred=True
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

    portfolio = [(starting_date, starting_portfolio_value)]


    current_day = starting_date

    while current_day < ending_date:
        todays_predictions = predictions[predictions['dates'] == str(current_day)]

        if todays_predictions.empty:
            current_day += timedelta(days=1)
            continue

        top_n = todays_predictions.nlargest(20, 'y_pred')
        true_returns = np.array(top_n['y_true'].values) + 1
        new_value = (true_returns * (portfolio[-1][1] / len(true_returns))).sum()
        portfolio.append((current_day, new_value))

        current_day += timedelta(days=1)

    return portfolio


def metrics(year, portfolio, save_dir="./"):

    df, metrics_data = analyze_portfolio(portfolio)
    create_visualizations(df, year, save_dir)
    export_metrics(metrics_data, year, save_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=2)
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

    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

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
        portfolio = trade(year, save_dir=prediction_dir)


        # Calculate metrics
        metrics(year, portfolio, results_dir)