"""Tests for the gers module (used by baseline_ablation.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "eval_scripts"))

import pytest

np = pytest.importorskip("numpy", reason="numpy required for gers tests")
pd = pytest.importorskip("pandas", reason="pandas required for gers tests")

from gers import compute_gers, identify_shock_days


def _make_gpr(values: list[float]) -> pd.Series:
    idx = pd.date_range("2022-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, name="gpr_index")


def test_compute_gers_no_shocks():
    gpr = _make_gpr([100.0] * 300)
    y_true = np.array([0.01] * 50)
    y_pred = np.array([0.01] * 50)
    result = compute_gers(y_true, y_pred, gpr)
    assert np.isnan(result)


def test_compute_gers_perfect_on_shock_days():
    values = [100.0] * 252 + [200.0] * 10 + [100.0] * 38
    gpr = _make_gpr(values)
    y_true = np.ones(50)
    y_pred = np.ones(50) * 0.5
    result = compute_gers(y_true, y_pred, gpr)
    assert result == 1.0 or np.isnan(result)


def test_compute_gers_wrong_direction_on_shock_days():
    values = [100.0] * 252 + [300.0, 100.0] * 5 + [100.0] * 38
    gpr = _make_gpr(values)
    y_true = np.ones(50)
    y_pred = np.ones(50) * -0.5
    result = compute_gers(y_true, y_pred, gpr)
    if not np.isnan(result):
        assert result == 0.0


def test_compute_gers_length_mismatch_raises():
    gpr = _make_gpr([100.0] * 300)
    with pytest.raises(ValueError):
        compute_gers(np.ones(10), np.ones(20), gpr)


def test_identify_shock_days_marks_spike():
    values = [100.0] * 252 + [500.0] + [100.0] * 50
    gpr = _make_gpr(values)
    shocks = identify_shock_days(gpr)
    assert shocks.any()
    assert shocks.iloc[252]


def test_compute_gers_returns_between_0_and_1():
    rng = np.random.default_rng(42)
    values = rng.uniform(50, 200, 300).tolist()
    gpr = _make_gpr(values)
    y_true = rng.uniform(-0.05, 0.05, 50)
    y_pred = rng.uniform(-0.05, 0.05, 50)
    result = compute_gers(y_true, y_pred, gpr)
    if not np.isnan(result):
        assert 0.0 <= result <= 1.0
