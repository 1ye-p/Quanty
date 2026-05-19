"""cquant.bt_analyzer.sensitivity — Parameter sensitivity approximation.

For MVP: instead of re-running the strategy across a full parameter grid
(which requires strategy access), we approximate sensitivity by measuring
rolling Sharpe stability — a volatile Sharpe implies fragile parameterization.
"""

from __future__ import annotations

from math import prod

import polars as pl

from cquant.backtest_vector.engine import BacktestResult
from cquant.bt_analyzer.models import AnalysisSpec
from cquant.bt_analyzer.walk_forward import _period_metrics


class SensitivityAnalyzer:
    """Approximate parameter sensitivity from rolling Sharpe coefficient of variation."""

    def __init__(self, spec: AnalysisSpec) -> None:
        self.spec = spec

    def analyze(self, result: BacktestResult) -> dict[str, float]:
        """Return sensitivity / stability metrics.

        Returns:
            stability_score: 1.0 = perfectly stable, 0.0 = highly unstable
            instability: complement of stability_score
            rolling_sharpe_*: rolling Sharpe distribution statistics
            parameter_grid_size: number of param combinations declared in spec
        """
        values = [
            float(v) for v in
            result.portfolio_returns.sort("trade_date")
            .get_column("portfolio_return").fill_null(0.0).to_list()
        ]
        grid_size = float(_grid_size(self.spec.param_grid))

        if len(values) < 4:
            return {
                "stability_score": 1.0, "instability": 0.0,
                "rolling_sharpe_mean": 0.0, "rolling_sharpe_std": 0.0,
                "rolling_sharpe_cv": 0.0,
                "rolling_window_days": float(len(values)),
                "parameter_grid_size": grid_size,
            }

        window = max(3, min(len(values) // max(self.spec.n_oos_windows, 1), max(5, len(values) // 3)))
        sharpes = [
            _period_metrics(
                pl.Series("portfolio_return", values[i: i + window]),
                self.spec.trading_days_per_year,
            )["sharpe"]
            for i in range(0, len(values) - window + 1)
        ]

        mean = sum(sharpes) / len(sharpes)
        var = sum((s - mean) ** 2 for s in sharpes) / len(sharpes)
        std = var ** 0.5
        cv = std / max(abs(mean), 1e-12)
        instability = min(max(cv / 2.0, 0.0), 1.0)

        return {
            "stability_score": 1.0 - instability,
            "instability": instability,
            "rolling_sharpe_mean": float(mean),
            "rolling_sharpe_std": float(std),
            "rolling_sharpe_cv": float(cv),
            "rolling_window_days": float(window),
            "parameter_grid_size": grid_size,
        }


def _grid_size(param_grid: dict) -> int:
    if not param_grid:
        return 1
    return int(prod(max(len(v), 1) for v in param_grid.values()))
