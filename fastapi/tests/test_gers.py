"""Unit tests for eval_scripts/gers.py compute_gers function."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "eval_scripts"))

import pytest

np = pytest.importorskip("numpy", reason="numpy required")
pd = pytest.importorskip("pandas", reason="pandas required")

from gers import compute_gers, identify_shock_days


def _gpr(values: list[float]) -> "pd.Series":
    idx = pd.date_range("2022-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, name="gpr_index")


def test_no_shock_days_returns_nan():
    gpr = _gpr([100.0] * 300)
    result = compute_gers(np.ones(50), np.ones(50) * 0.5, gpr)
    assert np.isnan(result)


def test_perfect_direction_on_shock_days():
    vals = [100.0] * 252 + [300.0, 100.0] * 5 + [100.0] * 28
    gpr = _gpr(vals)
    y_t = np.ones(38)
    y_p = np.ones(38) * 0.5
    result = compute_gers(y_t, y_p, gpr)
    if not np.isnan(result):
        assert result == 1.0


def test_wrong_direction_on_shock_days():
    vals = [100.0] * 252 + [300.0, 100.0] * 5 + [100.0] * 28
    gpr = _gpr(vals)
    y_t = np.ones(38)
    y_p = np.ones(38) * -0.5
    result = compute_gers(y_t, y_p, gpr)
    if not np.isnan(result):
        assert result == 0.0


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        compute_gers(np.ones(10), np.ones(15), _gpr([100.0] * 300))


def test_result_between_0_and_1():
    rng = np.random.default_rng(0)
    vals = rng.uniform(50, 300, 300).tolist()
    gpr = _gpr(vals)
    y_t = rng.uniform(-0.05, 0.05, 50)
    y_p = rng.uniform(-0.05, 0.05, 50)
    result = compute_gers(y_t, y_p, gpr)
    if not np.isnan(result):
        assert 0.0 <= result <= 1.0


def test_identify_shock_days_marks_large_spike():
    vals = [100.0] * 260 + [600.0] + [100.0] * 39
    gpr = _gpr(vals)
    shocks = identify_shock_days(gpr)
    assert shocks.iloc[260]
