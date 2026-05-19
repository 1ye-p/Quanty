"""cquant.bt_analyzer.walk_forward — Rolling out-of-sample validation."""

from __future__ import annotations

import math
from datetime import timedelta

import polars as pl

from cquant.backtest_vector.engine import BacktestResult
from cquant.backtest_vector.metrics import compute_metrics
from cquant.bt_analyzer.models import AnalysisSpec, ValidationWindow


class WalkForwardAnalyzer:
    """Generate sliding out-of-sample windows from a completed backtest.

    Each window uses all returns up to a cutoff for in-sample context
    (not re-fitted here — that is the strategy's concern), and evaluates
    performance on the subsequent OOS period.
    """

    def __init__(self, spec: AnalysisSpec) -> None:
        if spec.n_oos_windows < 1:
            raise ValueError("n_oos_windows must be >= 1")
        if not 0.0 < spec.oos_fraction < 1.0:
            raise ValueError("oos_fraction must be in (0, 1)")
        if spec.gap_days < 0:
            raise ValueError("gap_days must be >= 0")
        self.spec = spec

    def analyze(self, result: BacktestResult) -> list[ValidationWindow]:
        """Return one ValidationWindow per OOS sliding window."""
        frame = result.portfolio_returns.sort("trade_date")
        if frame.is_empty():
            return []
        dates = frame.get_column("trade_date").to_list()
        if len(dates) < 3:
            return []

        oos_size = max(2, min(int(len(dates) * self.spec.oos_fraction), len(dates) - 1))
        max_start = len(dates) - oos_size
        start_indices = _evenly_spaced(max_start, self.spec.n_oos_windows)

        windows: list[ValidationWindow] = []
        for wid, start_idx in enumerate(start_indices, start=1):
            test_start = dates[start_idx]
            test_end = dates[start_idx + oos_size - 1]
            train_cutoff = test_start - timedelta(days=self.spec.gap_days)

            train_df = frame.filter(pl.col("trade_date") < train_cutoff)
            test_df = frame.filter(
                (pl.col("trade_date") >= test_start) & (pl.col("trade_date") <= test_end)
            )
            if train_df.is_empty() or test_df.is_empty():
                continue

            windows.append(
                ValidationWindow(
                    window_id=wid,
                    train_start=train_df.item(0, "trade_date"),
                    train_end=train_df.item(train_df.height - 1, "trade_date"),
                    test_start=test_start,
                    test_end=test_end,
                    metrics=_period_metrics(
                        test_df.get_column("portfolio_return"),
                        self.spec.trading_days_per_year,
                    ),
                )
            )
        return windows


def _period_metrics(returns: pl.Series, trading_days_per_year: int) -> dict[str, float]:
    """Compute validation metrics for one return series slice."""
    values = [float(v) for v in returns.fill_null(0.0).to_list() if math.isfinite(float(v))]
    if not values:
        return _zero_metrics()
    if len(values) == 1:
        r = values[0]
        return {"sharpe": 0.0, "total_return": r, "max_drawdown": min(r, 0.0),
                "annualized_return": r, "annualized_volatility": 0.0,
                "information_ratio": 0.0, "trading_days": 1.0}
    m = compute_metrics(pl.Series("portfolio_return", values), trading_days_per_year=trading_days_per_year)
    ir = m.annualized_return / (m.annualized_volatility + 1e-12) if math.isfinite(m.annualized_volatility) else 0.0
    return {
        "sharpe": float(m.sharpe_ratio),
        "total_return": float(m.total_return),
        "max_drawdown": float(m.max_drawdown),
        "annualized_return": float(m.annualized_return),
        "annualized_volatility": float(m.annualized_volatility),
        "information_ratio": float(ir),
        "trading_days": float(m.trading_days),
    }


def _zero_metrics() -> dict[str, float]:
    return {"sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0,
            "annualized_return": 0.0, "annualized_volatility": 0.0,
            "information_ratio": 0.0, "trading_days": 0.0}


def _evenly_spaced(max_start: int, n: int) -> list[int]:
    """Return n evenly-spaced integer indices in [1, max_start]."""
    if max_start <= 1:
        return [1]
    if n == 1:
        return [max_start]
    return sorted({min(max(1, 1 + round(i * (max_start - 1) / (n - 1))), max_start) for i in range(n)})
