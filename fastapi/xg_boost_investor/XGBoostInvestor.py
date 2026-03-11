import pickle
from datetime import timedelta, date, datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import BaggingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import RobustScaler
import warnings

from xgboost import XGBRegressor

from xg_boost_investor.Features import build_full_features, get_feature_explanations
from xg_boost_investor.symbol_collector import get_sp500_at_date

warnings.filterwarnings('ignore')

class XGBoostInvestor:
    def __init__(self):

        self.model = None
        self.x_scaler = RobustScaler()
        self.y_scaler = RobustScaler()
        self.calibrator = IsotonicRegression(out_of_bounds='clip')

        self.constant_cols = None

        self.training_buffer_X = []
        self.training_buffer_y = []
        self.buffer_size = 100

    def prepare_predictions(self, features_df, target_series):
        dates = np.array(features_df["Date"].values)
        tickers = np.array(features_df["ticker"].values)

        if isinstance(target_series, np.ndarray):
            target_series = pd.Series(target_series, index=features_df.index).reset_index(drop=True)
        else:
            target_series = target_series.reset_index(drop=True)

        features_df.groupby("ticker").fillna(method="ffill")
        features_df = features_df.reset_index(drop=True)

        # Ensure temporal ordering for time series predictions (sort both features and values)
        features_df['values'] = target_series
        features_df = features_df.sort_values(by="Date")
        target_series = features_df['values']

        # remove illegal features, ticker, date, and target values
        features_df = features_df.drop(columns=['Date', 'ticker', 'values'])

        if len(self.constant_cols) > 0:
            features_df = features_df.drop(columns=self.constant_cols)


        features_bad = ~np.isfinite(features_df).all(axis=1)
        target_bad = ~np.isfinite(target_series.squeeze())
        rows_to_drop = features_bad | target_bad

        # Filter data
        valid_indices = ~rows_to_drop
        features_df = features_df[valid_indices].reset_index(drop=True)
        target_series = target_series[valid_indices].reset_index(drop=True)
        dates = dates[np.array(valid_indices).astype(bool)]
        tickers = tickers[np.array(valid_indices).astype(bool)]

        # Scale
        X = self.x_scaler.transform(features_df)
        X = np.nan_to_num(X, posinf=0, neginf=0)
        y = target_series.values
        y = np.nan_to_num(y, posinf=0, neginf=0)


        return X, y, dates, tickers


    def prepare_training(self, features_df, target_series):
        original_shape = features_df.shape

        if isinstance(target_series, np.ndarray):
            target_series = pd.Series(target_series, index=features_df.index).reset_index(drop=True)
        else:
            target_series = target_series.reset_index(drop=True)


        features_df.groupby("ticker").fillna(method="ffill")
        features_df = features_df.reset_index(drop=True)

        #Ensure temporal ordering for time series predictions (sort both features and values)
        features_df['values'] = target_series
        features_df = features_df.sort_values(by="Date")
        target_series = features_df['values']

        #remove illegal features, ticker, date, and target values
        features_df = features_df.drop(columns=['Date', 'ticker', 'values'])

        self.constant_cols = features_df.columns[features_df.nunique() <= 1]

        if len(self.constant_cols) > 0:
            print("Removing columns: ", self.constant_cols)
            features_df = features_df.drop(columns=self.constant_cols)


        features_bad = ~np.isfinite(features_df).all(axis=1)
        target_bad = ~np.isfinite(target_series.squeeze())
        rows_to_drop = features_bad | target_bad

        # Filter data
        valid_indices = ~rows_to_drop
        features_df = features_df[valid_indices].reset_index(drop=True)
        target_series = target_series[valid_indices].reset_index(drop=True)

        # Scale
        X = self.x_scaler.fit_transform(features_df)
        X = np.nan_to_num(X, posinf=0, neginf=0)
        y = target_series.values
        y = self.y_scaler.fit_transform(y.reshape(-1, 1)).ravel()
        y = np.nan_to_num(y, posinf=0, neginf=0)

        print(f"SCALING & SHUFFLING COMPLETE")
        print(f"Rows retained: {X.shape[0]:,} ({(X.shape[0] / original_shape[0]) * 100:.2f}%)")

        return X, y


    def build_model(self):
        self.model = BaggingRegressor(
            n_estimators=100,
            max_samples=.8,
            max_features=.8,
            bootstrap=True,
            n_jobs=-1,
            random_state=42,
            oob_score=True,
            estimator=XGBRegressor(
                loss='squared_error',
                learning_rate=0.05,
                n_estimators=10,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=0
            ),
        )

    def train(self, X_train, y_train):
        if self.model == None:
            self.build_model()

        assert np.isfinite(X_train).all()
        assert np.isfinite(y_train).all()

        self.model.fit(X_train, y_train)

    def calibrate(self, X_cal, y_cal):
        if self.model is None:
            raise ValueError("Model must be trained before calibration")

        raw_pred = self.model.predict(X_cal)
        self.calibrator = IsotonicRegression(out_of_bounds='clip')
        self.calibrator.fit(raw_pred, y_cal)

    def continuous_learn(self, X_batch, y_batch, retrain_threshold=100):
        self.training_buffer_X.extend(X_batch)
        self.training_buffer_y.extend(y_batch)

        should_retrain = len(self.training_buffer_X) >= retrain_threshold

        if should_retrain:
            print(f"Retraining on {len(self.training_buffer_X)} new samples...")
            X_retrain = np.array(self.training_buffer_X)
            y_retrain = np.array(self.training_buffer_y)

            self.train(X_retrain, y_retrain)

            # Clear buffer
            self.training_buffer_X = []
            self.training_buffer_y = []

        return should_retrain


    def predict(self, X_test):
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        X = self.x_scaler.transform(X_test)
        raw_predictions = self.model.predict(X)

        calibrated_pred = self.calibrator.predict(raw_predictions)

        unscaled_predictions = self.y_scaler.inverse_transform(calibrated_pred.reshape(-1, 1)).ravel()
        return unscaled_predictions

    def save(self, filepath):

        with open(filepath + '_model.pkl', 'wb') as file:
            pickle.dump(self.model, file, protocol=pickle.HIGHEST_PROTOCOL)
        with open(filepath + '_xscaler.pkl', 'wb') as file:
            pickle.dump(self.x_scaler, file, protocol=pickle.HIGHEST_PROTOCOL)
        with open(filepath + '_yscaler.pkl', 'wb') as file:
            pickle.dump(self.y_scaler, file, protocol=pickle.HIGHEST_PROTOCOL)
        with open(filepath + '_constant_cols.pkl', 'wb') as file:
            pickle.dump(self.constant_cols, file, protocol=pickle.HIGHEST_PROTOCOL)
        with open(filepath + '_calibrator.pkl', 'wb') as file:
            pickle.dump(self.calibrator, file, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath):
        with open(filepath + '_model.pkl', 'rb') as file:
            self.model = pickle.load(file)

        with open(filepath + '_xscaler.pkl', 'rb') as file:
            self.x_scaler = pickle.load(file)

        with open(filepath + '_yscaler.pkl', 'rb') as file:
            self.y_scaler = pickle.load(file)

        with open(filepath + '_constant_cols.pkl', 'rb') as file:
            self.constant_cols = pickle.load(file)

        with open(filepath + '_calibrator.pkl', 'rb') as file:
            self.calibrator = pickle.load(file)



def retrain_model(save_dir='./model_save', start_date=date.today()):

    quarterly_features = None
    quarterly_targets = None
    model_path = f'{save_dir}/model/xgboost_investor'
    data_dir = f'{save_dir}/data/'


    for i in reversed(range(8)):
        feature_file_save = f"{data_dir}feature_dataset_{i + 1}.csv"
        target_file_save = f"{data_dir}target_series_{i + 1}.csv"

        #Take chunks by quarters, collecting new tickers
        start_training_date = start_date - timedelta(days=((365 / 4) * (i + 1)))
        end_training_date = start_training_date + timedelta(days=((365 / 4)))

        tickers = get_sp500_at_date(start_training_date)
        features, target = build_full_features(
            tickers,
            start_date=start_training_date,
            end_date=end_training_date,
            alias_tag=i,
            save_fred=True
        )
        target.to_csv(target_file_save, index=False)
        features.to_csv(feature_file_save, index=False)

        features = pd.read_csv(feature_file_save)
        target = pd.read_csv(target_file_save)

        if quarterly_features is None:
            quarterly_features = features
            quarterly_targets = target
        else:
            quarterly_features = pd.concat([quarterly_features, features], ignore_index=True)
            quarterly_targets = pd.concat([quarterly_targets, target], ignore_index=True)


    model = XGBoostInvestor()

    X_train, y_train = model.prepare_training(quarterly_features, quarterly_targets)
    model.train(X_train, y_train)

    # Calibrate on last 20% of training data
    split_idx = int(len(X_train) * 0.8)
    model.calibrate(X_train[split_idx:], y_train[split_idx:])

    model.save(model_path)

if __name__ == "__main__":
    retrain_model()
    symbol = "AAPL"
    today = date.today()
    market_conditions, _ = build_full_features([symbol.replace(".US", "")], today, today)
    feature_explanations = get_feature_explanations()
    xgboost = XGBoostInvestor()
    xgboost.load('model_save/model/xgboost_investor')
    market_conditions_df = pd.DataFrame(market_conditions)
    market_conditions_df = market_conditions_df.reset_index(drop=True)
    X_test, _, _, _ = xgboost.prepare_predictions(market_conditions_df, pd.DataFrame([{'ret_1d': 0}]))
    prediction = xgboost.predict(X_test)

    print({"market_conditions": market_conditions.iloc[-1].to_dict(), "feature_explanations": feature_explanations,
            "prediction": float(prediction[0])})