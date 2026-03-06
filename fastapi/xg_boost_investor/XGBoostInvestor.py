import pickle
from random import shuffle

import numpy as np
import pandas as pd
from sklearn.ensemble import BaggingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import RobustScaler
import warnings

from xgboost import XGBRegressor

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

