"""Geopolitical Event Response Score (GERS) metric.

GERS = Directional Accuracy computed only on days where:
  |GPR_t - GPR_{t-1}| > 2 * std(GPR) over trailing 252 days

This is a novel metric for the paper that measures whether a model
correctly predicts direction on days of high geopolitical stress.
"""

import numpy as np
import pandas as pd


def compute_gers(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    gpr_series: pd.Series,
    sigma_multiplier: float = 2.0,
    trailing_window: int = 252,
) -> float:
    """Directional accuracy restricted to geopolitical shock days.

    Parameters
    ----------
    y_true:
        Actual returns (aligned by index with gpr_series).
    y_pred:
        Predicted returns (same alignment).
    gpr_series:
        Daily GPR index values (from Caldara-Iacoviello) aligned by date.
        Must have a DatetimeIndex.
    sigma_multiplier:
        Threshold = sigma_multiplier * trailing std of GPR delta.
    trailing_window:
        Look-back for computing GPR delta std (252 = 1 year).

    Returns
    -------
    float
        Directional accuracy on shock days, or NaN if no shock days found.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")

    gpr = gpr_series.copy()
    gpr_delta = gpr.diff().abs()

    rolling_std = gpr_delta.rolling(trailing_window, min_periods=30).std()
    threshold = sigma_multiplier * rolling_std

    shock_mask = gpr_delta > threshold

    if hasattr(gpr_series.index, 'dtype') and len(y_true) == len(gpr_series):
        shock_days_bool = shock_mask.values[-len(y_true):]
    else:
        shock_days_bool = shock_mask.values if len(shock_mask) == len(y_true) else np.zeros(len(y_true), dtype=bool)

    if not np.any(shock_days_bool):
        return float('nan')

    y_true_shock = y_true[shock_days_bool]
    y_pred_shock = y_pred[shock_days_bool]

    valid = np.isfinite(y_true_shock) & np.isfinite(y_pred_shock)
    if not np.any(valid):
        return float('nan')

    correct = np.sign(y_true_shock[valid]) == np.sign(y_pred_shock[valid])
    return float(np.mean(correct))


def identify_shock_days(
    gpr_series: pd.Series,
    sigma_multiplier: float = 2.0,
    trailing_window: int = 252,
) -> pd.Series:
    """Return a boolean Series marking geopolitical shock days."""
    gpr_delta = gpr_series.diff().abs()
    rolling_std = gpr_delta.rolling(trailing_window, min_periods=30).std()
    threshold = sigma_multiplier * rolling_std
    return gpr_delta > threshold
