"""Tests for DownsideVol20d factor correctness."""
import polars as pl
import pytest
from cquant.factorlab.factors.volatility import DownsideVol20d
from cquant.factorlab.factor import FactorContext
from datetime import date


def _make_frame(returns: list[float]) -> pl.DataFrame:
    """Build a price frame from daily returns for a single asset."""
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    n = len(prices)
    return pl.DataFrame({
        "asset_id": ["SH600000"] * n,
        "trade_date": [date(2025, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(n)],
        "close": prices,
    })


def test_downside_vol_all_positive():
    """When all returns are positive, downside vol should be 0."""
    returns = [0.01, 0.02, 0.01, 0.03, 0.02] * 4  # 20 positive returns
    frame = _make_frame(returns)
    ctx = FactorContext(as_of_date=date(2025, 1, 21))
    factor = DownsideVol20d()
    result = factor.compute(frame, ctx)
    # Last value should be 0 (no negative returns)
    assert result.tail(1).to_list()[0] == pytest.approx(0.0, abs=1e-6)


def test_downside_vol_known_value():
    """Verify against hand-calculated semideviation."""
    # 20 returns: 10 negative (-5%), 10 positive (+5%)
    returns = [-0.05, 0.05] * 10
    frame = _make_frame(returns)
    ctx = FactorContext(as_of_date=date(2025, 1, 21))
    factor = DownsideVol20d()
    result = factor.compute(frame, ctx)
    val = result.tail(1).to_list()[0]
    # The factor uses log returns, so expected uses log(1+r) not r
    import math
    neg_log_ret = math.log(1 - 0.05)  # log(0.95) ≈ -0.051293
    # mean of squared negatives over 20 (10 negative, 10 zero)
    mean_sq = 10 * neg_log_ret**2 / 20
    expected = mean_sq**0.5 * (252**0.5)
    assert val == pytest.approx(expected, rel=0.001)


def test_downside_vol_mixed():
    """Downside vol should only reflect negative returns."""
    # Scenario A: all negative
    returns_a = [-0.02] * 20
    # Scenario B: same magnitude but half positive
    returns_b = [-0.02, 0.02] * 10
    frame_a = _make_frame(returns_a)
    frame_b = _make_frame(returns_b)
    ctx = FactorContext(as_of_date=date(2025, 1, 21))
    factor = DownsideVol20d()
    val_a = factor.compute(frame_a, ctx).tail(1).to_list()[0]
    val_b = factor.compute(frame_b, ctx).tail(1).to_list()[0]
    # A should be higher than B (more negative returns)
    assert val_a > val_b
    # B should be ~1/sqrt(2) of A (half the negative returns squared)
    assert val_b == pytest.approx(val_a / (2 ** 0.5), rel=0.05)
