import argparse
import os
from datetime import date

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
import numpy as np

from Features import build_full_features
from symbol_collector import get_sp500_at_date
from XGBoostInvestor import XGBoostInvestor


def simulate_year(year, look_back=5, precompute=True, save_dir= "./"):

    if not save_dir != './':
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

    yearly_features = None
    yearly_targets = None
    model_path = f'{save_dir}xgboost_investor_{year}'

    print(f"{year} - COLLECTING DATA")
    for i in reversed(range(look_back)):

        feature_file_save = f"{save_dir}feature_dataset_{year - 1 - i}.csv"
        target_file_save = f"{save_dir}target_series_{year - 1 - i}.csv"

        if precompute and os.path.isfile(model_path + "_model.bin"):
            break
        if not (precompute and os.path.isfile(feature_file_save) and os.path.isfile(target_file_save)):
            tickers = get_sp500_at_date(date(year - 1 - i, 1, 1))
            tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
            features, target = build_full_features(tickers, start_date=date(year - 1 - i, 1, 1), end_date=date(year - i, 1, 1))

            target.to_csv(target_file_save, index=False)
            features.to_csv(feature_file_save, index=False)

        features = pd.read_csv(feature_file_save)
        target = pd.read_csv(target_file_save)

        if yearly_features is None:
            yearly_features = features
            yearly_targets = target

        else:
            yearly_features = pd.concat([yearly_features, features], ignore_index = True)
            yearly_targets = pd.concat([yearly_targets, target], ignore_index=True)

    print(f"{year} - PREPROCESSING DATA")

    model = XGBoostInvestor()

    if precompute and os.path.isfile(model_path + "_model.bin"):
        model.load(model_path)

    else:
        print(yearly_targets.head())
        X_train, y_train = model.prepare_training(yearly_features, yearly_targets)

        print(f"{year} - TRAINING MODEL")
        print(f"{len(X_train)} Training Samples")
        model.train(X_train, y_train)
        model.save(f'{save_dir}xgboost_investor_{year}')

    print(f"{year} - COLLECTING PREDICTION DATA")

    feature_file_save = f"{save_dir}feature_dataset_{year}.csv"
    target_file_save = f"{save_dir}target_series_{year}.csv"

    if not (precompute and os.path.isfile(feature_file_save) and os.path.isfile(target_file_save)):
        tickers = get_sp500_at_date(date(year, 1, 1))
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        features, target = build_full_features(tickers, start_date=date(year, 1, 1), end_date=date(year + 1, 1, 1))

        target.to_csv(target_file_save, index=False)
        features.to_csv(feature_file_save, index=False)

    features = pd.read_csv(feature_file_save)
    target = pd.read_csv(target_file_save)

    X_test, y_test, dates, ticker_list = model.prepare_predictions(features, target)
    print(f"{year} - PREDICTING")
    print(f"{len(X_test)} Testing Samples")
    y_preds = model.predict(X_test).flatten()
    y_test = y_test.flatten()

    output = pd.DataFrame({"y_true": y_test, "y_pred": y_preds, "dates": dates, "tickers": ticker_list})
    output.to_csv(f"{save_dir}predictions_{year}.csv")

    err = y_test - y_preds
    print({
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "R2": float(1 - np.sum(err ** 2) / np.sum((y_test - y_test.mean()) ** 2)),
        "Directional_Accuracy": float(np.mean(np.sign(y_test) == np.sign(y_preds))),
        "Corr": float(np.corrcoef(y_test, y_preds)[0, 1]),
    })

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=5)
    parser.add_argument("--gpu", type=bool, default=True)
    parser.add_argument("--use-precomputed-df", type=bool, default=True)
    args = parser.parse_args()

    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    for year in years:
        simulate_year(year, look_back=args.lookback, precompute=args.use_precomputed_df, save_dir="./prediction_simulation/")

