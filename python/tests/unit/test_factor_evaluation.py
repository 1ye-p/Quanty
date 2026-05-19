"""Unit tests for cquant.factorlab.evaluation — FactorEvaluator (IC/IR)."""

import numpy as np
import polars as pl
import pytest

from cquant.factorlab.evaluation import FactorEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_panel(
    n_assets: int = 50,
    n_dates: int = 20,
    seed: int = 42,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Generate factor + return panels with a known signal.

    Returns:  factor = [asset_id, trade_date, factor_value]
              returns = [asset_id, trade_date, fwd_ret]
              where  fwd_ret = factor_value * 0.3 + noise
    """
    rng = np.random.default_rng(seed)
    dates = [f"2025-01-{d:02d}" for d in range(1, n_dates + 1)]
    assets = [f"SSE:{i:06d}" for i in range(n_assets)]

    rows_f, rows_r = [], []
    for dt in dates:
        for ast in assets:
            fv = rng.standard_normal()
            ret = fv * 0.3 + rng.standard_normal() * 0.5
            rows_f.append({"asset_id": ast, "trade_date": dt, "factor_value": fv})
            rows_r.append({"asset_id": ast, "trade_date": dt, "fwd_ret": ret})

    factors = pl.DataFrame(rows_f)
    returns = pl.DataFrame(rows_r)
    return factors, returns


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def panel() -> tuple[pl.DataFrame, pl.DataFrame]:
    return _make_panel()


def test_ic_series_length(panel) -> None:
    factors, returns = panel
    ev = FactorEvaluator(factor_col="factor_value", return_col="fwd_ret")
    ic_df = ev.ic_series(factors, returns)
    assert len(ic_df) == 20


def test_ic_series_columns(panel) -> None:
    factors, returns = panel
    ev = FactorEvaluator(factor_col="factor_value", return_col="fwd_ret")
    ic_df = ev.ic_series(factors, returns)
    assert "trade_date" in ic_df.columns
    assert "ic" in ic_df.columns


def test_mean_ic(panel) -> None:
    factors, returns = panel
    ev = FactorEvaluator(factor_col="factor_value", return_col="fwd_ret")
    mic = ev.mean_ic(factors, returns)
    assert isinstance(mic, float)
    assert -1.0 <= mic <= 1.0


def test_ic_ir(panel) -> None:
    factors, returns = panel
    ev = FactorEvaluator(factor_col="factor_value", return_col="fwd_ret")
    ir = ev.ic_ir(factors, returns)
    assert isinstance(ir, float)


def test_rank_ic_preferred(panel) -> None:
    factors, returns = panel
    ev = FactorEvaluator(factor_col="factor_value", return_col="fwd_ret", method="rank")
    ic_df = ev.ic_series(factors, returns)
    # Spearman IC on a signal with 0.3 weight should be positive on average
    assert ic_df["ic"].mean() > 0


def test_summary_report(panel) -> None:
    factors, returns = panel
    ev = FactorEvaluator(factor_col="factor_value", return_col="fwd_ret")
    s = ev.summary(factors, returns)
    expected_keys = {"factor_name", "method", "mean_ic", "ic_ir", "ic_positive_pct", "dates_evaluated"}
    assert expected_keys.issubset(s.keys())
