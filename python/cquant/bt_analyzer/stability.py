"""cquant.bt_analyzer.stability — Time-slice and regime stability diagnostics."""

from __future__ import annotations

import polars as pl

from cquant.backtest_vector.engine import BacktestResult
from cquant.bt_analyzer.models import AnalysisSpec
from cquant.bt_analyzer.walk_forward import _period_metrics


class StabilityAnalyzer:
    """Measure how stable Sharpe and return profiles are through time and regimes."""

    def __init__(self, spec: AnalysisSpec) -> None:
        self.spec = spec

    def analyze(self, result: BacktestResult) -> dict[str, float]:
        """Return stability metrics across time segments and bull/bear/vol regimes."""
        values = [
            float(v) for v in
            result.portfolio_returns.sort("trade_date")
            .get_column("portfolio_return").fill_null(0.0).to_list()
        ]
        if len(values) < 4:
            return self._empty()

        # Time-slice stability: partition into 4 segments, compare Sharpe
        segments = [values[i::4] for i in range(4) if values[i::4]]
        seg_sharpes = [
            _period_metrics(pl.Series("portfolio_return", s), self.spec.trading_days_per_year)["sharpe"]
            for s in segments if len(s) >= 2
        ]
        if not seg_sharpes:
            return self._empty()

        mean = sum(seg_sharpes) / len(seg_sharpes)
        var = sum((s - mean) ** 2 for s in seg_sharpes) / len(seg_sharpes)
        std = var ** 0.5
        cv = std / max(abs(mean), 1e-12)
        pos_ratio = sum(1 for s in seg_sharpes if s > 0) / len(seg_sharpes)

        # Regime-based stability
        bull, bear, hi_vol, lo_vol = _regime_buckets(values)
        regime_sharpes = [
            _subset_sharpe(g, self.spec.trading_days_per_year)
            for g in (bull, bear, hi_vol, lo_vol)
        ]
        r_mean = sum(regime_sharpes) / 4
        r_var = sum((s - r_mean) ** 2 for s in regime_sharpes) / 4
        regime_dispersion = min((r_var ** 0.5) / max(abs(r_mean), 1.0), 1.0)

        instability = min(max((cv + regime_dispersion) / 2.0, 0.0), 1.0)

        return {
            "stability_score": 1.0 - instability,
            "instability": instability,
            "segment_count": float(len(seg_sharpes)),
            "sharpe_mean": float(mean),
            "sharpe_std": float(std),
            "sharpe_cv": float(cv),
            "positive_period_ratio": float(pos_ratio),
            "bull_sharpe": float(regime_sharpes[0]),
            "bear_sharpe": float(regime_sharpes[1]),
            "high_vol_sharpe": float(regime_sharpes[2]),
            "low_vol_sharpe": float(regime_sharpes[3]),
            "regime_dispersion": float(regime_dispersion),
        }

    @staticmethod
    def _empty() -> dict[str, float]:
        return {
            "stability_score": 1.0, "instability": 0.0, "segment_count": 0.0,
            "sharpe_mean": 0.0, "sharpe_std": 0.0, "sharpe_cv": 0.0,
            "positive_period_ratio": 0.0, "bull_sharpe": 0.0, "bear_sharpe": 0.0,
            "high_vol_sharpe": 0.0, "low_vol_sharpe": 0.0, "regime_dispersion": 0.0,
        }


def _regime_buckets(values: list[float]) -> tuple[list[float], list[float], list[float], list[float]]:
    """Split returns into bull/bear and high-vol/low-vol regime buckets."""
    lb = min(max(5, len(values) // 6), 20)
    rolling_trend, rolling_vol = [], []
    for i in range(len(values)):
        w = values[max(0, i - lb + 1): i + 1]
        m = sum(w) / len(w)
        v = sum((x - m) ** 2 for x in w) / max(len(w), 1)
        rolling_trend.append(m)
        rolling_vol.append(v ** 0.5)

    vol_med = sorted(rolling_vol)[len(rolling_vol) // 2]
    bull = [r for r, t in zip(values, rolling_trend) if t >= 0]
    bear = [r for r, t in zip(values, rolling_trend) if t < 0]
    hi = [r for r, v in zip(values, rolling_vol) if v >= vol_med]
    lo = [r for r, v in zip(values, rolling_vol) if v < vol_med]
    return bull, bear, hi, lo


def _subset_sharpe(values: list[float], tdy: int) -> float:
    if len(values) < 2:
        return 0.0
    return _period_metrics(pl.Series("portfolio_return", values), tdy)["sharpe"]
