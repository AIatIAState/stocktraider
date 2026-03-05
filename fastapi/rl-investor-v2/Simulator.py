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

def trade(year, save_dir="./"):
    predictions = pd.read_csv(f"{save_dir}predictions_{year}.csv")
    predictions = predictions.sort_values(by="dates")

    starting_portfolio_value = 100000
    starting_date = date(year, 1, 1)
    ending_date = date(year + 1, 1, 1)


    portfolio1 =[(starting_date, starting_portfolio_value)]
    n = 30

    portfolio2 = [(starting_date, starting_portfolio_value)]
    min_return = .005
    max_investments = 30

    portfolio3 = [(starting_date, starting_portfolio_value)]


    current_day = starting_date


    while current_day < ending_date:
        todays_predictions = predictions[predictions['dates'] == current_day.strftime("%Y-%m-%d")]
        if todays_predictions.empty:
            current_day += timedelta(days=1)
            continue

        # Strategy 1: Equal weights on top n predictions (ignores confidence)
        top_n_prediction_rows = todays_predictions.nlargest(n, 'y_pred')
        true_returns = np.array(top_n_prediction_rows['y_true'].values) + 1
        new_portfolio_value = (true_returns * (portfolio1[-1][1] / n)).sum()
        portfolio1.append((current_day, new_portfolio_value))

        # Strategy 2: Equal weights with threshold
        candidates = todays_predictions[todays_predictions['y_pred'] > min_return]
        if not candidates.empty:
            candidates = candidates.nlargest(max_investments, 'y_pred')
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio1[-1][1] / len(true_returns))).sum()
            portfolio2.append((current_day, new_portfolio_value))

        #Strategy 3: Weighted top predictions
        candidates = todays_predictions[todays_predictions['y_pred'] > min_return]
        if not candidates.empty:
            candidates = candidates.nlargest(max_investments, 'y_pred')
            weights = np.array(candidates['y_pred'] / candidates['y_pred'].sum())
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (weights * portfolio1[-1][1])).sum()
            portfolio3.append((current_day, new_portfolio_value))




        current_day += timedelta(days=1)

    portfolios = [portfolio1, portfolio2, portfolio3]
    sp_returns = {2019: 131490, 2020: 118400, 2021: 128710, 2022: 91990, 2023: 126290, 2024: 125020, 2025: 117880}
    print(f"{year} - S&P500: {sp_returns[year]}")
    for i, portfolio in enumerate(portfolios):
        print(f"{year} - Portfolio {i}: {portfolio[-1][1]}")



    return portfolios





if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=5)
    parser.add_argument("--gpu", type=bool, default=True)
    parser.add_argument("--use-precomputed-df", type=bool, default=True)
    args = parser.parse_args()

    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    for year in years:
        simulate_year(year, look_back=args.lookback, precompute=args.use_precomputed_df, save_dir="./prediction_simulation/")
        trade(year, save_dir="./prediction_simulation/")

