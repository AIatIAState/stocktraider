import pickle
from random import shuffle

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler
import warnings

from xgboost import XGBRegressor

warnings.filterwarnings('ignore')
class XGBoostInvestor:
    def __init__(self):

        self.model = None
        self.x_scaler = RobustScaler()
        self.y_scaler = RobustScaler()

        self.history = {
            'train_loss': [],
            'val_loss': [],
            'best_epoch': 0,
            'best_val_loss': float('inf')
        }

        print(f"XGBoostInvestor initialized")

    def prepare_predictions(self, features_df, target_series):
        dates = np.array(features_df["Date"].values)
        tickers = np.array(features_df["ticker"].values)

        features_df = features_df.reset_index(drop=True)
        features_df = features_df.drop(columns=['Date', 'ticker'])

        if len(self.constant_cols) > 0:
            print("Removing columns: ", self.constant_cols)
            features_df = features_df.drop(columns=self.constant_cols)

        if isinstance(target_series, np.ndarray):
            target_series = pd.Series(target_series, index=features_df.index).reset_index(drop=True)
        else:
            target_series = target_series.reset_index(drop=True)

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
        features_df = features_df.reset_index(drop=True)
        features_df = features_df.drop(columns=['Date', 'ticker'])

        self.constant_cols = features_df.columns[features_df.nunique() <= 1]

        if len(self.constant_cols) > 0:
            print("Removing columns: ", self.constant_cols)
            features_df = features_df.drop(columns=self.constant_cols)

        if isinstance(target_series, np.ndarray):
            target_series = pd.Series(target_series, index=features_df.index).reset_index(drop=True)
        else:
            target_series = target_series.reset_index(drop=True)

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
        y = np.nan_to_num(y, posinf=0, neginf=0)

        # Shuffle data (maintain alignment with same seed)
        rng = np.random.default_rng(42)
        shuffle_idx = rng.permutation(len(X))
        X = X[shuffle_idx]
        y = y[shuffle_idx]

        print(f"SCALING & SHUFFLING COMPLETE")
        print(f"Final training shape: {X.shape}")
        print(f"Rows retained: {X.shape[0]:,} ({(X.shape[0] / original_shape[0]) * 100:.2f}%)")

        return X, y


    def build_model(self):
        self.model = XGBRegressor(
            loss='squared_error',
            learning_rate=0.1,
            n_estimators=100,
            max_depth=5,
            subsample=0.8,
            random_state=42,
            verbose=0
        )

    def train(self, X_train, y_train):
        if self.model == None:
            self.build_model()

        assert np.isfinite(X_train).all()
        assert np.isfinite(y_train).all()

        self.model.fit(X_train, y_train)

    def predict(self, X_test):
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")
        return self.model.predict(X_test)


    def save(self, filepath):
        """Save entire model for later use."""
        self.model.save_model(filepath + '_model.bin')

        with open(filepath + '_xscaler.pkl', 'wb') as file:
            pickle.dump(self.x_scaler, file, protocol=pickle.HIGHEST_PROTOCOL)

        with open(filepath + '_yscaler.pkl', 'wb') as file:
            pickle.dump(self.y_scaler, file, protocol=pickle.HIGHEST_PROTOCOL)

        with open(filepath + '_constant_cols.pkl', 'wb') as file:
            pickle.dump(self.constant_cols, file, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, filepath):
        """Load entire model from checkpoint."""
        loaded_model = XGBRegressor()
        loaded_model.load_model(filepath + '_model.bin')
        self.model = loaded_model

        with open(filepath + '_xscaler.pkl', 'rb') as file:
            self.x_scaler = pickle.load(file)

        with open(filepath + '_yscaler.pkl', 'rb') as file:
            self.y_scaler = pickle.load(file)

        with open(filepath + '_constant_cols.pkl', 'rb') as file:
            self.constant_cols = pickle.load(file)

