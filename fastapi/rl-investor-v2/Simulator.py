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

def simulate_year(year, look_back, retrain, precompute, data_dir, model_dir, pred_dir):

    yearly_features = None
    yearly_targets = None
    model_path = f'{model_dir}xgboost_investor_{year}'

    print(f"{year} - COLLECTING DATA")
    for i in reversed(range(look_back)):

        feature_file_save = f"{data_dir}feature_dataset_{year - 1 - i}.csv"
        target_file_save = f"{data_dir}target_series_{year - 1 - i}.csv"

        if not retrain and os.path.isfile(model_path + "_model.pkl"):
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

    if not retrain and os.path.isfile(model_path + "_model.pkl"):
        model.load(model_path)

    else:
        X_train, y_train = model.prepare_training(yearly_features, yearly_targets)

        print(f"{year} - TRAINING MODEL")
        print(f"{len(X_train)} Training Samples")
        model.train(X_train, y_train)
        model.save(f'{model_dir}xgboost_investor_{year}')

    print(f"{year} - COLLECTING PREDICTION DATA")

    feature_file_save = f"{data_dir}feature_dataset_{year}.csv"
    target_file_save = f"{data_dir}target_series_{year}.csv"

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
    y_preds = model.predict(X_test)
    y_test = y_test.flatten()

    output = pd.DataFrame({"y_true": y_test, "y_pred": y_preds, "dates": dates, "tickers": ticker_list})
    output.to_csv(f"{pred_dir}predictions_{year}.csv")

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


    portfolio0 = {
        "name": "equal_weights_top_10",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio1 = {
        "name": "equal_weights_top_30",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }

    portfolio2 = {
        "name": "equal_weights_thresholded_top_30",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }

    portfolio3 = {
        "name": "weighted_000_thresholded_top_10",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio4 = {
        "name": "weighted_000_thresholded_top_30",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio5 = {
        "name": "weighted_000_thresholded_top_50",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio6 = {
        "name": "weighted_000_thresholded_all",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio9 = {
        "name": "015_thresholded_top_10",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio10 = {
        "name": "sortino_weighted_005_threshold_top_30",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio11 = {
        "name": "005_to_015_acceptable_theshold_top_30",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio12 = {
        "name": "squared_weighted_010_thresholded_top_50",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio13 =  {
        "name": "equal_weights_top_20",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio14 = {
        "name": "threshold_0_equal_weights_top_10",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio15 = {
        "name": "threshold_0_equal_weights_top_20",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio16 = {
        "name": "threshold_0_equal_weights_top_30",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    portfolio17 = {
        "name": "equal_weights_threshold_0",
        "portfolio":[(starting_date, starting_portfolio_value)]
    }
    weighted_portfolios = [portfolio3, portfolio4, portfolio5, portfolio6]


    current_day = starting_date


    while current_day < ending_date:
        todays_predictions = predictions[predictions['dates'] == current_day.strftime("%Y-%m-%d")]
        if todays_predictions.empty:
            current_day += timedelta(days=1)
            continue

        # Strategy 0: Equal weights on top 10 predictions (ignores confidence)
        top_n_prediction_rows = todays_predictions.nlargest(10, 'y_pred')
        true_returns = np.array(top_n_prediction_rows['y_true'].values) + 1
        new_portfolio_value = (true_returns * (portfolio0['portfolio'][-1][1] / 30)).sum()
        portfolio0['portfolio'].append((current_day, new_portfolio_value))


        # Strategy 1: Equal weights on top 30 predictions (ignores confidence)
        top_n_prediction_rows = todays_predictions.nlargest(30, 'y_pred')
        true_returns = np.array(top_n_prediction_rows['y_true'].values) + 1
        new_portfolio_value = (true_returns * (portfolio1['portfolio'][-1][1] / 30)).sum()
        portfolio1['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 2: Equal weights with threshold
        candidates = todays_predictions[todays_predictions['y_pred'] > .005]
        if not candidates.empty:
            candidates = candidates.nlargest(30, 'y_pred')
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio2['portfolio'][-1][1] / len(true_returns))).sum()
            portfolio2['portfolio'].append((current_day, new_portfolio_value))

        #Strategy 3-6: Weighted top predictions
        for  portfolio, top_n in zip(weighted_portfolios, [10, 30, 50, 1000]):
            candidates = todays_predictions[todays_predictions['y_pred'] > 0]
            if not candidates.empty:
                candidates = candidates.nlargest(top_n, 'y_pred')
                weights = np.array(candidates['y_pred'] / candidates['y_pred'].sum())
                true_returns = np.array(candidates['y_true'].values) + 1
                new_portfolio_value = (true_returns * (weights * portfolio['portfolio'][-1][1])).sum()
                portfolio['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 9: Ultra-high confidence threshold (0.15%)
        candidates = todays_predictions[todays_predictions['y_pred'] > .0015]
        if not candidates.empty:
            candidates = candidates.nlargest(10, 'y_pred')
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio9['portfolio'][-1][1] / len(true_returns))).sum()
            portfolio9['portfolio'].append((current_day, new_portfolio_value))
        else:
            portfolio9['portfolio'].append((current_day, portfolio9['portfolio'][-1][1]))

        # Strategy 10: Sortino-adjusted weighting (penalize downside)
        candidates = todays_predictions[todays_predictions['y_pred'] > .005]
        if not candidates.empty:
            candidates = candidates.nlargest(30, 'y_pred')
            # Use softmax-like weighting but adjusted for positive predictions
            confidence = np.array(candidates['y_pred'].values)
            weights = np.exp(confidence * 5) / np.exp(confidence * 5).sum()  # Exponential weighting
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (weights * portfolio10['portfolio'][-1][1])).sum()
            portfolio10['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 11: Mean-reversion/Contrarian (bet against extreme predictions)
        candidates = todays_predictions.copy()
        if not candidates.empty:
            # Filter for moderate predictions (neither too high nor too low)
            median_pred = candidates['y_pred'].median()
            candidates = candidates[
                (candidates['y_pred'] > median_pred * 0.5) &
                (candidates['y_pred'] < median_pred * 1.5)
                ].nlargest(30, 'y_pred')

            if not candidates.empty:
                true_returns = np.array(candidates['y_true'].values) + 1
                new_portfolio_value = (true_returns * (portfolio11['portfolio'][-1][1] / len(true_returns))).sum()
                portfolio11['portfolio'].append((current_day, new_portfolio_value))
            else:
                portfolio11['portfolio'].append((current_day, portfolio11['portfolio'][-1][1]))

        # Strategy 12: Confidence-squared weighting (amplify confidence differences)
        candidates = todays_predictions[todays_predictions['y_pred'] > .005]
        if not candidates.empty:
            candidates = candidates.nlargest(30, 'y_pred')
            confidence = np.array(candidates['y_pred'].values)
            weights = (confidence ** 2) / (confidence ** 2).sum()  # Square weighting
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (weights * portfolio12['portfolio'][-1][1])).sum()
            portfolio12['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 13: Equal weights on top 20 predictions (ignores confidence)
        top_n_prediction_rows = todays_predictions.nlargest(20, 'y_pred')
        true_returns = np.array(top_n_prediction_rows['y_true'].values) + 1
        new_portfolio_value = (true_returns * (portfolio13['portfolio'][-1][1] / 30)).sum()
        portfolio13['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 14: Equal weights with 0 threshold, top 10
        candidates = todays_predictions[todays_predictions['y_pred'] > 0]
        if not candidates.empty:
            candidates = candidates.nlargest(10, 'y_pred')
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio14['portfolio'][-1][1] / len(true_returns))).sum()
            portfolio14['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 15: Equal weights with 0 threshold, top 20
        candidates = todays_predictions[todays_predictions['y_pred'] > 0]
        if not candidates.empty:
            candidates = candidates.nlargest(20, 'y_pred')
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio15['portfolio'][-1][1] / len(true_returns))).sum()
            portfolio15['portfolio'].append((current_day, new_portfolio_value))

        # Strategy 16: Equal weights with 0 threshold, top 30
        candidates = todays_predictions[todays_predictions['y_pred'] > 0]
        if not candidates.empty:
            candidates = candidates.nlargest(30, 'y_pred')
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio16['portfolio'][-1][1] / len(true_returns))).sum()
            portfolio16['portfolio'].append((current_day, new_portfolio_value))
        current_day += timedelta(days=1)

        #Strategy 17: Equal Weights on all predictions
        candidates = todays_predictions[todays_predictions['y_pred'] > 0]
        if not candidates.empty:
            true_returns = np.array(candidates['y_true'].values) + 1
            new_portfolio_value = (true_returns * (portfolio17['portfolio'][-1][1] / len(true_returns))).sum()
            portfolio17['portfolio'].append((current_day, new_portfolio_value))
        current_day += timedelta(days=1)

    portfolios = [portfolio1, portfolio2] + weighted_portfolios + [portfolio9, portfolio10, portfolio11, portfolio12, portfolio13, portfolio14, portfolio15, portfolio16]
    return portfolios

def metrics(year, portfolios, save_dir="./"):

    results_dir = f"{save_dir}/metrics_{year}/"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    for portfolio in portfolios:

        metrics_dir = f"{results_dir}/{portfolio['name']}/"
        if not os.path.exists(metrics_dir):
            os.makedirs(metrics_dir)

        df, metrics = analyze_portfolio(portfolio['portfolio'])
        create_visualizations(df, portfolio['name'], year, metrics_dir)
        export_metrics(metrics, portfolio['name'], year, metrics_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback", type=int, default=1)
    parser.add_argument("--retrain", type=bool, default=True)
    parser.add_argument("--use-precomputed-df", type=bool, default=True)
    parser.add_argument("--save-directory", type=str, default="./backtest-1-year-lookback/")
    args = parser.parse_args()

    #Create save directory
    if not os.path.exists(args.save_directory):
        os.makedirs(args.save_directory)

    #Create prediction save directory
    prediction_dir = f"{args.save_directory}/preds/"
    if not os.path.exists(prediction_dir):
        os.makedirs(prediction_dir)


    #Create training/testing save directory
    data_dir = f"{args.save_directory}/data/"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    #Create results save directory

    results_dir = f"{args.save_directory}/results/"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # Create models save directory

    models_dir = f"{args.save_directory}/models/"
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    for year in years:
        simulate_year(year, look_back=args.lookback, precompute=args.use_precomputed_df, retrain=args.retrain, data_dir=data_dir, model_dir=models_dir, pred_dir=prediction_dir)
        portfolios = trade(year, save_dir=prediction_dir)
        metrics(year, portfolios, results_dir)